from odoo import models, fields, api
from odoo.exceptions import UserError
import re

class SmsTemplate(models.Model):
    _name = 'sms.template'
    _description = 'SMS Template'
    _order = 'name'

    name = fields.Char(string='Template Name', required=True)
    template_type = fields.Selection([
        ('birthday', 'Birthday Wish'),
        ('appointment', 'Appointment Reminder'),
        ('payment', 'Payment Reminder'),
        ('welcome', 'Welcome Message'),
        ('followup', 'Follow-up Message'),
        ('promotion', 'Promotional Message'),
        ('custom', 'Custom Template'),
    ], string='Template Type', required=True, default='custom')
    
    model_id = fields.Many2one('ir.model', string='Applies to', required=True,
                               domain=[('transient', '=', False)], ondelete='cascade')
    model = fields.Char(related='model_id.model', string='Model', readonly=True, store=True)
    body = fields.Text(string='Message Body', required=True,
                      help='You can use ${object.field_name} to insert dynamic content')
    active = fields.Boolean(default=True)
    
    # Validation fields
    char_count = fields.Integer(string='Character Count', compute='_compute_char_count', store=True)
    sms_count = fields.Integer(string='SMS Count', compute='_compute_sms_count', store=True)
    
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
                # After 160, each SMS is 153 chars (7 chars for concatenation)
                record.sms_count = 1 + ((record.char_count - 160 + 152) // 153)
    
    @api.constrains('body')
    def _check_body(self):
        for record in self:
            if not record.body or not record.body.strip():
                raise UserError('Message body cannot be empty.')
            # Validate placeholders
            placeholders = re.findall(r'\$\{(.*?)\}', record.body)
            for placeholder in placeholders:
                if not placeholder.startswith('object.'):
                    raise UserError(f'Invalid placeholder: ${{{placeholder}}}. Must start with "object."')
    
    def generate_sms(self, res_id):
        """Generate SMS content for a specific record"""
        self.ensure_one()
        record = self.env[self.model].browse(res_id)
        if not record.exists():
            raise UserError(f'Record with ID {res_id} not found in model {self.model}')
        
        body = self.body
        # Find all placeholders
        placeholders = re.findall(r'\$\{object\.(.*?)\}', body)
        
        for field_name in placeholders:
            try:
                value = record
                for part in field_name.split('.'):
                    value = getattr(value, part)
                # Handle different field types
                if hasattr(value, 'name'):
                    value = value.name
                elif isinstance(value, (list, tuple)):
                    value = ', '.join([v.name if hasattr(v, 'name') else str(v) for v in value])
                body = body.replace(f'${{object.{field_name}}}', str(value or ''))
            except AttributeError:
                raise UserError(f'Field "{field_name}" not found in model {self.model}')
        
        return body