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
    sender_id = fields.Char(string='Sender ID/Phone Number', required=False)
    
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
            # Strict 'sandbox' only
            is_sandbox = self.username and self.username.strip().lower() == 'sandbox'


            if is_sandbox:
                url = 'https://api.sandbox.africastalking.com/version1/messaging'
                _logger.info("Using Africa's Talking SANDBOX environment")
            else:
                url = 'https://api.africastalking.com/version1/messaging'
                _logger.info("Using Africa's Talking PRODUCTION environment")

            # Headers per documentation
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded',
                'apiKey': self.api_key  
            }

            # Ensure phone number has country code
            phone = phone_number.strip()
            if not phone.startswith('+'):
                if phone.startswith('0'):
                    phone = '+254' + phone[1:]
                elif phone.startswith('254'):
                    phone = '+' + phone
                else:
                    phone = '+254' + phone

            # Payload - per bulk SMS docs
            data = {
                'username': self.username,
                'to': phone,
                'message': message,
            }

            # Only add sender_id for production (sandbox ignores it)
            if self.sender_id and not is_sandbox:
                data['from'] = self.sender_id
                _logger.info("Using sender ID: %s", self.sender_id)
            elif is_sandbox:
                _logger.info("Sandbox mode: sender ID ignored")

            _logger.info("Sending to: %s", phone)
            _logger.info("Username: %s", self.username)

            # Make request
            response = requests.post(url, headers=headers, data=data, timeout=30)

            # Log response
            _logger.info("Response Status: %d", response.status_code)
            _logger.info("Response Body: %s", response.text)

            response.raise_for_status()

            result = response.json()

            # Check for successful delivery
            sms_data = result.get('SMSMessageData', {})
            recipients = sms_data.get('Recipients', [])
            
            if recipients:
                # Log each recipient status
                for recipient in recipients:
                    status = recipient.get('status', 'Unknown')
                    number = recipient.get('number', phone_number)
                    _logger.info("Recipient %s: %s", number, status)
                return True, result
            else:
                error_msg = sms_data.get('Message', 'Unknown error')
                _logger.error("AT Error: %s", error_msg)
                return False, error_msg

        except requests.exceptions.HTTPError as e:
            _logger.error("HTTP Error: %s - %s", e.response.status_code, e.response.text)
            return False, f"HTTP {e.response.status_code}: {e.response.text}"
        except requests.exceptions.RequestException as e:
            _logger.error("Request Error: %s", str(e))
            return False, f"Request failed: {str(e)}"
        except Exception as e:
            _logger.error("Unexpected error: %s", str(e))
            return False, f"Error: {str(e)}"
    
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
            _logger.info("SMS sent successfully via Custom API")
            return True, response.text
            
        except Exception as e:
            _logger.error("Error sending SMS via Custom API: %s", str(e))
            return False, str(e)
    
    def test_connection(self):
        """Test the gateway connection"""
        self.ensure_one()
        test_message = "Test message from Odoo SMS Module"
        test_number = '+254700000000'
        
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