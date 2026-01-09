from odoo import models, fields, api
from odoo.exceptions import UserError
import base64
import csv
import io
import logging

_logger = logging.getLogger(__name__)


class ImportSmsRecipients(models.TransientModel):
    _name = 'import.sms.recipients'
    _description = 'Import SMS Recipients'

    campaign_id = fields.Many2one('sms.campaign', string='Campaign', required=True)
    import_file = fields.Binary(string='CSV File', required=True, help="Upload a CSV file with columns: name, phone_number")
    filename = fields.Char(string='Filename')
    
    @api.model
    def default_get(self, fields_list):
        res = super(ImportSmsRecipients, self).default_get(fields_list)
        if self._context.get('active_id'):
            res['campaign_id'] = self._context.get('active_id')
        return res
    
    def action_import(self):
        """Import recipients from CSV file"""
        self.ensure_one()
        
        if not self.import_file:
            raise UserError('Please upload a CSV file.')
        
        # Decode the file
        try:
            file_content = base64.b64decode(self.import_file)
            csv_data = io.StringIO(file_content.decode('utf-8'))
        except Exception as e:
            raise UserError(f'Error reading file: {str(e)}')
        
        # Parse CSV
        try:
            csv_reader = csv.DictReader(csv_data)
            recipients = []
            errors = []
            row_num = 1
            
            for row in csv_reader:
                row_num += 1
                
                # Validate required fields
                if 'phone_number' not in row or not row['phone_number']:
                    errors.append(f"Row {row_num}: Missing phone number")
                    continue
                
                name = row.get('name', row.get('phone_number', 'Unknown'))
                phone_number = row['phone_number'].strip()
                
                # Basic phone number validation
                if not phone_number:
                    errors.append(f"Row {row_num}: Empty phone number")
                    continue
                
                # Check if number is blacklisted
                blacklisted = self.env['sms.blacklist'].search([
                    ('phone_number', '=', phone_number),
                    ('active', '=', True)
                ], limit=1)
                
                if blacklisted:
                    errors.append(f"Row {row_num}: Phone number {phone_number} is blacklisted")
                    continue
                
                # Check for duplicates in this campaign
                existing = self.env['sms.recipient'].search([
                    ('campaign_id', '=', self.campaign_id.id),
                    ('phone_number', '=', phone_number)
                ], limit=1)
                
                if existing:
                    errors.append(f"Row {row_num}: Phone number {phone_number} already exists in this campaign")
                    continue
                
                recipients.append({
                    'campaign_id': self.campaign_id.id,
                    'name': name,
                    'phone_number': phone_number,
                    'state': 'pending'
                })
            
            # Create recipients
            if recipients:
                self.env['sms.recipient'].create(recipients)
                _logger.info(f"Imported {len(recipients)} recipients for campaign {self.campaign_id.name}")
            
            # Show result message
            message = f"Successfully imported {len(recipients)} recipients."
            if errors:
                message += f"\n\nErrors encountered:\n" + "\n".join(errors[:10])
                if len(errors) > 10:
                    message += f"\n... and {len(errors) - 10} more errors"
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Import Complete',
                    'message': message,
                    'type': 'success' if not errors else 'warning',
                    'sticky': bool(errors),
                }
            }
            
        except Exception as e:
            raise UserError(f'Error parsing CSV file: {str(e)}\n\nPlease ensure your CSV has columns: name, phone_number')
    
    def action_download_template(self):
        """Download a sample CSV template"""
        csv_content = "name,phone_number\n"
        csv_content += "John Doe,+254712345678\n"
        csv_content += "Jane Smith,+254723456789\n"
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'data:text/csv;base64,{base64.b64encode(csv_content.encode()).decode()}',
            'target': 'download',
        }