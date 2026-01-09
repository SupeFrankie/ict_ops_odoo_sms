# models/sms_recipient.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re


class SmsRecipient(models.Model):
    _name = 'sms.recipient'
    _description = 'SMS Recipient'
    _order = 'create_date desc'

    # core
    campaign_id = fields.Many2one(
        'sms.campaign',
        string='Campaign',
        required=True,
        ondelete='cascade',
        index=True
    )

    name = fields.Char(required=True)
    phone = fields.Char(required=True, index=True)
    email = fields.Char()

    # identifiers
    admission_number = fields.Char(index=True)
    staff_id = fields.Char(index=True)

    recipient_type = fields.Selection(
        [
            ('student', 'Student'),
            ('staff', 'Staff'),
            ('other', 'Other'),
        ],
        default='student',
        index=True
    )

    # message tracking
    status = fields.Selection(
        [
            ('pending', 'Pending'),
            ('sent', 'Sent'),
            ('delivered', 'Delivered'),
            ('failed', 'Failed'),
        ],
        default='pending',
        index=True
    )

    personalized_message = fields.Text()
    sent_date = fields.Datetime()
    delivered_date = fields.Datetime()
    error_message = fields.Text()

    gateway_message_id = fields.Char(index=True)
    retry_count = fields.Integer(default=0)

    # cost tracking
    cost = fields.Monetary(
        currency_field='currency_id',
        help='SMS cost returned by gateway'
    )

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    # metadata section
    department = fields.Char(help='Department name (legacy-compatible)')
    club = fields.Char(help='Club name (legacy-compatible)')
    year_of_study = fields.Char()

    # constraints
    _sql_constraints = [
        (
            'unique_phone_campaign',
            'unique(phone, campaign_id)',
            'This phone number already exists in this campaign.'
        )
    ]

    # phone normalization
    @api.model
    def normalize_phone(self, phone):
        if not phone:
            return phone

        phone = re.sub(r'\s+', '', phone)

        if phone.startswith('+'):
            return phone
        if phone.startswith('0'):
            return '+254' + phone[1:]
        if phone.startswith(('7', '1')):
            return '+254' + phone

        raise ValidationError(f'Invalid phone number: {phone}')

    @api.constrains('phone')
    def _check_phone(self):
        for rec in self:
            rec.phone = self.normalize_phone(rec.phone)
