# models/sms_recipient.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re


class SmsRecipient(models.Model):
    _name = 'sms.recipient'
    _description = 'SMS Recipient'
    _order = 'create_date desc'

    campaign_id = fields.Many2one(
        'sms.campaign',
        string='Campaign',
        required=True,
        ondelete='cascade',
        index=True
    )

    name = fields.Char(required=True)
    phone_number = fields.Char(string='Phone Number', required=True, index=True)
    email = fields.Char()

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

    cost = fields.Monetary(
        currency_field='currency_id',
        help='SMS cost returned by gateway'
    )

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    department = fields.Char(help='Department name')
    club = fields.Char(help='Club name')
    year_of_study = fields.Char()

    _sql_constraints = [
        (
            'unique_phone_campaign',
            'unique(phone_number, campaign_id)',
            'This phone number already exists in this campaign.'
        )
    ]

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

    @api.constrains('phone_number')
    def _check_phone(self):
        for rec in self:
            rec.phone_number = self.normalize_phone(rec.phone_number)