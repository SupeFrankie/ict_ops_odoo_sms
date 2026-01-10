from odoo import http
from odoo.http import request
import logging
import re

_logger = logging.getLogger(__name__)

# Phone number validation pattern
PHONE_PATTERN = re.compile(r'^\+?1?\d{9,15}$')


class SmsOptOutController(http.Controller):
    
    def _validate_phone_number(self, phone_number):
        """Validate phone number format"""
        if not phone_number or not PHONE_PATTERN.match(phone_number):
            raise ValueError("Invalid phone number format")
        return phone_number.strip()
    
    def _render_response(self, template, message, status, phone_number):
        """Helper method to render responses"""
        # FIX: Add module prefix to template name
        full_template = f'ict_ops.{template}'
        return request.render(full_template, {
            'message': message,
            'status': status,
            'phone_number': phone_number
        })
    
    @http.route('/sms/optout/<string:phone_number>', type='http', auth='public', website=True, csrf=False)
    def sms_opt_out(self, phone_number):
        """Handle SMS opt-out requests via web link"""
        try:
            phone_number = self._validate_phone_number(phone_number)
            
            existing = request.env['sms.blacklist'].sudo().search([
                ('phone_number', '=', phone_number),
                ('active', '=', True)
            ], limit=1)
            
            if existing:
                return self._render_response(
                    'sms_opt_out_page',
                    f"Phone number {phone_number} is already opted out.",
                    "already_opted_out",
                    phone_number
                )
            
            request.env['sms.blacklist'].sudo().create({
                'phone_number': phone_number,
                'reason': 'user_request',  # FIX: Use valid selection value
                'notes': 'User opted out via web link',
                'active': True
            })
            _logger.info(f"Phone number {phone_number} opted out via web link")
            
            return self._render_response(
                'sms_opt_out_page',
                f"Phone number {phone_number} has been successfully opted out from SMS campaigns.",
                "success",
                phone_number
            )
            
        except ValueError as e:
            _logger.warning(f"Invalid phone number: {str(e)}")
            return self._render_response(
                'sms_opt_out_page',
                "Invalid phone number format.",
                "invalid",
                phone_number if phone_number else ''
            )
        except Exception as e:
            _logger.error(f"Error processing opt-out for {phone_number}: {str(e)}")
            return self._render_response(
                'sms_opt_out_page',
                'An error occurred while processing your request. Please try again later.',
                'error',
                phone_number if phone_number else ''
            )
    
    @http.route('/sms/optin/<string:phone_number>', type='http', auth='public', website=True, csrf=False)
    def sms_opt_in(self, phone_number):
        """Handle SMS opt-in requests (re-subscribe)"""
        try:
            phone_number = self._validate_phone_number(phone_number)
            
            blacklist_entry = request.env['sms.blacklist'].sudo().search([
                ('phone_number', '=', phone_number),
                ('active', '=', True)
            ], limit=1)
            
            if blacklist_entry:
                blacklist_entry.write({'active': False})
                _logger.info(f"Phone number {phone_number} opted back in via web link")
                return self._render_response(
                    'sms_opt_in_page',
                    f"Phone number {phone_number} has been successfully re-subscribed to SMS campaigns.",
                    "success",
                    phone_number
                )
            
            return self._render_response(
                'sms_opt_in_page',
                f"Phone number {phone_number} is not currently opted out.",
                "not_opted_out",
                phone_number
            )
            
        except ValueError as e:
            _logger.warning(f"Invalid phone number: {str(e)}")
            return self._render_response(
                'sms_opt_in_page',
                "Invalid phone number format.",
                "invalid",
                phone_number if phone_number else ''
            )
        except Exception as e:
            _logger.error(f"Error processing opt-in for {phone_number}: {str(e)}")
            return self._render_response(
                'sms_opt_in_page',
                'An error occurred while processing your request. Please try again later.',
                'error',
                phone_number if phone_number else ''
            )
    
    @http.route('/sms/status', type='http', auth='public', website=True)
    def check_opt_status(self):
        """Page to check opt-out status"""
        return request.render('sms_marketing.sms_status_check_page')
    
    @http.route('/sms/check_status', type='json', auth='public', csrf=False)
    def check_status_json(self, phone_number):
        """JSON endpoint to check if a number is opted out"""
        try:
            phone_number = self._validate_phone_number(phone_number)
            
            blacklisted = request.env['sms.blacklist'].sudo().search([
                ('phone_number', '=', phone_number),
                ('active', '=', True)
            ], limit=1)
            
            return {
                'success': True,
                'phone_number': phone_number,
                'is_opted_out': bool(blacklisted),
                'reason': blacklisted.reason if blacklisted else None
            }
        except ValueError as e:
            return {
                'success': False,
                'error': 'Invalid phone number format'
            }
        except Exception as e:
            _logger.error(f"Error checking status for {phone_number}: {str(e)}")
            return {
                'success': False,
                'error': 'An error occurred while processing your request'
            }