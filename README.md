# ICT Operations SMS Module

![Odoo Version](https://img.shields.io/badge/Odoo-17.0%2B-purple?style=for-the-badge&logo=odoo)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Status](https://img.shields.io/badge/Status-Production_Ready-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-LGPL--3-orange?style=for-the-badge)

A localized SMS Gateway integration for Strathmore University ICT Operations, powered by Africa's Talking.

---

## Table of Contents

- [Overview](#overview)
- [Scope and Intended Use](#scope-and-intended-use)
- [Key Features](#key-features)
  - [Core Functionality](#core-functionality)
  - [Technical Resilience](#technical-resilience)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Gateway Setup](#gateway-setup)
  - [Testing the Connection](#testing-the-connection)
- [Operational Notes (ICT Use)](#operational-notes-ict-use)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)
- [Security and Compliance](#security-and-compliance)
- [Author](#author)

---

## Overview

The **ICT Operations SMS Module** replaces Odoo’s default SMS IAP provider with a direct integration to **Africa’s Talking**, enabling reliable, cost-effective SMS delivery for internal university communication.

The module is designed specifically for institutional environments where:

- Internet access is restricted by firewalls
- Network reliability fluctuates
- Data protection and auditability are mandatory

It is suitable for use in:
- Student notifications
- ICT service alerts
- Administrative messaging
- Internal operational broadcasts

---

## Scope and Intended Use

This module is intended for **internal university deployment only**.

Primary users:
- ICT Administrators
- System Administrators
- Authorized Marketing / Communications staff

It is **not** designed for:
- Commercial bulk SMS resale
- External third-party tenant usage
- Personal or non-institutional messaging

---

## Key Features

### Core Functionality

- **Direct SMS Gateway Integration**  
  Custom Python connector communicating directly with Africa’s Talking via REST API.

- **Sandbox and Production Modes**  
  Allows safe testing using Africa’s Talking Sandbox before switching to live production.

- **Administrator Test Messaging**  
  Uses the logged-in admin’s profile number for controlled gateway verification.

---

### Technical Resilience

- **Exponential Backoff Retry Logic**  
  Automatically retries failed requests during temporary network outages.

- **Firewall-Compatible SSL Handling**  
  Supports relaxed SSL verification for controlled internal university networks.

- **Phone Number Normalization**  
  Automatically converts Kenyan numbers into E.164 format  
  (`07xxxxxxxx` → `+2547xxxxxxxx`).

---

## Architecture

The module intercepts Odoo’s SMS dispatch flow and reroutes messages through the Africa’s Talking gateway.

```mermaid
graph LR
    A[User Sends SMS] --> B{Environment Check}
    B -- Sandbox --> C[api.sandbox.africastalking.com]
    B -- Production --> D[api.africastalking.com]
    C & D --> E[Firewall / SSL Handling]
    E --> F[Africa's Talking Gateway]
    F --> G[Recipient Mobile Device]
    F -.-> H[HTTP Status Response]
    H --> I[Odoo Logs & Dashboard]

Installation
Prerequisites

    Odoo 19.0 or higher

    Python 3.10+

    Africa’s Talking account (Sandbox or Production)

    Server internet access (outbound HTTPS)

Installation Steps

    Copy the module into your Odoo addons directory:

    cp -r ict_ops /opt/odoo/custom_addons/

    Update the addons path in odoo.conf if required:

    addons_path = /opt/odoo/addons,/opt/odoo/custom_addons

    Restart the Odoo service:

    sudo systemctl restart odoo

    Activate Developer Mode in Odoo.

    Navigate to Apps, click Update Apps List, then search for:

    ICT Operations SMS Module

    Install the module.

Configuration
Gateway Setup

Navigate to:

SMS Marketing → Configuration → SMS Gateway
Field	Value	Description
Provider	Africa's Talking	Custom gateway provider
Username	sandbox	Use sandbox for testing
API Key	atsk_...	Generated from Africa’s Talking
Sender ID	STRATHMORE	Optional (subject to approval)
Environment	Sandbox / Production	Toggle before going live
Testing the Connection

Click Test Connection.

The system will:

    Detect the currently logged-in administrator

    Read the admin’s phone number from the user profile

    Send a test SMS

    Display:

        Success confirmation, or

        A detailed error message for diagnostics

No bulk messages are sent during testing.
Operational Notes (ICT Use)

    Always test in Sandbox Mode before switching to Production.

    Ensure user phone numbers are correctly stored in international format.

    Limit access to SMS configuration menus using Odoo ACLs.

    Monitor logs during high-volume campaigns.

Troubleshooting
SMS Not Sending

Possible causes:

    Incorrect API Key

    Wrong environment selected

    No internet access from the server

Solution:

    Verify credentials in SMS Gateway settings

    Test connection using Sandbox

    Check server outbound HTTPS access

SSL / Certificate Errors

Cause:

    University firewall performing SSL inspection

Solution:

    Confirm SSL handling is enabled in gateway settings

    Verify firewall rules allow HTTPS traffic to Africa’s Talking

Invalid Phone Number Errors

Cause:

    Incorrect phone number format in user records

Solution:

    Ensure numbers follow:

    +2547XXXXXXXX

    Avoid spaces or special characters

Messages Sent but Not Received

Possible causes:

    Unapproved Sender ID

    Carrier delivery delay

Solution:

    Use default Africa’s Talking sender during testing

    Confirm Sender ID approval status

Project Structure

ict_ops/
├── models/
│   ├── sms_gateway_config.py   # API connector and retry logic
│   ├── sms_campaign.py         # Mass messaging logic
│   ├── sms_blacklist.py        # Opt-out and compliance handling
│   └── ...
├── views/
│   ├── sms_gateway_views.xml   # Gateway configuration UI
│   ├── sms_campaign_views.xml  # Campaign dashboard
│   └── menus.xml               # Navigation menus
├── wizard/
│   └── sms_test_wizard.py      # Connection testing wizard
├── security/
│   └── ir.model.access.csv     # Access control rules
├── __manifest__.py             # Module metadata
└── README.md                   # Documentation

Security and Compliance

    No SMS content is stored outside Odoo

    API keys are stored securely in Odoo system parameters

    Supports opt-out handling via blacklist model

    Compliant with institutional data protection policies

Author

Francis Martine Nyabuto Agata
ICT Department
Strathmore University