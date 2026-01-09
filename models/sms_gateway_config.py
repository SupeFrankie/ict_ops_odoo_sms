from odoo import models, fields, api
from odoo.exceptions import ValidationError
import requests
import logging

_logger = logging.getLogger(__name__)


class SmsGatewayConfiguration(models.Model):
    _name = 'sms.gateway.configuration'
    _description = 'SMS Gateway Configuration'

    name = fields.Char(string='Gateway Name', required=True)
    gateway_type = fields.Selection([
        ('africastalking', 'Africa\'s Talking'),
        ('custom', 'Custom API')
    ], string='Gateway Type', required=True, default='africastalking')
    
    # Common fields
    api_key = fields.Char(string='API Key', required=True)
    api_secret = fields.Char(string='API Secret/Auth Token')
    sender_id = fields.Char(string='Sender ID/Phone Number', required=True)
    
    # Africa's Talking specific
    username = fields.Char(string='Username')
    
    # Custom API fields
    api_url = fields.Char(string='API URL')
    request_method = fields.Selection([
        ('GET', 'GET'),
        ('POST', 'POST')
    ], string='Request Method', default='POST')
    
    active = fields.Boolean(string='Active', default=True)
    is_default = fields.Boolean(string='Default Gateway', default=False)
    
    @api.constrains('is_default')
    def _check_default_gateway(self):
        for record in self:
            if record.is_default:
                other_defaults = self.search([
                    ('is_default', '=', True),
                    ('id', '!=', record.id)
                ])
                if other_defaults:
                    other_defaults.write({'is_default': False})
    
    def send_sms(self, phone_number, message):
        """Send SMS through configured gateway"""
        self.ensure_one()
        
        if self.gateway_type == 'africastalking':
            return self._send_africastalking(phone_number, message)
        elif self.gateway_type == 'custom':
            return self._send_custom(phone_number, message)
        else:
            raise ValidationError('Unsupported gateway type')
    
    def _send_africastalking(self, phone_number, message):
        """Send SMS via Africa's Talking"""
        try:
            url = 'https://api.africastalking.com/version1/messaging'
            headers = {
                'apiKey': self.api_key,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            data = {
                'username': self.username,
                'to': phone_number,
                'message': message,
                'from': self.sender_id
            }
            
            response = requests.post(url, headers=headers, data=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            _logger.info(f"SMS sent successfully via Africa's Talking: {result}")
            return True, result
            
        except Exception as e:
            _logger.error(f"Error sending SMS via Africa's Talking: {str(e)}")
            return False, str(e)
    
    def _send_custom(self, phone_number, message):
        """Send SMS via Custom API"""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            data = {
                'phone': phone_number,
                'message': message,
                'sender': self.sender_id
            }
            
            if self.request_method == 'POST':
                response = requests.post(self.api_url, headers=headers, json=data, timeout=30)
            else:
                response = requests.get(self.api_url, headers=headers, params=data, timeout=30)
            
            response.raise_for_status()
            _logger.info(f"SMS sent successfully via Custom API")
            return True, response.text
            
        except Exception as e:
            _logger.error(f"Error sending SMS via Custom API: {str(e)}")
            return False, str(e)
    
    def test_connection(self):
        """Test the gateway connection"""
        self.ensure_one()
        test_message = "Test message from Odoo SMS Module"
        test_number = self.sender_id  # Send test to sender number
        
        success, result = self.send_sms(test_number, test_message)
        
        if success:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Test SMS sent successfully!',
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Failed to send test SMS: {result}',
                    'type': 'danger',
                    'sticky': True,
                }
            }