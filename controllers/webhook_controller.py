#controllers/webhook_controller
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class SmsWebhookController(http.Controller):
    
    
    @http.route('/sms/webhook/status', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def sms_status_webhook(self, **kwargs):
        """
        Webhook endpoint for SMS delivery status updates
        Expected payload: {
            'message_id': 'external_id',
            'status': 'delivered|failed|sent',
            'error_message': 'optional error description'
        }
        """
        try:
            data = request.jsonrequest
            _logger.info(f'SMS webhook received: {data}')
            
            message_id = data.get('message_id')
            status = data.get('status')
            error_message = data.get('error_message', '')
            
            if not message_id or not status:
                return {'status': 'error', 'message': 'Missing required fields'}
            
            # Find the SMS message
            sms = request.env['sms.message'].sudo().search([
                ('external_id', '=', message_id)
            ], limit=1)
            
            if not sms:
                _logger.warning(f'SMS message not found: {message_id}')
                return {'status': 'error', 'message': 'Message not found'}
            
            # Update status
            status_map = {
                'sent': 'sent',
                'delivered': 'delivered',
                'failed': 'failed'
            }
            
            odoo_status = status_map.get(status.lower(), 'failed')
            sms.write({
                'state': odoo_status,
                'error_message': error_message if odoo_status == 'failed' else False
            })
            
            return {'status': 'success', 'message': 'Status updated'}
            
        except Exception as e:
            _logger.error(f'Error processing SMS webhook: {str(e)}')
            return {'status': 'error', 'message': str(e)}
    
    
    @http.route('/sms/webhook/incoming', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def sms_incoming_webhook(self, **kwargs):
        """
        Webhook endpoint for incoming SMS messages
        Expected payload: {
            'from': '+1234567890',
            'body': 'message content',
            'timestamp': '2024-01-01T12:00:00Z'
        }
        """
        try:
            data = request.jsonrequest
            _logger.info(f'Incoming SMS webhook received: {data}')
            
            from_number = data.get('from')
            body = data.get('body')
            
            if not from_number or not body:
                return {'status': 'error', 'message': 'Missing required fields'}
            
            # You can implement incoming SMS handling logic here
            # For example, create a record, trigger automation, etc.
            
            return {'status': 'success', 'message': 'Message received'}
            
        except Exception as e:
            _logger.error(f'Error processing incoming SMS: {str(e)}')
            return {'status': 'error', 'message': str(e)}