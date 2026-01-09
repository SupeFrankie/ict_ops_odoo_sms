# models/sms_campaign.py
from odoo import models, fields, api, exceptions
import logging

_logger = logging.getLogger(__name__)

class SMSCampaign(models.Model):
    _name = 'sms.campaign'
    _description = 'SMS Campaign'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # For chatter/notes
    _order = 'create_date desc'
    
    name = fields.Char('Campaign Name', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True)
    
    # Message content
    message = fields.Text('Message Content', required=True)
    personalized = fields.Boolean('Use Personalization', 
        help="Replace {name}, {admission_number}, {staff_id} with actual values")
    
    # Targeting
    target_type = fields.Selection([
        ('all_students', 'All Students'),
        ('all_staff', 'All Staff'),
        ('department', 'Specific Department'),
        ('club', 'Specific Club'),
        ('custom', 'Custom List'),
    ], string='Target Audience', required=True)
    
    department_id = fields.Many2one('university.department', 'Department', 
        states={'required': [('target_type', '=', 'department')]})
    club_id = fields.Many2one('university.club', 'Club',
        states={'required': [('target_type', '=', 'club')]})
    custom_recipient_ids = fields.Many2many('university.student', 'sms_campaign_custom_student_rel',
        'campaign_id', 'student_id', 'Custom Recipients',
        states={'required': [('target_type', '=', 'custom')]})
    
    # Recipients
    recipient_ids = fields.One2many('sms.recipient', 'campaign_id', 'Recipients')
    recipient_count = fields.Integer('Total Recipients', compute='_compute_recipient_count')
    
    # Scheduling
    send_immediately = fields.Boolean('Send Immediately', default=True)
    scheduled_date = fields.Datetime('Scheduled Send Time')
    
    # Stats
    sent_count = fields.Integer('Sent', readonly=True)
    failed_count = fields.Integer('Failed', readonly=True)
    delivered_count = fields.Integer('Delivered', readonly=True)
    
    # API config
    api_config_id = fields.Many2one('africas.talking.sms', 'API Configuration', 
        default=lambda self: self.env['africas.talking.sms'].search([], limit=1))
    
    @api.depends('recipient_ids')
    def _compute_recipient_count(self):
        for campaign in self:
            campaign.recipient_count = len(campaign.recipient_ids)
    
    def action_prepare_recipients(self):
        """Generate recipient list based on target_type"""
        self.ensure_one()
        
        # Clear existing recipients
        self.recipient_ids.unlink()
        
        recipients_data = []
        
        if self.target_type == 'all_students':
            students = self.env['university.student'].search([('active', '=', True)])
            for student in students:
                if self._check_not_blacklisted(student.phone):
                    recipients_data.append({
                        'campaign_id': self.id,
                        'name': student.name,
                        'phone': student.phone,
                        'admission_number': student.admission_number,
                        'recipient_type': 'student',
                    })
        
        elif self.target_type == 'department':
            if not self.department_id:
                raise exceptions.UserError("Please select a department")
            
            # Get students in department
            students = self.env['university.student'].search([
                ('department_id', '=', self.department_id.id),
                ('active', '=', True)
            ])
            for student in students:
                if self._check_not_blacklisted(student.phone):
                    recipients_data.append({
                        'campaign_id': self.id,
                        'name': student.name,
                        'phone': student.phone,
                        'admission_number': student.admission_number,
                        'recipient_type': 'student',
                    })
        
        # Create recipients in batch (more efficient)
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
        """Check if phone number is blacklisted"""
        return not self.env['sms.blacklist'].search([('phone', '=', phone)], limit=1)
    
    def action_send_sms(self):
        """Send SMS to all recipients"""
        self.ensure_one()
        
        if not self.recipient_ids:
            raise exceptions.UserError("No recipients! Please prepare recipients first.")
        
        if not self.api_config_id:
            raise exceptions.UserError("No API configuration found!")
        
        self.state = 'sending'
        
        # Get recipients who haven't been sent to yet
        pending_recipients = self.recipient_ids.filtered(lambda r: r.state == 'pending')
        
        # Send in batches of 1000 (Africa's Talking limit)
        batch_size = 1000
        for i in range(0, len(pending_recipients), batch_size):
            batch = pending_recipients[i:i+batch_size]
            
            # Prepare messages
            phone_numbers = []
            for recipient in batch:
                phone_numbers.append(recipient.phone)
                
                # Personalize if needed
                if self.personalized:
                    message = self.message
                    message = message.replace('{name}', recipient.name or '')
                    message = message.replace('{admission_number}', recipient.admission_number or '')
                    message = message.replace('{staff_id}', recipient.staff_id or '')
                    recipient.personalized_message = message
            
            # Send batch
            result = self.api_config_id.send_sms(phone_numbers, self.message)
            
            if result['success']:
                # Mark as sent
                batch.write({'state': 'sent', 'sent_date': fields.Datetime.now()})
                self.sent_count += result['sent_count']
                self.failed_count += result['failed_count']
            else:
                batch.write({'state': 'failed', 'error_message': result.get('error', 'Unknown error')})
                self.failed_count += len(batch)
        
        self.state = 'sent'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Campaign sent! {self.sent_count} successful, {self.failed_count} failed',
                'type': 'success',
                'sticky': False,
            }
        }