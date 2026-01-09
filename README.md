# Author - Francis Martine Nyabuto Tompo Agata
* github - SupeFrankie@github.com

# ICT OPs - SMS Module (Main communication module)
 * This is an extension of Odoo's SMS module to provide mass communication and personalised messaging to different departments,clubs, parents and individuals in a recepients list.

# Understanding: 
    - Base SMS module; Handles the structure (sending logic & tracking). defines SMS message models.
        - Provides Ui components (write, schedule & preview message).
        - Adds SMS support across apps
        - Basically an engine without fuel
    - ICT OPs module; adds Africa's Talking integration + custom features & further additions.
        - Adds an external gateway via Africa's Talking to minimize costs.

# Management Tools:
    - Mailing Lists; Organize contacts into segments for targeted outreach.
    - Blacklisting; Maintain a list of phone numbers that have opted out to ensure compliance and avoid spanning
    - A/B Testing; Test different versions on a small percentage of your audience before sending the most successful one to the rest.

# Implementation:
    - Extension --> Python Development; deep integration into institutional models(e.g medical records, student portals, AMS systems etc.) using ORM instance.
    - Model Inheritance; inherit core models like (res.partner or hr.applicant) to add automated logic.
    - Programmatic Composer; use python to trigger SMS.composer dialog allowing users to send messages from anywhere in the ERP.
    - External Gateways; we are using a custom gateway connector, Africa's Talking, by integrating their API using python's [urllib] or [requestslib]

# Needs:
    * SMS alerts for --> upcoming exams, events, holidays, weather alerts, automated actions
    * Must be reusable, scalable, control mass messaging and communictation to separate people(e.g marketing department, ICT department, marketing club etc)
    * Personalised messaging (e.g "Good day <record.partner_id.name>")
    * Opt in/Opt out code
    * Africa's Talking API integration python SDK
    * Database storage of numbers; CSV, DOCX, DOC (microsoft 2007--365 format)
    * Requests --> Handlers --> Controllers 

    
