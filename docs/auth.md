# Authentication and Security

Login, JWT tokens, logging out other devices, protected routes, rate limiting, and password reset.

[← Back to the README](../README.md)

---

## Authentication

Authentication utilities are defined in:

```text
auth.py
```

It provides:

- `hash_password()` / `verify_password()` — Argon2 password hashing via
  `pwdlib`
- `create_access_token(data)` — creates a signed JWT from the given claims and
  adds an `exp` expiry (default 30 minutes)
- `create_user_access_token(user)` — the login token for a user:
  `{"sub": "<user id>", "ver": <token_version>}`
- `verify_access_token()` — verifies the signature and requires the `exp`,
  `sub` and `ver` claims, returning the claims or `None`
- `oauth2_scheme` — an `OAuth2PasswordBearer` scheme with token URL
  `/api/users/token`
- `get_current_user()` — a FastAPI dependency that resolves the bearer token
  to a `User`, or raises `401 Unauthorized` with a
  `WWW-Authenticate: Bearer` header. It also checks that the token's `ver`
  matches the user's current `token_version`
- `CurrentUser` — shorthand for `Annotated[User, Depends(get_current_user)]`,
  used by routers to require login
- `generate_reset_token()` / `hash_reset_token()` — make a random password
  reset token and its SHA-256 hash (only the hash is saved in the database)

Tokens are signed with `SECRET_KEY` using the configured algorithm (`HS256` by
default).

### Login flow

```text
POST /api/users          register with username, email, password
        |
        v
POST /api/users/token    send email (in the "username" form field) + password
        |
        v
{"access_token": "...", "token_type": "bearer"}
        |
        v
Authorization: Bearer <access_token>   sent with protected requests
        |
        v
get_current_user()  ->  the logged-in User
```

The login endpoint uses FastAPI's `OAuth2PasswordRequestForm`. The OAuth2
standard names the field `username`, but users log in with their **email**
(matched case-insensitively).

A wrong password and an unknown email return the same
`401 Incorrect email or password` response. For unknown emails the password is
still checked against a dummy hash, so response time does not reveal which
emails are registered.

### Login cookie (for pages)

The JavaScript keeps the token in `localStorage` and sends it to the API in the
`Authorization: Bearer` header. The browser doesn't send `localStorage` when
it asks for a *page*, so the login response also stores the same token in a
cookie:

| Cookie setting | Value | Why |
| --- | --- | --- |
| Name | `access_token` | |
| `HttpOnly` | yes | JavaScript can't read it, so an XSS bug can't steal it |
| `SameSite` | `Lax` | Not sent when another site embeds or posts to this one |
| `Max-Age` | `ACCESS_TOKEN_EXPIRE_MINUTES` × 60 | Expires together with the token |
| `Secure` | `COOKIE_SECURE` (default `false`) | Set to `true` when deployed with HTTPS |

- `get_page_user()` (`PageUser`) reads the cookie on page routes and raises
  `LoginRequired`, which `main.py` turns into a `303` redirect to
  `/login?next=<page>`.
- API routes ignore the cookie and keep requiring the header. That way another
  site can't make a logged-in browser call the API with its cookie (CSRF).
- The cookie holds the same token, so it stops working at the same moment:
  when it expires, or when the password is changed or reset (`token_version`).
- `POST /api/users/logout` clears it. `POST /api/users/session` (needs the
  Bearer header) copies a valid token into the cookie, for browsers that
  logged in before the cookie existed.
- Changing the password sets a new cookie together with the new token, so the
  current browser stays logged in.

Only `/`, `/login`, `/register`, `/forgot-password` and `/reset-password` work
without logging in. `/` shows a welcome page to logged-out visitors.

### Logging out other devices

A JWT is checked only by its signature and expiry; the server doesn't store
it. To make old tokens stop working early, every token carries the user's
`token_version` (`ver`), and `get_current_user()` rejects a token whose `ver`
doesn't match the database:

