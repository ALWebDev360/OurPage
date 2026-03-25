"""
Lightweight SEO Audit API server.
Comprehensive multi-factor SEO analysis inspired by SEOstats.
Uses extraction functions from seo-audits-toolkit + custom checks for
meta tags, performance, security, and technical SEO.
Also provides account creation and consultation scheduling.
"""

import sys
import os
import re
import json
import time
import uuid
import sqlite3
import subprocess
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, request, jsonify, g
from flask_cors import CORS

# Default TLD list (the TLDs we offer; prices come live from Porkbun)
DEFAULT_DOMAIN_TLDS = [
    {"tld": ".com", "price": 11.08},
    {"tld": ".net", "price": 12.52},
    {"tld": ".org", "price": 6.88},
    {"tld": ".io", "price": 51.80},
    {"tld": ".co", "price": 25.03},
    {"tld": ".dev", "price": 12.87},
    {"tld": ".app", "price": 14.93},
    {"tld": ".us", "price": 7.00},
    {"tld": ".biz", "price": 15.96},
    {"tld": ".info", "price": 22.14},
    {"tld": ".xyz", "price": 12.98},
    {"tld": ".online", "price": 28.84},
    {"tld": ".store", "price": 43.77},
    {"tld": ".tech", "price": 50.98},
    {"tld": ".site", "price": 28.84},
]

# ---- Porkbun live pricing cache ----
_porkbun_cache = {"data": None, "ts": 0}
PORKBUN_CACHE_TTL = 3600  # 1 hour

