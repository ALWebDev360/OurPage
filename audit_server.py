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
import time
import uuid
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import urlparse, urljoin
from flask import Flask, request, jsonify, g
from flask_cors import CORS
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
CORS(app, origins=["http://localhost:*", "http://127.0.0.1:*"])

# --- Stripe Configuration ---
# Set these to your Stripe keys (use env vars in production)
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_REPLACE_ME")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "pk_test_REPLACE_ME")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_REPLACE_ME")
STRIPE_CURRENCY = "usd"
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://127.0.0.1:8080")
stripe.api_key = STRIPE_SECRET_KEY

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
    """)
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
            "SELECT u.id, u.name, u.email, u.company, u.role, u.payment_portal FROM users u "
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
    return jsonify({"user": g.current_user})


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
    query = "SELECT id, name, email, company, role, payment_portal, created_at FROM users WHERE 1=1"
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
        "SELECT id, name, email, company, role, payment_portal, created_at FROM users WHERE id = ?", (user_id,)
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
        "SELECT id, name, email, company, role, payment_portal, created_at FROM users WHERE id = ?", (user_id,)
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
    return jsonify({"publishableKey": STRIPE_PUBLISHABLE_KEY})


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
        success_url=FRONTEND_URL + "/dashboard.html?payment=success&type=onetime",
        cancel_url=FRONTEND_URL + "/dashboard.html?payment=cancel",
    )

    db.execute("UPDATE payment_config SET stripe_onetime_session_id = ? WHERE user_id = ?", (session.id, uid))
    db.commit()

    return jsonify({"checkout_url": session.url, "session_id": session.id})


@app.route("/api/me/payments/monthly", methods=["POST"])
@require_auth
def setup_monthly():
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
        success_url=FRONTEND_URL + "/dashboard.html?payment=success&type=monthly",
        cancel_url=FRONTEND_URL + "/dashboard.html?payment=cancel",
    )

    return jsonify({"checkout_url": session.url, "session_id": session.id})


@app.route("/api/stripe/webhook", methods=["POST"])
def stripe_webhook():
    """Handle Stripe webhook events to confirm payments."""
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        if STRIPE_WEBHOOK_SECRET and STRIPE_WEBHOOK_SECRET != "whsec_REPLACE_ME":
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
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


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
