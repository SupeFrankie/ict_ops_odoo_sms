from odoo import models, fields, api
from odoo.exceptions import UserError
import re

class SmsComposer(models.TransientModel):
    _name = 'sms.composer'
    _description = 'SMS Composer'

    # Template selection
    template_id = fields.Many2one('sms.template', string='Use Template')
    
    # Message content
    body = fields.Text(string='Message', required=True)
    recipient_phone = fields.Char(string='Recipient Phone', required=True)
    
    # Context
    res_model = fields.Char(string='Related Model')
    res_id = fields.Integer(string='Related Record ID')
    
    # Validation
    char_count = fields.Integer(string='Characters', compute='_compute_char_count')
    sms_count = fields.Integer(string='SMS Parts', compute='_compute_sms_count')
    
    @api.depends('body')
    def _compute_char_count(self):
        for record in self:
            record.char_count = len(record.body) if record.body else 0
    
    @api.depends('char_count')
    def _compute_sms_count(self):
        for record in self:
            if record.char_count == 0:
                record.sms_count = 0
            elif record.char_count <= 160:
                record.sms_count = 1
            else:
                record.sms_count = 1 + ((record.char_count - 160 + 152) // 153)
    
    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Load template content"""
        if self.template_id and self.res_id and self.res_model:
            try:
                self.body = self.template_id.generate_sms(self.res_id)
            except Exception as e:
                return {
                    'warning': {
                        'title': 'Template Error',
                        'message': str(e)
                    }
                }
    
    @api.model
    def default_get(self, fields_list):
        """Set default values from context"""
        result = super().default_get(fields_list)
        
        # Get context values
        res_model = self.env.context.get('default_res_model')
        res_id = self.env.context.get('default_res_id')
        
        result['res_model'] = res_model
        result['res_id'] = res_id
        
        # Try to get phone from record
        if res_model and res_id:
            record = self.env[res_model].browse(res_id)
            # Try different phone field names
            phone_fields = ['mobile', 'phone', 'mobile_phone']
            for field in phone_fields:
                if hasattr(record, field):
                    phone = getattr(record, field)
                    if phone:
                        result['recipient_phone'] = phone
                        break
        
        return result
    
    def action_send_sms(self):
        """Send the SMS"""
        self.ensure_one()
        
        # Validate phone number
        if not self.recipient_phone:
            raise UserError('Please provide a recipient phone number.')
        
        # Clean phone number
        phone = re.sub(r'[^0-9+]', '', self.recipient_phone)
        if not phone:
            raise UserError('Invalid phone number format.')
        
        # Check if blacklisted
        if self.env['sms.blacklist'].is_blacklisted(phone):
            raise UserError(f'Phone number {phone} is blacklisted and cannot receive SMS.')
        
        # Get default gateway
        gateway = self.env['sms.gateway.configuration'].search([
            ('is_default', '=', True),
            ('active', '=', True)
        ], limit=1)
        
        if not gateway:
            gateway = self.env['sms.gateway.configuration'].search([
                ('active', '=', True)
            ], limit=1)
        
        if not gateway:
            raise UserError('No SMS gateway configured. Please configure a gateway in Settings.')
        
        # Send SMS via gateway
        try:
            success, result = gateway.send_sms(phone, self.body)
            
            if success:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': f'SMS sent successfully to {self.recipient_phone}',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(f'Failed to send SMS: {result}')
                
        except Exception as e:
            raise UserError(f'Failed to send SMS: {str(e)}')