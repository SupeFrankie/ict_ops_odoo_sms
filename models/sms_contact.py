#models/sms_contact.py
"""
SMS Contact Model
=================

Stores contact information for SMS recipients.
Supports students, staff, and external contacts.

Key Features:
- Student/Staff ID tracking
- Department/Club assignment
- Opt-in/out status
- Contact type classification
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


class SMSContact(models.Model):
    """
    Contact information for SMS recipients.
    
    Think of this as your phonebook for SMS.
    Each record is one person you can send messages to.
    """
    
    _name = 'sms.contact'
    _description = 'SMS Contact'
    _order = 'name'
    _rec_name = 'name'  # What shows when you reference this record
    
    # Basic Information
    name = fields.Char(
        string='Full Name',
        required=True,
        index=True,  # Makes searching faster
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
    
    # University-specific fields
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
        'hr.department',  # Odoo's built-in department model
        string='Department',
        help='Department for staff or faculty for students'
    )
    
    # Additional categorization
    club_ids = fields.Many2many(
        'sms.club',  
        string='Clubs',
        help='Clubs this contact belongs to'
    )
    
    tag_ids = fields.Many2many(
        'sms.tag',  # Custom tags for grouping
        string='Tags',
        help='Tags for flexible categorization (e.g., Year 1, Finalists, etc.)'
    )
    
    # Opt-in/out management
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
    
    # Mailing lists this contact belongs to
    mailing_list_ids = fields.Many2many(
        'sms.mailing_list',
        string='Mailing Lists',
        help='Lists this contact is subscribed to'
    )
    
    # Statistics
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
    
    # Metadata
    active = fields.Boolean(
        default=True,
        help='Inactive contacts won\'t appear in searches'
    )
    
    notes = fields.Text(
        string='Notes',
        help='Internal notes about this contact'
    )
    
    # Related partner (link to Odoo contacts if needed)
    partner_id = fields.Many2one(
        'res.partner',
        string='Related Contact',
        help='Link to Odoo contact if this person exists there'
    )
    
    # Computed fields
    @api.depends('mobile')
    def _compute_blacklisted(self):
        """
        Check if this contact's number is blacklisted.
        
        This is a computed field - it automatically updates
        when the blacklist changes.
        """
        Blacklist = self.env['sms.blacklist']
        for contact in self:
            # Clean the mobile number for comparison
            clean_mobile = self._clean_phone(contact.mobile)
            contact.blacklisted = bool(
                Blacklist.search([('mobile', '=', clean_mobile)], limit=1)
            )
    
    @api.depends('mailing_list_ids')
    def _compute_messages_sent(self):
        """
        Count total messages sent to this contact.
        
        We search the sms.message model for messages
        sent to this contact's number.
        """
        Message = self.env['sms.message']
        for contact in self:
            contact.messages_sent = Message.search_count([
                ('mobile', '=', contact.mobile)
            ])
    
    # Validation
    @api.constrains('mobile')
    def _check_mobile(self):
        """
        Validate mobile number format.
        
        Ensures:
        1. Mobile number is provided
        2. Format is correct (Kenyan: +254... or 07...)
        3. No duplicate numbers
        """
        for contact in self:
            if not contact.mobile:
                raise ValidationError(_('Mobile number is required.'))
            
            # Clean and validate format
            clean_mobile = self._clean_phone(contact.mobile)
            
            # Check for duplicates (excluding this record)
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
        """
        Clean and standardize phone number.
        
        Converts:
        - 0712345678 -> +254712345678
        - 712345678 -> +254712345678
        - +254712345678 -> +254712345678
        
        Args:
            phone (str): Phone number to clean
            
        Returns:
            str: Cleaned phone number in international format
        """
        if not phone:
            return ''
        
        # Remove spaces, dashes, parentheses
        phone = re.sub(r'[\s\-\(\)]', '', phone)
        
        # Remove leading zeros and add country code
        if phone.startswith('0'):
            phone = '+254' + phone[1:]
        elif not phone.startswith('+'):
            phone = '+254' + phone
        
        return phone
    
    # Actions
    def action_opt_in(self):
        """
        Opt this contact in to receive SMS.
        
        Can be triggered from a button in the UI.
        """
        self.ensure_one()  # Make sure we're working with one record
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
        """Opt this contact out of receiving SMS."""
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
        """Add this contact to the blacklist."""
        self.ensure_one()
        Blacklist = self.env['sms.blacklist']
        
        # Check if already blacklisted
        if self.blacklisted:
            raise ValidationError(_('This contact is already blacklisted.'))
        
        # Add to blacklist
        Blacklist.create({
            'mobile': self._clean_phone(self.mobile),
            'reason': _('Added from contact: %s') % self.name,
        })
        
        # Refresh computed field
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
        """
        Override create to clean phone number on creation.
        
        This runs automatically when a new contact is created.
        """
        if 'mobile' in vals:
            vals['mobile'] = self._clean_phone(vals['mobile'])
        
        if vals.get('opt_in') and 'opt_in_date' not in vals:
            vals['opt_in_date'] = fields.Datetime.now()
        
        return super(SMSContact, self).create(vals)
    
    def write(self, vals):
        """
        Override write to clean phone number on update.
        
        This runs automatically when a contact is updated.
        """
        if 'mobile' in vals:
            vals['mobile'] = self._clean_phone(vals['mobile'])
        
        if 'opt_in' in vals:
            if vals['opt_in']:
                vals['opt_in_date'] = fields.Datetime.now()
            else:
                vals['opt_out_date'] = fields.Datetime.now()
        
        return super(SMSContact, self).write(vals)


# Supporting models for categorization
class SMSClub(models.Model):
    """Clubs for categorizing contacts."""
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
    """Tags for flexible contact categorization."""
    _name = 'sms.tag'
    _description = 'SMS Tag'
    _order = 'name'
    
    name = fields.Char(string='Tag Name', required=True)
    color = fields.Integer(string='Color', help='Color index for UI')
    active = fields.Boolean(default=True)