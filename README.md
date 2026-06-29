# Claim Submission Portal

A simple Python web application built with Flask where staff can submit and track claims, and OIC (Officer in Charge) staff can manage claim types, review submissions, and approve or reject them.

---

## Overview

This application provides two levels of access:

- **Normal Staff** — Log in, submit claims by selecting a claim type and entering the required details, and search or track the status of their own submissions.
- **OIC Staff** — Log in to create and manage claim types, review submitted claims, approve or reject them, and customise the claim approval notification template.

The app is designed to remain simple while including the main features needed for claims submission and approval workflows.


## Features

### Normal Staff
- Register and log in
- Submit claims by selecting a claim type and providing details
- Search and view their own submitted claims
- Track the status of submissions

### OIC Staff
- Create and manage claim types
- Review all submitted claims
- Approve or reject claims
- Customise the claim approval notification template

---

## Security Vulnerabilities (Intentional — For Educational / CTF Purposes)

> **Warning:** This application contains **intentional security vulnerabilities** designed for demonstration and learning purposes. **Do not deploy this in production.**

### Privilege Escalation 1 — Stored XSS

- **Location:** Claim submission fields (e.g., claim description)
- **Description:** Claim submission fields are stored directly in PostgreSQL without sanitisation and rendered on the OIC review page using Jinja2. A normal staff user can submit a claim containing a stored XSS payload. When an OIC staff member opens the claim to review or approve it, the payload executes in the OIC staff session, allowing actions to be performed with elevated privileges.

### Privilege Escalation 2 — SQL Injection

- **Location:** Claims search function
- **Description:** The claims search function is vulnerable to SQL injection because user input is concatenated directly into the database query. Authenticated normal staff users can search and view their own submitted claims, while OIC staff can review all submitted claims. A normal staff user can exploit this flaw to extract other users' claim records or credential data from PostgreSQL, which can then be used to access higher-privileged OIC staff accounts and perform privileged actions.

### RCE 1 — SSTI through Jinja Template

- **Location:** OIC claim approval notification template customisation page (`/oic/customize-claim-notification`)
- **Description:** OIC staff can edit the claim approval notification template, which is stored in PostgreSQL. When a claim is approved or updated, the stored template is rendered with claim data using `render_template_string(stored_template, claim_data=claim)`. An attacker with OIC access can modify the template to include SSTI payloads, and when the notification is rendered, arbitrary commands execute on the server.

### Business Logic Flaw — Broken Approval Workflow

- **Location:** Claim approval/rejection endpoint
- **Description:** The claim approval workflow relies only on a hidden form field or client-side button visibility to restrict approve or reject actions, but the server does not enforce a proper role check. A normal staff user can tamper with the request or directly access the approval endpoint to approve their own submitted claim, bypassing the intended OIC-only authorisation control.

---

## Getting Started

### Prerequisites

- Docker & Docker Compose

### Running the Application

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd "Claim Submission Portal"
   ```

2. Start the application with Docker Compose:
   ```bash
   docker-compose up --build
   ```

3. Access the application at:
   ```
   http://localhost:5000
   ```

### Environment Variables

| Variable       | Description                  | Default                                              |
|----------------|------------------------------|------------------------------------------------------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://claimuser:claimpass@db:5432/claimdb`   |
| `SECRET_KEY`   | Flask secret key             | Must be set manually                                 |

---

## Solutions

Detailed exploitation write-ups for each vulnerability can be found in the [`solutions/`](solutions/) folder:

| Vulnerability | File | CWE |
|---------------|------|-----|
| Stored XSS | [`solutions/stored_xss.md`](solutions/stored_xss.md) | CWE-79 |
| SQL Injection | [`solutions/sql_injection.md`](solutions/sql_injection.md) | CWE-89 |
| SSTI (Server-Side Template Injection) | [`solutions/ssti.md`](solutions/ssti.md) | CWE-1336 |
| Broken Approval Workflow | [`solutions/broken_approval_workflow.md`](solutions/broken_approval_workflow.md) | CWE-862 |

### Default Credentials

| Role | Username | Password |
|------|----------|----------|
| OIC Staff | `oic_admin` | `oic_admin_pass` |
| Normal Staff | `staff_user` | `staff_pass` |

---

## Disclaimer

This project is intended for **educational and demonstration purposes only**. The intentional vulnerabilities present in this application should only be used in controlled environments for learning about web application security. **Never deploy this application in a production environment.**
