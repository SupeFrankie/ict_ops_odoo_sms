{
    'name': 'ICT Operations - SMS Module (Main Communications)',
    'version': '1.0.0',
    'category': 'Marketing/SMS',
    'summary': 'SMS Campaigns with Africa\'s Talking API for Mass University Communication at Strathmore University',
    'description': """
        University SMS Communication & Management System
        ================================================
        Features:
        ---------
        * Send bulk SMS to students, staff, clubs, departments and parents.
        * Africa's Talking API integration.
        * Import recipients list from CSV/DOC/DOCX.
        * Personalised messages with name, admission number, staff ID
        * Opt-in/Opt-out management.
        * Blacklist functionality.
        * Department & group-based campaigns.
    """,
    'author': 'Francis Martine Nyabuto Agata',
    'website': 'SupeFrankie@github.com',
    'license': 'LGPL-3',
    'depends': ['base', 
                'mail', 
                'contacts', 
                'web',
                'hr',
                ],
    
    'data': [
        
        #Security
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        
        #Data Files
        'data/sms_template_data.xml',
        #'data/ir_cron.xml',
        
        #Menu Structure
        'views/menu_views.xml',
        
        #views
        'views/sms_template_views.xml',
        'views/sms_campaign_views.xml',
        'views/sms_recipient_views.xml',
        'views/sms_blacklist_views.xml',
        'views/sms_gateway_views.xml',
        'views/opt_out_templates.xml',
        
        #Wizards
        'wizard/sms_composer_views.xml',
        'wizard/import_recipients_wizard.xml',
    ],
    'demo': [],
    
    'installable': True,
    'application': True,
    'auto_install': False,
    
    
}