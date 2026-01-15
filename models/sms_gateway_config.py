from odoo import models, fields, api
from odoo.exceptions import ValidationError
import requests
import logging
import time

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
        """Send SMS through configured gateway with Retry Logic"""
        self.ensure_one()
        
        # Settings for retries
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # 1. Attempt to send based on gateway type
                if self.gateway_type == 'africastalking':
                    return self._send_africastalking(phone_number, message)
                elif self.gateway_type == 'custom':
                    return self._send_custom(phone_number, message)
                else:
                    return False, "Unsupported gateway type"

            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                # 2. If it's a network error, wait and try again
                _logger.warning(f"Network error sending SMS (Attempt {attempt + 1}/{max_retries}): {str(e)}")
                
                if attempt < max_retries - 1:
                    sleep_time = 2 ** attempt 
                    time.sleep(sleep_time)
                    continue
                else:
                    # 3. If we ran out of retries, return the error
                    return False, f"Network failed after {max_retries} attempts: {str(e)}"
            
            except Exception as e:
                # 4. If it's a generic code error (not network), fail immediately
                return False, str(e)
    
    # Send via AT
    def _send_africastalking(self, phone_number, message):
        """Send SMS via Africa's Talking"""
        try:
            is_sandbox = self.username and self.username.strip().lower() == 'sandbox'

            if is_sandbox:
                url = 'https://api.sandbox.africastalking.com/version1/messaging'
            else:
                url = 'https://api.africastalking.com/version1/messaging'

            # Ensure phone number has country code
            phone = phone_number.strip()
            if not phone.startswith('+'):
                if phone.startswith('0'):
                    phone = '+254' + phone[1:]
                else:
                    phone = '+254' + phone

            # Payload
            data = {
                'username': self.username,
                'to': phone,
                'message': message,
            }

            if self.sender_id and not is_sandbox:
                data['from'] = self.sender_id

        
            headers = {
                'apiKey': self.api_key,
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded'
            }

            _logger.info("=== DEBUG INFO ===")
            _logger.info("URL: %s", url)
            _logger.info("Username: %s", self.username)
            _logger.info("API Key (first 10 chars): %s", self.api_key[:10] if self.api_key else 'None')
            _logger.info("Headers: %s", headers)
            _logger.info("Data: %s", data)

            response = requests.post(url, headers=headers, data=data, timeout=30, verify=False)

            _logger.info("Response Status: %d", response.status_code)
            _logger.info("Response Body: %s", response.text)

            response.raise_for_status()
            result = response.json()

            sms_data = result.get('SMSMessageData', {})
            recipients = sms_data.get('Recipients', [])
            
            if recipients:
                return True, result
            else:
                error_msg = sms_data.get('Message', 'Unknown error')
                return False, error_msg

        except requests.exceptions.HTTPError as e:
            _logger.error("HTTP Error: %s - %s", e.response.status_code, e.response.text)
            return False, f"HTTP {e.response.status_code}: {e.response.text}"
        except Exception as e:
            _logger.error("Error: %s", str(e))
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
            _logger.info("SMS sent successfully via Custom API")
            return True, response.text
            
        except Exception as e:
            _logger.error("Error sending SMS via Custom API: %s", str(e))
            return False, str(e)
    
    def test_connection(self):
        """Test the gateway connection by sending to the current user"""
        self.ensure_one()
        
        # Get the mobile number of the user currently logged in
        test_number = self.env.user.partner_id.mobile or self.env.user.partner_id.phone
        
        # If user has no number in their profile
        if not test_number:
            raise ValidationError("The current user has no Mobile/Phone number set in their profile. Please add one to test.")

        test_message = f"Success! {self.name} is connected. Sent by {self.env.user.name}."
        
        # Send the SMS
        success, result = self.send_sms(test_number, test_message)
        
        if success:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': f'Test SMS sent to {test_number}!',
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