# Email: addresses, verification and account recovery

Players can attach an email address to an account, confirm it, and use it to reset a forgotten password or be reminded
of a username (issues #12 and #13).

## How it behaves

| | |
|---|---|
| Sign-up | The email is optional. If given, a confirmation link is sent. |
| Add or change an address later | `POST /api/account/email` (logged in). The new address starts unconfirmed and a link is sent to it. A link for the old address stops working. |
| Confirm | The link opens `/verifyemail?token=...` in the React app, which posts the token to `POST /api/account/email/verify`. Links last 48 hours. |
| Forgot password | `/forgot` in the app, `POST /api/account/forgot-password`. A reset link (`/resetpassword?token=...`) is sent. It works **once** and for **one hour**. |
| Forgot username | `POST /api/account/forgot-username` emails the usernames on that address. |

**Only a confirmed address can recover an account.** Otherwise anyone could type your username's owner's address at
sign-up time and reset passwords with it. The recovery endpoints answer identically for unknown, unconfirmed and
confirmed addresses, so they can not be used to find out who plays. They are rate limited (5 per minute per client).

Links are signed with `SECRET_KEY` (itsdangerous), so nothing about them is stored on the server. A reset link includes a
fingerprint of the current password hash, which is why it stops working the moment the password changes. **Rotating
`SECRET_KEY` invalidates every outstanding link**, as it already logs everyone out.

## Sending

`api/untitledapp/mailer.py` has one function, `send_email(to, subject, text)`. The backend is chosen by `EMAIL_BACKEND`:

| Value | Used for | What it does |
|---|---|---|
| `smtp` | Production | Sends through Flask-Mail with the `MAIL_*` settings in `api/config.py` (SendGrid's SMTP relay). The default when `SENDGRID_API_KEY` is set. |
| `console` | Local development | Writes the message, including the link, to the Flask log. The default when there is no key, so sign-up never fails for lack of one. |
| `memory` | Tests | Collects messages in `app.extensions["mail_outbox"]`. |

A failed send is logged and swallowed. The request still succeeds, because an error would tell an attacker that the
address exists.

### To switch real delivery on in Azure

App settings on the web app: `SENDGRID_API_KEY`, `MAIL_DEFAULT_SENDER` (an address or domain verified in SendGrid) and
`FRONTEND_URL` (for example `https://untitled-space-game-12k34j134.azurewebsites.net`). Without `FRONTEND_URL`, links use
the host of the request that triggered the email.

## Data

`User` gained `email` and `email_verified`. `create_all()` does not add columns to an existing SQLite table, so
`_add_missing_columns()` in `api/untitledapp/__init__.py` adds them at startup (tested against an old-schema file).
Both fields are included in the accounts document the function app keeps as a backup of the users table, like the rest
of the row.

## Not done

- No email on the old `/api/register` and `/api/finalize` routes. They are unused leftovers with a hard-coded sender and
  `localhost` link; they could be deleted.
- No "change password while logged in" page, and no notification email when a password changes.
- Mail is plain text. A template system is not worth it for four messages.
