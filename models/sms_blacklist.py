# models/sms_blacklist.py
from odoo import models, fields, api, exceptions
import re

class SMSBlacklist(models.Model):
    _name = 'sms.blacklist'
    _description = 'SMS Blacklist - Opt-out Management'
    _order = 'create_date desc'
    
    phone_number = fields.Char(string='Phone Number', required=True, index=True)
    name = fields.Char('Name')
    reason = fields.Selection([
        ('user_request', 'User Opt-out Request'),
        ('bounced', 'Number Not Reachable'),
        ('complaint', 'Spam Complaint'),
        ('admin', 'Administrator Action'),
    ], string='Blacklist Reason', default='user_request')
    
    notes = fields.Text('Notes')
    blacklist_date = fields.Datetime('Blacklisted On', default=fields.Datetime.now)
    active = fields.Boolean(default=True)
    
    _sql_constraints = [
        ('phone_unique', 'UNIQUE(phone_number)', 'This phone number is already blacklisted!')
    ]
    
    @api.model
    def add_to_blacklist(self, phone, reason='user_request', notes=''):
        clean_phone = self._normalize_phone(phone)
        
        existing = self.search([('phone_number', '=', clean_phone)])
        if existing:
            return {'success': False, 'message': 'Already blacklisted'}
        
        self.create({
            'phone_number': clean_phone,
            'reason': reason,
            'notes': notes,
        })
        
        return {'success': True, 'message': 'Number added to blacklist'}
    
    @api.model
    def remove_from_blacklist(self, phone):
        clean_phone = self._normalize_phone(phone)
        
        blacklisted = self.search([('phone_number', '=', clean_phone)])
        if blacklisted:
            blacklisted.unlink()
            return {'success': True, 'message': 'Number removed from blacklist'}
        
        return {'success': False, 'message': 'Number not found in blacklist'}
    
    @api.model
    def is_blacklisted(self, phone):
        clean_phone = self._normalize_phone(phone)
        return bool(self.search([('phone_number', '=', clean_phone)], limit=1))
    
    def _normalize_phone(self, phone):
        if not phone:
            return ''
        
        clean = re.sub(r'[^\d+]', '', phone)
        
        if not clean.startswith('+'):
            if clean.startswith('0'):
                clean = '+254' + clean[1:]
            elif len(clean) == 9:
                clean = '+254' + clean
        
        return clean