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
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True)
    
    message = fields.Text('Message Content', required=True)
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
    recipient_count = fields.Integer('Total Recipients', compute='_compute_recipient_count')
    
    send_immediately = fields.Boolean('Send Immediately', default=True)
    scheduled_date = fields.Datetime('Scheduled Send Time')
    
    sent_count = fields.Integer('Sent', readonly=True)
    failed_count = fields.Integer('Failed', readonly=True)
    delivered_count = fields.Integer('Delivered', readonly=True)
    
    api_config_id = fields.Many2one('africas.talking.sms', 'API Configuration', 
        default=lambda self: self.env['africas.talking.sms'].search([], limit=1))
    
    @api.depends('recipient_ids')
    def _compute_recipient_count(self):
        for campaign in self:
            campaign.recipient_count = len(campaign.recipient_ids)
    
    def action_prepare_recipients(self):
        self.ensure_one()
        self.recipient_ids.unlink()
        
        recipients_data = []
        
        if self.target_type == 'all_students':
            contacts = self.env['sms.contact'].search([
                ('contact_type', '=', 'student'),
                ('active', '=', True)
            ])
            for contact in contacts:
                if self._check_not_blacklisted(contact.mobile):
                    recipients_data.append({
                        'campaign_id': self.id,
                        'name': contact.name,
                        'phone_number': contact.mobile,
                        'phone': contact.mobile,
                        'admission_number': contact.student_id,
                        'recipient_type': 'student',
                    })
        
        elif self.target_type == 'department':
            if not self.department_id:
                raise exceptions.UserError("Please select a department")
            
            contacts = self.env['sms.contact'].search([
                ('department_id', '=', self.department_id.id),
                ('active', '=', True)
            ])
            for contact in contacts:
                if self._check_not_blacklisted(contact.mobile):
                    recipients_data.append({
                        'campaign_id': self.id,
                        'name': contact.name,
                        'phone_number': contact.mobile,
                        'phone': contact.mobile,
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
        return not self.env['sms.blacklist'].search([('phone_number', '=', phone)], limit=1)
    
    def action_send_sms(self):
        self.ensure_one()
        
        if not self.recipient_ids:
            raise exceptions.UserError("No recipients! Please prepare recipients first.")
        
        if not self.api_config_id:
            raise exceptions.UserError("No API configuration found!")
        
        self.state = 'sending'
        
        pending_recipients = self.recipient_ids.filtered(lambda r: r.status == 'pending')
        
        batch_size = 1000
        for i in range(0, len(pending_recipients), batch_size):
            batch = pending_recipients[i:i+batch_size]
            
            phone_numbers = []
            for recipient in batch:
                phone_numbers.append(recipient.phone_number)
                
                if self.personalized:
                    message = self.message
                    message = message.replace('{name}', recipient.name or '')
                    message = message.replace('{admission_number}', recipient.admission_number or '')
                    message = message.replace('{staff_id}', recipient.staff_id or '')
                    recipient.personalized_message = message
            
            result = self.api_config_id.send_sms(phone_numbers, self.message)
            
            if result['success']:
                batch.write({'status': 'sent', 'sent_date': fields.Datetime.now()})
                self.sent_count += result['sent_count']
                self.failed_count += result['failed_count']
            else:
                batch.write({'status': 'failed', 'error_message': result.get('error', 'Unknown error')})
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