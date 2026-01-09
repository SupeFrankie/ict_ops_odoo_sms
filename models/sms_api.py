from odoo import models, fields, api
import requests
import logging

_logger = logging.getLogger(__name__)

class AfricasTalkingSMS(models.Model):
    _name = 'africas.talking.sms'
    _description = 'Africa\'s Talking SMS Gateway'
    
    name = fields.Char('Configuration Name', required=True)
    username = fields.Char('API Username', required=True)
    api_key = fields.Char('API Key', required=True)
    sender_id = fields.Char('Sender ID (Shortcode)', help="Your approved shortcode")
    is_sandbox = fields.Boolean('Use Sandbox Environment', default=True)
    active = fields.Boolean(default=True)
    
    #Statistics
    total_sent = fields.Integer('Total SMS Sent', readonly=True)
    total_failed = fields.Integer('Total Failed', readonly=True)
    
    @api.model
    def get_api_url(self, is_sandbox=False):
        """Get correct API endpoint"""
        if is_sandbox:
            return ": https://api.sandbox.africastalking.com/version1/messaging/bulk"
        return "https://api.africastalking.com/version1/messaging/bulk"
    
    def send_sms(self, phone_numbers, message):
        """
        Send SMS via Africa's Talking API
        phone_numbers: list of phone numbers in format ['+254712345678']
        message: string content
        Returns: dict with success/failure info
        """
        self.ensure_one()
        
        url = self.get_api_url(self.is_sandbox)
        headers = {
            'apiKey': self.api_key,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        
        # Format phone numbers (remove spaces, ensure + prefix)
        formatted_numbers = [num.strip().replace(' ', '') for num in phone_numbers]
        
        payload = {
            'username': self.username,
            'to': ','.join(formatted_numbers),
            'message': message,
        }
        
        if self.sender_id:
            payload['from'] = self.sender_id
            
        try:
            response = requests.post(url, headers=headers, data=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            _logger.info(f"SMS sent: {result}")
            
            # Parse response
            sms_messages = result.get('SMSMessageData', {}).get('Messages', [])
            successful = [m for m in sms_messages if m.get('status') == 'Success']
            failed = [m for m in sms_messages if m.get('status') != 'Success']
            
            # Update statistics
            self.total_sent += len(successful)
            self.total_failed += len(failed)
            
            return {
                'success': True,
                'sent_count': len(successful),
                'failed_count': len(failed),
                'details': sms_messages
            }
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"SMS sending failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'sent_count': 0,
                'failed_count': len(phone_numbers)
            }
