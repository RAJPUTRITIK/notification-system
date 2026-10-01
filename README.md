# Notification System (Django + React)

Admin manages **triggers × channels (WhatsApp / Email / Web Push)** from one table. Templates, on/off toggles and variable mappings are stored in the DB.

```
backend/   Django + DRF  → deploy on Render
frontend/  React (Vite)  → deploy on Vercel
```

## 1. Run backend locally
```bash
cd backend
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # fill in sandbox keys
python manage.py migrate
python manage.py adminusercreate                                 # triggers, sample templates, admin user
python manage.py runserver                            # http://localhost:8000
```
**Admin login:** `admin` / `admin12345` (change via `ADMIN_USERNAME` / `ADMIN_PASSWORD` in `.env`).

## 2. Run frontend locally
```bash
cd frontend
cp .env.example .env      # set VITE_API_URL and VITE_ONESIGNAL_APP_ID
npm install
npm run dev               # http://localhost:5173
```

## 3. Sandbox accounts (see assignment doc section 4)
| Channel | .env variables |
|---|---|
| WhatsApp (Meta sandbox) | `WHATSAPP_ACCESS_TOKEN`, `PHONE_NUMBER_ID` (+ optional `WHATSAPP_BUSINESS_ACCOUNT_ID`). Add your phone as a test recipient. Token expires often. |
| Email | `EMAIL_PROVIDER=postmark\|brevo\|resend` + `POSTMARKAPP_TOKEN`+`POSTMARK_FROM_EMAIL` **or** `BREVO_API_KEY`+`BREVO_FROM_EMAIL` **or** `RESEND_API_KEY`+`RESEND_FROM_EMAIL`. Sender must be verified. |
| Web Push (OneSignal) | Backend: `ONESIGNAL_APP_ID`, `ONESIGNAL_REST_API_KEY`. Frontend: `VITE_ONESIGNAL_APP_ID`. In OneSignal choose Web only; set site URL to your frontend URL (for local dev use `http://localhost:5173`). |

Never commit `.env`.

## 4. How to test (Tasks A–C)
1. Register a normal user (or use admin) → in **Website** tab save your WhatsApp number (e.g. `919999999999`) + email, click **Enable Web Push** and allow the browser prompt.
2. Log in as admin → **Admin – Notification Settings**. Each cell: **Create / Edit / On-Off / Test**.
3. WhatsApp: Create → Save → **Sync** until *approved* → Test. Without `WHATSAPP_BUSINESS_ACCOUNT_ID` the template is auto-approved and sent as free-form text (works for test recipients who messaged the sandbox number in the last 24h). With it, the template is submitted to Meta. To use Meta's built-in `hello_world`, edit the row in Django admin (`/django-admin/`) and set `wa_template_name=hello_world`, `wa_status=approved`.
4. Log out / log in → Login & Logout triggers fire automatically on all active channels. Result summary is shown in a banner and in **delivery logs**.

## 5. Triggers built
`login`, `logout` (fire automatically), `order_placed`, `password_reset` (buttons on Website tab via `POST /api/events/<key>/`), `not_logged_in_1_day`, `not_logged_in_1_week` (real: `python manage.py fire_inactive`, run daily via cron / Render Cron Job; also simulated by buttons). New triggers can be added from the admin table.

## 6. API summary
| Endpoint | Purpose |
|---|---|
| `POST /api/auth/register|login|logout/`, `GET/PATCH /api/auth/me/` | Auth (Token) – login/logout fire triggers |
| `POST /api/push/subscribe/` | Save OneSignal subscription id |
| `POST /api/events/<key>/` | Fire any trigger for current user |
| `GET/POST/DELETE /api/admin/triggers/` | Admin: triggers with nested templates |
| `POST/PATCH/DELETE /api/admin/templates/` | Admin: templates |
| `POST /api/admin/templates/<id>/toggle|test|sync/` | On/off, test send, WhatsApp status sync |
| `GET /api/admin/logs/` | Delivery logs |

Templates support `{{name}} {{username}} {{email}} {{order_id}}`. WhatsApp uses positional `{{1}}` mapped by "variable mappings" (e.g. `1=name`).

## 7. Deploy
**Render (backend):** New Web Service → root dir `backend`, build `./build.sh`, start `gunicorn config.wsgi:application`. Add a Postgres DB and set `DATABASE_URL`; set `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS=*`, `CORS_ALLOWED_ORIGINS=https://<your-vercel-app>.vercel.app`, plus all provider vars. Optional Cron Job: `python manage.py fire_inactive` daily.
**Vercel (frontend):** Import repo, root dir `frontend`, framework Vite, env `VITE_API_URL=https://<render-app>.onrender.com/api`, `VITE_ONESIGNAL_APP_ID`.

## 8. Task D – short answers
- **Trigger:** any event/condition that should send a notification – login, order placed, not logged in for 1 week, password reset.
- **Channels:** WhatsApp, Email, Web Push (browser).
- **Why admin panel:** one place for non-technical admins; the system talks to WhatsApp/Postmark/OneSignal for them, keeps templates, toggles and logs together.
- **Web Push:** browser pop-up notifications delivered to a subscribed browser, even when the site is closed.

Email provider used: set in `EMAIL_PROVIDER` (mention yours here).