def get_porkbun_pricing():
    """Fetch TLD pricing from Porkbun API, cached for 1 hour."""
    now = time.time()
    if _porkbun_cache["data"] and now - _porkbun_cache["ts"] < PORKBUN_CACHE_TTL:
        return _porkbun_cache["data"]
    try:
        import urllib.request as _urlreq
        req = _urlreq.Request(
            "https://api.porkbun.com/api/json/v3/pricing/get",
            data=b'{}',
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with _urlreq.urlopen(req, timeout=30) as resp:
            pricing = json.loads(resp.read()).get("pricing", {})
        _porkbun_cache["data"] = pricing
        _porkbun_cache["ts"] = now
        return pricing
    except Exception:
        return _porkbun_cache["data"] or {}

# ---- Aftermarket domain detection & pricing ----
AFTERMARKET_NS_KEYWORDS = [
    "afternic.com", "sedoparking.com", "dan.com", "hugedomains.com",
    "parkingcrew.net", "bodis.com", "above.com", "uniregistry.com",
]

def get_rdap_nameservers(domain):
    """Query rdap.org to get nameservers for a domain."""
    try:
        import urllib.request as _urlreq
        req = _urlreq.Request(
            f"https://rdap.org/domain/{domain}",
            headers={"Accept": "application/rdap+json"},
        )
        with _urlreq.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        # Follow registrar RDAP link for detailed nameserver info
        for link in data.get("links", []):
            href = link.get("href", "")
            if "rdap" in href and href != f"https://rdap.org/domain/{domain}" and "type" in link and "rdap" in link["type"]:
                try:
                    req2 = _urlreq.Request(href, headers={"Accept": "application/rdap+json"})
                    with _urlreq.urlopen(req2, timeout=10) as resp2:
                        data = json.loads(resp2.read())
                except Exception:
                    pass
                break
        nameservers = []
        for ns in data.get("nameservers", []):
            nameservers.append(ns.get("ldhName", "").lower())
        return nameservers
    except Exception:
        return []

def is_aftermarket_ns(nameservers):
    """Check if nameservers suggest the domain is parked on an aftermarket platform."""
    for ns in nameservers:
        for kw in AFTERMARKET_NS_KEYWORDS:
            if kw in ns:
                return True
    return False

def get_aftermarket_price(domain):
    """Try to scrape aftermarket price from Afternic for-sale page."""
    try:
        import urllib.request as _urlreq
        req = _urlreq.Request(
            f"https://www.afternic.com/forsale/{domain}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with _urlreq.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        # Prefer buyNowPrice (actual listing price), fall back to minPrice (minimum offer)
        buy_now_enabled = '"buyNowEnabled":true' in html or '"buyNowEnabled": true' in html
        m_buy = re.search(r'"buyNowPrice"\s*:\s*(\d+)', html)
        m_min = re.search(r'"minPrice"\s*:\s*(\d+)', html)
        price = None
        if buy_now_enabled and m_buy:
            price = int(m_buy.group(1))
        elif m_min:
            price = int(m_min.group(1))
        if price and price > 0:
            return {
                "price": price,
                "buy_now": buy_now_enabled,
                "make_offer": '"makeOfferEnabled":true' in html or '"makeOfferEnabled": true' in html,
                "leasing": '"leasingEnabled":true' in html or '"leasingEnabled": true' in html,
            }
    except Exception:
        pass
    return None

# ---- Porkbun Domain Check API ----
def get_porkbun_keys():
    """Get Porkbun API keys from DB (site_config) or env vars."""
    try:
        db = get_db()
        row_api = db.execute("SELECT value FROM site_config WHERE key = 'porkbun_api_key'").fetchone()
        row_sec = db.execute("SELECT value FROM site_config WHERE key = 'porkbun_secret_key'").fetchone()
        apikey = row_api["value"] if row_api else ""
        secret = row_sec["value"] if row_sec else ""
        if apikey and secret:
            return {"apikey": apikey, "secretapikey": secret}
    except Exception:
        pass
    return {"apikey": PORKBUN_API_KEY, "secretapikey": PORKBUN_SECRET_KEY}


def get_stripe_keys():
    """Get Stripe keys from DB (site_config) first, fall back to env vars."""
    try:
        db = get_db()
        row_sk = db.execute("SELECT value FROM site_config WHERE key = 'stripe_secret_key'").fetchone()
        row_pk = db.execute("SELECT value FROM site_config WHERE key = 'stripe_publishable_key'").fetchone()
        row_wh = db.execute("SELECT value FROM site_config WHERE key = 'stripe_webhook_secret'").fetchone()
        sk = row_sk["value"] if row_sk else ""
        pk = row_pk["value"] if row_pk else ""
        wh = row_wh["value"] if row_wh else ""
        if sk and pk:
            return {"secret_key": sk, "publishable_key": pk, "webhook_secret": wh or ""}
    except Exception:
        pass
    return {"secret_key": STRIPE_SECRET_KEY, "publishable_key": STRIPE_PUBLISHABLE_KEY, "webhook_secret": STRIPE_WEBHOOK_SECRET}


def configure_stripe():
    """Ensure stripe.api_key is set from the best available source."""
    keys = get_stripe_keys()
    stripe.api_key = keys["secret_key"]
    return keys


def get_ngrok_url():
    """Get ngrok tunnel URL from site_config if set."""
    try:
        db = get_db()
        row = db.execute("SELECT value FROM site_config WHERE key = 'ngrok_url'").fetchone()
        if row and row["value"]:
            return row["value"].rstrip("/")
    except Exception:
        pass
    return None


def get_email_config():
    """Get SMTP email config from site_config."""
    try:
        db = get_db()
        keys = ['smtp_host', 'smtp_port', 'smtp_user', 'smtp_pass', 'smtp_from_name', 'smtp_from_email']
        cfg = {}
        for k in keys:
            row = db.execute("SELECT value FROM site_config WHERE key = ?", (k,)).fetchone()
            cfg[k] = row["value"] if row else ""
        if cfg['smtp_host'] and cfg['smtp_user'] and cfg['smtp_pass']:
            return cfg
    except Exception:
        pass
    return None


def send_email(to_email, subject, html_body, text_body=None):
    """Send an email via SMTP. Returns True on success, error string on failure."""
    cfg = get_email_config()
    if not cfg:
        return "Email not configured"
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{cfg['smtp_from_name']} <{cfg['smtp_from_email']}>" if cfg['smtp_from_name'] else cfg['smtp_from_email'] or cfg['smtp_user']
        msg["To"] = to_email
        msg["Subject"] = subject
        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
        port = int(cfg['smtp_port'] or 587)
        if port == 465:
            server = smtplib.SMTP_SSL(cfg['smtp_host'], port, timeout=30)
        else:
            server = smtplib.SMTP(cfg['smtp_host'], port, timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()
        server.login(cfg['smtp_user'], cfg['smtp_pass'])
        sender = cfg['smtp_from_email'] or cfg['smtp_user']
        server.sendmail(sender, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"[send_email] Error: {e}")
        return str(e)


def send_email_async(to_email, subject, html_body, text_body=None):
    """Fire-and-forget email send in a background thread. Never blocks the caller."""
    t = threading.Thread(target=send_email, args=(to_email, subject, html_body, text_body), daemon=True)
    t.start()


def get_frontend_url():
    """Return ngrok URL if configured, otherwise FRONTEND_URL."""
    ngrok = get_ngrok_url()
    return ngrok if ngrok else FRONTEND_URL


def check_domain_porkbun(domain, apikey, secretkey):
    """Check single domain availability via Porkbun checkDomain API.
    Returns dict with avail, price, premium, etc. or None on failure."""
    if not apikey or not secretkey:
        return None
    try:
        import urllib.request as _urlreq
        payload = json.dumps({"secretapikey": secretkey, "apikey": apikey})
        req = _urlreq.Request(
            f"https://api.porkbun.com/api/json/v3/domain/checkDomain/{domain}",
            data=payload.encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with _urlreq.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        if data.get("status") == "SUCCESS":
            r = data.get("response", data)
            return {
                "avail": r.get("avail") == "yes",
                "price": float(r.get("price", 0)),
                "regular_price": float(r.get("regularPrice", 0)),
                "first_year_promo": r.get("firstYearPromo") == "yes",
                "premium": r.get("premium") == "yes",
                "type": r.get("type", ""),
                "renewal": float((r.get("additional") or {}).get("renewal", {}).get("price", 0)),
                "transfer": float((r.get("additional") or {}).get("transfer", {}).get("price", 0)),
            }
        return None
    except Exception:
        return None

from werkzeug.security import generate_password_hash, check_password_hash
import requests as http_requests
from bs4 import BeautifulSoup
import stripe

# Add the toolkit's server directory to the path so we can import its modules
TOOLKIT_PATH = os.path.join(os.path.dirname(__file__), "seo-audits-toolkit", "server")
sys.path.insert(0, TOOLKIT_PATH)

from extractor.src.headers import find_all_headers_url
from extractor.src.images import find_all_images
from extractor.src.links import find_all_links

app = Flask(__name__)
CORS(app, origins=["http://localhost:*", "http://127.0.0.1:*", "https://*.ngrok-free.app", "https://*.ngrok.io", "null"])

# --- Stripe Configuration ---
# Set these to your Stripe keys (use env vars in production)
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_REPLACE_ME")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "pk_test_REPLACE_ME")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_REPLACE_ME")
STRIPE_CURRENCY = "usd"
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://127.0.0.1:8080")
stripe.api_key = STRIPE_SECRET_KEY

# --- Porkbun API Configuration ---
PORKBUN_API_KEY = os.environ.get("PORKBUN_API_KEY", "")
PORKBUN_SECRET_KEY = os.environ.get("PORKBUN_SECRET_KEY", "")

# --- Database Setup ---
DB_PATH = os.path.join(os.path.dirname(__file__), "elevatedsolutions.db")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            company TEXT DEFAULT '',
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'client',
            payment_portal INTEGER DEFAULT 0,
            demo_preview INTEGER DEFAULT 0,
            demo_preview_site TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS auth_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS consultations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            duration INTEGER DEFAULT 30,
            type TEXT DEFAULT 'general',
            notes TEXT DEFAULT '',
            status TEXT DEFAULT 'scheduled',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_of_week INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            slot_duration INTEGER DEFAULT 30,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS blocked_dates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            reason TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            paid_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS payment_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            onetime_amount REAL DEFAULT 0,
            monthly_amount REAL DEFAULT 0,
            onetime_paid INTEGER DEFAULT 0,
            onetime_paid_at TEXT,
            monthly_active INTEGER DEFAULT 0,
            monthly_started_at TEXT,
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            stripe_onetime_session_id TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS deploy_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            base_fee REAL DEFAULT 499,
            monthly_maintenance REAL DEFAULT 49,
            tax_rate REAL DEFAULT 8.25,
            addons TEXT DEFAULT '[]',
            domain_tlds TEXT DEFAULT '[]',
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS deploy_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            domain TEXT NOT NULL,
            selected_addons TEXT DEFAULT '[]',
            subtotal REAL DEFAULT 0,
            tax REAL DEFAULT 0,
            total REAL DEFAULT 0,
            monthly REAL DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT DEFAULT '',
            body TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            is_read INTEGER DEFAULT 0,
            admin_reply TEXT DEFAULT '',
            replied_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS site_config (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE COLLATE NOCASE,
            discount_type TEXT DEFAULT 'percent',
            discount_value REAL DEFAULT 0,
            max_uses INTEGER DEFAULT 0,
            times_used INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            free_first_month INTEGER DEFAULT 0,
            expires_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    # Add free_first_month to coupons if upgrading
    try:
        db.execute("ALTER TABLE coupons ADD COLUMN free_first_month INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    # Add role column if upgrading from older schema
    try:
        db.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'client'")
    except sqlite3.OperationalError:
        pass  # column already exists
    # Add duration column if upgrading
    try:
        db.execute("ALTER TABLE consultations ADD COLUMN duration INTEGER DEFAULT 30")
    except sqlite3.OperationalError:
        pass
    # Add payment_portal column if upgrading
    try:
        db.execute("ALTER TABLE users ADD COLUMN payment_portal INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    # Add demo_preview column if upgrading
    try:
        db.execute("ALTER TABLE users ADD COLUMN demo_preview INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    # Add demo_preview_site column if upgrading
    try:
        db.execute("ALTER TABLE users ADD COLUMN demo_preview_site TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    # Add domain_tlds column to deploy_config if upgrading
    try:
        db.execute("ALTER TABLE deploy_config ADD COLUMN domain_tlds TEXT DEFAULT '[]'")
    except sqlite3.OperationalError:
        pass
    # Add stripe_session_id and stripe_subscription_id to deploy_requests if upgrading
    for col in ["stripe_session_id TEXT DEFAULT ''", "stripe_subscription_id TEXT DEFAULT ''", "coupon_code TEXT DEFAULT ''", "discount REAL DEFAULT 0"]:
        try:
            db.execute(f"ALTER TABLE deploy_requests ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    # Add Stripe columns to payment_config if upgrading
    for col in ["stripe_customer_id TEXT", "stripe_subscription_id TEXT", "stripe_onetime_session_id TEXT"]:
        try:
            db.execute(f"ALTER TABLE payment_config ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    # Seed default availability (Mon-Fri, 9AM-5PM, 30-min slots)
    existing_avail = db.execute("SELECT COUNT(*) FROM availability").fetchone()[0]
    if existing_avail == 0:
        for dow in range(0, 5):  # 0=Monday .. 4=Friday
            db.execute(
                "INSERT INTO availability (day_of_week, start_time, end_time, slot_duration) VALUES (?, ?, ?, ?)",
                (dow, "09:00", "17:00", 30)
            )
        db.commit()
    # Seed default admin account
    existing = db.execute("SELECT id FROM users WHERE email = 'admin@elevatedsolutions.com'").fetchone()
    if not existing:
        from werkzeug.security import generate_password_hash
        db.execute(
            "INSERT INTO users (name, email, company, password_hash, role) VALUES (?, ?, ?, ?, ?)",
            ("Admin", "admin@elevatedsolutions.com", "Elevated Solutions",
             generate_password_hash("Admin123!"), "admin")
        )
        db.commit()
    db.close()


init_db()


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authentication required"}), 401
        token = auth_header[7:]
        db = get_db()
        row = db.execute(
            "SELECT u.id, u.name, u.email, u.company, u.role, u.payment_portal, u.demo_preview, u.demo_preview_site FROM users u "
            "JOIN auth_tokens t ON t.user_id = u.id WHERE t.token = ?",
            (token,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Invalid or expired token"}), 401
        g.current_user = dict(row)
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        if g.current_user.get("role") != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated

# --- URL validation ---
ALLOWED_SCHEMES = {"http", "https"}
URL_REGEX = re.compile(
    r"^https?://"
    r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,}"
    r"(?::\d{1,5})?"
    r"(?:/[^\s]*)?$"
)


def is_valid_url(url: str) -> bool:
    """Validate URL format and scheme to prevent SSRF."""
    if not url or len(url) > 2048:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False
    if not parsed.hostname:
        return False
    # Block private/internal IPs
    hostname = parsed.hostname.lower()
    blocked = ["localhost", "127.0.0.1", "0.0.0.0", "::1", "169.254.169.254"]
    if hostname in blocked or hostname.startswith("10.") or hostname.startswith("192.168."):
        return False
    return bool(URL_REGEX.match(url))


def fetch_page(url, timeout=10):
    """Fetch a page and return (response, soup, elapsed_ms) or raise."""
    start = time.time()
    resp = http_requests.get(url, timeout=timeout, headers={
        "User-Agent": "Mozilla/5.0 (compatible; ElevatedSEOAudit/1.0)"
    }, allow_redirects=True)
    elapsed_ms = round((time.time() - start) * 1000)
    soup = BeautifulSoup(resp.text, "lxml")
    return resp, soup, elapsed_ms


# ── Meta Tags Analysis ──────────────────────────────────────────
def analyze_meta(soup, url):
    """Analyze title, description, Open Graph, Twitter Cards, canonical, viewport."""
    result = {}

    # Title
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    result["title"] = {
        "value": title,
        "length": len(title),
        "present": bool(title),
        "optimal_length": 30 <= len(title) <= 60
    }

    # Meta description
    desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    desc = desc_tag.get("content", "").strip() if desc_tag else ""
    result["description"] = {
        "value": desc,
        "length": len(desc),
        "present": bool(desc),
        "optimal_length": 120 <= len(desc) <= 160
    }

    # Viewport
    vp = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
    result["viewport"] = {
        "present": vp is not None,
        "content": vp.get("content", "") if vp else ""
    }

    # Canonical
    canon = soup.find("link", attrs={"rel": "canonical"})
    result["canonical"] = {
        "present": canon is not None,
        "href": canon.get("href", "") if canon else ""
    }

    # Language
    html_tag = soup.find("html")
    lang = html_tag.get("lang", "") if html_tag else ""
    result["language"] = {"present": bool(lang), "value": lang}

    # Open Graph
    og_tags = {}
    for meta in soup.find_all("meta", attrs={"property": re.compile(r"^og:", re.I)}):
        og_tags[meta.get("property", "")] = meta.get("content", "")
    result["open_graph"] = {
        "present": len(og_tags) > 0,
        "tags_found": len(og_tags),
        "has_title": "og:title" in og_tags,
        "has_description": "og:description" in og_tags,
        "has_image": "og:image" in og_tags,
        "has_url": "og:url" in og_tags,
    }

    # Twitter Cards
    tw_tags = {}
    for meta in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:", re.I)}):
        tw_tags[meta.get("name", "")] = meta.get("content", "")
    result["twitter_card"] = {
        "present": len(tw_tags) > 0,
        "tags_found": len(tw_tags),
        "has_card": "twitter:card" in tw_tags,
        "has_title": "twitter:title" in tw_tags,
        "has_description": "twitter:description" in tw_tags,
    }

    # Robots meta
    robots = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    result["robots"] = {
        "present": robots is not None,
        "content": robots.get("content", "") if robots else "",
        "noindex": "noindex" in (robots.get("content", "") if robots else "").lower()
    }

    return result


# ── Performance Analysis ────────────────────────────────────────
def analyze_performance(resp, elapsed_ms):
    """Analyze page load time, size, compression, caching."""
    page_size = len(resp.content)
    headers = resp.headers

    return {
        "response_time_ms": elapsed_ms,
        "page_size_bytes": page_size,
        "page_size_kb": round(page_size / 1024, 1),
        "compressed": "gzip" in headers.get("Content-Encoding", "").lower()
                      or "br" in headers.get("Content-Encoding", "").lower(),
        "http_version": None,
        "status_code": resp.status_code,
        "redirect_count": len(resp.history),
        "caching": {
            "cache_control": headers.get("Cache-Control", ""),
            "etag": bool(headers.get("ETag")),
            "expires": headers.get("Expires", ""),
            "has_caching": bool(headers.get("Cache-Control") or headers.get("ETag") or headers.get("Expires"))
        }
    }


# ── Security Analysis ──────────────────────────────────────────
def analyze_security(resp, url):
    """Check HTTPS, security headers, and cookie flags."""
    headers = resp.headers
    parsed = urlparse(url)

    sec_headers = {
        "Strict-Transport-Security": headers.get("Strict-Transport-Security", ""),
        "Content-Security-Policy": headers.get("Content-Security-Policy", ""),
        "X-Content-Type-Options": headers.get("X-Content-Type-Options", ""),
        "X-Frame-Options": headers.get("X-Frame-Options", ""),
        "X-XSS-Protection": headers.get("X-XSS-Protection", ""),
        "Referrer-Policy": headers.get("Referrer-Policy", ""),
        "Permissions-Policy": headers.get("Permissions-Policy", ""),
    }
    present_count = sum(1 for v in sec_headers.values() if v)

    return {
        "https": parsed.scheme == "https",
        "headers": sec_headers,
        "headers_present": present_count,
        "headers_total": len(sec_headers),
    }


# ── Technical SEO Analysis ─────────────────────────────────────
def analyze_technical(soup, url, resp):
    """Check robots.txt, sitemap.xml, structured data, charset, doctype."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    # robots.txt
    robots_ok = False
    try:
        r = http_requests.get(urljoin(base, "/robots.txt"), timeout=5, headers={
            "User-Agent": "Mozilla/5.0 (compatible; ElevatedSEOAudit/1.0)"
        })
        robots_ok = r.status_code == 200 and len(r.text.strip()) > 0
    except Exception:
        pass

    # sitemap.xml
    sitemap_ok = False
    try:
        r = http_requests.get(urljoin(base, "/sitemap.xml"), timeout=5, headers={
            "User-Agent": "Mozilla/5.0 (compatible; ElevatedSEOAudit/1.0)"
        })
        sitemap_ok = r.status_code == 200 and ("<?xml" in r.text[:100] or "<urlset" in r.text[:500])
    except Exception:
        pass

    # Structured data (JSON-LD)
    json_ld = soup.find_all("script", attrs={"type": "application/ld+json"})

    # Charset
    charset_meta = soup.find("meta", attrs={"charset": True})
    charset = charset_meta.get("charset", "") if charset_meta else ""

    # Doctype
    raw = resp.text[:100].strip().lower()
    has_doctype = raw.startswith("<!doctype")

    # Favicon
    favicon = soup.find("link", attrs={"rel": re.compile(r"icon", re.I)})

    return {
        "robots_txt": robots_ok,
        "sitemap_xml": sitemap_ok,
        "structured_data": {
            "json_ld_count": len(json_ld),
            "present": len(json_ld) > 0
        },
        "charset": {"present": bool(charset), "value": charset},
        "doctype": has_doctype,
        "favicon": favicon is not None,
    }


# ── Score Calculation ──────────────────────────────────────────
def calculate_score(results):
    """Calculate 0-100 score from all audit categories."""
    breakdown = {}

    # ── Meta Tags (max 25) ──
    meta = results.get("meta")
    m_pts = 0
    if meta and "error" not in meta:
        if meta["title"]["present"]:
            m_pts += 4
        if meta["title"]["optimal_length"]:
            m_pts += 2
        if meta["description"]["present"]:
            m_pts += 4
        if meta["description"]["optimal_length"]:
            m_pts += 2
        if meta["viewport"]["present"]:
            m_pts += 3
        if meta["canonical"]["present"]:
            m_pts += 2
        if meta["language"]["present"]:
            m_pts += 2
        if meta["open_graph"]["present"]:
            m_pts += 2
        if meta["open_graph"].get("has_image"):
            m_pts += 1
        if meta["twitter_card"]["present"]:
            m_pts += 2
        if not meta["robots"]["noindex"]:
            m_pts += 1
    breakdown["meta"] = min(m_pts, 25)

    # ── Performance (max 15) ──
    perf = results.get("performance")
    p_pts = 0
    if perf and "error" not in perf:
        rt = perf["response_time_ms"]
        if rt < 500:
            p_pts += 5
        elif rt < 1500:
            p_pts += 3
        elif rt < 3000:
            p_pts += 1

        size_kb = perf["page_size_kb"]
        if size_kb < 200:
            p_pts += 4
        elif size_kb < 500:
            p_pts += 2
        elif size_kb < 1000:
            p_pts += 1

        if perf["compressed"]:
            p_pts += 3
        if perf["caching"]["has_caching"]:
            p_pts += 3
    breakdown["performance"] = min(p_pts, 15)

    # ── Security (max 15) ──
    sec = results.get("security")
    s_pts = 0
    if sec and "error" not in sec:
        if sec["https"]:
            s_pts += 6
        present = sec["headers_present"]
        s_pts += min(present, 7)  # up to 7 security headers = 7 pts
        if sec["headers"].get("Strict-Transport-Security"):
            s_pts += 2
    breakdown["security"] = min(s_pts, 15)

    # ── Technical SEO (max 15) ──
    tech = results.get("technical")
    t_pts = 0
    if tech and "error" not in tech:
        if tech["robots_txt"]:
            t_pts += 3
        if tech["sitemap_xml"]:
            t_pts += 3
        if tech["structured_data"]["present"]:
            t_pts += 3
        if tech["charset"]["present"]:
            t_pts += 2
        if tech["doctype"]:
            t_pts += 2
        if tech["favicon"]:
            t_pts += 2
    breakdown["technical"] = min(t_pts, 15)

    # ── Headings (max 10) ──
    h = results.get("headers")
    h_pts = 0
    if h and not isinstance(h, str) and "error" not in h:
        h1 = h.get("h1", {}).get("count", 0)
        h2 = h.get("h2", {}).get("count", 0)
        if h1 == 1:
            h_pts += 5
        elif h1 > 1:
            h_pts += 2
        if h2 >= 1:
            h_pts += 3
        total_h = sum(h.get(t, {}).get("count", 0) for t in ["h1","h2","h3","h4","h5","h6"])
        if total_h >= 3:
            h_pts += 2
    breakdown["headings"] = min(h_pts, 10)

    # ── Images (max 10) ──
    img = results.get("images")
    i_pts = 0
    if img and not isinstance(img, str) and "error" not in img:
        summary = img.get("summary", {})
        total = summary.get("total", 0)
        missing_alt = summary.get("missing_alt", 0)
        if total == 0:
            i_pts = 6
        else:
            alt_ratio = (total - missing_alt) / total
            i_pts += round(alt_ratio * 7)
            i_pts += 3  # having images
    breakdown["images"] = min(i_pts, 10)

    # ── Links (max 10) ──
    lnk = results.get("links")
    l_pts = 0
    if lnk and not isinstance(lnk, str) and "error" not in lnk:
        total_links = 0
        broken_links = 0
        for code, urls in lnk.items():
            count = len(urls) if isinstance(urls, list) else 0
            total_links += count
            if int(code) >= 400:
                broken_links += count
        if total_links == 0:
            l_pts = 4
        else:
            healthy_ratio = (total_links - broken_links) / total_links
            l_pts += round(healthy_ratio * 7)
            if broken_links == 0:
                l_pts += 3
    breakdown["links"] = min(l_pts, 10)

    total = sum(breakdown.values())
    total = min(total, 100)

    return {
        "total": total,
        "max": 100,
        "breakdown": breakdown,
        "grade": (
            "A" if total >= 90 else
            "B" if total >= 75 else
            "C" if total >= 60 else
            "D" if total >= 40 else "F"
        )
    }


@app.route("/api/audit", methods=["POST"])
def audit():
    """Run SEO audit on a given URL and return combined results."""
    data = request.get_json(silent=True)
    if not data or "url" not in data:
        return jsonify({"error": "Missing 'url' in request body"}), 400

    url = data["url"].strip()

    # Strip trailing slashes for consistency, then ensure URL has a scheme
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    if not is_valid_url(url):
        return jsonify({"error": "Invalid URL. Please provide a valid public website URL."}), 400

    results = {"url": url}

    # --- Fetch page once for meta/performance/security/technical ---
    try:
        resp, soup, elapsed_ms = fetch_page(url)
    except Exception as e:
        return jsonify({"error": f"Could not fetch URL: {e}"}), 400

    # --- Meta Tags ---
    try:
        results["meta"] = analyze_meta(soup, url)
    except Exception as e:
        results["meta"] = {"error": str(e)}

    # --- Performance ---
    try:
        results["performance"] = analyze_performance(resp, elapsed_ms)
    except Exception as e:
        results["performance"] = {"error": str(e)}

    # --- Security ---
    try:
        results["security"] = analyze_security(resp, url)
    except Exception as e:
        results["security"] = {"error": str(e)}

    # --- Technical SEO ---
    try:
        results["technical"] = analyze_technical(soup, url, resp)
    except Exception as e:
        results["technical"] = {"error": str(e)}

    # --- Headers audit ---
    try:
        results["headers"] = find_all_headers_url(url)
    except Exception as e:
        results["headers"] = {"error": str(e)}

    # --- Images audit ---
    try:
        results["images"] = find_all_images(url)
    except Exception as e:
        results["images"] = {"error": str(e)}

    # --- Links audit ---
    try:
        results["links"] = find_all_links(url)
    except Exception as e:
        results["links"] = {"error": str(e)}

    # --- Calculate overall score ---
    results["score"] = calculate_score(results)

    return jsonify(results)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# ── Account Endpoints ──────────────────────────────────────────

@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    company = (data.get("company") or "").strip()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required"}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"error": "Invalid email address"}), 400

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        return jsonify({"error": "An account with this email already exists"}), 409

    password_hash = generate_password_hash(password)
    cursor = db.execute(
        "INSERT INTO users (name, email, company, password_hash) VALUES (?, ?, ?, ?)",
        (name, email, company, password_hash)
    )
    db.commit()
    user_id = cursor.lastrowid

    token = uuid.uuid4().hex
    db.execute("INSERT INTO auth_tokens (token, user_id) VALUES (?, ?)", (token, user_id))
    db.commit()

    # Send welcome email (async-ish, don't block signup on email failure)
    try:
        site_url = get_frontend_url()
        welcome_html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:30px 20px;">
            <div style="text-align:center;margin-bottom:30px;">
                <h1 style="color:#1e3c72;margin:0;">Welcome to Elevated Solutions</h1>
                <div style="width:60px;height:3px;background:linear-gradient(90deg,#1e3c72,#ff5959);margin:12px auto;"></div>
            </div>
            <p style="font-size:16px;color:#333;">Hi <strong>{name}</strong>,</p>
            <p style="font-size:15px;color:#555;line-height:1.7;">Thank you for creating an account with Elevated Solutions! We're excited to have you on board.</p>
            <p style="font-size:15px;color:#555;line-height:1.7;">From your dashboard you can:</p>
            <ul style="font-size:14px;color:#555;line-height:2;">
                <li>Schedule a free consultation with our team</li>
                <li>Preview your custom website demo</li>
                <li>Deploy your site with a custom domain</li>
                <li>Manage your account and billing</li>
            </ul>
            <div style="text-align:center;margin:30px 0;">
                <a href="{site_url}/dashboard.html" style="background:linear-gradient(135deg,#1e3c72,#2a5298);color:#fff;padding:14px 36px;border-radius:10px;text-decoration:none;font-weight:600;font-size:15px;display:inline-block;">Go to Your Dashboard</a>
            </div>
            <p style="font-size:14px;color:#888;line-height:1.6;">If you have any questions, feel free to reply to this email or reach out through your dashboard.</p>
            <hr style="border:none;border-top:1px solid #eee;margin:30px 0;">
            <p style="font-size:12px;color:#aaa;text-align:center;">Elevated Solutions &mdash; Web Design & Development</p>
        </div>
        """
        result = send_email_async(email, "Welcome to Elevated Solutions!", welcome_html,
                           f"Hi {name},\n\nWelcome to Elevated Solutions! Visit your dashboard at {site_url}/dashboard.html\n\nThank you for signing up!")
        if result is not True:
            print(f"[signup] Welcome email queued for {email}")
    except Exception as e:
        print(f"[signup] Welcome email error: {e}")

    return jsonify({
        "message": "Account created successfully",
        "token": token,
        "user": {"id": user_id, "name": name, "email": email, "company": company}
    }), 201


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401

    token = uuid.uuid4().hex
    db.execute("INSERT INTO auth_tokens (token, user_id) VALUES (?, ?)", (token, user["id"]))
    db.commit()

    return jsonify({
        "token": token,
        "user": {"id": user["id"], "name": user["name"], "email": user["email"], "company": user["company"], "payment_portal": user["payment_portal"]}
    })


@app.route("/api/me", methods=["GET"])
@require_auth
def get_me():
    user_data = dict(g.current_user)
    site = user_data.get("demo_preview_site", "")
    if site:
        user_data["demo_has_dist"] = os.path.isfile(os.path.join(PREVIEWS_DIR, site, "dist", "index.html"))
    return jsonify({"user": user_data})


@app.route("/api/me", methods=["PUT"])
@require_auth
def update_me():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    company = (data.get("company") or "").strip()
    if not name or len(name) < 2:
        return jsonify({"error": "Name must be at least 2 characters"}), 400
    if len(name) > 100:
        name = name[:100]
    if len(company) > 100:
        company = company[:100]
    db = get_db()
    db.execute("UPDATE users SET name=?, company=? WHERE id=?",
               (name, company, g.current_user["id"]))
    db.commit()
    g.current_user["name"] = name
    g.current_user["company"] = company
    return jsonify({"message": "Profile updated", "user": g.current_user})


@app.route("/api/me/password", methods=["PUT"])
@require_auth
def change_password():
    data = request.get_json(silent=True) or {}
    current_pw = data.get("current_password", "")
    new_pw = data.get("new_password", "")
    if not current_pw or not new_pw:
        return jsonify({"error": "Current and new password required"}), 400
    if len(new_pw) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400
    db = get_db()
    row = db.execute("SELECT password_hash FROM users WHERE id=?", (g.current_user["id"],)).fetchone()
    if not check_password_hash(row["password_hash"], current_pw):
        return jsonify({"error": "Current password is incorrect"}), 403
    db.execute("UPDATE users SET password_hash=? WHERE id=?",
               (generate_password_hash(new_pw), g.current_user["id"]))
    db.commit()
    return jsonify({"message": "Password changed successfully"})


@app.route("/api/me/dashboard", methods=["GET"])
@require_auth
def client_dashboard():
    db = get_db()
    uid = g.current_user["id"]
    total = db.execute("SELECT COUNT(*) FROM consultations WHERE user_id=?", (uid,)).fetchone()[0]
    scheduled = db.execute("SELECT COUNT(*) FROM consultations WHERE user_id=? AND status='scheduled'", (uid,)).fetchone()[0]
    completed = db.execute("SELECT COUNT(*) FROM consultations WHERE user_id=? AND status='completed'", (uid,)).fetchone()[0]
    cancelled = db.execute("SELECT COUNT(*) FROM consultations WHERE user_id=? AND status='cancelled'", (uid,)).fetchone()[0]
    upcoming = db.execute(
        "SELECT id, date, time, duration, type, notes, status, created_at FROM consultations "
        "WHERE user_id=? AND status='scheduled' AND date >= date('now') ORDER BY date ASC, time ASC LIMIT 5",
        (uid,)
    ).fetchall()
    past = db.execute(
        "SELECT id, date, time, duration, type, notes, status, created_at FROM consultations "
        "WHERE user_id=? AND (status!='scheduled' OR date < date('now')) ORDER BY date DESC LIMIT 10",
        (uid,)
    ).fetchall()
    return jsonify({
        "stats": {"total": total, "scheduled": scheduled, "completed": completed, "cancelled": cancelled},
        "upcoming": [dict(r) for r in upcoming],
        "past": [dict(r) for r in past]
    })


# ── Appointment Scheduler Endpoints ────────────────────────────

CONSULTATION_TYPES = ["general", "website", "seo", "automation", "strategy"]
DAYS_AHEAD_LIMIT = 60  # How far ahead clients can book


def get_available_slots(date_str):
    """Get available time slots for a given date, considering availability rules and existing bookings."""
    db = get_db()
    target_date = datetime.strptime(date_str, "%Y-%m-%d")
    dow = target_date.weekday()  # 0=Monday

    # Check if date is blocked
    blocked = db.execute("SELECT id FROM blocked_dates WHERE date = ?", (date_str,)).fetchone()
    if blocked:
        return []

    # Get availability for this day of week
    avail = db.execute(
        "SELECT start_time, end_time, slot_duration FROM availability WHERE day_of_week = ? AND is_active = 1",
        (dow,)
    ).fetchone()
    if not avail:
        return []

    start_h, start_m = map(int, avail["start_time"].split(":"))
    end_h, end_m = map(int, avail["end_time"].split(":"))
    duration = avail["slot_duration"]

    # Generate all possible slots
    slots = []
    current = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m
    while current + duration <= end_minutes:
        slot_time = f"{current // 60:02d}:{current % 60:02d}"
        slots.append(slot_time)
        current += duration

    # Remove already-booked slots
    booked = db.execute(
        "SELECT time, duration FROM consultations WHERE date = ? AND status != 'cancelled'",
        (date_str,)
    ).fetchall()
    booked_ranges = set()
    for b in booked:
        bh, bm = map(int, b["time"].split(":"))
        b_start = bh * 60 + bm
        b_dur = b["duration"] or 30
        for m in range(b_start, b_start + b_dur, duration):
            booked_ranges.add(f"{m // 60:02d}:{m % 60:02d}")

    available = [s for s in slots if s not in booked_ranges]
    return available


@app.route("/api/scheduler/available-dates", methods=["GET"])
@require_auth
def get_available_dates():
    """Return dates in the next N days that have available slots."""
    db = get_db()
    today = datetime.now().date()
    dates = []
    for i in range(1, DAYS_AHEAD_LIMIT + 1):
        d = today + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        dow = d.weekday()
        # Check if this day has availability configured
        avail = db.execute(
            "SELECT id FROM availability WHERE day_of_week = ? AND is_active = 1", (dow,)
        ).fetchone()
        if not avail:
            continue
        # Check if blocked
        blocked = db.execute("SELECT id FROM blocked_dates WHERE date = ?", (date_str,)).fetchone()
        if blocked:
            continue
        dates.append({"date": date_str, "day": d.strftime("%A"), "formatted": d.strftime("%b %d, %Y")})
    return jsonify({"dates": dates})


@app.route("/api/scheduler/slots", methods=["GET"])
@require_auth
def get_slots():
    """Return available time slots for a specific date."""
    date_str = request.args.get("date", "").strip()
    if not date_str:
        return jsonify({"error": "Date parameter required"}), 400
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d")
        if target.date() <= datetime.now().date():
            return jsonify({"error": "Date must be in the future"}), 400
        if (target.date() - datetime.now().date()).days > DAYS_AHEAD_LIMIT:
            return jsonify({"error": f"Cannot book more than {DAYS_AHEAD_LIMIT} days ahead"}), 400
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    slots = get_available_slots(date_str)
    # Format for display
    formatted = []
    for s in slots:
        h, m = map(int, s.split(":"))
        ampm = "AM" if h < 12 else "PM"
        h12 = h if h <= 12 else h - 12
        if h12 == 0:
            h12 = 12
        formatted.append({"value": s, "label": f"{h12}:{m:02d} {ampm}"})
    return jsonify({"date": date_str, "slots": formatted})


@app.route("/api/consultations", methods=["POST"])
@require_auth
def create_consultation():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    date_str = (data.get("date") or "").strip()
    time_str = (data.get("time") or "").strip()
    consult_type = (data.get("type") or "general").strip().lower()
    notes = (data.get("notes") or "").strip()

    if not date_str or not time_str:
        return jsonify({"error": "Date and time are required"}), 400

    # Validate date
    try:
        consult_date = datetime.strptime(date_str, "%Y-%m-%d")
        if consult_date.date() <= datetime.now().date():
            return jsonify({"error": "Date must be in the future"}), 400
        if (consult_date.date() - datetime.now().date()).days > DAYS_AHEAD_LIMIT:
            return jsonify({"error": f"Cannot book more than {DAYS_AHEAD_LIMIT} days ahead"}), 400
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    # Validate time format
    if not re.match(r"^\d{2}:\d{2}$", time_str):
        return jsonify({"error": "Invalid time format. Use HH:MM"}), 400

    # Check slot is actually available
    available = get_available_slots(date_str)
    if time_str not in available:
        return jsonify({"error": "This time slot is no longer available. Please choose another."}), 409

    if consult_type not in CONSULTATION_TYPES:
        consult_type = "general"

    if len(notes) > 1000:
        notes = notes[:1000]

    db = get_db()
    cursor = db.execute(
        "INSERT INTO consultations (user_id, date, time, duration, type, notes) VALUES (?, ?, ?, 30, ?, ?)",
        (g.current_user["id"], date_str, time_str, consult_type, notes)
    )
    db.commit()

    # Send consultation confirmation email
    try:
        user_email = g.current_user.get("email", "")
        user_name = g.current_user.get("name") or g.current_user.get("first_name") or user_email.split("@")[0]
        type_labels = {"general": "General Consultation", "website": "Website Development", "seo": "SEO Strategy", "automation": "Automation", "strategy": "Business Strategy"}
        type_label = type_labels.get(consult_type, consult_type.title())
        from datetime import datetime as _dt
        try:
            nice_date = _dt.strptime(date_str, "%Y-%m-%d").strftime("%A, %B %d, %Y")
        except Exception:
            nice_date = date_str
        send_email_async(
            user_email,
            "Consultation Confirmed — " + nice_date,
            '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">'
            '<div style="background:linear-gradient(135deg,#1e3c72,#2a5298);padding:30px;text-align:center;">'
            '<h1 style="color:#fff;margin:0;font-size:24px;">Consultation Confirmed</h1></div>'
            '<div style="padding:30px;">'
            '<p style="color:#333;font-size:16px;">Hi ' + user_name + ',</p>'
            '<p style="color:#555;font-size:15px;">Your consultation has been booked! Here are the details:</p>'
            '<div style="background:#f8f9fa;border-radius:12px;padding:20px;margin:20px 0;border-left:4px solid #1e3c72;">'
            '<table style="width:100%;font-size:14px;color:#333;">'
            '<tr><td style="padding:8px 0;font-weight:600;width:120px;">Date</td><td>' + nice_date + '</td></tr>'
            '<tr><td style="padding:8px 0;font-weight:600;">Time</td><td>' + time_str + '</td></tr>'
            '<tr><td style="padding:8px 0;font-weight:600;">Duration</td><td>30 minutes</td></tr>'
            '<tr><td style="padding:8px 0;font-weight:600;">Type</td><td>' + type_label + '</td></tr>'
            + ('<tr><td style="padding:8px 0;font-weight:600;">Notes</td><td>' + notes + '</td></tr>' if notes else '') +
            '</table></div>'
            '<p style="color:#555;font-size:14px;">We\'ll reach out before the call to confirm. If you need to reschedule, visit your <a href="' + get_frontend_url() + '/dashboard.html" style="color:#1e3c72;font-weight:600;">dashboard</a>.</p>'
            '<p style="color:#888;font-size:13px;margin-top:30px;">— Elevated Solutions</p>'
            '</div></div>',
            'Consultation Confirmed — ' + nice_date + '\nType: ' + type_label + '\nTime: ' + time_str + '\nDuration: 30 minutes'
        )
    except Exception as e:
        print(f"[consultation-email] Error: {e}")

    # Notify admin about new consultation
    try:
        admin_row = db.execute("SELECT email FROM users WHERE role = 'admin' LIMIT 1").fetchone()
        if admin_row:
            send_email_async(
                admin_row["email"],
                "New Consultation Booked — " + user_name,
                '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">'
                '<div style="background:linear-gradient(135deg,#e67e22,#d35400);padding:30px;text-align:center;">'
                '<h1 style="color:#fff;margin:0;font-size:24px;">New Consultation Booked</h1></div>'
                '<div style="padding:30px;">'
                '<p style="color:#333;font-size:16px;">A client just scheduled a consultation:</p>'
                '<div style="background:#f8f9fa;border-radius:12px;padding:20px;margin:20px 0;border-left:4px solid #e67e22;">'
                '<table style="width:100%;font-size:14px;color:#333;">'
                '<tr><td style="padding:8px 0;font-weight:600;width:120px;">Client</td><td>' + user_name + ' (' + user_email + ')</td></tr>'
                '<tr><td style="padding:8px 0;font-weight:600;">Date</td><td>' + nice_date + '</td></tr>'
                '<tr><td style="padding:8px 0;font-weight:600;">Time</td><td>' + time_str + '</td></tr>'
                '<tr><td style="padding:8px 0;font-weight:600;">Type</td><td>' + type_label + '</td></tr>'
                + ('<tr><td style="padding:8px 0;font-weight:600;">Notes</td><td>' + notes + '</td></tr>' if notes else '') +
                '</table></div>'
                '<p style="color:#555;font-size:14px;">View details in the <a href="' + get_frontend_url() + '/admin.html" style="color:#e67e22;font-weight:600;">admin panel</a>.</p>'
                '</div></div>',
                'New consultation from ' + user_name + ' (' + user_email + ')\nDate: ' + nice_date + '\nTime: ' + time_str + '\nType: ' + type_label
            )
    except Exception as e:
        print(f"[consultation-admin-email] Error: {e}")

    return jsonify({
        "message": "Consultation scheduled successfully",
        "consultation": {
            "id": cursor.lastrowid,
            "date": date_str,
            "time": time_str,
            "type": consult_type,
            "notes": notes,
            "status": "scheduled"
        }
    }), 201


@app.route("/api/consultations", methods=["GET"])
@require_auth
def get_consultations():
    db = get_db()
    rows = db.execute(
        "SELECT id, date, time, duration, type, notes, status, created_at FROM consultations "
        "WHERE user_id = ? ORDER BY date ASC, time ASC",
        (g.current_user["id"],)
    ).fetchall()
    return jsonify({"consultations": [dict(r) for r in rows]})


@app.route("/api/consultations/<int:consult_id>", methods=["DELETE"])
@require_auth
def cancel_consultation(consult_id):
    db = get_db()
    row = db.execute(
        "SELECT id, status FROM consultations WHERE id = ? AND user_id = ?",
        (consult_id, g.current_user["id"])
    ).fetchone()
    if not row:
        return jsonify({"error": "Consultation not found"}), 404
    if row["status"] == "cancelled":
        return jsonify({"error": "Already cancelled"}), 400
    db.execute("UPDATE consultations SET status = 'cancelled' WHERE id = ?", (consult_id,))
    db.commit()
    return jsonify({"message": "Consultation cancelled"})


# ══════════════════════════════════════════════════════════════════
# ── Admin Panel Endpoints ─────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════

@app.route("/api/admin/stats", methods=["GET"])
@require_admin
def admin_stats():
    """Dashboard statistics."""
    db = get_db()
    total_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_clients = db.execute("SELECT COUNT(*) FROM users WHERE role = 'client'").fetchone()[0]
    total_admins = db.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
    total_consultations = db.execute("SELECT COUNT(*) FROM consultations").fetchone()[0]
    scheduled = db.execute("SELECT COUNT(*) FROM consultations WHERE status = 'scheduled'").fetchone()[0]
    completed = db.execute("SELECT COUNT(*) FROM consultations WHERE status = 'completed'").fetchone()[0]
    cancelled = db.execute("SELECT COUNT(*) FROM consultations WHERE status = 'cancelled'").fetchone()[0]
    recent_users = db.execute(
        "SELECT id, name, email, company, role, created_at FROM users ORDER BY created_at DESC LIMIT 5"
    ).fetchall()
    upcoming = db.execute(
        "SELECT c.id, c.date, c.time, c.type, c.status, u.name, u.email "
        "FROM consultations c JOIN users u ON c.user_id = u.id "
        "WHERE c.status = 'scheduled' ORDER BY c.date ASC, c.time ASC LIMIT 5"
    ).fetchall()
    return jsonify({
        "users": {"total": total_users, "clients": total_clients, "admins": total_admins},
        "consultations": {"total": total_consultations, "scheduled": scheduled, "completed": completed, "cancelled": cancelled},
        "recent_users": [dict(r) for r in recent_users],
        "upcoming_consultations": [dict(r) for r in upcoming]
    })


# ── Users / Accounts CRUD ─────────────────────────────────────

@app.route("/api/admin/users", methods=["GET"])
@require_admin
def admin_list_users():
    db = get_db()
    search = request.args.get("search", "").strip()
    role_filter = request.args.get("role", "").strip()
    query = "SELECT id, name, email, company, role, payment_portal, demo_preview, demo_preview_site, created_at FROM users WHERE 1=1"
    params = []
    if search:
        query += " AND (name LIKE ? OR email LIKE ? OR company LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])
    if role_filter:
        query += " AND role = ?"
        params.append(role_filter)
    query += " ORDER BY created_at DESC"
    rows = db.execute(query, params).fetchall()
    return jsonify({"users": [dict(r) for r in rows]})


@app.route("/api/admin/users/<int:user_id>", methods=["GET"])
@require_admin
def admin_get_user(user_id):
    db = get_db()
    user = db.execute(
        "SELECT id, name, email, company, role, payment_portal, demo_preview, demo_preview_site, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not user:
        return jsonify({"error": "User not found"}), 404
    consults = db.execute(
        "SELECT id, date, time, type, notes, status, created_at FROM consultations "
        "WHERE user_id = ? ORDER BY date DESC", (user_id,)
    ).fetchall()
    return jsonify({"user": dict(user), "consultations": [dict(c) for c in consults]})


@app.route("/api/admin/users/<int:user_id>", methods=["PUT"])
@require_admin
def admin_update_user(user_id):
    db = get_db()
    user = db.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return jsonify({"error": "User not found"}), 404
    data = request.get_json(silent=True) or {}
    updates = []
    params = []
    if "name" in data:
        name = (data["name"] or "").strip()
        if name:
            updates.append("name = ?")
            params.append(name)
    if "email" in data:
        email = (data["email"] or "").strip().lower()
        if email:
            dup = db.execute("SELECT id FROM users WHERE email = ? AND id != ?", (email, user_id)).fetchone()
            if dup:
                return jsonify({"error": "Email already in use"}), 409
            updates.append("email = ?")
            params.append(email)
    if "company" in data:
        updates.append("company = ?")
        params.append((data["company"] or "").strip())
    if "role" in data and data["role"] in ("client", "admin"):
        updates.append("role = ?")
        params.append(data["role"])
    if "password" in data and data["password"]:
        if len(data["password"]) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400
        updates.append("password_hash = ?")
        params.append(generate_password_hash(data["password"]))
    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400
    params.append(user_id)
    db.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
    db.commit()
    updated = db.execute(
        "SELECT id, name, email, company, role, payment_portal, demo_preview, demo_preview_site, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return jsonify({"message": "User updated", "user": dict(updated)})


@app.route("/api/admin/users/<int:user_id>/payment-portal", methods=["POST"])
@require_admin
def admin_toggle_payment_portal(user_id):
    db = get_db()
    user = db.execute("SELECT id, payment_portal FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return jsonify({"error": "User not found"}), 404
    new_val = 0 if user["payment_portal"] else 1
    db.execute("UPDATE users SET payment_portal = ? WHERE id = ?", (new_val, user_id))
    db.commit()
    # Create payment_config row if enabling
    if new_val:
        existing = db.execute("SELECT id FROM payment_config WHERE user_id = ?", (user_id,)).fetchone()
        if not existing:
            db.execute("INSERT INTO payment_config (user_id, onetime_amount, monthly_amount) VALUES (?, 0, 0)", (user_id,))
            db.commit()
    return jsonify({"message": "Payment portal " + ("enabled" if new_val else "disabled"), "payment_portal": new_val})


@app.route("/api/admin/users/<int:user_id>/demo-preview", methods=["POST"])
@require_admin
def admin_toggle_demo_preview(user_id):
    db = get_db()
    data = request.get_json(silent=True) or {}
    site = (data.get("site") or "").strip()
    user = db.execute("SELECT id, demo_preview, demo_preview_site FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return jsonify({"error": "User not found"}), 404
    if site:
        # Validate site folder exists
        previews_dir = os.path.join(os.path.dirname(__file__), "websitepreviews")
        site_path = os.path.join(previews_dir, site)
        has_dist = os.path.isfile(os.path.join(site_path, "dist", "index.html"))
        has_root = os.path.isfile(os.path.join(site_path, "index.html"))
        if not os.path.isdir(site_path) or not (has_dist or has_root):
            return jsonify({"error": "Invalid preview site"}), 400
        db.execute("UPDATE users SET demo_preview = 1, demo_preview_site = ? WHERE id = ?", (site, user_id))
        db.commit()

        # Send "site ready to preview" email
        try:
            u = db.execute("SELECT email, name, first_name FROM users WHERE id = ?", (user_id,)).fetchone()
            if u:
                u_email = u["email"]
                u_name = u.get("name") or u.get("first_name") or u_email.split("@")[0]
                preview_url = get_frontend_url() + "/preview-viewer.html"
                send_email_async(
                    u_email,
                    "Your Website Preview is Ready!",
                    '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">'
                    '<div style="background:linear-gradient(135deg,#1e3c72,#2a5298);padding:30px;text-align:center;">'
                    '<h1 style="color:#fff;margin:0;font-size:24px;">Your Preview is Ready!</h1></div>'
                    '<div style="padding:30px;">'
                    '<p style="color:#333;font-size:16px;">Hi ' + u_name + ',</p>'
                    '<p style="color:#555;font-size:15px;">Great news — your website preview is now live and ready for you to review!</p>'
                    '<div style="text-align:center;margin:30px 0;">'
                    '<a href="' + preview_url + '" style="background:linear-gradient(135deg,#1e3c72,#2a5298);color:#fff;padding:14px 36px;border-radius:30px;text-decoration:none;font-weight:600;font-size:16px;display:inline-block;">View Your Preview</a>'
                    '</div>'
                    '<p style="color:#555;font-size:14px;">Take your time exploring the design. You can request revisions or approve it directly from your <a href="' + get_frontend_url() + '/dashboard.html" style="color:#1e3c72;font-weight:600;">dashboard</a>.</p>'
                    '<div style="background:#f0f7ff;border-radius:10px;padding:16px;margin:20px 0;">'
                    '<p style="color:#1e3c72;font-size:13px;margin:0;"><strong>What\'s next?</strong></p>'
                    '<ul style="color:#555;font-size:13px;margin:8px 0 0;padding-left:20px;">'
                    '<li>Review every page and feature</li>'
                    '<li>Request any changes or revisions</li>'
                    '<li>Approve and we\'ll deploy to your live domain</li>'
                    '</ul></div>'
                    '<p style="color:#888;font-size:13px;margin-top:30px;">— Elevated Solutions</p>'
                    '</div></div>',
                    'Your website preview is ready! View it here: ' + preview_url
                )
        except Exception as e:
            print(f"[preview-email] Error: {e}")

        return jsonify({"message": "Service preview enabled", "demo_preview": 1, "demo_preview_site": site})
    else:
        # Disable
        db.execute("UPDATE users SET demo_preview = 0, demo_preview_site = '' WHERE id = ?", (user_id,))
        db.commit()
        return jsonify({"message": "Service preview disabled", "demo_preview": 0, "demo_preview_site": ""})


@app.route("/api/admin/users/<int:user_id>/payment-config", methods=["GET", "PUT"])
@require_admin
def admin_payment_config(user_id):
    db = get_db()
    user = db.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return jsonify({"error": "User not found"}), 404

    if request.method == "GET":
        cfg = db.execute("SELECT * FROM payment_config WHERE user_id = ?", (user_id,)).fetchone()
        if not cfg:
            return jsonify({"config": None})
        return jsonify({"config": dict(cfg)})

    data = request.get_json(silent=True) or {}
    onetime = data.get("onetime_amount")
    monthly = data.get("monthly_amount")
    cfg = db.execute("SELECT id FROM payment_config WHERE user_id = ?", (user_id,)).fetchone()
    if not cfg:
        db.execute("INSERT INTO payment_config (user_id, onetime_amount, monthly_amount) VALUES (?, ?, ?)",
                   (user_id, float(onetime or 0), float(monthly or 0)))
    else:
        updates = []
        params = []
        if onetime is not None:
            updates.append("onetime_amount = ?")
            params.append(float(onetime))
        if monthly is not None:
            updates.append("monthly_amount = ?")
            params.append(float(monthly))
        if updates:
            params.append(user_id)
            db.execute(f"UPDATE payment_config SET {', '.join(updates)} WHERE user_id = ?", params)
    db.commit()
    cfg = db.execute("SELECT * FROM payment_config WHERE user_id = ?", (user_id,)).fetchone()
    return jsonify({"message": "Payment config updated", "config": dict(cfg)})


@app.route("/api/me/payments", methods=["GET"])
@require_auth
def get_my_payments():
    db = get_db()
    uid = g.current_user["id"]
    if not g.current_user.get("payment_portal"):
        return jsonify({"error": "Payment portal not enabled"}), 403
    cfg = db.execute("SELECT * FROM payment_config WHERE user_id = ?", (uid,)).fetchone()
    if not cfg:
        return jsonify({"config": None, "history": []})
    history = db.execute(
        "SELECT id, type, amount, status, paid_at, created_at FROM payments WHERE user_id = ? ORDER BY created_at DESC",
        (uid,)
    ).fetchall()
    return jsonify({"config": dict(cfg), "history": [dict(h) for h in history]})


@app.route("/api/stripe/config", methods=["GET"])
@require_auth
def get_stripe_config():
    """Return publishable key so the frontend can load Stripe."""
    keys = get_stripe_keys()
    return jsonify({"publishableKey": keys["publishable_key"]})


def get_or_create_stripe_customer(user, db):
    """Ensure user has a Stripe customer, return customer ID."""
    cfg = db.execute("SELECT stripe_customer_id FROM payment_config WHERE user_id = ?", (user["id"],)).fetchone()
    if cfg and cfg["stripe_customer_id"]:
        return cfg["stripe_customer_id"]
    customer = stripe.Customer.create(
        email=user["email"],
        name=user["name"],
        metadata={"user_id": str(user["id"])}
    )
    db.execute("UPDATE payment_config SET stripe_customer_id = ? WHERE user_id = ?", (customer.id, user["id"]))
    db.commit()
    return customer.id


@app.route("/api/me/payments/onetime", methods=["POST"])
@require_auth
def pay_onetime():
    configure_stripe()
    db = get_db()
    uid = g.current_user["id"]
    if not g.current_user.get("payment_portal"):
        return jsonify({"error": "Payment portal not enabled"}), 403
    cfg = db.execute("SELECT * FROM payment_config WHERE user_id = ?", (uid,)).fetchone()
    if not cfg:
        return jsonify({"error": "No payment config found"}), 404
    if cfg["onetime_paid"]:
        return jsonify({"error": "One-time fee already paid"}), 400

    customer_id = get_or_create_stripe_customer(g.current_user, db)
    amount_cents = int(round(cfg["onetime_amount"] * 100))

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": STRIPE_CURRENCY,
                "unit_amount": amount_cents,
                "product_data": {
                    "name": "One-Time Project Fee",
                    "description": "Initial setup, design, and development"
                }
            },
            "quantity": 1
        }],
        metadata={"user_id": str(uid), "payment_type": "onetime"},
        success_url=get_frontend_url() + "/dashboard.html?payment=success&type=onetime",
        cancel_url=get_frontend_url() + "/dashboard.html?payment=cancel",
    )

    db.execute("UPDATE payment_config SET stripe_onetime_session_id = ? WHERE user_id = ?", (session.id, uid))
    db.commit()

    return jsonify({"checkout_url": session.url, "session_id": session.id})


@app.route("/api/me/payments/monthly", methods=["POST"])
@require_auth
def setup_monthly():
    configure_stripe()
    db = get_db()
    uid = g.current_user["id"]
    if not g.current_user.get("payment_portal"):
        return jsonify({"error": "Payment portal not enabled"}), 403
    cfg = db.execute("SELECT * FROM payment_config WHERE user_id = ?", (uid,)).fetchone()
    if not cfg:
        return jsonify({"error": "No payment config found"}), 404
    if not cfg["onetime_paid"]:
        return jsonify({"error": "One-time fee must be paid first"}), 400
    if cfg["monthly_active"]:
        return jsonify({"error": "Monthly payments already active"}), 400

    customer_id = get_or_create_stripe_customer(g.current_user, db)
    amount_cents = int(round(cfg["monthly_amount"] * 100))

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        mode="subscription",
        line_items=[{
            "price_data": {
                "currency": STRIPE_CURRENCY,
                "unit_amount": amount_cents,
                "recurring": {"interval": "month"},
                "product_data": {
                    "name": "Monthly Upkeep",
                    "description": "Hosting, maintenance, updates & support"
                }
            },
            "quantity": 1
        }],
        metadata={"user_id": str(uid), "payment_type": "monthly"},
        success_url=get_frontend_url() + "/dashboard.html?payment=success&type=monthly",
        cancel_url=get_frontend_url() + "/dashboard.html?payment=cancel",
    )

    return jsonify({"checkout_url": session.url, "session_id": session.id})


@app.route("/api/stripe/webhook", methods=["POST"])
def stripe_webhook():
    """Handle Stripe webhook events to confirm payments."""
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")

    keys = configure_stripe()
    wh_secret = keys["webhook_secret"]

    try:
        if wh_secret and wh_secret != "whsec_REPLACE_ME":
            event = stripe.Webhook.construct_event(payload, sig_header, wh_secret)
        else:
            # In dev/test mode without webhook secret, parse directly
            import json as _json
            event = stripe.Event.construct_from(_json.loads(payload), stripe.api_key)
    except (ValueError, stripe.error.SignatureVerificationError):
        return jsonify({"error": "Invalid signature"}), 400

    db = get_db()

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        meta = session.get("metadata", {})
        user_id = meta.get("user_id")
        payment_type = meta.get("payment_type")

        if not user_id:
            return jsonify({"received": True}), 200

        user_id = int(user_id)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if payment_type == "onetime":
            cfg = db.execute("SELECT onetime_paid FROM payment_config WHERE user_id = ?", (user_id,)).fetchone()
            if cfg and not cfg["onetime_paid"]:
                amount = session.get("amount_total", 0) / 100.0
                db.execute(
                    "UPDATE payment_config SET onetime_paid = 1, onetime_paid_at = ? WHERE user_id = ?",
                    (now, user_id)
                )
                db.execute(
                    "INSERT INTO payments (user_id, type, amount, status, paid_at) VALUES (?, 'onetime', ?, 'paid', ?)",
                    (user_id, amount, now)
                )
                db.commit()

        elif payment_type == "monthly":
            subscription_id = session.get("subscription")
            amount = session.get("amount_total", 0) / 100.0
            db.execute(
                "UPDATE payment_config SET monthly_active = 1, monthly_started_at = ?, stripe_subscription_id = ? WHERE user_id = ?",
                (now, subscription_id, user_id)
            )
            db.execute(
                "INSERT INTO payments (user_id, type, amount, status, paid_at) VALUES (?, 'monthly', ?, 'paid', ?)",
                (user_id, amount, now)
            )
            db.commit()

        elif payment_type == "deploy":
            deploy_id = meta.get("deploy_id")
            if deploy_id:
                deploy_id = int(deploy_id)
                dr = db.execute("SELECT * FROM deploy_requests WHERE id = ? AND status = 'pending_payment'", (deploy_id,)).fetchone()
                if dr:
                    amount = session.get("amount_total", 0) / 100.0
                    subscription_id = session.get("subscription")
                    db.execute("UPDATE deploy_requests SET status = 'paid', stripe_subscription_id = ? WHERE id = ?", (subscription_id, deploy_id))
                    # Store subscription for recurring invoice tracking
                    if subscription_id:
                        db.execute(
                            "UPDATE payment_config SET monthly_active = 1, stripe_subscription_id = ? WHERE user_id = ?",
                            (subscription_id, user_id)
                        )
                    # Now create the admin message
                    try:
                        addons = json.loads(dr["selected_addons"])
                    except (json.JSONDecodeError, TypeError):
                        addons = []
                    db.execute(
                        "INSERT INTO messages (user_id, subject, body, category) VALUES (?,?,?,?)",
                        (user_id, "Deploy Request: " + dr["domain"],
                         "Domain: " + dr["domain"] +
                         "\nSelected Add-ons: " + ", ".join(addons if addons else ["None"]) +
                         "\nSubtotal: $" + str(dr["subtotal"]) +
                         "\nTax: $" + str(dr["tax"]) +
                         "\nTotal: $" + str(dr["total"]) +
                         "\nMonthly Maintenance: $" + str(dr["monthly"]) +
                         "\n\n✅ Payment confirmed via Stripe ($" + f"{amount:.2f}" + ")" +
                         ("\n🔄 Monthly subscription active: " + subscription_id if subscription_id else ""),
                         "deploy")
                    )
                    db.commit()

                    # Send payment receipt email to client
                    try:
                        u = db.execute("SELECT email, name, first_name FROM users WHERE id = ?", (user_id,)).fetchone()
                        if u:
                            u_email = u["email"]
                            u_name = u.get("name") or u.get("first_name") or u_email.split("@")[0]
                            addon_list = ", ".join(addons) if addons else "None"
                            monthly_str = f"${float(dr['monthly']):.2f}/mo" if float(dr['monthly']) > 0 else "—"
                            send_email_async(
                                u_email,
                                "Payment Receipt — " + dr["domain"],
                                '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">'
                                '<div style="background:linear-gradient(135deg,#1e3c72,#2a5298);padding:30px;text-align:center;">'
                                '<h1 style="color:#fff;margin:0;font-size:24px;">Payment Receipt</h1></div>'
                                '<div style="padding:30px;">'
                                '<p style="color:#333;font-size:16px;">Hi ' + u_name + ',</p>'
                                '<p style="color:#555;font-size:15px;">Thank you for your purchase! Here\'s your receipt:</p>'
                                '<div style="background:#f8f9fa;border-radius:12px;padding:20px;margin:20px 0;">'
                                '<table style="width:100%;font-size:14px;color:#333;border-collapse:collapse;">'
                                '<tr style="border-bottom:1px solid #eee;"><td style="padding:10px 0;font-weight:600;">Domain</td><td style="text-align:right;">' + dr["domain"] + '</td></tr>'
                                '<tr style="border-bottom:1px solid #eee;"><td style="padding:10px 0;font-weight:600;">Add-ons</td><td style="text-align:right;">' + addon_list + '</td></tr>'
                                '<tr style="border-bottom:1px solid #eee;"><td style="padding:10px 0;font-weight:600;">Subtotal</td><td style="text-align:right;">$' + f"{float(dr['subtotal']):.2f}" + '</td></tr>'
                                '<tr style="border-bottom:1px solid #eee;"><td style="padding:10px 0;font-weight:600;">Tax</td><td style="text-align:right;">$' + f"{float(dr['tax']):.2f}" + '</td></tr>'
                                '<tr style="border-bottom:2px solid #1e3c72;"><td style="padding:10px 0;font-weight:700;font-size:16px;">Total Paid</td><td style="text-align:right;font-weight:700;font-size:16px;color:#1e3c72;">$' + f"{amount:.2f}" + '</td></tr>'
                                '<tr><td style="padding:10px 0;font-weight:600;">Monthly Maintenance</td><td style="text-align:right;">' + monthly_str + '</td></tr>'
                                '</table></div>'
                                '<p style="color:#555;font-size:14px;">We\'ll begin working on your site right away. You can track progress from your <a href="' + get_frontend_url() + '/dashboard.html" style="color:#1e3c72;font-weight:600;">dashboard</a>.</p>'
                                '<p style="color:#888;font-size:12px;margin-top:30px;">Transaction date: ' + datetime.now().strftime("%B %d, %Y at %I:%M %p") + '</p>'
                                '<p style="color:#888;font-size:13px;">— Elevated Solutions</p>'
                                '</div></div>',
                                'Payment Receipt — ' + dr["domain"] + '\nTotal: $' + f"{amount:.2f}" + '\nMonthly: ' + monthly_str
                            )
                    except Exception as e:
                        print(f"[receipt-email-webhook] Error: {e}")

                    # Notify admin about new purchase
                    try:
                        admin_row = db.execute("SELECT email FROM users WHERE role = 'admin' LIMIT 1").fetchone()
                        if admin_row and u:
                            u_name_admin = u.get("name") or u.get("first_name") or u["email"].split("@")[0]
                            send_email_async(
                                admin_row["email"],
                                "New Purchase — " + dr["domain"] + " ($" + f"{amount:.2f}" + ")",
                                '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">'
                                '<div style="background:linear-gradient(135deg,#28a745,#218838);padding:30px;text-align:center;">'
                                '<h1 style="color:#fff;margin:0;font-size:24px;">New Deploy Purchase!</h1></div>'
                                '<div style="padding:30px;">'
                                '<p style="color:#333;font-size:16px;">A client just completed a deploy payment:</p>'
                                '<div style="background:#f8f9fa;border-radius:12px;padding:20px;margin:20px 0;border-left:4px solid #28a745;">'
                                '<table style="width:100%;font-size:14px;color:#333;border-collapse:collapse;">'
                                '<tr style="border-bottom:1px solid #eee;"><td style="padding:10px 0;font-weight:600;">Client</td><td style="text-align:right;">' + u_name_admin + ' (' + u["email"] + ')</td></tr>'
                                '<tr style="border-bottom:1px solid #eee;"><td style="padding:10px 0;font-weight:600;">Domain</td><td style="text-align:right;">' + dr["domain"] + '</td></tr>'
                                '<tr style="border-bottom:1px solid #eee;"><td style="padding:10px 0;font-weight:600;">Add-ons</td><td style="text-align:right;">' + addon_list + '</td></tr>'
                                '<tr style="border-bottom:1px solid #eee;"><td style="padding:10px 0;font-weight:600;">Total</td><td style="text-align:right;font-weight:700;color:#28a745;">$' + f"{amount:.2f}" + '</td></tr>'
                                '<tr><td style="padding:10px 0;font-weight:600;">Monthly</td><td style="text-align:right;">' + monthly_str + '</td></tr>'
                                '</table></div>'
                                '<p style="color:#555;font-size:14px;">Manage in the <a href="' + get_frontend_url() + '/admin.html" style="color:#28a745;font-weight:600;">admin panel</a>.</p>'
                                '</div></div>',
                                'New purchase from ' + u_name_admin + '\nDomain: ' + dr["domain"] + '\nTotal: $' + f"{amount:.2f}"
                            )
                    except Exception as e:
                        print(f"[purchase-admin-email-webhook] Error: {e}")

    elif event["type"] == "invoice.paid":
        invoice = event["data"]["object"]
        subscription_id = invoice.get("subscription")
        if subscription_id:
            cfg = db.execute(
                "SELECT user_id, monthly_amount FROM payment_config WHERE stripe_subscription_id = ?",
                (subscription_id,)
            ).fetchone()
            if cfg:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                amount = invoice.get("amount_paid", 0) / 100.0
                db.execute(
                    "INSERT INTO payments (user_id, type, amount, status, paid_at) VALUES (?, 'monthly', ?, 'paid', ?)",
                    (cfg["user_id"], amount, now)
                )
                db.commit()

    return jsonify({"received": True}), 200


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@require_admin
def admin_delete_user(user_id):
    db = get_db()
    user = db.execute("SELECT id, role FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return jsonify({"error": "User not found"}), 404
    if user["id"] == g.current_user["id"]:
        return jsonify({"error": "Cannot delete your own account"}), 400
    db.execute("DELETE FROM auth_tokens WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM consultations WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    return jsonify({"message": "User and associated data deleted"})


@app.route("/api/admin/users", methods=["POST"])
@require_admin
def admin_create_user():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid request body"}), 400
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    company = (data.get("company") or "").strip()
    password = data.get("password") or ""
    role = data.get("role", "client")
    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if role not in ("client", "admin"):
        role = "client"
    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        return jsonify({"error": "Email already in use"}), 409
    cursor = db.execute(
        "INSERT INTO users (name, email, company, password_hash, role) VALUES (?, ?, ?, ?, ?)",
        (name, email, company, generate_password_hash(password), role)
    )
    db.commit()
    return jsonify({
        "message": "User created",
        "user": {"id": cursor.lastrowid, "name": name, "email": email, "company": company, "role": role}
    }), 201


# ── Consultations Admin CRUD ──────────────────────────────────

@app.route("/api/admin/consultations", methods=["GET"])
@require_admin
def admin_list_consultations():
    db = get_db()
    status_filter = request.args.get("status", "").strip()
    type_filter = request.args.get("type", "").strip()
    search = request.args.get("search", "").strip()
    query = (
        "SELECT c.id, c.date, c.time, c.type, c.notes, c.status, c.created_at, "
        "u.id AS user_id, u.name, u.email, u.company "
        "FROM consultations c JOIN users u ON c.user_id = u.id WHERE 1=1"
    )
    params = []
    if status_filter:
        query += " AND c.status = ?"
        params.append(status_filter)
    if type_filter:
        query += " AND c.type = ?"
        params.append(type_filter)
    if search:
        query += " AND (u.name LIKE ? OR u.email LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like])
    query += " ORDER BY c.date DESC, c.time DESC"
    rows = db.execute(query, params).fetchall()
    return jsonify({"consultations": [dict(r) for r in rows]})


@app.route("/api/admin/consultations/<int:consult_id>", methods=["PUT"])
@require_admin
def admin_update_consultation(consult_id):
    db = get_db()
    row = db.execute("SELECT id FROM consultations WHERE id = ?", (consult_id,)).fetchone()
    if not row:
        return jsonify({"error": "Consultation not found"}), 404
    data = request.get_json(silent=True) or {}
    updates = []
    params = []
    if "status" in data and data["status"] in ("scheduled", "completed", "cancelled"):
        updates.append("status = ?")
        params.append(data["status"])
    if "date" in data:
        updates.append("date = ?")
        params.append(data["date"])
    if "time" in data:
        updates.append("time = ?")
        params.append(data["time"])
    if "type" in data:
        updates.append("type = ?")
        params.append(data["type"])
    if "notes" in data:
        updates.append("notes = ?")
        params.append((data["notes"] or "")[:1000])
    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400
    params.append(consult_id)
    db.execute(f"UPDATE consultations SET {', '.join(updates)} WHERE id = ?", params)
    db.commit()
    return jsonify({"message": "Consultation updated"})


@app.route("/api/admin/consultations/<int:consult_id>", methods=["DELETE"])
@require_admin
def admin_delete_consultation(consult_id):
    db = get_db()
    row = db.execute("SELECT id FROM consultations WHERE id = ?", (consult_id,)).fetchone()
    if not row:
        return jsonify({"error": "Consultation not found"}), 404
    db.execute("DELETE FROM consultations WHERE id = ?", (consult_id,))
    db.commit()
    return jsonify({"message": "Consultation deleted"})


# ── Admin Availability Management ──────────────────────────────

@app.route("/api/admin/availability", methods=["GET"])
@require_admin
def admin_get_availability():
    db = get_db()
    rows = db.execute("SELECT * FROM availability ORDER BY day_of_week ASC").fetchall()
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    result = []
    for r in rows:
        d = dict(r)
        d["day_name"] = days[r["day_of_week"]] if r["day_of_week"] < len(days) else "Unknown"
        result.append(d)
    return jsonify({"availability": result})


@app.route("/api/admin/availability/<int:avail_id>", methods=["PUT"])
@require_admin
def admin_update_availability(avail_id):
    data = request.get_json(silent=True) or {}
    db = get_db()
    row = db.execute("SELECT * FROM availability WHERE id = ?", (avail_id,)).fetchone()
    if not row:
        return jsonify({"error": "Availability rule not found"}), 404

    start_time = data.get("start_time", row["start_time"])
    end_time = data.get("end_time", row["end_time"])
    slot_duration = data.get("slot_duration", row["slot_duration"])
    is_active = data.get("is_active", row["is_active"])

    if not re.match(r"^\d{2}:\d{2}$", start_time) or not re.match(r"^\d{2}:\d{2}$", end_time):
        return jsonify({"error": "Invalid time format"}), 400
    if not isinstance(slot_duration, int) or slot_duration < 15 or slot_duration > 120:
        return jsonify({"error": "Slot duration must be 15-120 minutes"}), 400

    db.execute(
        "UPDATE availability SET start_time=?, end_time=?, slot_duration=?, is_active=? WHERE id=?",
        (start_time, end_time, int(slot_duration), 1 if is_active else 0, avail_id)
    )
    db.commit()
    return jsonify({"message": "Availability updated"})


@app.route("/api/admin/blocked-dates", methods=["GET"])
@require_admin
def admin_get_blocked_dates():
    db = get_db()
    rows = db.execute("SELECT * FROM blocked_dates ORDER BY date ASC").fetchall()
    return jsonify({"blocked_dates": [dict(r) for r in rows]})


@app.route("/api/admin/blocked-dates", methods=["POST"])
@require_admin
def admin_add_blocked_date():
    data = request.get_json(silent=True) or {}
    date_str = (data.get("date") or "").strip()
    reason = (data.get("reason") or "").strip()
    if not date_str:
        return jsonify({"error": "Date required"}), 400
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400
    db = get_db()
    existing = db.execute("SELECT id FROM blocked_dates WHERE date = ?", (date_str,)).fetchone()
    if existing:
        return jsonify({"error": "Date already blocked"}), 409
    db.execute("INSERT INTO blocked_dates (date, reason) VALUES (?, ?)", (date_str, reason))
    db.commit()
    return jsonify({"message": "Date blocked"}), 201


@app.route("/api/admin/blocked-dates/<int:block_id>", methods=["DELETE"])
@require_admin
def admin_delete_blocked_date(block_id):
    db = get_db()
    row = db.execute("SELECT id FROM blocked_dates WHERE id = ?", (block_id,)).fetchone()
    if not row:
        return jsonify({"error": "Blocked date not found"}), 404
    db.execute("DELETE FROM blocked_dates WHERE id = ?", (block_id,))
    db.commit()
    return jsonify({"message": "Blocked date removed"})


# ── Preview Sites ──

PREVIEWS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "websitepreviews")


@app.route("/api/admin/preview-sites", methods=["GET"])
@require_admin
def admin_list_preview_sites():
    """List subfolders in websitepreviews/ that contain an index.html (or dist/index.html)."""
    sites = []
    if os.path.isdir(PREVIEWS_DIR):
        for name in sorted(os.listdir(PREVIEWS_DIR)):
            folder = os.path.join(PREVIEWS_DIR, name)
            if os.path.isdir(folder):
                has_dist = os.path.isfile(os.path.join(folder, "dist", "index.html"))
                has_root = os.path.isfile(os.path.join(folder, "index.html"))
                if has_dist or has_root:
                    sites.append({"name": name, "has_dist": has_dist})
    return jsonify({"sites": sites})


# ── Messages API ──

@app.route("/api/messages", methods=["POST"])
@require_auth
def create_message():
    """Client sends a message / revision request."""
    user = g.current_user
    data = request.get_json() or {}
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"error": "Message body is required"}), 400
    subject = (data.get("subject") or "").strip()[:200]
    category = data.get("category", "general")
    if category not in ("general", "revision", "deploy", "bug", "other"):
        category = "general"
    db = get_db()
    db.execute(
        "INSERT INTO messages (user_id, subject, body, category) VALUES (?, ?, ?, ?)",
        (user["id"], subject, body[:5000], category)
    )
    db.commit()
    return jsonify({"ok": True, "message": "Message sent"}), 201


@app.route("/api/me/messages", methods=["GET"])
@require_auth
def get_my_messages():
    """Client views their own messages."""
    user = g.current_user
    db = get_db()
    rows = db.execute(
        "SELECT id, subject, body, category, is_read, admin_reply, replied_at, created_at "
        "FROM messages WHERE user_id = ? ORDER BY created_at DESC",
        (user["id"],)
    ).fetchall()
    return jsonify({"messages": [dict(r) for r in rows]})


@app.route("/api/admin/messages", methods=["GET"])
@require_admin
def admin_get_messages():
    """Admin views all messages."""
    db = get_db()
    rows = db.execute(
        "SELECT m.id, m.subject, m.body, m.category, m.is_read, m.admin_reply, m.replied_at, m.created_at, "
        "u.name as user_name, u.email as user_email, u.company as user_company "
        "FROM messages m JOIN users u ON m.user_id = u.id ORDER BY m.created_at DESC"
    ).fetchall()
    return jsonify({"messages": [dict(r) for r in rows]})


@app.route("/api/admin/messages/<int:msg_id>/read", methods=["POST"])
@require_admin
def admin_mark_read(msg_id):
    db = get_db()
    db.execute("UPDATE messages SET is_read = 1 WHERE id = ?", (msg_id,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/messages/<int:msg_id>/reply", methods=["POST"])
@require_admin
def admin_reply_message(msg_id):
    data = request.get_json() or {}
    reply = (data.get("reply") or "").strip()
    if not reply:
        return jsonify({"error": "Reply is required"}), 400
    db = get_db()
    db.execute(
        "UPDATE messages SET admin_reply = ?, replied_at = datetime('now'), is_read = 1 WHERE id = ?",
        (reply[:5000], msg_id)
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/messages/<int:msg_id>", methods=["DELETE"])
@require_admin
def admin_delete_message(msg_id):
    db = get_db()
    db.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/messages/unread-count", methods=["GET"])
@require_admin
def admin_unread_count():
    db = get_db()
    row = db.execute("SELECT COUNT(*) as cnt FROM messages WHERE is_read = 0").fetchone()
    return jsonify({"count": row["cnt"]})


# ── Deploy Pricing API ──

@app.route("/api/admin/users/<int:user_id>/deploy-config", methods=["GET"])
@require_admin
def admin_get_deploy_config(user_id):
    db = get_db()
    row = db.execute("SELECT * FROM deploy_config WHERE user_id = ?", (user_id,)).fetchone()
    if row:
        cfg = dict(row)
        try:
            cfg["addons"] = json.loads(cfg["addons"])
        except (json.JSONDecodeError, TypeError):
            cfg["addons"] = []
        try:
            cfg["domain_tlds"] = json.loads(cfg.get("domain_tlds") or "[]")
        except (json.JSONDecodeError, TypeError):
            cfg["domain_tlds"] = []
        return jsonify({"config": cfg})
    return jsonify({"config": {"user_id": user_id, "base_fee": 499, "monthly_maintenance": 49, "tax_rate": 8.25, "addons": [], "domain_tlds": DEFAULT_DOMAIN_TLDS}})


@app.route("/api/admin/users/<int:user_id>/deploy-config", methods=["PUT"])
@require_admin
def admin_set_deploy_config(user_id):
    data = request.get_json() or {}
    base_fee = float(data.get("base_fee", 499))
    monthly = float(data.get("monthly_maintenance", 49))
    tax_rate = float(data.get("tax_rate", 8.25))
    addons = data.get("addons", [])
    if not isinstance(addons, list):
        addons = []
    # Validate addon structure
    clean_addons = []
    for a in addons:
        if isinstance(a, dict) and a.get("name") and a.get("price") is not None:
            clean_addons.append({"name": str(a["name"])[:100], "price": float(a["price"]), "description": str(a.get("description", ""))[:200]})
    # Validate domain TLDs
    tlds = data.get("domain_tlds", [])
    if not isinstance(tlds, list):
        tlds = []
    clean_tlds = []
    for t in tlds:
        if isinstance(t, dict) and t.get("tld") and t.get("price") is not None:
            clean_tlds.append({"tld": str(t["tld"])[:20].strip(), "price": float(t["price"])})
    db = get_db()
    existing = db.execute("SELECT id FROM deploy_config WHERE user_id = ?", (user_id,)).fetchone()
    if existing:
        db.execute(
            "UPDATE deploy_config SET base_fee=?, monthly_maintenance=?, tax_rate=?, addons=?, domain_tlds=? WHERE user_id=?",
            (base_fee, monthly, tax_rate, json.dumps(clean_addons), json.dumps(clean_tlds), user_id)
        )
    else:
        db.execute(
            "INSERT INTO deploy_config (user_id, base_fee, monthly_maintenance, tax_rate, addons, domain_tlds) VALUES (?,?,?,?,?,?)",
            (user_id, base_fee, monthly, tax_rate, json.dumps(clean_addons), json.dumps(clean_tlds))
        )
    db.commit()
    return jsonify({"ok": True})


# ── Coupon CRUD ──────────────────────────────────────────────────────
@app.route("/api/admin/coupons", methods=["GET"])
@require_admin
def admin_list_coupons():
    db = get_db()
    rows = db.execute("SELECT * FROM coupons ORDER BY created_at DESC").fetchall()
    return jsonify({"coupons": [dict(r) for r in rows]})

@app.route("/api/admin/coupons", methods=["POST"])
@require_admin
def admin_create_coupon():
    data = request.get_json() or {}
    code = str(data.get("code", "")).strip().upper()
    if not code or len(code) > 50:
        return jsonify({"error": "Coupon code is required (max 50 chars)"}), 400
    discount_type = data.get("discount_type", "percent")
    if discount_type not in ("percent", "flat"):
        discount_type = "percent"
    discount_value = float(data.get("discount_value", 0))
    if discount_value <= 0:
        return jsonify({"error": "Discount value must be positive"}), 400
    if discount_type == "percent" and discount_value > 100:
        return jsonify({"error": "Percent discount cannot exceed 100"}), 400
    max_uses = int(data.get("max_uses", 0))  # 0 = unlimited
    free_first_month = 1 if data.get("free_first_month") else 0
    expires_at = data.get("expires_at") or None
    db = get_db()
    existing = db.execute("SELECT id FROM coupons WHERE code = ?", (code,)).fetchone()
    if existing:
        return jsonify({"error": "Coupon code already exists"}), 409
    db.execute(
        "INSERT INTO coupons (code, discount_type, discount_value, max_uses, free_first_month, expires_at) VALUES (?,?,?,?,?,?)",
        (code, discount_type, discount_value, max_uses, free_first_month, expires_at)
    )
    db.commit()
    return jsonify({"ok": True}), 201

@app.route("/api/admin/coupons/<int:coupon_id>", methods=["PUT"])
@require_admin
def admin_update_coupon(coupon_id):
    data = request.get_json() or {}
    db = get_db()
    c = db.execute("SELECT * FROM coupons WHERE id = ?", (coupon_id,)).fetchone()
    if not c:
        return jsonify({"error": "Coupon not found"}), 404
    active = int(data.get("active", c["active"]))
    max_uses = int(data.get("max_uses", c["max_uses"]))
    free_first_month = int(data.get("free_first_month", c["free_first_month"]))
    expires_at = data.get("expires_at", c["expires_at"]) or None
    discount_value = float(data.get("discount_value", c["discount_value"]))
    discount_type = data.get("discount_type", c["discount_type"])
    db.execute(
        "UPDATE coupons SET active=?, max_uses=?, free_first_month=?, expires_at=?, discount_value=?, discount_type=? WHERE id=?",
        (active, max_uses, free_first_month, expires_at, discount_value, discount_type, coupon_id)
    )
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/admin/coupons/<int:coupon_id>", methods=["DELETE"])
@require_admin
def admin_delete_coupon(coupon_id):
    db = get_db()
    db.execute("DELETE FROM coupons WHERE id = ?", (coupon_id,))
    db.commit()
    return jsonify({"ok": True})

# ── Client coupon validation ────────────────────────────────────────
@app.route("/api/validate-coupon", methods=["POST"])
@require_auth
def validate_coupon():
    data = request.get_json() or {}
    code = str(data.get("code", "")).strip().upper()
    if not code:
        return jsonify({"error": "Please enter a coupon code"}), 400
    db = get_db()
    c = db.execute("SELECT * FROM coupons WHERE code = ? AND active = 1", (code,)).fetchone()
    if not c:
        return jsonify({"error": "Invalid coupon code"}), 404
    if c["max_uses"] > 0 and c["times_used"] >= c["max_uses"]:
        return jsonify({"error": "This coupon has been fully redeemed"}), 410
    if c["expires_at"]:
        from datetime import datetime as dt
        try:
            exp = dt.strptime(c["expires_at"], "%Y-%m-%d")
            if dt.now() > exp:
                return jsonify({"error": "This coupon has expired"}), 410
        except ValueError:
            pass
    return jsonify({"ok": True, "code": c["code"], "discount_type": c["discount_type"], "discount_value": c["discount_value"], "free_first_month": bool(c["free_first_month"])})


@app.route("/api/admin/site-config/porkbun", methods=["GET"])
@require_admin
def admin_get_porkbun_config():
    """Get Porkbun API key config (keys masked for security)."""
    db = get_db()
    row_api = db.execute("SELECT value FROM site_config WHERE key = 'porkbun_api_key'").fetchone()
    row_sec = db.execute("SELECT value FROM site_config WHERE key = 'porkbun_secret_key'").fetchone()
    apikey = row_api["value"] if row_api else ""
    secret = row_sec["value"] if row_sec else ""
    # Mask keys for display (show last 6 chars)
    masked_api = ("*" * max(0, len(apikey) - 6) + apikey[-6:]) if apikey else ""
    masked_sec = ("*" * max(0, len(secret) - 6) + secret[-6:]) if secret else ""
    return jsonify({
        "apikey_masked": masked_api,
        "secret_masked": masked_sec,
        "configured": bool(apikey and secret),
        "source": "database" if (apikey and secret) else ("env" if (PORKBUN_API_KEY and PORKBUN_SECRET_KEY) else "none"),
    })


@app.route("/api/admin/site-config/porkbun", methods=["PUT"])
@require_admin
def admin_set_porkbun_config():
    """Save Porkbun API keys to site_config."""
    data = request.get_json() or {}
    apikey = (data.get("apikey") or "").strip()
    secret = (data.get("secretapikey") or "").strip()
    if not apikey or not secret:
        return jsonify({"error": "Both API Key and Secret API Key are required"}), 400
    db = get_db()
    db.execute("INSERT OR REPLACE INTO site_config (key, value) VALUES (?, ?)", ("porkbun_api_key", apikey))
    db.execute("INSERT OR REPLACE INTO site_config (key, value) VALUES (?, ?)", ("porkbun_secret_key", secret))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/porkbun-test", methods=["POST"])
@require_admin
def admin_test_porkbun():
    """Test Porkbun API connection using the ping endpoint."""
    keys = get_porkbun_keys()
    if not keys["apikey"] or not keys["secretapikey"]:
        return jsonify({"error": "Porkbun API keys not configured"}), 400
    try:
        import urllib.request as _urlreq
        payload = json.dumps({"secretapikey": keys["secretapikey"], "apikey": keys["apikey"]})
        req = _urlreq.Request(
            "https://api.porkbun.com/api/json/v3/ping",
            data=payload.encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with _urlreq.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        if result.get("status") == "SUCCESS":
            return jsonify({"ok": True, "ip": result.get("yourIp", "")})
        return jsonify({"error": "Porkbun returned: " + result.get("message", "Unknown error")}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/site-config/stripe", methods=["GET"])
@require_admin
def admin_get_stripe_config():
    """Get Stripe key config (keys masked for security)."""
    db = get_db()
    row_sk = db.execute("SELECT value FROM site_config WHERE key = 'stripe_secret_key'").fetchone()
    row_pk = db.execute("SELECT value FROM site_config WHERE key = 'stripe_publishable_key'").fetchone()
    row_wh = db.execute("SELECT value FROM site_config WHERE key = 'stripe_webhook_secret'").fetchone()
    sk = row_sk["value"] if row_sk else ""
    pk = row_pk["value"] if row_pk else ""
    wh = row_wh["value"] if row_wh else ""
    masked_sk = ("*" * max(0, len(sk) - 6) + sk[-6:]) if sk else ""
    masked_pk = ("*" * max(0, len(pk) - 6) + pk[-6:]) if pk else ""
    masked_wh = ("*" * max(0, len(wh) - 6) + wh[-6:]) if wh else ""
    # Determine source
    has_db = bool(sk and pk)
    has_env = bool(STRIPE_SECRET_KEY and STRIPE_SECRET_KEY != "sk_test_REPLACE_ME")
    return jsonify({
        "secret_masked": masked_sk,
        "publishable_masked": masked_pk,
        "webhook_masked": masked_wh,
        "configured": has_db or has_env,
        "source": "database" if has_db else ("env" if has_env else "none"),
    })


@app.route("/api/admin/site-config/stripe", methods=["PUT"])
@require_admin
def admin_set_stripe_config():
    """Save Stripe API keys to site_config."""
    data = request.get_json() or {}
    sk = (data.get("secret_key") or "").strip()
    pk = (data.get("publishable_key") or "").strip()
    wh = (data.get("webhook_secret") or "").strip()
    if not sk or not pk:
        return jsonify({"error": "Secret Key and Publishable Key are required"}), 400
    db = get_db()
    db.execute("INSERT OR REPLACE INTO site_config (key, value) VALUES (?, ?)", ("stripe_secret_key", sk))
    db.execute("INSERT OR REPLACE INTO site_config (key, value) VALUES (?, ?)", ("stripe_publishable_key", pk))
    if wh:
        db.execute("INSERT OR REPLACE INTO site_config (key, value) VALUES (?, ?)", ("stripe_webhook_secret", wh))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/site-config/ngrok", methods=["GET"])
@require_admin
def admin_get_ngrok_config():
    """Get current ngrok tunnel URL."""
    db = get_db()
    row = db.execute("SELECT value FROM site_config WHERE key = 'ngrok_url'").fetchone()
    url = row["value"] if row else ""
    return jsonify({"ngrok_url": url, "active": bool(url)})


@app.route("/api/admin/site-config/ngrok", methods=["PUT"])
@require_admin
def admin_set_ngrok_config():
    """Save or clear ngrok tunnel URL."""
    data = request.get_json() or {}
    url = (data.get("ngrok_url") or "").strip().rstrip("/")
    db = get_db()
    if url:
        if not url.startswith("https://"):
            return jsonify({"error": "ngrok URL must start with https://"}), 400
        db.execute("INSERT OR REPLACE INTO site_config (key, value) VALUES (?, ?)", ("ngrok_url", url))
    else:
        db.execute("DELETE FROM site_config WHERE key = 'ngrok_url'")
    db.commit()
    return jsonify({"ok": True, "ngrok_url": url})


@app.route("/api/admin/site-config/email", methods=["GET"])
@require_admin
def admin_get_email_config():
    """Get SMTP email configuration."""
    db = get_db()
    keys = ['smtp_host', 'smtp_port', 'smtp_user', 'smtp_pass', 'smtp_from_name', 'smtp_from_email']
    cfg = {}
    for k in keys:
        row = db.execute("SELECT value FROM site_config WHERE key = ?", (k,)).fetchone()
        cfg[k] = row["value"] if row else ""
    # Mask password
    if cfg['smtp_pass']:
        cfg['smtp_pass_masked'] = cfg['smtp_pass'][:3] + '***' + cfg['smtp_pass'][-2:] if len(cfg['smtp_pass']) > 5 else '***'
    else:
        cfg['smtp_pass_masked'] = ''
    cfg.pop('smtp_pass', None)
    configured = bool(cfg.get('smtp_host') and cfg.get('smtp_user'))
    return jsonify({"configured": configured, "config": cfg})


@app.route("/api/admin/site-config/email", methods=["PUT"])
@require_admin
def admin_set_email_config():
    """Save SMTP email configuration."""
    data = request.get_json() or {}
    db = get_db()
    fields = {
        'smtp_host': (data.get('smtp_host') or '').strip(),
        'smtp_port': str(data.get('smtp_port') or '587').strip(),
        'smtp_user': (data.get('smtp_user') or '').strip(),
        'smtp_from_name': (data.get('smtp_from_name') or '').strip(),
        'smtp_from_email': (data.get('smtp_from_email') or '').strip(),
    }
    # Only update password if provided (not masked)
    smtp_pass = str(data.get('smtp_pass') or '').strip()
    if smtp_pass and '***' not in smtp_pass:
        fields['smtp_pass'] = smtp_pass
    for k, v in fields.items():
        db.execute("INSERT OR REPLACE INTO site_config (key, value) VALUES (?, ?)", (k, v))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/site-config/email/test", methods=["POST"])
@require_admin
def admin_test_email():
    """Send a test email to verify SMTP config."""
    data = request.get_json() or {}
    to = (data.get('to') or '').strip()
    if not to:
        return jsonify({"error": "Recipient email required"}), 400
    result = send_email(to, "Test Email from Elevated Solutions",
        '<div style="font-family:Arial,sans-serif;padding:30px;text-align:center;"><h2 style="color:#1e3c72;">Email Configuration Working!</h2><p style="color:#555;">This is a test email from your Elevated Solutions admin panel.</p><p style="color:#888;font-size:13px;">Sent at ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '</p></div>',
        'Test email from Elevated Solutions. Email configuration is working!')
    if result is True:
        return jsonify({"ok": True, "message": "Test email sent to " + to})
    return jsonify({"error": "Failed to send: " + str(result)}), 500


@app.route("/api/deploy-payment-status", methods=["GET"])
@require_auth
def deploy_payment_status():
    """Client checks if their latest deploy payment went through.
    Also serves as webhook fallback: if status is still pending_payment,
    checks Stripe directly and confirms payment + creates admin message."""
    user = g.current_user
    session_id = request.args.get("session_id", "").strip()
    db = get_db()
    if session_id:
        row = db.execute(
            "SELECT * FROM deploy_requests WHERE user_id = ? AND stripe_session_id = ?",
            (user["id"], session_id)
        ).fetchone()
    else:
        row = db.execute(
            "SELECT * FROM deploy_requests WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user["id"],)
        ).fetchone()
    if not row:
        return jsonify({"found": False})

    # If still pending_payment and we have a stripe session, check Stripe directly
    if row["status"] == "pending_payment" and row["stripe_session_id"]:
        try:
            if not configure_stripe():
                return jsonify({"found": True, "id": row["id"], "domain": row["domain"], "status": row["status"], "total": row["total"]})
            checkout_session = stripe.checkout.Session.retrieve(row["stripe_session_id"])
            if checkout_session.payment_status == "paid":
                subscription_id = checkout_session.subscription
                db.execute("UPDATE deploy_requests SET status = 'paid', stripe_subscription_id = ? WHERE id = ?",
                           (subscription_id, row["id"]))
                if subscription_id:
                    db.execute(
                        "UPDATE payment_config SET monthly_active = 1, stripe_subscription_id = ? WHERE user_id = ?",
                        (subscription_id, user["id"])
                    )
                # Create admin message
                try:
                    addons = json.loads(row["selected_addons"])
                except (json.JSONDecodeError, TypeError):
                    addons = []
                amount = (checkout_session.amount_total or 0) / 100.0
                db.execute(
                    "INSERT INTO messages (user_id, subject, body, category) VALUES (?,?,?,?)",
                    (user["id"], "Deploy Request: " + row["domain"],
                     "Domain: " + row["domain"] +
                     "\nSelected Add-ons: " + ", ".join(addons if addons else ["None"]) +
                     "\nSubtotal: $" + str(row["subtotal"]) +
                     "\nTax: $" + str(row["tax"]) +
                     "\nTotal: $" + str(row["total"]) +
                     "\nMonthly Maintenance: $" + str(row["monthly"]) +
                     "\n\n✅ Payment confirmed via Stripe ($" + f"{amount:.2f}" + ")" +
                     ("\n🔄 Monthly subscription active: " + subscription_id if subscription_id else ""),
                     "deploy")
                )
                db.commit()

                # Send payment receipt email (fallback path)
                try:
                    u_name = user.get("name") or user.get("first_name") or user["email"].split("@")[0]
                    addon_list = ", ".join(addons) if addons else "None"
                    monthly_str = f"${float(row['monthly']):.2f}/mo" if float(row['monthly']) > 0 else "—"
                    send_email_async(
                        user["email"],
                        "Payment Receipt — " + row["domain"],
                        '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">'
                        '<div style="background:linear-gradient(135deg,#1e3c72,#2a5298);padding:30px;text-align:center;">'
                        '<h1 style="color:#fff;margin:0;font-size:24px;">Payment Receipt</h1></div>'
                        '<div style="padding:30px;">'
                        '<p style="color:#333;font-size:16px;">Hi ' + u_name + ',</p>'
                        '<p style="color:#555;font-size:15px;">Thank you for your purchase! Here\'s your receipt:</p>'
                        '<div style="background:#f8f9fa;border-radius:12px;padding:20px;margin:20px 0;">'
                        '<table style="width:100%;font-size:14px;color:#333;border-collapse:collapse;">'
                        '<tr style="border-bottom:1px solid #eee;"><td style="padding:10px 0;font-weight:600;">Domain</td><td style="text-align:right;">' + row["domain"] + '</td></tr>'
                        '<tr style="border-bottom:1px solid #eee;"><td style="padding:10px 0;font-weight:600;">Add-ons</td><td style="text-align:right;">' + addon_list + '</td></tr>'
                        '<tr style="border-bottom:1px solid #eee;"><td style="padding:10px 0;font-weight:600;">Subtotal</td><td style="text-align:right;">$' + f"{float(row['subtotal']):.2f}" + '</td></tr>'
                        '<tr style="border-bottom:1px solid #eee;"><td style="padding:10px 0;font-weight:600;">Tax</td><td style="text-align:right;">$' + f"{float(row['tax']):.2f}" + '</td></tr>'
                        '<tr style="border-bottom:2px solid #1e3c72;"><td style="padding:10px 0;font-weight:700;font-size:16px;">Total Paid</td><td style="text-align:right;font-weight:700;font-size:16px;color:#1e3c72;">$' + f"{amount:.2f}" + '</td></tr>'
                        '<tr><td style="padding:10px 0;font-weight:600;">Monthly Maintenance</td><td style="text-align:right;">' + monthly_str + '</td></tr>'
                        '</table></div>'
                        '<p style="color:#555;font-size:14px;">We\'ll begin working on your site right away. You can track progress from your <a href="' + get_frontend_url() + '/dashboard.html" style="color:#1e3c72;font-weight:600;">dashboard</a>.</p>'
                        '<p style="color:#888;font-size:12px;margin-top:30px;">Transaction date: ' + datetime.now().strftime("%B %d, %Y at %I:%M %p") + '</p>'
                        '<p style="color:#888;font-size:13px;">— Elevated Solutions</p>'
                        '</div></div>',
                        'Payment Receipt — ' + row["domain"] + '\nTotal: $' + f"{amount:.2f}" + '\nMonthly: ' + monthly_str
                    )
                except Exception as e:
                    print(f"[receipt-email-fallback] Error: {e}")

                # Notify admin about new purchase (fallback path)
                try:
                    admin_row = db.execute("SELECT email FROM users WHERE role = 'admin' LIMIT 1").fetchone()
                    if admin_row:
                        send_email_async(
                            admin_row["email"],
                            "New Purchase — " + row["domain"] + " ($" + f"{amount:.2f}" + ")",
                            '<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;">'
                            '<div style="background:linear-gradient(135deg,#28a745,#218838);padding:30px;text-align:center;">'
                            '<h1 style="color:#fff;margin:0;font-size:24px;">New Deploy Purchase!</h1></div>'
                            '<div style="padding:30px;">'
                            '<p style="color:#333;font-size:16px;">A client just completed a deploy payment:</p>'
                            '<div style="background:#f8f9fa;border-radius:12px;padding:20px;margin:20px 0;border-left:4px solid #28a745;">'
                            '<table style="width:100%;font-size:14px;color:#333;border-collapse:collapse;">'
                            '<tr style="border-bottom:1px solid #eee;"><td style="padding:10px 0;font-weight:600;">Client</td><td style="text-align:right;">' + u_name + ' (' + user["email"] + ')</td></tr>'
                            '<tr style="border-bottom:1px solid #eee;"><td style="padding:10px 0;font-weight:600;">Domain</td><td style="text-align:right;">' + row["domain"] + '</td></tr>'
                            '<tr style="border-bottom:1px solid #eee;"><td style="padding:10px 0;font-weight:600;">Add-ons</td><td style="text-align:right;">' + addon_list + '</td></tr>'
                            '<tr style="border-bottom:1px solid #eee;"><td style="padding:10px 0;font-weight:600;">Total</td><td style="text-align:right;font-weight:700;color:#28a745;">$' + f"{amount:.2f}" + '</td></tr>'
                            '<tr><td style="padding:10px 0;font-weight:600;">Monthly</td><td style="text-align:right;">' + monthly_str + '</td></tr>'
                            '</table></div>'
                            '<p style="color:#555;font-size:14px;">Manage in the <a href="' + get_frontend_url() + '/admin.html" style="color:#28a745;font-weight:600;">admin panel</a>.</p>'
                            '</div></div>',
                            'New purchase from ' + u_name + '\nDomain: ' + row["domain"] + '\nTotal: $' + f"{amount:.2f}"
                        )
                except Exception as e:
                    print(f"[purchase-admin-email-fallback] Error: {e}")

                return jsonify({"found": True, "id": row["id"], "domain": row["domain"], "status": "paid", "total": row["total"]})
        except Exception as e:
            print(f"[deploy-payment-status] Stripe check error: {e}")

    return jsonify({"found": True, "id": row["id"], "domain": row["domain"], "status": row["status"], "total": row["total"]})


@app.route("/api/me/deploy-pricing", methods=["GET"])
@require_auth
def get_my_deploy_pricing():
    """Client fetches their deploy pricing config."""
    user = g.current_user
    db = get_db()
    row = db.execute("SELECT * FROM deploy_config WHERE user_id = ?", (user["id"],)).fetchone()
    if row:
        cfg = dict(row)
        try:
            cfg["addons"] = json.loads(cfg["addons"])
        except (json.JSONDecodeError, TypeError):
            cfg["addons"] = []
        try:
            cfg["domain_tlds"] = json.loads(cfg.get("domain_tlds") or "[]")
        except (json.JSONDecodeError, TypeError):
            cfg["domain_tlds"] = []
        return jsonify({"config": cfg})
    return jsonify({"config": {"base_fee": 499, "monthly_maintenance": 49, "tax_rate": 8.25, "addons": [], "domain_tlds": DEFAULT_DOMAIN_TLDS}})


@app.route("/api/domain-availability", methods=["POST"])
@require_auth
def check_domain_availability():
    """Check domain availability via Porkbun checkDomain API (primary) + tldx fallback."""
    data = request.get_json() or {}
    keyword = (data.get("keyword") or "").strip().lower()
    keyword = re.sub(r'[^a-z0-9\-]', '', keyword)
    if not keyword or len(keyword) > 63:
        return jsonify({"error": "Invalid domain keyword"}), 400

    # Get TLD list from user's deploy config or defaults
    user = g.current_user
    db = get_db()
    row = db.execute("SELECT domain_tlds FROM deploy_config WHERE user_id = ?", (user["id"],)).fetchone()
    tld_list = DEFAULT_DOMAIN_TLDS
    if row:
        try:
            parsed = json.loads(row["domain_tlds"] or "[]")
            if parsed:
                tld_list = parsed
        except (json.JSONDecodeError, TypeError):
            pass

    # Fetch live Porkbun bulk pricing (no auth, cached 1hr)
    porkbun_bulk = get_porkbun_pricing()

    # Get Porkbun API keys for domain check
    keys = get_porkbun_keys()
    pb_apikey = keys["apikey"]
    pb_secret = keys["secretapikey"]
    has_porkbun_keys = bool(pb_apikey and pb_secret)

    # Build domain list
    domains_to_check = [keyword + t["tld"] for t in tld_list]

    # --- Run tldx + Porkbun checkDomain in parallel ---
    avail_map = {}       # domain -> {available, details} from tldx
    porkbun_map = {}     # domain -> {avail, price, premium, ...} from Porkbun checkDomain

    def run_tldx():
        """Run tldx CLI for fast bulk availability."""
        tlds_str = ",".join(t["tld"].lstrip(".") for t in tld_list)
        tldx_paths = [
            "tldx",
            os.path.expanduser("~") + r"\AppData\Local\Microsoft\WinGet\Packages\brandonyoungdev.tldx_Microsoft.Winget.Source_8wekyb3d8bbwe\tldx.exe",
        ]
        tldx_bin = "tldx"
        for p in tldx_paths:
            if os.path.isfile(p):
                tldx_bin = p
                break
        try:
            result = subprocess.run(
                [tldx_bin, keyword, "--tlds", tlds_str, "--format", "json"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                for r in json.loads(result.stdout):
                    avail_map[r["domain"]] = {
                        "available": r["available"],
                        "details": r.get("details", ""),
                    }
        except Exception:
            pass

    def run_porkbun_check(domain):
        """Check a single domain via Porkbun API."""
        return domain, check_domain_porkbun(domain, pb_apikey, pb_secret)

    with ThreadPoolExecutor(max_workers=len(domains_to_check) + 1) as executor:
        # Submit tldx (always runs as fallback)
        tldx_future = executor.submit(run_tldx)

        # Submit Porkbun checks for all domains (if keys configured)
        pb_futures = {}
        if has_porkbun_keys:
            for d in domains_to_check:
                pb_futures[executor.submit(run_porkbun_check, d)] = d

        # Wait for tldx to finish
        tldx_future.result(timeout=35)

        # Collect whatever Porkbun results are available (some may be rate-limited)
        for future in as_completed(pb_futures, timeout=20):
            try:
                domain, result = future.result()
                if result:
                    porkbun_map[domain] = result
            except Exception:
                pass

    # Build combined results — Porkbun checkDomain takes priority
    results = []
    aftermarket_domains = []
    for t in tld_list:
        tld_key = t["tld"].lstrip(".")
        domain = keyword + t["tld"]
        pb_check = porkbun_map.get(domain)  # Porkbun checkDomain result (may be None)
        pb_bulk = porkbun_bulk.get(tld_key, {})  # cached bulk pricing

        # Determine availability
        if pb_check is not None:
            # Porkbun checkDomain succeeded — use its data
            available = pb_check["avail"]
            reg_price = pb_check["price"]
            regular_price = pb_check["regular_price"]
            renewal_price = pb_check["renewal"] or regular_price
            is_sale = pb_check["first_year_promo"]
            is_premium = pb_check["premium"]
            porkbun_checked = True
        else:
            # Fallback to tldx + bulk pricing
            available = avail_map.get(domain, {}).get("available")
            reg_price = float(pb_bulk.get("registration", t.get("price", 0)))
            regular_price = reg_price
            renewal_price = float(pb_bulk.get("renewal", reg_price))
            is_sale = reg_price < renewal_price
            is_premium = False
            porkbun_checked = False

        # Determine status — default unavailable to "registered";
        # aftermarket status is only set after Afternic confirms a listing
        status = "unknown"
        if available is True:
            status = "available"
        elif available is False:
            status = "registered"
        # else: status stays "unknown"

        entry = {
            "domain": domain,
            "tld": t["tld"],
            "available": available,
            "status": status,
            "registration": round(reg_price, 2),
            "regular_price": round(regular_price, 2),
            "renewal": round(renewal_price, 2),
            "is_sale": is_sale,
            "is_premium": is_premium,
            "porkbun_checked": porkbun_checked,
            "aftermarket_price": None,
            "aftermarket_buy_now": False,
            "aftermarket_make_offer": False,
            "aftermarket_leasing": False,
        }
        results.append(entry)

    # For all unavailable domains, check Afternic in parallel for real listings
    unavailable_entries = [e for e in results if e["status"] == "registered"]

    def check_afternic(entry):
        try:
            return entry, get_aftermarket_price(entry["domain"])
        except Exception:
            return entry, None

    if unavailable_entries:
        with ThreadPoolExecutor(max_workers=min(len(unavailable_entries), 8)) as executor:
            futures = {executor.submit(check_afternic, e): e for e in unavailable_entries}
            for future in as_completed(futures, timeout=30):
                try:
                    entry, price_info = future.result()
                    if price_info:
                        entry["status"] = "aftermarket"
                        entry["aftermarket_price"] = price_info["price"]
                        entry["aftermarket_buy_now"] = price_info["buy_now"]
                        entry["aftermarket_make_offer"] = price_info["make_offer"]
                        entry["aftermarket_leasing"] = price_info["leasing"]
                except Exception:
                    pass

    return jsonify({"results": results})


@app.route("/api/deploy-request", methods=["POST"])
@require_auth
def submit_deploy_request():
    """Client submits a deploy request — creates Stripe checkout, defers admin message until paid."""
    user = g.current_user
    data = request.get_json() or {}
    domain = (data.get("domain") or "").strip()
    if not domain:
        return jsonify({"error": "Domain is required"}), 400
    domain_price = float(data.get("domain_price", 0))
    selected_addons = data.get("addons", [])
    if not isinstance(selected_addons, list):
        selected_addons = []

    # Load pricing config
    db = get_db()
    row = db.execute("SELECT * FROM deploy_config WHERE user_id = ?", (user["id"],)).fetchone()
    if row:
        cfg = dict(row)
        try:
            cfg["addons"] = json.loads(cfg["addons"])
        except (json.JSONDecodeError, TypeError):
            cfg["addons"] = []
    else:
        cfg = {"base_fee": 499, "monthly_maintenance": 49, "tax_rate": 8.25, "addons": []}

    # Validate domain price against TLD list
    try:
        tld_list = json.loads(cfg.get("domain_tlds") or "[]")
    except (json.JSONDecodeError, TypeError):
        tld_list = []
    if not tld_list:
        tld_list = DEFAULT_DOMAIN_TLDS
    # Accept the domain_price if it's within a reasonable range (real-time Porkbun pricing may differ from static config)
    if domain_price < 0 or domain_price > 100000:
        domain_price = 0

    # Validate coupon if provided
    coupon_code = str(data.get("coupon_code", "")).strip().upper()
    discount_amount = 0
    coupon_row = None
    if coupon_code:
        coupon_row = db.execute("SELECT * FROM coupons WHERE code = ? AND active = 1", (coupon_code,)).fetchone()
        if coupon_row:
            if coupon_row["max_uses"] > 0 and coupon_row["times_used"] >= coupon_row["max_uses"]:
                coupon_row = None
            elif coupon_row["expires_at"]:
                from datetime import datetime as dt
                try:
                    if dt.now() > dt.strptime(coupon_row["expires_at"], "%Y-%m-%d"):
                        coupon_row = None
                except ValueError:
                    pass

    # Calculate total
    subtotal = cfg["base_fee"] + domain_price
    addon_map = {a["name"]: a["price"] for a in cfg["addons"]}
    for name in selected_addons:
        if name in addon_map:
            subtotal += addon_map[name]

    # Apply coupon discount before tax
    if coupon_row:
        if coupon_row["discount_type"] == "percent":
            discount_amount = round(subtotal * coupon_row["discount_value"] / 100, 2)
        else:
            discount_amount = min(round(coupon_row["discount_value"], 2), subtotal)
        subtotal = round(subtotal - discount_amount, 2)

    tax = round(subtotal * cfg["tax_rate"] / 100, 2)
    total = round(subtotal + tax, 2)
    # Calculate monthly with domain renewal
    monthly = cfg["monthly_maintenance"]
    domain_renewal = data.get("domain_renewal", 0)
    try:
        domain_renewal = float(domain_renewal)
    except (TypeError, ValueError):
        domain_renewal = 0
    monthly_with_renewal = round(monthly + domain_renewal / 12, 2) if domain_renewal > 0 else monthly

    # Insert deploy_request as pending_payment
    cursor = db.execute(
        "INSERT INTO deploy_requests (user_id, domain, selected_addons, subtotal, tax, total, monthly, status, coupon_code, discount) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (user["id"], domain, json.dumps(selected_addons), subtotal, tax, total, monthly, "pending_payment", coupon_code if coupon_row else "", discount_amount)
    )
    deploy_id = cursor.lastrowid
    # Increment coupon usage
    if coupon_row:
        db.execute("UPDATE coupons SET times_used = times_used + 1 WHERE id = ?", (coupon_row["id"],))
    db.commit()

    # Create Stripe Checkout session
    keys = configure_stripe()
    if not keys["secret_key"] or keys["secret_key"] == "sk_test_REPLACE_ME":
        # Stripe not configured — fall back to old behaviour (immediate)
        db.execute("UPDATE deploy_requests SET status = 'pending' WHERE id = ?", (deploy_id,))
        db.execute(
            "INSERT INTO messages (user_id, subject, body, category) VALUES (?,?,?,?)",
            (user["id"], "Deploy Request: " + domain,
             "Domain: " + domain + "\nSelected Add-ons: " + ", ".join(selected_addons if selected_addons else ["None"]) +
             "\nSubtotal: $" + str(subtotal) + "\nTax: $" + str(tax) + "\nTotal: $" + str(total) +
             "\nMonthly Maintenance: $" + str(monthly_with_renewal),
             "deploy")
        )
        db.commit()
        return jsonify({"ok": True, "total": total, "monthly": monthly_with_renewal}), 201

    try:
        amount_cents = int(round(total * 100))
        # Build line items — one-time charges + recurring monthly maintenance
        line_items = []
        line_items.append({
            "price_data": {
                "currency": STRIPE_CURRENCY,
                "unit_amount": int(round(cfg["base_fee"] * 100)),
                "product_data": {"name": "Website Deployment Fee"}
            },
            "quantity": 1
        })
        if domain_price > 0:
            line_items.append({
                "price_data": {
                    "currency": STRIPE_CURRENCY,
                    "unit_amount": int(round(domain_price * 100)),
                    "product_data": {"name": "Domain Registration: " + domain}
                },
                "quantity": 1
            })
        for name in selected_addons:
            if name in addon_map:
                line_items.append({
                    "price_data": {
                        "currency": STRIPE_CURRENCY,
                        "unit_amount": int(round(addon_map[name] * 100)),
                        "product_data": {"name": "Add-on: " + name}
                    },
                    "quantity": 1
                })
        if tax > 0:
            line_items.append({
                "price_data": {
                    "currency": STRIPE_CURRENCY,
                    "unit_amount": int(round(tax * 100)),
                    "product_data": {"name": "Tax"}
                },
                "quantity": 1
            })
        if discount_amount > 0:
            # Show discount as a negative line item via coupon on the Stripe session
            stripe_coupon = stripe.Coupon.create(
                amount_off=int(round(discount_amount * 100)),
                currency=STRIPE_CURRENCY,
                duration="once",
                name="Coupon: " + coupon_code
            )

        # Recurring monthly maintenance line item
        monthly_desc = "Monthly Maintenance"
        if domain_renewal > 0:
            monthly_desc += " (incl. domain renewal)"
        line_items.append({
            "price_data": {
                "currency": STRIPE_CURRENCY,
                "unit_amount": int(round(monthly_with_renewal * 100)),
                "recurring": {"interval": "month"},
                "product_data": {"name": monthly_desc}
            },
            "quantity": 1
        })

        session_params = {
            "payment_method_types": ["card"],
            "mode": "subscription",
            "line_items": line_items,
            "subscription_data": {
                "metadata": {
                    "user_id": str(user["id"]),
                    "deploy_id": str(deploy_id),
                    "payment_type": "deploy"
                }
            },
            "metadata": {
                "user_id": str(user["id"]),
                "deploy_id": str(deploy_id),
                "payment_type": "deploy"
            },
            "success_url": get_frontend_url() + "/dashboard.html?deploy_payment=success&session_id={CHECKOUT_SESSION_ID}",
            "cancel_url": get_frontend_url() + "/dashboard.html?deploy_payment=cancel",
        }
        if discount_amount > 0:
            session_params["discounts"] = [{"coupon": stripe_coupon.id}]
        # Free first month: use Stripe trial to skip first recurring charge
        if coupon_row and coupon_row["free_first_month"]:
            session_params["subscription_data"]["trial_period_days"] = 30

        # Attach existing Stripe customer if available
        pc = db.execute("SELECT stripe_customer_id FROM payment_config WHERE user_id = ?", (user["id"],)).fetchone()
        if pc and pc["stripe_customer_id"]:
            session_params["customer"] = pc["stripe_customer_id"]
        else:
            session_params["customer_email"] = user["email"]

        session = stripe.checkout.Session.create(**session_params)
        db.execute("UPDATE deploy_requests SET stripe_session_id = ? WHERE id = ?", (session.id, deploy_id))
        db.commit()

        return jsonify({"ok": True, "checkout_url": session.url, "total": total, "monthly": monthly_with_renewal}), 201
    except Exception as e:
        # Stripe call failed — mark as failed
        db.execute("UPDATE deploy_requests SET status = 'payment_failed' WHERE id = ?", (deploy_id,))
        db.commit()
        return jsonify({"error": "Payment setup failed: " + str(e)}), 500


@app.route("/api/admin/deploy-requests", methods=["GET"])
@require_admin
def admin_get_deploy_requests():
    db = get_db()
    rows = db.execute(
        "SELECT d.*, u.name as user_name, u.email as user_email "
        "FROM deploy_requests d JOIN users u ON d.user_id = u.id ORDER BY d.created_at DESC"
    ).fetchall()
    reqs = []
    for r in rows:
        d = dict(r)
        try:
            d["selected_addons"] = json.loads(d["selected_addons"])
        except (json.JSONDecodeError, TypeError):
            d["selected_addons"] = []
        reqs.append(d)
    return jsonify({"requests": reqs})


@app.route("/preview/<path:filepath>")
@require_auth
def serve_preview(filepath):
    """Serve files from websitepreviews/ for authenticated users with demo access."""
    user = g.current_user
    if not user.get("demo_preview") or not user.get("demo_preview_site"):
        return jsonify({"error": "Preview not enabled"}), 403
    site = user["demo_preview_site"]
    # Security: ensure requested path starts with user's assigned site
    if not filepath.startswith(site + "/") and filepath != site:
        return jsonify({"error": "Access denied"}), 403
    safe_path = os.path.normpath(os.path.join(PREVIEWS_DIR, filepath))
    if not safe_path.startswith(os.path.normpath(PREVIEWS_DIR)):
        return jsonify({"error": "Invalid path"}), 400
    if os.path.isdir(safe_path):
        safe_path = os.path.join(safe_path, "index.html")
    if not os.path.isfile(safe_path):
        return jsonify({"error": "File not found"}), 404
    from flask import send_file
    return send_file(safe_path)


# ── Static file serving (for ngrok single-tunnel mode) ──
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route("/")
def serve_index():
    from flask import send_from_directory
    return send_from_directory(STATIC_DIR, "index.html")

@app.route("/<path:filepath>")
def serve_static_file(filepath):
    """Serve static frontend files so a single ngrok tunnel to port 5000 works for everything."""
    from flask import send_from_directory
    safe_path = os.path.normpath(os.path.join(STATIC_DIR, filepath))
    if not safe_path.startswith(STATIC_DIR):
        return jsonify({"error": "Invalid path"}), 400
    if os.path.isfile(safe_path):
        return send_from_directory(STATIC_DIR, filepath)
    return jsonify({"error": "Not found"}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
