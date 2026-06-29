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

## Getting Started

### Prerequisites

- Docker & Docker Compose

### Running the Application

1. Clone the repository:
   ```bash
   git clone https://github.com/WrathScythe/Claim-Submission-Portal.git
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