- Resetting the password (emailed link) adds 1, so every device is logged out.
- Changing the password (`PATCH /api/users/me/password`) adds 1 and returns a
  fresh token (`PasswordChangedResponse`), so only the *other* devices are
  logged out; the account page saves the new token.

Tokens made before `ver` existed are rejected too, so everyone logs in once
after upgrading.

### Rate Limiting

`slowapi` limits how often each IP address can call the routes attackers like
to hammer (`rate_limit.py`):

| Route | Limit | Why |
| --- | --- | --- |
| `POST /api/users/token` | 5 per minute | Slows down password guessing |
| `POST /api/users/forgot-password` | 3 per hour | Stops flooding an inbox with reset emails |
| `POST /api/users/reset-password` | 5 per minute | Slows down guessing reset tokens |

Going over the limit returns `429` with
`{"detail": "Too many attempts. Please wait a while and try again."}`.

- The counts are kept in the server's memory: they reset when the server
  restarts and aren't shared between several server processes. A shared store
  such as Redis would be needed for that.
- Behind a proxy (e.g. nginx) every request seems to come from the proxy's IP,
  so the proxy's forwarded-for header has to be trusted when deploying.
- In tests, set `limiter.enabled = False` (from `rate_limit`) so repeated
  logins don't hit the limits.

### Protected routes

Routes that depend on `get_current_user` require a valid token:

- All `/api/applications` endpoints
- Everything under `/api/companies`, `/api/jobs` and the lookup lists (only
  your own rows; anyone else's gives `404`)
- `GET`, `PATCH`, and `DELETE /api/users/me`
- `PATCH` and `DELETE /api/users/me/picture`
- `PATCH /api/users/me/password`

Requests without a valid token receive `401 Unauthorized`. A logged-in user
who tries to read or change another user's application receives
`403 Forbidden`.

### Using Swagger UI

1. Register with `POST /api/users`.
2. Click **Authorize** (top right of `/docs`).
3. Enter your **email** in the `username` box and your password, then click
   **Authorize**.
4. Swagger now sends the token with every protected request. Tokens expire
   after 30 minutes by default; authorize again when you get `401`.

### Password reset flow

```text
POST /api/users/forgot-password   {"email": "..."}
        |
        |  delete everyone's expired reset tokens (housekeeping)
        |  if the email belongs to a user:
        |    - delete their old reset tokens
        |    - make a random token, save only its SHA-256 hash + expiry (60 min)
        |    - add a background task that emails the token
        v
202 "If an account exists with this email, ..."   (sent right away)
        |
        v
Background task sends the email (link: FRONTEND_URL/reset-password?token=...)
        |
        v
POST /api/users/reset-password    {"token": "...", "new_password": "..."}
        |
        |  hash the token, find it, check it hasn't expired
        |  set the new password, delete the user's reset tokens,
        |  add 1 to token_version (logs out every device)
        v
200 "Password reset successfully. ..."
```

- `forgot-password` gives the same answer whether or not the email is
  registered, so it can't be used to find out who has an account.
- The email is sent with FastAPI's `BackgroundTasks`. The response goes out
  first, then the email is sent, so the user doesn't wait for the slow mail
  server. If sending fails, `email_utils.py` logs "Could not send the password
  reset email for user ..." with the error details (never the token).
- A token works only once, only the newest token works, and it stops working
  after `RESET_TOKEN_EXPIRE_MINUTES`. An unknown, used, or expired token
  returns `400 Invalid or expired reset token`.
- `PATCH /api/users/me/password` changes the password for a logged-in user who
  knows their current password (`400` if it is wrong). It also cancels any
  reset tokens and logs out the user's other devices.

The link in the email opens the frontend's `/reset-password` page, which reads
the token from the URL and sends it to `POST /api/users/reset-password`. You
can still test the endpoint directly by copying the `token` value from the
link into Swagger.
