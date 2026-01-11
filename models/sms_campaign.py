# models/sms_campaign.py
from odoo import models, fields, api, exceptions
import logging

_logger = logging.getLogger(__name__)

class SMSCampaign(models.Model):
    _name = 'sms.campaign'
    _description = 'SMS Campaign'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    
    name = fields.Char('Campaign Name', required=True, tracking=True)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True, string='Status')
    
    message = fields.Text('Message Content', required=True)
    message_length = fields.Integer('Message Length', compute='_compute_message_length')
    
    personalized = fields.Boolean('Use Personalization', 
        help="Replace {name}, {admission_number}, {staff_id} with actual values")
    
    target_type = fields.Selection([
        ('all_students', 'All Students'),
        ('all_staff', 'All Staff'),
        ('department', 'Specific Department'),
        ('club', 'Specific Club'),
        ('custom', 'Custom List'),
    ], string='Target Audience', required=True)
    
    department_id = fields.Many2one('hr.department', 'Department')
    club_id = fields.Many2one('sms.club', 'Club')
    
    recipient_ids = fields.One2many('sms.recipient', 'campaign_id', 'Recipients')
    total_recipients = fields.Integer('Total Recipients', compute='_compute_recipient_count')
    
    send_immediately = fields.Boolean('Send Immediately', default=True)
    schedule_date = fields.Datetime('Scheduled Send Time')
    
    sent_count = fields.Integer('Sent', readonly=True, default=0)
    failed_count = fields.Integer('Failed', readonly=True, default=0)
    delivered_count = fields.Integer('Delivered', readonly=True, default=0)
    pending_count = fields.Integer('Pending', compute='_compute_recipient_count')
    
    success_rate = fields.Float('Success Rate', compute='_compute_success_rate', store=True)
    
    gateway_id = fields.Many2one(
        'sms.gateway.configuration', 
        'SMS Gateway',
        default=lambda self: self.env['sms.gateway.configuration'].search([
            ('is_default', '=', True),
            ('active', '=', True)
        ], limit=1)
    )
    
    @api.depends('message')
    def _compute_message_length(self):
        for campaign in self:
            campaign.message_length = len(campaign.message) if campaign.message else 0
    
    @api.depends('recipient_ids')
    def _compute_recipient_count(self):
        for campaign in self:
            campaign.total_recipients = len(campaign.recipient_ids)
            campaign.pending_count = len(campaign.recipient_ids.filtered(lambda r: r.status == 'pending'))
    
    @api.depends('sent_count', 'total_recipients')
    def _compute_success_rate(self):
        for campaign in self:
            if campaign.total_recipients > 0:
                campaign.success_rate = (campaign.sent_count / campaign.total_recipients) * 100
            else:
                campaign.success_rate = 0.0
    
    def action_prepare_recipients(self):
        """Prepare recipients based on target type"""
        self.ensure_one()
        self.recipient_ids.unlink()
        
        recipients_data = []
        
        if self.target_type == 'all_students':
            contacts = self.env['sms.contact'].search([
                ('contact_type', '=', 'student'),
                ('active', '=', True),
                ('opt_in', '=', True)
            ])
            for contact in contacts:
                if self._check_not_blacklisted(contact.mobile):
                    recipients_data.append({
                        'campaign_id': self.id,
                        'name': contact.name,
                        'phone_number': contact.mobile,
                        'admission_number': contact.student_id,
                        'recipient_type': 'student',
                    })
        
        elif self.target_type == 'all_staff':
            contacts = self.env['sms.contact'].search([
                ('contact_type', '=', 'staff'),
                ('active', '=', True),
                ('opt_in', '=', True)
            ])
            for contact in contacts:
                if self._check_not_blacklisted(contact.mobile):
                    recipients_data.append({
                        'campaign_id': self.id,
                        'name': contact.name,
                        'phone_number': contact.mobile,
                        'staff_id': contact.student_id,
                        'recipient_type': 'staff',
                    })
        
        elif self.target_type == 'department':
            if not self.department_id:
                raise exceptions.UserError("Please select a department")
            
            contacts = self.env['sms.contact'].search([
                ('department_id', '=', self.department_id.id),
                ('active', '=', True),
                ('opt_in', '=', True)
            ])
            for contact in contacts:
                if self._check_not_blacklisted(contact.mobile):
                    recipients_data.append({
                        'campaign_id': self.id,
                        'name': contact.name,
                        'phone_number': contact.mobile,
                        'recipient_type': 'student',
                    })
        
        elif self.target_type == 'club':
            if not self.club_id:
                raise exceptions.UserError("Please select a club")
            
            for contact in self.club_id.member_ids:
                if contact.opt_in and self._check_not_blacklisted(contact.mobile):
                    recipients_data.append({
                        'campaign_id': self.id,
                        'name': contact.name,
                        'phone_number': contact.mobile,
                        'recipient_type': 'student',
                    })
        
        if recipients_data:
            self.env['sms.recipient'].create(recipients_data)
            
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'{len(recipients_data)} recipients prepared!',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _check_not_blacklisted(self, phone):
        """Check if phone number is not blacklisted"""
        return not self.env['sms.blacklist'].is_blacklisted(phone)
    
    def action_send(self):
        """Send SMS campaign"""
        self.ensure_one()
        
        if not self.recipient_ids:
            raise exceptions.UserError("No recipients! Please prepare recipients first.")
        
        if not self.gateway_id:
            raise exceptions.UserError("No SMS gateway configured!")
        
        self.status = 'in_
        '
        
        pending_recipients = self.recipient_ids.filtered(lambda r: r.status == 'pending')
        
        # Send in batches of 100
        batch_size = 100
        for i in range(0, len(pending_recipients), batch_size):
            batch = pending_recipients[i:i+batch_size]
            
            for recipient in batch:
                message = self.message
                
                # Personalize if enabled
                if self.personalized:
                    message = message.replace('{name}', recipient.name or '')
                    message = message.replace('{admission_number}', recipient.admission_number or '')
                    message = message.replace('{staff_id}', recipient.staff_id or '')
                    recipient.personalized_message = message
                else:
                    recipient.personalized_message = message
                
                # Send SMS
                try:
                    success, result = self.gateway_id.send_sms(recipient.phone_number, message)
                    
                    if success:
                        recipient.write({
                            'status': 'sent',
                            'sent_date': fields.Datetime.now()
                        })
                        self.sent_count += 1
                    else:
                        recipient.write({
                            'status': 'failed',
                            'error_message': str(result)
                        })
                        self.failed_count += 1
                        
                except Exception as e:
                    _logger.error(f"Error sending SMS to {recipient.phone_number}: {str(e)}")
                    recipient.write({
                        'status': 'failed',
                        'error_message': str(e)
                    })
                    self.failed_count += 1
        
        self.status = 'completed'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Campaign completed! {self.sent_count} sent, {self.failed_count} failed',
                'type': 'success',
                'sticky': True,
            }
        }
    
    def action_schedule(self):
        """Schedule campaign for later"""
        self.ensure_one()
        
        if not self.schedule_date:
            raise exceptions.UserError("Please set a schedule date first!")
        
        if not self.recipient_ids:
            raise exceptions.UserError("No recipients! Please prepare recipients first.")
        
        self.status = 'scheduled'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Campaign scheduled for {self.schedule_date}',
                'type': 'success',
            }
        }
    
    def action_cancel(self):
        """Cancel campaign"""
        self.ensure_one()
        self.status = 'cancelled'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'Campaign cancelled',
                'type': 'info',
            }
        }