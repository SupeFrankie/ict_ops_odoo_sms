#models/res_partner.py
"""
Extend Odoo's Contact Model (res.partner)
==========================================

Adds SMS functionality to existing Odoo contacts.

This lets you:
- Send SMS directly from contact form
- Link SMS contacts to Odoo partners
- Track SMS history per partner
- Use Odoo contacts in SMS module
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    """
    Extend res.partner (Odoo's contact model).
    
    This adds SMS-related fields and actions to the
    standard Odoo contact form.
    """
    
    _inherit = 'res.partner'  # Extend existing model
    
    # Link to SMS contact
    sms_contact_id = fields.Many2one(
        'sms.contact',
        string='SMS Contact',
        help='Linked SMS contact record'
    )
    
    # SMS preferences
    sms_opt_in = fields.Boolean(
        string='SMS Opt-in',
        default=False,
        help='Whether this contact agreed to receive SMS'
    )
    
    sms_blacklisted = fields.Boolean(
        string='SMS Blacklisted',
        compute='_compute_sms_blacklisted',
        help='Whether this contact is on SMS blacklist'
    )
    
    # Student/Staff info (for university context)
    student_id = fields.Char(
        string='Student/Staff ID',
        help='Admission number or Staff ID'
    )
    
    contact_type = fields.Selection([
        ('student', 'Student'),
        ('staff', 'Staff'),
        ('external', 'External')
    ], string='Contact Type',
       help='Type of contact')
    
    # SMS statistics
    sms_count = fields.Integer(
        string='SMS Sent',
        compute='_compute_sms_count',
        help='Number of SMS sent to this contact'
    )
    
    last_sms_date = fields.Datetime(
        string='Last SMS',
        compute='_compute_sms_count',
        help='When we last sent SMS to this contact'
    )
    
    @api.depends('mobile')
    def _compute_sms_blacklisted(self):
        """Check if mobile is blacklisted."""
        Blacklist = self.env['sms.blacklist']
        for partner in self:
            if partner.mobile:
                partner.sms_blacklisted = Blacklist.is_blacklisted(partner.mobile)
            else:
                partner.sms_blacklisted = False
    
    def _compute_sms_count(self):
        """Count SMS sent to this partner."""
        Message = self.env['sms.message.detail']
        for partner in self:
            if partner.mobile:
                messages = Message.search([
                    ('mobile', '=', partner.mobile)
                ])
                partner.sms_count = len(messages)
                partner.last_sms_date = messages[0].send_date if messages else False
            else:
                partner.sms_count = 0
                partner.last_sms_date = False
    
    # Actions
    def action_send_sms(self):
        """
        Open SMS compose wizard for this partner.
        
        Button in partner form view opens wizard to send SMS.
        """
        self.ensure_one()
        
        if not self.mobile:
            raise UserError(_('This contact has no mobile number!'))
        
        if self.sms_blacklisted:
            raise UserError(_('This contact is blacklisted and cannot receive SMS!'))
        
        # Create or link SMS contact
        if not self.sms_contact_id:
            self._create_sms_contact()
        
        # Open SMS wizard
        return {
            'name': _('Send SMS'),
            'type': 'ir.actions.act_window',
            'res_model': 'sms.compose.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_contact_ids': [(6, 0, [self.sms_contact_id.id])],
                'default_recipient_type': 'individual',
            }
        }
    
    def action_create_sms_contact(self):
        """
        Create SMS contact from this partner.
        
        Copies information from partner to SMS contact.
        """
        self.ensure_one()
        
        if self.sms_contact_id:
            raise UserError(_('This partner already has an SMS contact!'))
        
        if not self.mobile:
            raise UserError(_('This partner has no mobile number!'))
        
        self._create_sms_contact()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('SMS contact created successfully!'),
                'type': 'success',
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'sms.contact',
                    'res_id': self.sms_contact_id.id,
                    'view_mode': 'form',
                }
            }
        }
    
    def action_view_sms_contact(self):
        """View linked SMS contact."""
        self.ensure_one()
        
        if not self.sms_contact_id:
            raise UserError(_('No SMS contact linked to this partner!'))
        
        return {
            'name': _('SMS Contact'),
            'type': 'ir.actions.act_window',
            'res_model': 'sms.contact',
            'res_id': self.sms_contact_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_sms_history(self):
        """View SMS sent to this partner."""
        self.ensure_one()
        
        if not self.mobile:
            raise UserError(_('This contact has no mobile number!'))
        
        return {
            'name': _('SMS History'),
            'type': 'ir.actions.act_window',
            'res_model': 'sms.message.detail',
            'view_mode': 'tree,form',
            'domain': [('mobile', '=', self.mobile)],
            'context': {'default_mobile': self.mobile}
        }
    
    def action_opt_in_sms(self):
        """Opt this partner in for SMS."""
        self.ensure_one()
        
        self.write({'sms_opt_in': True})
        
        # Update SMS contact if exists
        if self.sms_contact_id:
            self.sms_contact_id.action_opt_in()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('%s opted in for SMS.') % self.name,
                'type': 'success',
            }
        }
    
    def action_opt_out_sms(self):
        """Opt this partner out of SMS."""
        self.ensure_one()
        
        self.write({'sms_opt_in': False})
        
        # Update SMS contact if exists
        if self.sms_contact_id:
            self.sms_contact_id.action_opt_out()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('%s opted out of SMS.') % self.name,
                'type': 'info',
            }
        }
    
    def action_add_to_blacklist(self):
        """Add this partner to SMS blacklist."""
        self.ensure_one()
        
        if not self.mobile:
            raise UserError(_('This contact has no mobile number!'))
        
        if self.sms_blacklisted:
            raise UserError(_('This contact is already blacklisted!'))
        
        # Add to blacklist
        Blacklist = self.env['sms.blacklist']
        Blacklist.create({
            'mobile': self.mobile,
            'reason': 'manual',
            'reason_notes': _('Added from partner: %s') % self.name,
        })
        
        # Update computed field
        self._compute_sms_blacklisted()
        
        # Opt out
        self.write({'sms_opt_in': False})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('%s added to SMS blacklist.') % self.name,
                'type': 'warning',
            }
        }
    
    # Helper methods
    def _create_sms_contact(self):
        """
        Create SMS contact from partner data.
        
        Internal method to sync partner -> SMS contact.
        """
        self.ensure_one()
        
        Contact = self.env['sms.contact']
        
        # Prepare contact data
        contact_data = {
            'name': self.name,
            'mobile': self.mobile,
            'email': self.email or False,
            'opt_in': self.sms_opt_in,
            'partner_id': self.id,
        }
        
        # Add student/staff info if available
        if self.student_id:
            contact_data['student_id'] = self.student_id
        
        if self.contact_type:
            contact_data['contact_type'] = self.contact_type
        
        # Link to department if partner is employee
        if self.parent_id and self.parent_id.is_company:
            # Try to find matching department
            dept = self.env['hr.department'].search([
                ('name', 'ilike', self.parent_id.name)
            ], limit=1)
            if dept:
                contact_data['department_id'] = dept.id
        
        # Create SMS contact
        sms_contact = Contact.create(contact_data)
        
        # Link back to partner
        self.write({'sms_contact_id': sms_contact.id})
        
        return sms_contact
    
    @api.model
    def create(self, vals):
        """
        Override create to auto-create SMS contact if mobile provided.
        
        When someone creates a new contact with mobile number,
        optionally auto-create SMS contact.
        """
        partner = super(ResPartner, self).create(vals)
        
        # Auto-create SMS contact if:
        # 1. Has mobile number
        # 2. Opted in for SMS
        # 3. No SMS contact exists yet
        if partner.mobile and partner.sms_opt_in and not partner.sms_contact_id:
            try:
                partner._create_sms_contact()
            except Exception as e:
                # Don't fail partner creation if SMS contact fails
                _logger = logging.getLogger(__name__)
                _logger.warning(
                    'Failed to auto-create SMS contact for %s: %s',
                    partner.name, str(e)
                )
        
        return partner
    
    def write(self, vals):
        """
        Override write to sync changes to SMS contact.
        
        When partner mobile or name changes, update linked SMS contact.
        """
        result = super(ResPartner, self).write(vals)
        
        # Sync to SMS contact if changed
        if any(field in vals for field in ['name', 'mobile', 'email', 'sms_opt_in', 'student_id']):
            for partner in self:
                if partner.sms_contact_id:
                    sync_data = {}
                    
                    if 'name' in vals:
                        sync_data['name'] = partner.name
                    if 'mobile' in vals:
                        sync_data['mobile'] = partner.mobile
                    if 'email' in vals:
                        sync_data['email'] = partner.email or False
                    if 'sms_opt_in' in vals:
                        sync_data['opt_in'] = partner.sms_opt_in
                    if 'student_id' in vals:
                        sync_data['student_id'] = partner.student_id
                    
                    if sync_data:
                        try:
                            partner.sms_contact_id.write(sync_data)
                        except Exception as e:
                            _logger = logging.getLogger(__name__)
                            _logger.warning(
                                'Failed to sync partner %s to SMS contact: %s',
                                partner.name, str(e)
                            )
        
        return result
    
    # Bulk actions for multiple partners
    def action_bulk_send_sms(self):
        """
        Send SMS to multiple selected partners.
        
        Available in list view: select multiple, Actions > Send SMS.
        """
        if not self:
            raise UserError(_('Please select at least one contact!'))
        
        # Filter partners with mobile
        partners_with_mobile = self.filtered(lambda p: p.mobile and not p.sms_blacklisted)
        
        if not partners_with_mobile:
            raise UserError(_('None of the selected contacts have valid mobile numbers!'))
        
        # Create SMS contacts for those who don't have them
        for partner in partners_with_mobile:
            if not partner.sms_contact_id:
                partner._create_sms_contact()
        
        # Get all SMS contact IDs
        sms_contact_ids = partners_with_mobile.mapped('sms_contact_id').ids
        
        # Open SMS wizard
        return {
            'name': _('Send SMS to %d Contacts') % len(sms_contact_ids),
            'type': 'ir.actions.act_window',
            'res_model': 'sms.compose.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_contact_ids': [(6, 0, sms_contact_ids)],
                'default_recipient_type': 'individual',
            }
        }
    
    def action_bulk_create_sms_contacts(self):
        """
        Create SMS contacts for all selected partners.
        
        Bulk action: select multiple, Actions > Create SMS Contacts.
        """
        if not self:
            raise UserError(_('Please select at least one contact!'))
        
        created_count = 0
        skipped_count = 0
        error_count = 0
        
        for partner in self:
            try:
                if partner.sms_contact_id:
                    skipped_count += 1
                    continue
                
                if not partner.mobile:
                    skipped_count += 1
                    continue
                
                partner._create_sms_contact()
                created_count += 1
            
            except Exception as e:
                error_count += 1
                _logger = logging.getLogger(__name__)
                _logger.error(
                    'Failed to create SMS contact for %s: %s',
                    partner.name, str(e)
                )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bulk SMS Contact Creation'),
                'message': _(
                    'Created: %d\nSkipped: %d\nErrors: %d'
                ) % (created_count, skipped_count, error_count),
                'type': 'success' if error_count == 0 else 'warning',
                'sticky': True,
            }
        }


# Add logging
import logging
_logger = logging.getLogger(__name__)