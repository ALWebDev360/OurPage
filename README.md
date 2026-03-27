# Elevated Solutions

A full-stack SaaS platform for web design, SEO auditing, and digital consulting services. Built with Flask + vanilla JS and deployed on Fly.io.

## Tech Stack

- **Backend:** Python 3.13, Flask, SQLite (WAL mode), Gunicorn
- **Frontend:** Bootstrap 5, vanilla JavaScript
- **Payments:** Stripe (one-time, subscriptions, deploy invoicing)
- **Domains:** Porkbun API (availability checks)
- **Email:** SMTP (async sending)
- **Deployment:** Fly.io, Docker

## Features

- **SEO Audit Tool** — Public page-analysis tool (meta tags, headings, links, images, performance)
- **Client Dashboard** — Consultations, payments, messages, deploy requests, coupon management
- **Admin Panel** — User management, availability scheduling, message inbox, coupon system, deploy requests, site configuration
- **Appointment Scheduler** — Configurable availability with blocked dates
- **Payment System** — One-time payments, monthly subscriptions, deploy invoicing with coupon discounts
- **Domain Checker** — Real-time domain availability via Porkbun
- **Preview Sites** — Authenticated preview hosting for client review
- **Contact Form** — Public form with email notification

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `STRIPE_SECRET_KEY` | `sk_test_REPLACE_ME` | Stripe secret API key |
| `STRIPE_PUBLISHABLE_KEY` | `pk_test_REPLACE_ME` | Stripe publishable key |
| `STRIPE_WEBHOOK_SECRET` | `whsec_REPLACE_ME` | Stripe webhook signing secret |
| `PORKBUN_API_KEY` | *(empty)* | Porkbun domain API key |
| `PORKBUN_SECRET_KEY` | *(empty)* | Porkbun domain secret key |
| `FRONTEND_URL` | `https://elevatedsolutions.design` | Base URL for email links |
| `DATA_DIR` | Script directory | Database storage path (`/data` on Fly.io) |
| `PORT` | `5000` | Server port (overridden to `8080` in Docker) |
| `FLASK_ENV` | `development` | `development` or `production` |

Additional settings (SMTP, API keys, ngrok URL) are configurable via the admin panel and stored in the `site_config` database table.

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python audit_server.py
```

The app starts at `http://localhost:5000`. SQLite database is created automatically on first run.

## Deployment (Fly.io)

```bash
# First deploy
fly launch

# Subsequent deploys
fly deploy
```

The app uses a persistent volume mounted at `/data` for the SQLite database. Gunicorn serves the app on port 8080 with 2 workers.

### Fly.io Config

- **App:** `elevatedsolutions-app`
- **Region:** `iad`
- **VM:** shared CPU, 1 GB RAM
- **Volume:** `data` → `/data` (persistent SQLite storage)
- **HTTPS:** forced via `fly.toml`

## Project Structure

```
audit_server.py          # Main Flask backend (~3600 lines)
index.html               # Landing page + auth + SEO audit tool
dashboard.html           # Client dashboard (SPA-style)
verify-email.html        # Email verification + password reset
assets/                  # CSS, JS, images, fonts
websitepreviews/         # Client preview sites
```

## API Overview

~75 endpoints organized into:

- **Public:** SEO audit, contact form, health check
- **Auth:** Signup, login, email verification, password reset
- **Client:** Dashboard, consultations, payments, messages, coupons, deploy requests
- **Admin:** Users, consultations, availability, messages, coupons, deploy requests, site config, preview sites
- **Stripe:** Webhook handler, payment status checks