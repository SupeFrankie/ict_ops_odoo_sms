from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


class SMSContact(models.Model):
    
    _name = 'sms.contact'
    _description = 'SMS Contact'
    _order = 'name'
    _rec_name = 'name'
    
    name = fields.Char(
        string='Full Name',
        required=True,
        index=True,
        help='Contact\'s full name'
    )
    
    mobile = fields.Char(
        string='Mobile Number',
        required=True,
        index=True,
        help='Mobile number in international format (+254...)'
    )
    
    email = fields.Char(
        string='Email',
        help='Optional email address'
    )
    
    contact_type = fields.Selection([
        ('student', 'Student'),
        ('staff', 'Staff'),
        ('club', 'Club Member'),
        ('external', 'External')
    ], string='Contact Type', required=True, default='student',
       help='Type of contact for categorization')
    
    student_id = fields.Char(
        string='Student/Staff ID',
        index=True,
        help='Admission number for students or Staff ID for staff'
    )
    
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        help='Department for staff or faculty for students'
    )
    
    club_ids = fields.Many2many(
        'sms.club',  
        string='Clubs',
        help='Clubs this contact belongs to'
    )
    
    tag_ids = fields.Many2many(
        'sms.tag',
        string='Tags',
        help='Tags for flexible categorization (e.g., Year 1, Finalists, etc.)'
    )
    
    opt_in = fields.Boolean(
        string='Opt-in',
        default=True,
        help='Whether contact agreed to receive SMS'
    )
    
    opt_in_date = fields.Datetime(
        string='Opt-in Date',
        readonly=True,
        help='When contact opted in'
    )
    
    opt_out_date = fields.Datetime(
        string='Opt-out Date',
        readonly=True,
        help='When contact opted out'
    )
    
    blacklisted = fields.Boolean(
        string='Blacklisted',
        compute='_compute_blacklisted',
        store=True,
        help='Whether this contact is on the blacklist'
    )
    
    mailing_list_ids = fields.Many2many(
        'sms.mailing_list',
        string='Mailing Lists',
        help='Lists this contact is subscribed to'
    )
    
    messages_sent = fields.Integer(
        string='Messages Sent',
        compute='_compute_messages_sent',
        store=True,
        help='Total number of SMS sent to this contact'
    )
    
    last_message_date = fields.Datetime(
        string='Last Message Date',
        readonly=True,
        help='When we last sent an SMS to this contact'
    )
    
    active = fields.Boolean(
        default=True,
        help='Inactive contacts won\'t appear in searches'
    )
    
    notes = fields.Text(
        string='Notes',
        help='Internal notes about this contact'
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Related Contact',
        help='Link to Odoo contact if this person exists there'
    )
    
    @api.depends('mobile')
    def _compute_blacklisted(self):
        Blacklist = self.env['sms.blacklist']
        for contact in self:
            clean_mobile = self._clean_phone(contact.mobile)
            contact.blacklisted = bool(
                Blacklist.search([('phone_number', '=', clean_mobile), ('active', '=', True)], limit=1)
            )
    
    @api.depends('mailing_list_ids')
    def _compute_messages_sent(self):
        Message = self.env['sms.message']
        for contact in self:
            contact.messages_sent = Message.search_count([
                ('contact_ids', 'in', contact.id)
            ])
    
    @api.constrains('mobile')
    def _check_mobile(self):
        for contact in self:
            if not contact.mobile:
                raise ValidationError(_('Mobile number is required.'))
            
            clean_mobile = self._clean_phone(contact.mobile)
            
            duplicate = self.search([
                ('mobile', '=', clean_mobile),
                ('id', '!=', contact.id)
            ], limit=1)
            
            if duplicate:
                raise ValidationError(_(
                    'A contact with mobile number %s already exists: %s'
                ) % (clean_mobile, duplicate.name))
    
    @api.model
    def _clean_phone(self, phone):
        if not phone:
            return ''
        
        phone = re.sub(r'[\s\-\(\)]', '', phone)
        
        if phone.startswith('0'):
            phone = '+254' + phone[1:]
        elif not phone.startswith('+'):
            phone = '+254' + phone
        
        return phone
    
    def action_opt_in(self):
        self.ensure_one()
        self.write({
            'opt_in': True,
            'opt_in_date': fields.Datetime.now()
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('%s has been opted in.') % self.name,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_opt_out(self):
        self.ensure_one()
        self.write({
            'opt_in': False,
            'opt_out_date': fields.Datetime.now()
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('%s has been opted out.') % self.name,
                'type': 'info',
                'sticky': False,
            }
        }
    
    def action_add_to_blacklist(self):
        self.ensure_one()
        Blacklist = self.env['sms.blacklist']
        
        if self.blacklisted:
            raise ValidationError(_('This contact is already blacklisted.'))
        
        Blacklist.create({
            'phone_number': self._clean_phone(self.mobile),
            'reason': 'manual',
            'notes': _('Added from contact: %s') % self.name,
        })
        
        self._compute_blacklisted()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('%s has been blacklisted.') % self.name,
                'type': 'warning',
                'sticky': False,
            }
        }
    
    @api.model
    def create(self, vals):
        if 'mobile' in vals:
            vals['mobile'] = self._clean_phone(vals['mobile'])
        
        if vals.get('opt_in') and 'opt_in_date' not in vals:
            vals['opt_in_date'] = fields.Datetime.now()
        
        return super(SMSContact, self).create(vals)
    
    def write(self, vals):
        if 'mobile' in vals:
            vals['mobile'] = self._clean_phone(vals['mobile'])
        
        if 'opt_in' in vals:
            if vals['opt_in']:
                vals['opt_in_date'] = fields.Datetime.now()
            else:
                vals['opt_out_date'] = fields.Datetime.now()
        
        return super(SMSContact, self).write(vals)


class SMSClub(models.Model):
    _name = 'sms.club'
    _description = 'SMS Club'
    _order = 'name'
    
    name = fields.Char(string='Club Name', required=True)
    code = fields.Char(string='Code', help='Short code for the club')
    description = fields.Text(string='Description')
    member_ids = fields.Many2many(
        'sms.contact',
        string='Members',
        help='Club members'
    )
    member_count = fields.Integer(
        string='Members',
        compute='_compute_member_count'
    )
    active = fields.Boolean(default=True)
    
    @api.depends('member_ids')
    def _compute_member_count(self):
        for club in self:
            club.member_count = len(club.member_ids)


class SMSTag(models.Model):
    _name = 'sms.tag'
    _description = 'SMS Tag'
    _order = 'name'
    
    name = fields.Char(string='Tag Name', required=True)
    color = fields.Integer(string='Color', help='Color index for UI')
    active = fields.Boolean(default=True)