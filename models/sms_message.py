#models/sms_message.py
"""
SMS Message Model
=================

Handles actual SMS sending via Africa's Talking API.
Tracks all sent messages and their delivery status.

Africa's Talking API Integration:
- Sandbox: https://api.sandbox.africastalking.com
- Production: https://api.africastalking.com
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class SMSMessage(models.Model):
    """
    SMS Message records.
    
    Each record represents one SMS send operation.
    Can be sent to one or multiple recipients.
    """
    
    _name = 'sms.message'
    _description = 'SMS Message'
    _order = 'create_date desc'
    _rec_name = 'subject'
    
    # Message content
    subject = fields.Char(
        string='Subject',
        required=True,
        help='Brief description of this message'
    )
    
    body = fields.Text(
        string='Message Body',
        required=True,
        help='The actual SMS content (160 chars = 1 SMS)'
    )
    
    char_count = fields.Integer(
        string='Characters',
        compute='_compute_char_count',
        help='Number of characters in message'
    )
    
    sms_count = fields.Integer(
        string='SMS Parts',
        compute='_compute_char_count',
        help='Number of SMS this will cost (every 160 chars = 1 SMS)'
    )
    
    # Recipients
    recipient_type = fields.Selection([
        ('individual', 'Individual'),
        ('mailing_list', 'Mailing List'),
        ('department', 'Department'),
        ('club', 'Club'),
        ('manual', 'Manual Numbers')
    ], string='Recipient Type', required=True, default='individual',
       help='How recipients were selected')
    
    contact_ids = fields.Many2many(
        'sms.contact',
        string='Contacts',
        help='Individual contacts to send to'
    )
    
    mailing_list_id = fields.Many2one(
        'sms.mailing_list',
        string='Mailing List',
        help='Send to all contacts in this list'
    )
    
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        help='Send to all in this department'
    )
    
    club_id = fields.Many2one(
        'sms.club',
        string='Club',
        help='Send to all club members'
    )
    
    manual_numbers = fields.Text(
        string='Manual Numbers',
        help='Comma-separated phone numbers'
    )
    
    # Personalization
    personalize = fields.Boolean(
        string='Personalize',
        default=False,
        help='Use placeholders like {name}, {student_id}'
    )
    
    # Sending details
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('partial', 'Partially Sent')
    ], string='Status', default='draft', readonly=True,
       help='Current state of this message')
    
    send_date = fields.Datetime(
        string='Send Date',
        readonly=True,
        help='When this message was sent'
    )
    
    scheduled_date = fields.Datetime(
        string='Schedule For',
        help='Schedule to send at a specific time'
    )
    
    # Statistics
    total_recipients = fields.Integer(
        string='Total Recipients',
        compute='_compute_recipients',
        store=True,
        help='Total number of recipients'
    )
    
    sent_count = fields.Integer(
        string='Sent',
        default=0,
        help='Successfully sent'
    )
    
    failed_count = fields.Integer(
        string='Failed',
        default=0,
        help='Failed to send'
    )
    
    blacklisted_count = fields.Integer(
        string='Blacklisted',
        default=0,
        help='Skipped (blacklisted)'
    )
    
    total_cost = fields.Float(
        string='Total Cost (KES)',
        default=0.0,
        help='Total cost in Kenyan Shillings'
    )
    
    # Africa's Talking response
    at_response = fields.Text(
        string='API Response',
        readonly=True,
        help='Full response from Africa\'s Talking API'
    )
    
    error_message = fields.Text(
        string='Error Message',
        readonly=True,
        help='Error details if sending failed'
    )
    
    # Related records
    detail_ids = fields.One2many(
        'sms.message.detail',
        'message_id',
        string='Send Details',
        help='Per-recipient send status'
    )
    
    template_id = fields.Many2one(
        'sms.template',
        string='Template Used',
        help='Template this message was based on'
    )
    
    # Metadata
    sender_id = fields.Many2one(
        'res.users',
        string='Sent By',
        default=lambda self: self.env.user,
        readonly=True,
        help='User who sent this message'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        help='Company sending the SMS'
    )
    
    notes = fields.Text(string='Notes')
    
    # Computed fields
    @api.depends('body')
    def _compute_char_count(self):
        """Calculate character count and SMS parts."""
        for message in self:
            if message.body:
                message.char_count = len(message.body)
                # Standard SMS is 160 chars
                # With Unicode/emojis it's 70 chars per SMS
                # We'll use conservative 160
                message.sms_count = (message.char_count // 160) + 1
            else:
                message.char_count = 0
                message.sms_count = 0
    
    @api.depends('contact_ids', 'mailing_list_id', 'department_id', 
                 'club_id', 'manual_numbers')
    def _compute_recipients(self):
        """Calculate total number of recipients."""
        for message in self:
            recipients = set()  # Use set to avoid duplicates
            
            # Add individual contacts
            if message.contact_ids:
                recipients.update(message.contact_ids.mapped('mobile'))
            
            # Add mailing list contacts
            if message.mailing_list_id:
                recipients.update(
                    message.mailing_list_id.contact_ids.mapped('mobile')
                )
            
            # Add department contacts
            if message.department_id:
                dept_contacts = self.env['sms.contact'].search([
                    ('department_id', '=', message.department_id.id),
                    ('opt_in', '=', True)
                ])
                recipients.update(dept_contacts.mapped('mobile'))
            
            # Add club members
            if message.club_id:
                recipients.update(message.club_id.member_ids.mapped('mobile'))
            
            # Add manual numbers
            if message.manual_numbers:
                manual = [n.strip() for n in message.manual_numbers.split(',')]
                recipients.update(manual)
            
            message.total_recipients = len(recipients)
    
    # Main sending logic
    def action_send_sms(self):
        """
        Send the SMS message.
        
        This is the main method that:
        1. Validates everything
        2. Gets all recipients
        3. Calls Africa's Talking API
        4. Records results
        """
        self.ensure_one()
        
        if not self.body:
            raise UserError(_('Message body is required!'))
        
        if self.total_recipients == 0:
            raise UserError(_('No recipients selected!'))
        
        # Update state
        self.write({'state': 'sending'})
        
        try:
            # Get all unique recipients
            recipients = self._get_all_recipients()
            
            if not recipients:
                raise UserError(_('No valid recipients found!'))
            
            # Send via Africa's Talking
            result = self._send_via_africas_talking(recipients)
            
            # Update statistics
            self.write({
                'state': 'sent' if result['success'] else 'partial',
                'send_date': fields.Datetime.now(),
                'sent_count': result['sent_count'],
                'failed_count': result['failed_count'],
                'blacklisted_count': result['blacklisted_count'],
                'total_cost': result['total_cost'],
                'at_response': json.dumps(result['response'], indent=2),
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('SMS sent successfully! Sent: %d, Failed: %d') % (
                        result['sent_count'], result['failed_count']
                    ),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error('SMS sending failed: %s', str(e))
            self.write({
                'state': 'failed',
                'error_message': str(e),
            })
            raise UserError(_('Failed to send SMS: %s') % str(e))
    
    def _get_all_recipients(self):
        """
        Get all recipients with their contact info.
        
        Returns:
            list: List of dicts with recipient info
                  [{'mobile': '+254...', 'name': '...', 'student_id': '...'}]
        """
        recipients = []
        seen_numbers = set()
        Blacklist = self.env['sms.blacklist']
        
        def add_contact(contact):
            """Helper to add a contact if valid."""
            if not contact or not contact.mobile:
                return
            
            mobile = contact.mobile
            
            # Skip duplicates
            if mobile in seen_numbers:
                return
            
            # Skip blacklisted
            if Blacklist.is_blacklisted(mobile):
                self.blacklisted_count += 1
                return
            
            # Skip opted-out
            if not contact.opt_in:
                return
            
            seen_numbers.add(mobile)
            recipients.append({
                'mobile': mobile,
                'name': contact.name,
                'student_id': contact.student_id or '',
                'contact_id': contact.id,
            })
        
        # Add from different sources
        if self.contact_ids:
            for contact in self.contact_ids:
                add_contact(contact)
        
        if self.mailing_list_id:
            for contact in self.mailing_list_id.contact_ids:
                add_contact(contact)
        
        if self.department_id:
            dept_contacts = self.env['sms.contact'].search([
                ('department_id', '=', self.department_id.id),
                ('opt_in', '=', True)
            ])
            for contact in dept_contacts:
                add_contact(contact)
        
        if self.club_id:
            for contact in self.club_id.member_ids:
                add_contact(contact)
        
        if self.manual_numbers:
            for number in self.manual_numbers.split(','):
                number = number.strip()
                if number and not Blacklist.is_blacklisted(number):
                    if number not in seen_numbers:
                        seen_numbers.add(number)
                        recipients.append({
                            'mobile': number,
                            'name': '',
                            'student_id': '',
                            'contact_id': False,
                        })
        
        return recipients
    
    def _send_via_africas_talking(self, recipients):
        """
        Send SMS via Africa's Talking API.
        
        Args:
            recipients (list): List of recipient dicts
            
        Returns:
            dict: Result with counts and response
        """
        # Get API credentials from system parameters
        ICP = self.env['ir.config_parameter'].sudo()
        username = ICP.get_param('at_username', '')
        api_key = ICP.get_param('at_api_key', '')
        sender_id = ICP.get_param('at_sender_id', 'STRATHU')
        use_sandbox = ICP.get_param('at_use_sandbox', 'True') == 'True'
        
        if not username or not api_key:
            raise UserError(_(
                'Africa\'s Talking credentials not configured!\n'
                'Go to Settings > Technical > System Parameters and set:\n'
                '- at_username\n'
                '- at_api_key'
            ))
        
        # API endpoint
        if use_sandbox:
            base_url = 'https://api.sandbox.africastalking.com'
        else:
            base_url = 'https://api.africastalking.com'
        
        url = f'{base_url}/version1/messaging'
        
        # Prepare results
        result = {
            'success': True,
            'sent_count': 0,
            'failed_count': 0,
            'blacklisted_count': self.blacklisted_count,
            'total_cost': 0.0,
            'response': {},
        }
        
        # Send in batches (Africa's Talking limit is 1000 per request)
        batch_size = 1000
        MessageDetail = self.env['sms.message.detail']
        
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i+batch_size]
            
            # Build recipient list for API
            to_numbers = []
            for recipient in batch:
                # Personalize message if needed
                message = self.body
                if self.personalize:
                    message = message.replace('{name}', recipient['name'])
                    message = message.replace('{student_id}', recipient['student_id'])
                
                to_numbers.append(recipient['mobile'])
            
            # API request
            payload = {
                'username': username,
                'to': ','.join(to_numbers),
                'message': self.body,  # Note: AT doesn't support per-recipient messages
                'from': sender_id,
            }
            
            headers = {
                'apiKey': api_key,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
            }
            
            try:
                response = requests.post(url, data=payload, headers=headers, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                result['response'] = data
                
                # Parse response
                if 'SMSMessageData' in data:
                    sms_data = data['SMSMessageData']
                    recipients_response = sms_data.get('Recipients', [])
                    
                    for recipient_data in recipients_response:
                        status = recipient_data.get('status', '')
                        cost_str = recipient_data.get('cost', 'KES 0')
                        
                        # Parse cost (e.g., "KES 0.8000")
                        try:
                            cost = float(cost_str.split()[-1])
                        except:
                            cost = 0.0
                        
                        if 'Success' in status:
                            result['sent_count'] += 1
                            result['total_cost'] += cost
                        else:
                            result['failed_count'] += 1
                        
                        # Find matching recipient
                        mobile = recipient_data.get('number', '')
                        recipient_info = next(
                            (r for r in batch if r['mobile'] == mobile), 
                            {}
                        )
                        
                        # Create detail record
                        MessageDetail.create({
                            'message_id': self.id,
                            'contact_id': recipient_info.get('contact_id'),
                            'mobile': mobile,
                            'status': 'sent' if 'Success' in status else 'failed',
                            'cost': cost,
                            'message_id_at': recipient_data.get('messageId', ''),
                            'status_message': status,
                        })
                
            except requests.exceptions.RequestException as e:
                _logger.error('Africa\'s Talking API error: %s', str(e))
                result['success'] = False
                result['failed_count'] += len(batch)
                
                # Create failed detail records
                for recipient in batch:
                    MessageDetail.create({
                        'message_id': self.id,
                        'contact_id': recipient.get('contact_id'),
                        'mobile': recipient['mobile'],
                        'status': 'failed',
                        'status_message': str(e),
                    })
        
        return result


class SMSMessageDetail(models.Model):
    """Per-recipient send status."""
    
    _name = 'sms.message.detail'
    _description = 'SMS Message Detail'
    _order = 'create_date desc'
    
    message_id = fields.Many2one(
        'sms.message',
        string='Message',
        required=True,
        ondelete='cascade'
    )
    
    contact_id = fields.Many2one(
        'sms.contact',
        string='Contact'
    )
    
    mobile = fields.Char(string='Mobile', required=True)
    
    status = fields.Selection([
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('delivered', 'Delivered'),
        ('rejected', 'Rejected')
    ], string='Status', default='sent')
    
    cost = fields.Float(string='Cost (KES)')
    
    message_id_at = fields.Char(
        string='Africa\'s Talking Message ID',
        help='ID from Africa\'s Talking for tracking'
    )
    
    status_message = fields.Char(string='Status Message')
    
    send_date = fields.Datetime(
        string='Sent At',
        default=fields.Datetime.now
    )