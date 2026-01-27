#!/usr/bin/env python3
"""
Circuit-AI Web API
Minimal Flask API for circuit validation and Fritzing export
"""

from flask import Flask, request, jsonify, send_file, make_response, g
from pathlib import Path
from functools import wraps
from datetime import datetime, timezone
import hashlib
import json
import os
import secrets
import sqlite3
import sys
import tempfile
import uuid
from typing import Optional, Dict, Any, Tuple, Set, List
import textwrap
import subprocess
import shutil
import csv as _csv
import io as _io

# Ensure both styles of imports work across the codebase:
# - `from intelligence...` (requires `src` on sys.path)
# - `from src.engines...` (requires repo root on sys.path, where `src/` is a package)
REPO_ROOT = Path(__file__).resolve().parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SRC_DIR))

from intelligence.circuit_validator import CircuitValidator
from integrations.fritzing_integration import FritzingPartsLibrary, FritzingFileGenerator
from intelligence.recipe_optimizer import RecipeOptimizer
from intelligence.build_instructions import BuildInstructionsGenerator
from intelligence.repair_guide_generator import RepairGuideGenerator
from intelligence.device_diagnostic_engine import DeviceDiagnosticEngine
from intelligence.global_payment_service import GlobalPaymentService
from intelligence.learning_paths import LearningPathGenerator
from integrations.pricing_service import UnifiedPricingService
from engines.unified_workflow import UnifiedWorkflowEngine, UserProfile, UserLevel

app = Flask(__name__, static_folder='static', static_url_path='/static')

# ============================================================================
# Monetization hooks: API keys + daily quotas (v2 endpoints)
# ============================================================================

def _configured_api_keys() -> Set[str]:
    raw = (os.environ.get("CIRCUIT_AI_API_KEYS") or "").strip()
    if not raw:
        return set()
    parts = [p.strip() for p in raw.replace("\n", ",").split(",")]
    return {p for p in parts if p}


def _api_key_required() -> bool:
    if (os.environ.get("CIRCUIT_AI_REQUIRE_API_KEY") or "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    if _configured_api_keys():
        return True
    return _has_any_active_db_key()


def _extract_api_key() -> Optional[str]:
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return token
    x_api_key = (request.headers.get("X-API-Key") or "").strip()
    if x_api_key:
        return x_api_key
    q = (request.args.get("api_key") or "").strip()
    return q or None


def _quota_limit_env(action: str) -> int:
    action_u = (action or "").upper()
    env_key = f"CIRCUIT_AI_QUOTA_{action_u}_PER_DAY"
    raw = (os.environ.get(env_key) or "").strip()
    if raw.isdigit():
        return int(raw)
    default_raw = (os.environ.get("CIRCUIT_AI_QUOTA_DEFAULT_PER_DAY") or "200").strip()
    return int(default_raw) if default_raw.isdigit() else 200


def _usage_db_path() -> Path:
    # Use a tmp db by default; deploys can override for persistence.
    raw = (os.environ.get("CIRCUIT_AI_USAGE_DB") or "").strip()
    if raw:
        return Path(raw)
    return Path(tempfile.gettempdir()) / "circuit-ai-usage.sqlite"


def _key_hash(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:32]


def _open_usage_db() -> sqlite3.Connection:
    db_path = _usage_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(db_path))


def _init_usage_schema(con: sqlite3.Connection) -> None:
    con.execute(
        "CREATE TABLE IF NOT EXISTS usage (day TEXT NOT NULL, key_hash TEXT NOT NULL, action TEXT NOT NULL, count INTEGER NOT NULL, PRIMARY KEY(day, key_hash, action))"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS api_keys (key_hash TEXT PRIMARY KEY, label TEXT, plan TEXT, quotas_json TEXT, active INTEGER NOT NULL, created_at TEXT NOT NULL)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS stripe_events (event_id TEXT PRIMARY KEY, processed_at TEXT NOT NULL)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS fulfillments (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, source TEXT NOT NULL, customer_email TEXT, plan TEXT, status TEXT NOT NULL, key_hash TEXT)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS support_tickets (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, customer_email TEXT, subject TEXT, message TEXT, status TEXT NOT NULL)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, name TEXT, lane TEXT, design_intent TEXT)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS project_revisions (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, project_id TEXT NOT NULL, requirements_json TEXT, intake_id TEXT, notes TEXT)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS project_builds (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, project_id TEXT NOT NULL, revision_id TEXT, package_file TEXT, manifest_json TEXT)"
    )


def _has_any_active_db_key() -> bool:
    con = _open_usage_db()
    try:
        _init_usage_schema(con)
        row = con.execute("SELECT 1 FROM api_keys WHERE active=1 LIMIT 1").fetchone()
        return bool(row)
    except Exception:
        return False
    finally:
        con.close()


def _get_db_key_record(key_hash: str) -> Optional[Dict[str, Any]]:
    con = _open_usage_db()
    try:
        _init_usage_schema(con)
        row = con.execute(
            "SELECT key_hash, label, plan, quotas_json, active, created_at FROM api_keys WHERE key_hash=?",
            (key_hash,),
        ).fetchone()
        if not row:
            return None
        quotas_json = row[3] or ""
        quotas: Dict[str, Any] = {}
        if quotas_json:
            try:
                quotas = json.loads(quotas_json)
            except Exception:
                quotas = {}
        return {
            "key_hash": row[0],
            "label": row[1],
            "plan": row[2],
            "quotas": quotas,
            "active": bool(row[4]),
            "created_at": row[5],
        }
    finally:
        con.close()


def _validate_api_key(api_key: str) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Returns (valid, key_hash, db_record).
    """
    allow = _configured_api_keys()
    if allow:
        return (api_key in allow, _key_hash(api_key), None)

    kh = _key_hash(api_key)
    rec = _get_db_key_record(kh)
    if not rec or not rec.get("active"):
        return (False, kh, rec)
    return (True, kh, rec)


def _quota_limit_for_key(action: str, db_record: Optional[Dict[str, Any]]) -> int:
    if db_record and isinstance(db_record.get("quotas"), dict):
        quotas = db_record["quotas"]
        # Support both action-specific and default quotas
        if action in quotas and str(quotas[action]).isdigit():
            return int(quotas[action])
        if "default" in quotas and str(quotas["default"]).isdigit():
            return int(quotas["default"])
    return _quota_limit_env(action)

def _plan_presets() -> Dict[str, Dict[str, int]]:
    """
    Presets for quick monetization experiments.
    Values are per-key, per-day quotas.
    """
    return {
        # Free: validate only, small cap.
        "free": {
            "default": 10,
            "validate_kicad": 10,
            "manufacture_bom": 0,
            "manufacture_gerber": 0,
            "download_gerber": 0,
            "manufacture_pnp": 0,
            "manufacture_package": 0,
            "download_package": 0,
            "report_dfm": 0,
            "intake_template": 10,
            "intake_compile": 10,
            "intake_get": 10,
            "projects_create": 0,
            "projects_get": 0,
            "projects_revisions_list": 0,
            "projects_revision_create": 0,
            "projects_build_package": 0,
        },
        # Hobby: validation-only but higher than free.
        "hobby": {
            "default": 40,
            "validate_kicad": 40,
            "manufacture_bom": 0,
            "manufacture_gerber": 0,
            "download_gerber": 0,
            "manufacture_pnp": 0,
            "manufacture_package": 0,
            "download_package": 0,
            "report_dfm": 0,
            "intake_template": 40,
            "intake_compile": 40,
            "intake_get": 40,
            "projects_create": 0,
            "projects_get": 0,
            "projects_revisions_list": 0,
            "projects_revision_create": 0,
            "projects_build_package": 0,
        },
        # Builder: validation + limited BOM.
        "builder": {
            "default": 80,
            "validate_kicad": 80,
            "manufacture_bom": 10,
            "manufacture_gerber": 0,
            "download_gerber": 10,
            "manufacture_pnp": 10,
            "manufacture_package": 5,
            "download_package": 10,
            "report_dfm": 10,
            "intake_template": 80,
            "intake_compile": 80,
            "intake_get": 80,
            "projects_create": 10,
            "projects_get": 80,
            "projects_revisions_list": 80,
            "projects_revision_create": 20,
            "projects_build_package": 10,
        },
        # Pro: full workflow, moderate cap.
        "pro": {
            "default": 200,
            "validate_kicad": 200,
            "manufacture_bom": 50,
            "manufacture_gerber": 25,
            "download_gerber": 50,
            "manufacture_pnp": 50,
            "manufacture_package": 25,
            "download_package": 50,
            "report_dfm": 50,
            "intake_template": 200,
            "intake_compile": 200,
            "intake_get": 200,
            "projects_create": 50,
            "projects_get": 200,
            "projects_revisions_list": 200,
            "projects_revision_create": 200,
            "projects_build_package": 100,
        },
        # Back-compat alias.
        "paid": {
            "default": 200,
            "validate_kicad": 200,
            "manufacture_bom": 50,
            "manufacture_gerber": 25,
            "download_gerber": 50,
            "manufacture_pnp": 50,
            "manufacture_package": 25,
            "download_package": 50,
            "report_dfm": 50,
            "intake_template": 200,
            "intake_compile": 200,
            "intake_get": 200,
            "projects_create": 50,
            "projects_get": 200,
            "projects_revisions_list": 200,
            "projects_revision_create": 200,
            "projects_build_package": 100,
        },
    }


def _check_and_increment_usage(api_key: str, action: str, db_record: Optional[Dict[str, Any]]) -> Tuple[bool, int, int]:
    """
    Returns (allowed, remaining, limit).
    """
    limit = _quota_limit_for_key(action, db_record)
    if limit <= 0:
        return False, 0, limit

    day = datetime.now(timezone.utc).date().isoformat()
    kh = _key_hash(api_key)
    con = _open_usage_db()
    try:
        _init_usage_schema(con)
        row = con.execute("SELECT count FROM usage WHERE day=? AND key_hash=? AND action=?", (day, kh, action)).fetchone()
        used = int(row[0]) if row else 0
        if used >= limit:
            return False, 0, limit
        new_used = used + 1
        con.execute(
            "INSERT INTO usage(day, key_hash, action, count) VALUES(?,?,?,?) ON CONFLICT(day, key_hash, action) DO UPDATE SET count=excluded.count",
            (day, kh, action, new_used),
        )
        con.commit()
        return True, max(0, limit - new_used), limit
    finally:
        con.close()


def require_api_key(action: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not _api_key_required():
                return fn(*args, **kwargs)

            api_key = _extract_api_key()
            if not api_key:
                return jsonify({"error": "missing_api_key"}), 401

            valid, kh, rec = _validate_api_key(api_key)
            if not valid:
                return jsonify({"error": "invalid_api_key"}), 403

            ok, remaining, limit = _check_and_increment_usage(api_key, action, rec)
            if not ok:
                return jsonify({"error": "quota_exceeded", "action": action, "limit_per_day": limit}), 429

            g.circuit_ai_api_key_hash = kh
            out = fn(*args, **kwargs)
            resp = make_response(out)
            resp.headers["X-CircuitAI-Quota-Limit"] = str(limit)
            resp.headers["X-CircuitAI-Quota-Remaining"] = str(remaining)
            return resp

        return wrapper

    return decorator

# Admin endpoints for issuing/revoking keys.
def _admin_token() -> str:
    return (os.environ.get("CIRCUIT_AI_ADMIN_TOKEN") or "").strip()


def _extract_admin_token() -> Optional[str]:
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        return token or None
    x = (request.headers.get("X-Admin-Token") or "").strip()
    return x or None


def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = _admin_token()
        if not expected:
            return jsonify({"error": "admin_disabled"}), 404
        token = _extract_admin_token()
        if not token:
            return jsonify({"error": "missing_admin_token"}), 401
        if token != expected:
            return jsonify({"error": "invalid_admin_token"}), 403
        return fn(*args, **kwargs)

    return wrapper


@app.route("/api/v2/admin/keys", methods=["GET"])
@require_admin
def admin_list_keys():
    con = _open_usage_db()
    try:
        _init_usage_schema(con)
        rows = con.execute(
            "SELECT key_hash, label, plan, active, created_at FROM api_keys ORDER BY created_at DESC"
        ).fetchall()
        return jsonify(
            {
                "ok": True,
                "keys": [
                    {"key_hash": r[0], "label": r[1], "plan": r[2], "active": bool(r[3]), "created_at": r[4]}
                    for r in rows
                ],
            }
        )
    finally:
        con.close()

@app.route("/api/v2/admin/keys/issue", methods=["POST"])
@require_admin
def admin_issue_key():
    """
    Convenience endpoint: issue a key using a simple free/paid preset.
    Body:
      { "plan": "free" | "paid", "label": "optional label", "active": true }
    """
    payload = request.get_json(silent=True) or {}
    plan = str(payload.get("plan") or "free").strip().lower()
    label = str(payload.get("label") or "").strip() or f"{plan}-user"
    active = bool(payload.get("active", True))

    presets = _plan_presets()
    if plan not in presets:
        return jsonify({"error": "invalid_plan", "allowed": sorted(presets.keys())}), 400

    api_key = "cai_" + secrets.token_urlsafe(24)
    kh = _key_hash(api_key)
    now = datetime.now(timezone.utc).isoformat()
    quotas = presets[plan]

    con = _open_usage_db()
    try:
        _init_usage_schema(con)
        con.execute(
            "INSERT OR REPLACE INTO api_keys(key_hash, label, plan, quotas_json, active, created_at) VALUES(?,?,?,?,?,?)",
            (kh, label, plan, json.dumps(quotas), 1 if active else 0, now),
        )
        con.commit()
    finally:
        con.close()

    return jsonify({"ok": True, "api_key": api_key, "key_hash": kh, "label": label, "plan": plan, "active": active, "quotas": quotas})


def _stripe_secret_key() -> str:
    return (os.environ.get("CIRCUIT_AI_STRIPE_SECRET_KEY") or os.environ.get("STRIPE_SECRET_KEY") or "").strip()


def _stripe_webhook_secret() -> str:
    return (os.environ.get("CIRCUIT_AI_STRIPE_WEBHOOK_SECRET") or os.environ.get("STRIPE_WEBHOOK_SECRET") or "").strip()


def _sendgrid_api_key() -> str:
    return (os.environ.get("CIRCUIT_AI_SENDGRID_API_KEY") or "").strip()


def _support_from_email() -> str:
    return (os.environ.get("CIRCUIT_AI_SUPPORT_FROM_EMAIL") or "").strip()


def _support_bcc_email() -> str:
    return (os.environ.get("CIRCUIT_AI_SUPPORT_BCC_EMAIL") or "").strip()


def _stripe_price_plan_map() -> Dict[str, str]:
    """
    Map Stripe Price IDs to plan presets.
    Configure env vars like:
      CIRCUIT_AI_STRIPE_PRICE_HOBBY=price_...
      CIRCUIT_AI_STRIPE_PRICE_BUILDER=price_...
      CIRCUIT_AI_STRIPE_PRICE_PRO=price_...
    """
    out: Dict[str, str] = {}
    for plan in ("hobby", "builder", "pro"):
        pid = (os.environ.get(f"CIRCUIT_AI_STRIPE_PRICE_{plan.upper()}") or "").strip()
        if pid:
            out[pid] = plan
    return out


def _record_fulfillment(source: str, customer_email: Optional[str], plan: Optional[str], status: str, key_hash: Optional[str]) -> str:
    fid = "ful_" + secrets.token_urlsafe(12)
    con = _open_usage_db()
    try:
        _init_usage_schema(con)
        con.execute(
            "INSERT INTO fulfillments(id, created_at, source, customer_email, plan, status, key_hash) VALUES(?,?,?,?,?,?,?)",
            (fid, datetime.now(timezone.utc).isoformat(), source, customer_email, plan, status, key_hash),
        )
        con.commit()
    finally:
        con.close()
    return fid


def _stripe_event_seen(event_id: str) -> bool:
    con = _open_usage_db()
    try:
        _init_usage_schema(con)
        row = con.execute("SELECT 1 FROM stripe_events WHERE event_id=? LIMIT 1", (event_id,)).fetchone()
        return bool(row)
    finally:
        con.close()


def _mark_stripe_event_seen(event_id: str) -> None:
    con = _open_usage_db()
    try:
        _init_usage_schema(con)
        con.execute(
            "INSERT OR REPLACE INTO stripe_events(event_id, processed_at) VALUES(?,?)",
            (event_id, datetime.now(timezone.utc).isoformat()),
        )
        con.commit()
    finally:
        con.close()


def _issue_key_direct(plan: str, label: str, active: bool) -> Tuple[str, str, Dict[str, int]]:
    presets = _plan_presets()
    if plan not in presets:
        raise ValueError(f"invalid_plan: {plan}")
    api_key = "cai_" + secrets.token_urlsafe(24)
    kh = _key_hash(api_key)
    now = datetime.now(timezone.utc).isoformat()
    quotas = presets[plan]

    con = _open_usage_db()
    try:
        _init_usage_schema(con)
        con.execute(
            "INSERT OR REPLACE INTO api_keys(key_hash, label, plan, quotas_json, active, created_at) VALUES(?,?,?,?,?,?)",
            (kh, label, plan, json.dumps(quotas), 1 if active else 0, now),
        )
        con.commit()
    finally:
        con.close()
    return api_key, kh, quotas


def _send_email_sendgrid(to_email: str, subject: str, text_body: str) -> bool:
    api_key = _sendgrid_api_key()
    from_email = _support_from_email()
    if not api_key or not from_email:
        return False

    payload = {
        "personalizations": [{"to": [{"email": to_email}], "bcc": [{"email": _support_bcc_email()}] if _support_bcc_email() else []}],
        "from": {"email": from_email},
        "subject": subject,
        "content": [{"type": "text/plain", "value": text_body}],
    }

    try:
        import requests  # already a runtime dep

        resp = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=15,
        )
        return 200 <= resp.status_code < 300
    except Exception:
        return False


@app.route("/api/v2/webhooks/stripe", methods=["POST"])
def stripe_webhook():
    """
    Stripe webhook for automated fulfillment.

    Behavior:
    - On `checkout.session.completed`, detect purchased plan (via price id mapping),
      issue a key, and email setup instructions.
    - If email delivery is not configured, record a pending fulfillment for manual handling.
    """
    secret = _stripe_webhook_secret()
    sk = _stripe_secret_key()
    if not secret or not sk:
        return jsonify({"ok": False, "error": "stripe_not_configured"}), 404

    sig_header = request.headers.get("Stripe-Signature", "")
    payload = request.get_data(as_text=False) or b""
    try:
        import stripe

        stripe.api_key = sk
        event = stripe.Webhook.construct_event(payload=payload, sig_header=sig_header, secret=secret)
    except Exception as e:
        return jsonify({"ok": False, "error": "invalid_signature", "detail": str(e)}), 400

    event_id = str(event.get("id") or "")
    if event_id and _stripe_event_seen(event_id):
        return jsonify({"ok": True, "status": "duplicate_ignored"})
    if event_id:
        _mark_stripe_event_seen(event_id)

    if event.get("type") != "checkout.session.completed":
        return jsonify({"ok": True, "status": "ignored", "type": event.get("type")})

    session = event["data"]["object"]
    session_id = session.get("id")

    customer_email = None
    if isinstance(session.get("customer_details"), dict):
        customer_email = session["customer_details"].get("email")
    customer_email = (customer_email or "").strip().lower() or None

    price_plan = _stripe_price_plan_map()
    plan = None
    try:
        line_items = stripe.checkout.Session.list_line_items(session_id, limit=10)
        for li in getattr(line_items, "data", []) or []:
            price = li.get("price") if isinstance(li, dict) else getattr(li, "price", None)
            price_id = None
            if isinstance(price, dict):
                price_id = price.get("id")
            else:
                price_id = getattr(price, "id", None)
            if price_id and price_id in price_plan:
                plan = price_plan[price_id]
                break
    except Exception:
        plan = None

    plan = plan or "pro"
    label = customer_email or f"stripe-{session_id}"

    if not customer_email:
        fid = _record_fulfillment("stripe", None, plan, "pending_manual_missing_email", None)
        return jsonify({"ok": True, "status": "pending_manual", "reason": "missing_email", "fulfillment_id": fid})

    # If we can't send email, don't create a key we can't deliver.
    if not _sendgrid_api_key() or not _support_from_email():
        fid = _record_fulfillment("stripe", customer_email, plan, "pending_manual_email_not_configured", None)
        return jsonify({"ok": True, "status": "pending_manual", "reason": "email_not_configured", "fulfillment_id": fid})

    api_key, key_hash, quotas = _issue_key_direct(plan=plan, label=label, active=True)

    body = textwrap.dedent(
        f"""\
        Your Circuit-AI API key is ready.

        API URL:
          {request.host_url.strip().rstrip('/')}

        API Key:
          {api_key}

        Claude Desktop MCP config snippet:
        {{
          "mcpServers": {{
            "circuit-ai": {{
              "command": "node",
              "args": ["/ABS/PATH/TO/Circuit-AI/mcp_server/dist/index.js"],
              "env": {{
                "CIRCUIT_AI_API_URL": "{request.host_url.strip().rstrip('/')}",
                "CIRCUIT_AI_API_KEY": "{api_key}"
              }}
            }}
          }}
        }}

        Smoke test:
          curl -sS {request.host_url.strip().rstrip('/')}/api/v2/usage -H "Authorization: Bearer {api_key}"

        Quotas (per day):
          {json.dumps(quotas, indent=2)}
        """
    ).strip() + "\n"

    sent = _send_email_sendgrid(
        to_email=customer_email,
        subject="Your Circuit-AI API Key",
        text_body=body,
    )

    status = "delivered_email" if sent else "delivery_failed"
    fid = _record_fulfillment("stripe", customer_email, plan, status, key_hash)
    return jsonify({"ok": True, "status": status, "fulfillment_id": fid})


@app.route("/api/v2/support/tickets", methods=["POST"])
def create_support_ticket():
    """
    Basic support intake:
    - stores ticket in SQLite
    - optionally emails support + auto-acks the customer (SendGrid)
    """
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    subject = (payload.get("subject") or "Circuit-AI Support").strip()
    message = (payload.get("message") or "").strip()
    if not email or not message:
        return jsonify({"ok": False, "error": "email_and_message_required"}), 400

    tid = "tkt_" + secrets.token_urlsafe(10)
    now = datetime.now(timezone.utc).isoformat()
    con = _open_usage_db()
    try:
        _init_usage_schema(con)
        con.execute(
            "INSERT INTO support_tickets(id, created_at, customer_email, subject, message, status) VALUES(?,?,?,?,?,?)",
            (tid, now, email, subject, message, "open"),
        )
        con.commit()
    finally:
        con.close()

    # Optional email notifications.
    if _sendgrid_api_key() and _support_from_email():
        _send_email_sendgrid(
            to_email=email,
            subject=f"[Circuit-AI] Ticket received: {subject}",
            text_body=(
                "We received your support request.\n\n"
                f"Ticket: {tid}\n\n"
                "If this is an onboarding/setup issue, please include:\n"
                "- your OS (macOS/Windows/Linux)\n"
                "- the error message\n"
                "- whether you are using Claude Desktop or VSCode\n"
            ),
        )

    return jsonify({"ok": True, "ticket_id": tid})


@app.route("/api/v2/admin/ops", methods=["GET"])
@require_admin
def admin_ops_overview():
    """
    Minimal operator view for:
    - pending fulfillments (e.g. Stripe paid but email not configured)
    - open support tickets
    """
    con = _open_usage_db()
    try:
        _init_usage_schema(con)
        fulf = con.execute(
            "SELECT id, created_at, source, customer_email, plan, status, key_hash FROM fulfillments ORDER BY created_at DESC LIMIT 200"
        ).fetchall()
        tickets = con.execute(
            "SELECT id, created_at, customer_email, subject, status FROM support_tickets ORDER BY created_at DESC LIMIT 200"
        ).fetchall()
        return jsonify(
            {
                "ok": True,
                "fulfillments": [
                    {
                        "id": r[0],
                        "created_at": r[1],
                        "source": r[2],
                        "customer_email": r[3],
                        "plan": r[4],
                        "status": r[5],
                        "key_hash": r[6],
                    }
                    for r in fulf
                ],
                "tickets": [
                    {"id": r[0], "created_at": r[1], "customer_email": r[2], "subject": r[3], "status": r[4]}
                    for r in tickets
                ],
            }
        )
    finally:
        con.close()


@app.route("/api/v2/admin/fulfill", methods=["POST"])
@require_admin
def admin_fulfill_manual_purchase():
    """
    Manual fulfillment endpoint (for non-Stripe payments).

    Use this when you collect payment via PayPal/Wise/bank transfer and want
    a single API call that:
    - issues a key for a plan preset
    - records a fulfillment row
    - optionally emails the buyer the setup snippet (if SendGrid configured)

    Body:
      {
        "plan": "hobby" | "builder" | "pro" | "free",
        "email": "buyer@example.com",
        "label": "optional label",
        "payment_ref": "optional reference/invoice id",
        "active": true
      }
    """
    payload = request.get_json(silent=True) or {}
    plan = str(payload.get("plan") or "pro").strip().lower()
    email = (payload.get("email") or "").strip().lower()
    label = str(payload.get("label") or "").strip() or (email or f"manual-{plan}")
    payment_ref = str(payload.get("payment_ref") or "").strip()
    active = bool(payload.get("active", True))

    if not email:
        return jsonify({"ok": False, "error": "email_required"}), 400

    try:
        api_key, key_hash, quotas = _issue_key_direct(plan=plan, label=label, active=active)
    except Exception as e:
        return jsonify({"ok": False, "error": "issue_failed", "detail": str(e)}), 400

    base_url = request.host_url.strip().rstrip("/")
    body = textwrap.dedent(
        f"""\
        Your Circuit-AI API key is ready.

        API URL:
          {base_url}

        API Key:
          {api_key}

        Claude Desktop MCP config snippet:
        {{
          "mcpServers": {{
            "circuit-ai": {{
              "command": "node",
              "args": ["/ABS/PATH/TO/Circuit-AI/mcp_server/dist/index.js"],
              "env": {{
                "CIRCUIT_AI_API_URL": "{base_url}",
                "CIRCUIT_AI_API_KEY": "{api_key}"
              }}
            }}
          }}
        }}

        Smoke test:
          curl -sS {base_url}/api/v2/usage -H "Authorization: Bearer {api_key}"

        Quotas (per day):
          {json.dumps(quotas, indent=2)}
        """
    ).strip() + "\n"

    # Record fulfillment (include payment_ref in status if provided).
    status = "delivered_manual"
    if payment_ref:
        status = f"delivered_manual:{payment_ref}"
    fid = _record_fulfillment("manual", email, plan, status, key_hash)

    emailed = False
    if _sendgrid_api_key() and _support_from_email():
        emailed = _send_email_sendgrid(to_email=email, subject="Your Circuit-AI API Key", text_body=body)
        if emailed:
            _record_fulfillment("manual", email, plan, "delivered_email", key_hash)

    return jsonify(
        {
            "ok": True,
            "fulfillment_id": fid,
            "emailed": emailed,
            "plan": plan,
            "key_hash": key_hash,
            "api_key": api_key,
            "base_url": base_url,
            "quotas": quotas,
            "mcp_env": {"CIRCUIT_AI_API_URL": base_url, "CIRCUIT_AI_API_KEY": api_key},
        }
    )


@app.route("/api/v2/admin/keys", methods=["POST"])
@require_admin
def admin_create_key():
    payload = request.get_json(silent=True) or {}
    label = str(payload.get("label") or "").strip() or "unnamed"
    plan = str(payload.get("plan") or "").strip() or "default"
    quotas = payload.get("quotas") if isinstance(payload.get("quotas"), dict) else {}
    active = bool(payload.get("active", True))

    api_key = "cai_" + secrets.token_urlsafe(24)
    kh = _key_hash(api_key)
    now = datetime.now(timezone.utc).isoformat()

    con = _open_usage_db()
    try:
        _init_usage_schema(con)
        con.execute(
            "INSERT OR REPLACE INTO api_keys(key_hash, label, plan, quotas_json, active, created_at) VALUES(?,?,?,?,?,?)",
            (kh, label, plan, json.dumps(quotas), 1 if active else 0, now),
        )
        con.commit()
    finally:
        con.close()

    # Return the raw key only at creation time.
    return jsonify({"ok": True, "api_key": api_key, "key_hash": kh, "label": label, "plan": plan, "active": active})


@app.route("/api/v2/admin/keys/<key_hash>/revoke", methods=["POST"])
@require_admin
def admin_revoke_key(key_hash: str):
    kh = (key_hash or "").strip()
    if not kh:
        return jsonify({"error": "key_hash_required"}), 400
    con = _open_usage_db()
    try:
        _init_usage_schema(con)
        con.execute("UPDATE api_keys SET active=0 WHERE key_hash=?", (kh,))
        con.commit()
        return jsonify({"ok": True, "key_hash": kh, "active": False})
    finally:
        con.close()

# Small helper endpoint for debugging quotas/keys during rollout.
@app.route("/api/v2/usage", methods=["GET"])
@require_api_key("usage")
def usage():
    return jsonify(
        {
            "ok": True,
            "key_hash": getattr(g, "circuit_ai_api_key_hash", None),
            "quota_default_per_day": _quota_limit_env("default"),
            "usage_db": str(_usage_db_path()),
        }
    )

# Initialize services
validator = CircuitValidator()
fritzing_lib = FritzingPartsLibrary()
fritzing_gen = FritzingFileGenerator(fritzing_lib)
recipe_optimizer = RecipeOptimizer()
instructions_gen = BuildInstructionsGenerator()
repair_guide_gen = RepairGuideGenerator()
diagnostic_engine = DeviceDiagnosticEngine()
payment_service = GlobalPaymentService()
learning_paths = LearningPathGenerator()
pricing_service = UnifiedPricingService()

# Initialize unified workflow engine (v2 API)
workflow_engine = UnifiedWorkflowEngine()


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'Circuit-AI API',
        'version': '0.1.0'
    })


@app.route('/api/validate', methods=['POST'])
def validate_circuit():
    """
    Validate a circuit design

    Request body:
    {
        "microcontroller": "arduino_uno",
        "components": ["bme280", "servo_sg90"],
        "external_power": false
    }

    Returns:
    {
        "valid": true/false,
        "issues": [...],
        "summary": {
            "critical": 0,
            "errors": 0,
            "warnings": 0
        }
    }
    """
    try:
        design = request.get_json()

        if not design:
            return jsonify({'error': 'No design provided'}), 400

        if 'microcontroller' not in design:
            return jsonify({'error': 'microcontroller field required'}), 400

        # Run validation
        issues = validator.validate_circuit(design)

        # Categorize issues
        critical = [i for i in issues if i.severity.value == 'critical']
        errors = [i for i in issues if i.severity.value == 'error']
        warnings = [i for i in issues if i.severity.value == 'warning']

        # Format response
        result = {
            'valid': len(critical) == 0 and len(errors) == 0,
            'issues': [
                {
                    'severity': i.severity.value,
                    'component': i.component,
                    'issue': i.issue,
                    'explanation': i.explanation,
                    'solution': i.solution,
                    'source': i.source
                }
                for i in issues
            ],
            'summary': {
                'critical': len(critical),
                'errors': len(errors),
                'warnings': len(warnings),
                'total': len(issues)
            },
            'message': 'Circuit looks good!' if len(issues) == 0 else f'Found {len(issues)} issue(s)'
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/export/fritzing', methods=['POST'])
def export_fritzing():
    """
    Export circuit design to Fritzing .fzz file

    Request body:
    {
        "project_name": "My Circuit",
        "microcontroller": "arduino_uno",
        "components": ["bme280", "led", "resistor"]
    }

    Returns: .fzz file (application/zip)
    """
    try:
        design = request.get_json()

        if not design:
            return jsonify({'error': 'No design provided'}), 400

        # Generate unique filename
        project_name = design.get('project_name', 'circuit')
        filename = f"{project_name.replace(' ', '_')}_{uuid.uuid4().hex[:8]}.fzz"

        # Use temp directory for output
        temp_dir = Path(tempfile.gettempdir()) / 'circuit-ai'
        temp_dir.mkdir(exist_ok=True)
        output_path = temp_dir / filename

        # Generate .fzz file
        fzz_path = fritzing_gen.generate_fzz(design, str(output_path))

        # Send file
        return send_file(
            fzz_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/design', methods=['POST'])
def design_and_validate():
    """
    Complete workflow: Design, validate, and optionally export

    Request body:
    {
        "project_name": "Temperature Monitor",
        "microcontroller": "arduino_uno",
        "components": ["bme280", "led"],
        "export": true  // optional
    }

    Returns:
    {
        "validation": {...},
        "export_url": "/api/export/fritzing" (if export=true)
    }
    """
    try:
        design = request.get_json()

        if not design:
            return jsonify({'error': 'No design provided'}), 400

        # Step 1: Validate
        issues = validator.validate_circuit(design)

        critical = [i for i in issues if i.severity.value == 'critical']
        errors = [i for i in issues if i.severity.value == 'error']
        warnings = [i for i in issues if i.severity.value == 'warning']

        validation_result = {
            'valid': len(critical) == 0 and len(errors) == 0,
            'issues': [
                {
                    'severity': i.severity.value,
                    'component': i.component,
                    'issue': i.issue,
                    'solution': i.solution
                }
                for i in issues
            ],
            'summary': {
                'critical': len(critical),
                'errors': len(errors),
                'warnings': len(warnings)
            }
        }

        result = {
            'validation': validation_result,
            'message': 'Circuit validated successfully'
        }

        # Step 2: Export if requested
        if design.get('export', False):
            project_name = design.get('project_name', 'circuit')
            filename = f"{project_name.replace(' ', '_')}.fzz"

            temp_dir = Path(tempfile.gettempdir()) / 'circuit-ai'
            temp_dir.mkdir(exist_ok=True)
            output_path = temp_dir / filename

            fzz_path = fritzing_gen.generate_fzz(design, str(output_path))
            result['export_file'] = str(fzz_path)
            result['message'] += ' and exported to Fritzing'

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/components', methods=['GET'])
def list_components():
    """List available components"""
    components = {
        'microcontrollers': [
            'arduino_uno', 'arduino_nano', 'arduino_mega', 'arduino_leonardo',
            'esp32', 'esp8266'
        ],
        'sensors': [
            'bme280', 'bmp280', 'dht22', 'dht11', 'hc_sr04', 'mpu6050'
        ],
        'displays': [
            'oled_ssd1306', 'lcd_16x2', 'lcd_20x4'
        ],
        'actuators': [
            'servo_sg90', 'servo', 'relay'
        ],
        'basic': [
            'led', 'led_rgb', 'ws2812b', 'resistor', 'capacitor'
        ]
    }

    # Count Fritzing mappings
    mapped = sum(
        1 for comp_list in components.values()
        for comp in comp_list
        if fritzing_lib.find_part(comp)
    )

    return jsonify({
        'components': components,
        'total': sum(len(v) for v in components.values()),
        'fritzing_mapped': mapped
    })


@app.route('/api/recipes/analyze-inventory', methods=['POST'])
def analyze_inventory():
    """
    Analyze inventory value

    Request body:
    {
        "inventory": [
            {"id": "arduino_uno", "condition": "used", "quantity": 1},
            {"id": "bme280", "condition": "new", "quantity": 1}
        ]
    }

    Returns inventory analysis with total value
    """
    try:
        data = request.get_json()

        if not data or 'inventory' not in data:
            return jsonify({'error': 'inventory field required'}), 400

        analysis = recipe_optimizer.analyze_inventory(data['inventory'])

        return jsonify(analysis)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recipes/generate', methods=['POST'])
def generate_recipes():
    """
    Generate project recipes from inventory

    Request body:
    {
        "inventory": [
            {"id": "arduino_uno", "condition": "used", "quantity": 1},
            {"id": "bme280", "condition": "new", "quantity": 1}
        ],
        "top_n": 5,
        "validate": true  // optional: validate circuits
    }

    Returns list of project recipes sorted by ROI
    """
    try:
        data = request.get_json()

        if not data or 'inventory' not in data:
            return jsonify({'error': 'inventory field required'}), 400

        inventory = data['inventory']
        top_n = data.get('top_n', 5)
        validate_circuits = data.get('validate', False)

        # Generate recipes
        recipes = recipe_optimizer.generate_recipes(inventory, top_n)

        # Optionally validate each recipe
        if validate_circuits:
            for recipe in recipes:
                design = {
                    'project_name': recipe.name,
                    'microcontroller': recipe.required_components[0],  # First is usually MCU
                    'components': recipe.required_components[1:]
                }
                issues = validator.validate_circuit(design)
                recipe.validated = len(issues) == 0
                recipe.validation_issues = [i.issue for i in issues[:3]]  # Top 3 issues

        # Format response
        result = {
            'recipes': [
                {
                    'name': r.name,
                    'category': r.category.value,
                    'description': r.description,
                    'difficulty': r.difficulty,
                    'economics': {
                        'parts_cost': r.parts_cost,
                        'market_price_low': r.market_price_low,
                        'market_price_high': r.market_price_high,
                        'profit_margin': r.profit_margin,
                        'roi_percent': r.roi_percent,
                        'missing_parts_cost': r.missing_parts_cost
                    },
                    'inventory': {
                        'match_percent': r.inventory_match_percent,
                        'components_owned': r.components_owned,
                        'components_needed': r.components_needed,
                        'has_all_parts': len(r.components_needed) == 0
                    },
                    'build_time_hours': r.build_time_hours,
                    'validated': r.validated if validate_circuits else None,
                    'validation_issues': r.validation_issues if validate_circuits else None
                }
                for r in recipes
            ],
            'count': len(recipes)
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recipes/shopping-list', methods=['POST'])
def generate_shopping_list():
    """
    Generate shopping list for missing components

    Request body:
    {
        "inventory": [...],
        "recipe_name": "WiFi Weather Station"
    }

    Returns shopping list with prices and buy links
    """
    try:
        data = request.get_json()

        if not data or 'inventory' not in data or 'recipe_name' not in data:
            return jsonify({'error': 'inventory and recipe_name required'}), 400

        # Generate recipes to find the requested one
        recipes = recipe_optimizer.generate_recipes(data['inventory'], top_n=20)

        # Find matching recipe
        target_recipe = None
        for recipe in recipes:
            if recipe.name == data['recipe_name']:
                target_recipe = recipe
                break

        if not target_recipe:
            return jsonify({'error': 'Recipe not found'}), 404

        # Generate shopping list
        shopping = recipe_optimizer.generate_shopping_list(target_recipe)

        return jsonify(shopping)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recipes/filter', methods=['POST'])
def filter_recipes():
    """
    Generate recipes with advanced filtering

    Request body:
    {
        "inventory": [...],
        "max_difficulty": "easy",  // optional: 'easy', 'medium', 'hard'
        "max_build_hours": 2.0,    // optional: max build time
        "max_budget": 15.0,         // optional: max missing parts cost
        "min_match_percent": 80.0,  // optional: min inventory match
        "top_n": 5                  // optional: number of results
    }

    Returns filtered recipes
    """
    try:
        data = request.get_json()

        if not data or 'inventory' not in data:
            return jsonify({'error': 'inventory field required'}), 400

        # Extract filter parameters
        inventory = data['inventory']
        max_difficulty = data.get('max_difficulty')
        max_build_hours = data.get('max_build_hours')
        max_budget = data.get('max_budget')
        min_match_percent = data.get('min_match_percent', 50.0)
        top_n = data.get('top_n', 10)

        # Generate filtered recipes
        recipes = recipe_optimizer.generate_recipes_filtered(
            inventory=inventory,
            max_difficulty=max_difficulty,
            max_build_hours=max_build_hours,
            max_budget=max_budget,
            min_match_percent=min_match_percent,
            top_n=top_n
        )

        # Format response
        result = {
            'recipes': [
                {
                    'name': r.name,
                    'category': r.category.value,
                    'description': r.description,
                    'difficulty': r.difficulty,
                    'build_time_hours': r.build_time_hours,
                    'economics': {
                        'parts_cost': r.parts_cost,
                        'market_price_low': r.market_price_low,
                        'market_price_high': r.market_price_high,
                        'profit_margin': r.profit_margin,
                        'roi_percent': r.roi_percent,
                        'missing_parts_cost': r.missing_parts_cost
                    },
                    'inventory': {
                        'match_percent': r.inventory_match_percent,
                        'components_owned': r.components_owned,
                        'components_needed': r.components_needed
                    }
                }
                for r in recipes
            ],
            'count': len(recipes),
            'filters_applied': {
                'max_difficulty': max_difficulty,
                'max_build_hours': max_build_hours,
                'max_budget': max_budget,
                'min_match_percent': min_match_percent
            }
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/recipes/budget-optimize', methods=['POST'])
def budget_optimize():
    """
    Optimize project selection for a budget

    Request body:
    {
        "inventory": [...],
        "budget": 20.0,              // max budget for missing parts
        "goal": "learning"           // 'roi', 'learning', 'complexity', 'speed'
    }

    Returns optimized recommendation
    """
    try:
        data = request.get_json()

        if not data or 'inventory' not in data or 'budget' not in data:
            return jsonify({'error': 'inventory and budget fields required'}), 400

        inventory = data['inventory']
        budget = data['budget']
        goal = data.get('goal', 'roi')

        # Optimize
        result = recipe_optimizer.optimize_for_budget(
            inventory=inventory,
            budget=budget,
            goal=goal
        )

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/instructions/<project_name>', methods=['GET'])
def get_build_instructions(project_name):
    """
    Get step-by-step build instructions for a project

    Returns detailed assembly guide with wiring diagrams, code, and troubleshooting
    """
    try:
        # Get instructions
        instructions = instructions_gen.generate_instructions(project_name)

        if not instructions:
            return jsonify({'error': f'Instructions not found for project: {project_name}'}), 404

        return jsonify(instructions)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/instructions', methods=['GET'])
def list_available_instructions():
    """
    List all projects with available build instructions
    """
    try:
        available = instructions_gen.list_available_projects()

        return jsonify({
            'available_projects': available,
            'count': len(available)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Repair Guides API
# ============================================================================

@app.route('/api/repair-guides', methods=['GET'])
def list_repair_guides():
    """
    List all available repair guides for phones, laptops, and electronics
    """
    try:
        available = repair_guide_gen.list_available_guides()

        return jsonify({
            'available_guides': available,
            'count': len(available),
            'categories': {
                'iphone': [g for g in available if 'iPhone' in g],
                'android': [g for g in available if 'Samsung' in g or 'Android' in g],
                'laptop': [g for g in available if 'Laptop' in g or 'Macbook' in g]
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/repair-guides/<path:issue_name>', methods=['GET'])
def get_repair_guide(issue_name):
    """
    Get step-by-step repair guide for specific device issue

    Examples:
        /api/repair-guides/iPhone Screen Replacement
        /api/repair-guides/iPhone Battery Replacement
        /api/repair-guides/Laptop Not Charging

    Query params:
        device_model: Specific device model (e.g., "iPhone 12", "MacBook Pro 2020")
        user_id: User identifier (email or session_id) for access control
        preview: Set to 'true' for free preview (limited content)
    """
    try:
        device_model = request.args.get('device_model')
        user_id = request.args.get('user_id')
        preview_mode = request.args.get('preview', 'false').lower() == 'true'

        # Access control check (if user_id provided)
        has_access = True  # Default to true for testing
        if user_id and not preview_mode:
            access_check = payment_service.check_access(user_id, issue_name)
            has_access = access_check.get('has_access', False)

            if not has_access:
                # Return preview version with paywall
                return jsonify({
                    'error': 'Payment required',
                    'message': 'Purchase this guide to access full content',
                    'preview': True,
                    'pricing': {
                        'guide_onetime': '$4.99 one-time',
                        'pro_monthly': '$9.99/month for all guides'
                    },
                    'upgrade_url': '/static/repair-diagnostic.html'
                }), 402

        # Get repair guide
        guide = repair_guide_gen.generate_repair_guide(issue_name, device_model)

        if not guide:
            return jsonify({'error': f'Repair guide not found for: {issue_name}'}), 404

        # If preview mode, limit content
        if preview_mode and not has_access:
            if 'steps' in guide and len(guide['steps']) > 3:
                guide['steps'] = guide['steps'][:3]
                guide['preview_mode'] = True
                guide['preview_message'] = 'Preview - Purchase to see all steps'

        return jsonify(guide)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/diagnose', methods=['POST'])
def diagnose_device():
    """
    AI-powered device diagnostics from user symptoms

    Analyzes symptoms and recommends repair guides

    Request Body (JSON):
        {
            "symptoms": ["won't charge", "cable falls out"],
            "device_type": "iPhone"  // optional, defaults to "iPhone"
        }

    Returns:
        {
            "device_type": "iPhone",
            "diagnosis_method": "symptom_analysis",
            "recommendations": [
                {
                    "issue": "iPhone Charging Port",
                    "confidence": 0.67,
                    "guide_summary": {
                        "difficulty": "easy",
                        "time": "5-45 minutes",
                        "cost": "$0-25"
                    }
                }
            ],
            "top_recommendation": {...}
        }

    Examples:
        # Charging issue
        curl -X POST http://localhost:5000/api/diagnose \\
          -H "Content-Type: application/json" \\
          -d '{"symptoms": ["won\'t charge", "cable loose"]}'

        # Battery issue
        curl -X POST http://localhost:5000/api/diagnose \\
          -H "Content-Type: application/json" \\
          -d '{"symptoms": ["battery drains fast", "shuts down at 30%"]}'

        # Screen issue
        curl -X POST http://localhost:5000/api/diagnose \\
          -H "Content-Type: application/json" \\
          -d '{"symptoms": ["cracked screen", "touch not working"]}'
    """
    try:
        data = request.get_json()

        if not data or 'symptoms' not in data:
            return jsonify({
                'error': 'Missing required field: symptoms',
                'example': {
                    'symptoms': ['won\'t charge', 'cable falls out'],
                    'device_type': 'iPhone'
                }
            }), 400

        symptoms = data.get('symptoms', [])
        device_type = data.get('device_type', 'iPhone')

        if not isinstance(symptoms, list) or len(symptoms) == 0:
            return jsonify({'error': 'symptoms must be a non-empty list'}), 400

        # Run diagnosis
        diagnosis = diagnostic_engine.diagnose_from_symptoms(symptoms, device_type)

        return jsonify(diagnosis)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Payment Endpoints - Stripe Integration for Repair Guides
# ============================================================================

@app.route('/api/payment/create-checkout', methods=['POST'])
def create_checkout():
    """
    Create a Stripe checkout session for purchasing repair guides

    Request Body (JSON):
        {
            "product_type": "guide_onetime",  // or "pro_monthly", "expert_session"
            "repair_guide": "iPhone Screen Replacement",
            "customer_email": "user@example.com"  // optional
        }

    Returns:
        {
            "checkout_url": "https://checkout.stripe.com/...",
            "session_id": "cs_test_...",
            "publishable_key": "pk_test_..."
        }

    Examples:
        # Purchase one-time guide
        curl -X POST http://localhost:5000/api/payment/create-checkout \\
          -H "Content-Type: application/json" \\
          -d '{"product_type": "guide_onetime", "repair_guide": "iPhone Screen Replacement"}'

        # Subscribe to Pro
        curl -X POST http://localhost:5000/api/payment/create-checkout \\
          -H "Content-Type: application/json" \\
          -d '{"product_type": "pro_monthly", "repair_guide": "All Guides"}'
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Missing request body'}), 400

        product_type = data.get('product_type', 'guide_onetime')
        repair_guide = data.get('repair_guide')
        customer_email = data.get('customer_email')

        if not repair_guide:
            return jsonify({'error': 'repair_guide is required'}), 400

        # Create checkout session
        base_url = request.host_url.rstrip('/')
        checkout_result = payment_service.create_checkout_session(
            product_type=product_type,
            repair_guide=repair_guide,
            success_url=f"{base_url}/payment-success",
            cancel_url=f"{base_url}/payment-cancelled",
            customer_email=customer_email
        )

        if 'error' in checkout_result:
            return jsonify(checkout_result), 400

        return jsonify(checkout_result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/payment/verify', methods=['GET'])
def verify_payment():
    """
    Verify a payment and grant access to purchased content

    Query Parameters:
        session_id: Stripe checkout session ID

    Returns:
        {
            "status": "paid",
            "repair_guide": "iPhone Screen Replacement",
            "access_granted": true,
            "purchase_id": "purchase_..."
        }

    Examples:
        curl "http://localhost:5000/api/payment/verify?session_id=cs_test_123"
    """
    try:
        session_id = request.args.get('session_id')

        if not session_id:
            return jsonify({'error': 'session_id is required'}), 400

        verification = payment_service.verify_payment(session_id)

        if verification.get('access_granted'):
            return jsonify(verification)
        else:
            return jsonify(verification), 402  # Payment Required

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/payment/check-access', methods=['POST'])
def check_access():
    """
    Check if a user has access to a repair guide

    Request Body (JSON):
        {
            "user_identifier": "user@example.com",  // email or session_id
            "repair_guide": "iPhone Screen Replacement"
        }

    Returns:
        {
            "has_access": true,
            "type": "one_time_purchase",  // or "pro_subscription"
            "purchase_id": "purchase_..."
        }

    Examples:
        curl -X POST http://localhost:5000/api/payment/check-access \\
          -H "Content-Type: application/json" \\
          -d '{"user_identifier": "user@example.com", "repair_guide": "iPhone Screen Replacement"}'
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Missing request body'}), 400

        user_identifier = data.get('user_identifier')
        repair_guide = data.get('repair_guide')

        if not user_identifier or not repair_guide:
            return jsonify({'error': 'user_identifier and repair_guide are required'}), 400

        access_result = payment_service.check_access(user_identifier, repair_guide)

        if access_result.get('has_access'):
            return jsonify(access_result)
        else:
            return jsonify(access_result), 402  # Payment Required

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/payment/analytics', methods=['GET'])
def payment_analytics():
    """
    Get revenue analytics (admin only in production)

    Returns:
        {
            "total_revenue": "$99.80",
            "total_purchases": 20,
            "active_subscriptions": 5,
            "mrr": "$49.95",
            "avg_order_value": "$4.99"
        }

    Examples:
        curl http://localhost:5000/api/payment/analytics
    """
    try:
        analytics = payment_service.get_analytics()
        return jsonify(analytics)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/learning-paths', methods=['GET'])
def list_learning_paths():
    """
    List all available learning paths

    Returns overview of all learning paths with metadata
    """
    try:
        paths = learning_paths.get_all_paths()

        result = {
            'learning_paths': [
                {
                    'id': p.path_id,
                    'name': p.name,
                    'description': p.description,
                    'total_modules': p.total_modules,
                    'total_hours': p.total_hours,
                    'target_audience': p.target_audience,
                    'skills_gained': p.skills_gained
                }
                for p in paths
            ],
            'count': len(paths)
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/learning-paths/<path_id>', methods=['GET'])
def get_learning_path(path_id):
    """
    Get detailed learning path with all modules and projects

    Returns complete curriculum with module-by-module breakdown
    """
    try:
        path = learning_paths.get_path(path_id)

        if not path:
            return jsonify({'error': f'Learning path not found: {path_id}'}), 404

        result = {
            'id': path.path_id,
            'name': path.name,
            'description': path.description,
            'target_audience': path.target_audience,
            'total_modules': path.total_modules,
            'total_hours': path.total_hours,
            'skills_gained': path.skills_gained,
            'modules': [
                {
                    'number': m.module_number,
                    'title': m.title,
                    'description': m.description,
                    'estimated_hours': m.estimated_hours,
                    'projects': m.projects,
                    'concepts_taught': m.concepts_taught,
                    'prerequisites': m.prerequisites
                }
                for m in path.modules
            ]
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/learning-paths/recommend', methods=['POST'])
def recommend_learning_path():
    """
    Get personalized learning path recommendations

    Request body:
    {
        "current_skills": ["arduino_basics", "sensors"],  // optional
        "interests": ["iot", "home_automation"],          // optional
        "available_hours": 20                             // optional
    }

    Returns recommended learning paths ranked by match
    """
    try:
        data = request.get_json() or {}

        current_skills = data.get('current_skills', [])
        interests = data.get('interests', [])
        available_hours = data.get('available_hours')

        recommendations = learning_paths.recommend_path(
            current_skills=current_skills,
            interests=interests,
            available_hours=available_hours
        )

        result = {
            'recommendations': [
                {
                    'id': r['path'].path_id,
                    'name': r['path'].name,
                    'description': r['path'].description,
                    'total_hours': r['path'].total_hours,
                    'match_score': r['score'],
                    'reason': r['reason']
                }
                for r in recommendations
            ],
            'count': len(recommendations)
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pricing/component', methods=['POST'])
def get_component_pricing():
    """
    Get real-time component pricing

    Request body:
    {
        "components": [
            {"id": "arduino_uno", "condition": "new", "quantity": 1},
            {"id": "bme280", "condition": "used", "quantity": 2}
        ]
    }

    Returns detailed pricing breakdown with supplier info
    """
    try:
        data = request.get_json()

        if not data or 'components' not in data:
            return jsonify({'error': 'components field required'}), 400

        breakdown = pricing_service.get_price_breakdown(data['components'])

        return jsonify(breakdown)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pricing/market/<project_name>', methods=['GET'])
def get_market_pricing(project_name):
    """
    Get market pricing for a completed project

    Returns price range from eBay/Etsy comparable listings
    """
    try:
        # Decode URL-encoded project name
        from urllib.parse import unquote
        project_name = unquote(project_name)

        market_data = pricing_service.get_project_market_price(project_name)

        return jsonify(market_data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# V2 API - UNIFIED WORKFLOW ENGINE
# Integrates educational tools (recipe optimizer, learning paths, instructions)
# with professional validation (KiCAD, circuit solver, power tree validator)
# ============================================================================

@app.route('/api/v2/workflow/beginner', methods=['POST'])
@require_api_key("workflow_beginner")
def beginner_workflow():
    """
    Complete beginner workflow

    Request body:
    {
        "skill_level": 1,                           // 1-5 (BEGINNER-PROFESSIONAL)
        "completed_projects": ["LED Blink"],        // optional
        "inventory": [                              // optional
            {"id": "arduino_uno", "condition": "used", "quantity": 1},
            {"id": "bme280", "condition": "new", "quantity": 1}
        ],
        "budget": 50.0,                             // optional (default: 50)
        "goal": "learning"                          // "learning", "roi", or "speed"
    }

    Returns:
    {
        "status": "success" | "prerequisites_missing" | "no_projects",
        "project": {...},                           // if available
        "instructions": {...},                      // if project selected
        "next_steps": [...],
        "estimated_cost": 0.0,
        "estimated_time_hours": 0.0
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Request body required'}), 400

        # Build user profile
        user = UserProfile(
            skill_level=UserLevel(data.get('skill_level', 1)),
            completed_projects=data.get('completed_projects', []),
            inventory=data.get('inventory', []),
            budget=data.get('budget', 50.0),
            goal=data.get('goal', 'learning')
        )

        # Execute beginner workflow
        result = workflow_engine.execute_beginner_workflow(user)

        # Format response
        response = {
            'status': result.status,
            'next_steps': result.next_steps,
            'estimated_cost': result.estimated_cost,
            'estimated_time_hours': result.estimated_time_hours
        }

        # Add project details if available
        if result.project:
            response['project'] = {
                'name': result.project.name,
                'category': result.project.category.value,
                'description': result.project.description,
                'difficulty': result.project.difficulty,
                'build_time_hours': result.project.build_time_hours,
                'economics': {
                    'parts_cost': result.project.parts_cost,
                    'market_price_low': result.project.market_price_low,
                    'market_price_high': result.project.market_price_high,
                    'roi_percent': result.project.roi_percent,
                    'missing_parts_cost': result.project.missing_parts_cost
                },
                'inventory': {
                    'match_percent': result.project.inventory_match_percent,
                    'components_owned': result.project.components_owned,
                    'components_needed': result.project.components_needed
                }
            }

        # Add instructions if available
        if result.instructions:
            response['instructions'] = result.instructions

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v2/projects/catalog', methods=['GET'])
@require_api_key("catalog")
def get_projects_catalog():
    """
    Get comprehensive catalog of all available projects with economics

    Returns detailed information about each project including:
    - Build cost and time estimates
    - Market pricing and ROI
    - Difficulty level
    - Required components
    - Brief description
    """
    try:
        # Get all project templates from recipe database
        all_templates = recipe_optimizer.recipe_db.get_all()

        catalog = []
        for template in all_templates:
            # Calculate economics for each project (no inventory required)
            project = recipe_optimizer.get_project_by_name(template['name'], inventory=[])

            if project:
                catalog.append({
                    'name': project.name,
                    'description': project.description,
                    'difficulty': project.difficulty,
                    'category': project.category.value if hasattr(project.category, 'value') else str(project.category),
                    'build_time_hours': project.build_time_hours,
                    'economics': {
                        'parts_cost': project.parts_cost,
                        'market_price_low': project.market_price_low,
                        'market_price_high': project.market_price_high,
                        'profit_margin': project.profit_margin,
                        'roi_percent': project.roi_percent
                    },
                    'required_components': project.required_components,
                    'optional_components': project.optional_components
                })

        # Sort by ROI (highest first)
        catalog.sort(key=lambda x: x['economics']['roi_percent'], reverse=True)

        return jsonify({
            'projects': catalog,
            'count': len(catalog),
            'sorted_by': 'roi_percent (descending)'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v2/workflow/complete', methods=['POST'])
@require_api_key("workflow_complete")
def complete_workflow():
    """
    End-to-end complete workflow

    Request body:
    {
        "user": {
            "skill_level": 2,                       // 1-5 (BEGINNER-PROFESSIONAL)
            "completed_projects": ["LED Blink"],    // optional
            "inventory": [...],                     // optional
            "budget": 20.0,                         // optional
            "goal": "learning"                      // "learning", "roi", or "speed"
        },
        "project_name": "Air Quality Monitor",
        "kicad_file": "/path/to/design.net"        // optional - for validation
    }

    Returns complete workflow result with:
    - Project details
    - Build instructions
    - Validation issues (if KiCAD file provided)
    - Manufacturing readiness
    - Next steps
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Request body required'}), 400

        if 'user' not in data or 'project_name' not in data:
            return jsonify({'error': 'user and project_name fields required'}), 400

        # Build user profile
        user_data = data['user']
        user = UserProfile(
            skill_level=UserLevel(user_data.get('skill_level', 2)),
            completed_projects=user_data.get('completed_projects', []),
            inventory=user_data.get('inventory', []),
            budget=user_data.get('budget', 50.0),
            goal=user_data.get('goal', 'learning')
        )

        # Execute complete workflow
        result = workflow_engine.execute_complete_workflow(
            user=user,
            project_name=data['project_name'],
            kicad_file=data.get('kicad_file')
        )

        # Format response
        response = {
            'status': result.status,
            'next_steps': result.next_steps,
            'estimated_cost': result.estimated_cost,
            'estimated_time_hours': result.estimated_time_hours
        }

        # Add project details
        if result.project:
            response['project'] = {
                'name': result.project.name,
                'category': result.project.category.value,
                'description': result.project.description,
                'difficulty': result.project.difficulty,
                'build_time_hours': result.project.build_time_hours,
                'economics': {
                    'parts_cost': result.project.parts_cost,
                    'roi_percent': result.project.roi_percent,
                    'missing_parts_cost': result.project.missing_parts_cost
                }
            }

        # Add instructions
        if result.instructions:
            response['instructions'] = result.instructions

        # Add validation issues
        if result.validation_issues:
            response['validation'] = {
                'issues_count': len(result.validation_issues),
                'issues': [
                    {
                        'severity': i.severity,
                        'component': i.component,
                        'issue': i.issue,
                        'solution': i.solution
                    }
                    for i in result.validation_issues
                ]
            }

        # Add manufacturing status
        if result.manufacturing_files:
            response['manufacturing'] = result.manufacturing_files

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v2/workflow/validate-kicad', methods=['POST'])
@require_api_key("validate_kicad")
def validate_kicad_workflow():
    """
    Professional KiCAD validation workflow

    Request (multipart/form-data or JSON):
    - kicad_file: Path to .net or .kicad_pcb file, or file upload
    - hints: JSON hints (optional - will auto-generate if missing)

    Hints schema:
    {
        "sources": [
            {"name": "VUSB", "net": "VBUS", "volts": 5.0, "max_current_a": 0.5}
        ],
        "loads_cc": [
            {"name": "ESP32", "net": "+3V3", "amps": 0.24}
        ],
        "voltage_constraints": [
            {"net": "+3V3", "min_v": 3.0, "max_v": 3.6}
        ]
    }

    Returns:
    {
        "status": "validation_passed" | "validation_warning" | "validation_failed",
        "validation": {
            "issues_count": 2,
            "critical": 0,
            "errors": 0,
            "warnings": 2,
            "issues": [
                {
                    "severity": "warning",
                    "component": "Trace +3V3",
                    "issue": "Excessive voltage drop",
                    "physics": {
                        "current_a": 1.2,
                        "voltage_drop": 0.35,
                        "current_width_mm": 0.5,
                        "required_width_mm": 2.0
                    },
                    "solution": "Widen trace to 2.0mm or use copper pour"
                }
            ]
        },
        "manufacturing_ready": false,
        "next_steps": [...]
    }
    """
    try:
        # Handle both JSON and multipart form data
        if request.is_json:
            data = request.get_json()
            kicad_file = data.get('kicad_file')
            hints = data.get('hints')
        else:
            # Handle file upload
            if 'kicad_file' not in request.files:
                return jsonify({'error': 'kicad_file required (path or file upload)'}), 400

            # Save uploaded file temporarily
            file = request.files['kicad_file']
            temp_dir = Path(tempfile.gettempdir()) / 'circuit-ai'
            temp_dir.mkdir(exist_ok=True)
            orig_suffix = Path(file.filename or "").suffix.lower()
            suffix = ".kicad_pcb" if orig_suffix == ".kicad_pcb" else ".net"
            kicad_file = temp_dir / f"{uuid.uuid4().hex[:8]}{suffix}"
            file.save(str(kicad_file))

            hints = request.form.get('hints')
            if hints:
                import json
                hints = json.loads(hints)

        if not kicad_file:
            return jsonify({'error': 'kicad_file required'}), 400

        # Execute validation workflow
        result = workflow_engine.execute_validation_workflow(
            kicad_file=str(kicad_file),
            hints=hints
        )

        # Format response
        response = {
            'status': result.status,
            'next_steps': result.next_steps
        }

        # Add validation details
        if result.validation_issues:
            critical = [i for i in result.validation_issues if i.severity == 'critical']
            errors = [i for i in result.validation_issues if i.severity == 'error']
            warnings = [i for i in result.validation_issues if i.severity == 'warning']

            response['validation'] = {
                'issues_count': len(result.validation_issues),
                'critical': len(critical),
                'errors': len(errors),
                'warnings': len(warnings),
                'issues': [
                    {
                        'severity': i.severity,
                        'component': i.component,
                        'issue': i.issue,
                        'solution': i.solution,
                        'physics': i.physics if hasattr(i, 'physics') else None
                    }
                    for i in result.validation_issues
                ]
            }

            # FIXED: Handle validation_partial status (circuit solver failed, but geometric validation ran)
            if result.status == 'validation_partial':
                response['manufacturing_ready'] = False  # Circuit solver failed - needs electrical review
            else:
                response['manufacturing_ready'] = (len(critical) == 0 and len(errors) == 0)
        else:
            response['validation'] = {
                'issues_count': 0,
                'critical': 0,
                'errors': 0,
                'warnings': 0,
                'issues': []
            }
            # FIXED: Don't set manufacturing_ready=True if validation failed
            # If status is "error", the circuit solver crashed - not safe to manufacture
            if result.status in ['error', 'validation_failed']:
                response['manufacturing_ready'] = False
            else:
                response['manufacturing_ready'] = True

        # Optional: include geometry for `.kicad_pcb` inputs (enables 2.5D/3D viewer)
        try:
            if str(kicad_file).lower().endswith(".kicad_pcb"):
                from src.engines.kicad_pcb_geometry import extract_pcb_geometry
                response["pcb_geometry"] = extract_pcb_geometry(str(kicad_file))
        except Exception:
            # Geometry is best-effort; validation results should still return.
            pass

        # Optional: Add AI-powered design insights (separate from geometry)
        if "pcb_geometry" in response:
            from src.engines.llm_validator import get_llm_design_insights, get_fallback_insights

            llm_insights = get_llm_design_insights(response["pcb_geometry"])
            if llm_insights:
                response["ai_insights"] = llm_insights
            else:
                # Fallback to rule-based insights
                response["ai_insights"] = get_fallback_insights(response["pcb_geometry"])

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v2/manufacture/bom', methods=['POST'])
@require_api_key("manufacture_bom")
def generate_bom():
    """
    Generate Bill of Materials (BOM) from KiCAD netlist

    Request (multipart/form-data or JSON):
    - netlist_path: Path to .net file or file upload
    - include_pricing: Boolean (optional, default: false)
    - format: "json" or "csv" (optional, default: "json")

    Returns:
    {
        "status": "success",
        "summary": {
            "total_components": 15,
            "unique_parts": 7,
            "parts_with_digikey_numbers": 5,
            "estimated_total_cost": 12.50
        },
        "items": [
            {
                "references": ["R1", "R2"],
                "value": "10K",
                "footprint": "Resistor_SMD:R_0805",
                "quantity": 2,
                "part_number": "RMCF0805FT10K0CT-ND",
                "supplier": "DigiKey",
                "unit_price": 0.10,
                "total_price": 0.20
            },
            ...
        ]
    }
    """
    try:
        from engines.bom_generator import BOMGenerator

        # Handle both JSON and multipart form data
        if request.is_json:
            data = request.get_json()
            netlist_path = data.get('netlist_path')
            include_pricing = data.get('include_pricing', False)
            output_format = data.get('format', 'json')
        else:
            # Handle file upload
            if 'netlist_file' not in request.files:
                return jsonify({'error': 'netlist_path or netlist_file required'}), 400

            # Save uploaded file temporarily
            file = request.files['netlist_file']
            temp_dir = Path(tempfile.gettempdir()) / 'circuit-ai'
            temp_dir.mkdir(exist_ok=True)
            netlist_path = temp_dir / f"{uuid.uuid4().hex[:8]}.net"
            file.save(str(netlist_path))

            include_pricing = request.form.get('include_pricing', 'false').lower() == 'true'
            output_format = request.form.get('format', 'json')

        if not netlist_path:
            return jsonify({'error': 'netlist_path required'}), 400

        # Generate BOM
        generator = BOMGenerator()
        bom = generator.generate_bom(str(netlist_path), include_pricing=include_pricing)

        # Return appropriate format
        if output_format == 'csv':
            csv_content = generator.export_csv(bom)
            return csv_content, 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': 'attachment; filename=bom.csv'
            }
        else:
            return jsonify(bom)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v2/manufacture/gerber', methods=['POST'])
@require_api_key("manufacture_gerber")
def generate_gerber():
    """
    Generate Gerber files from KiCAD PCB

    Request (multipart/form-data or JSON):
    - pcb_path: Path to .kicad_pcb file or file upload
    - quantity: PCB quantity for cost estimation (optional, default: 5)

    Returns:
    {
        "status": "success",
        "pcb_info": {
            "name": "my_board",
            "dimensions": "100mm x 80mm",
            "layers": 2,
            "thickness": "1.6mm"
        },
        "gerber_files": [...],
        "zip_url": "/download/gerbers/my_board-gerbers.zip",
        "manufacturing_ready": true,
        "cost_estimates": {
            "JLCPCB": {"price_usd": 2.00, "lead_time_days": "2-5"},
            ...
        }
    }
    """
    try:
        from engines.gerber_generator import GerberGenerator

        # Handle both JSON and multipart form data
        if request.is_json:
            data = request.get_json()
            pcb_path = data.get('pcb_path')
            quantity = data.get('quantity', 5)
        else:
            # Handle file upload
            if 'pcb_file' not in request.files:
                return jsonify({'error': 'pcb_path or pcb_file required'}), 400

            # Save uploaded file temporarily
            file = request.files['pcb_file']
            temp_dir = Path(tempfile.gettempdir()) / 'circuit-ai'
            temp_dir.mkdir(exist_ok=True)
            pcb_path = temp_dir / f"{uuid.uuid4().hex[:8]}.kicad_pcb"
            file.save(str(pcb_path))

            quantity = int(request.form.get('quantity', 5))

        if not pcb_path:
            return jsonify({'error': 'pcb_path required'}), 400

        # Generate Gerber package
        generator = GerberGenerator()
        package = generator.generate_gerber_package(str(pcb_path))

        # Create ZIP file
        temp_dir = Path(tempfile.gettempdir()) / 'circuit-ai' / 'gerbers'
        temp_dir.mkdir(parents=True, exist_ok=True)
        zip_filename = f"{package['pcb_info']['name']}-gerbers.zip"
        zip_path = temp_dir / zip_filename
        generator.create_gerber_zip(package, str(zip_path))

        # Get cost estimates
        pcb_info = generator.extract_pcb_info(str(pcb_path))
        cost_estimates = generator.estimate_manufacturing_cost(pcb_info, quantity)

        # Format response
        response = {
            'status': package['status'],
            'export_method': package.get('export_method', 'unknown'),
            'pcb_info': package['pcb_info'],
            'gerber_files': [
                {
                    'filename': layer.filename,
                    'layer_type': layer.layer_type,
                    'description': layer.description,
                    'size_bytes': len(layer.content)
                }
                for layer in package['gerber_files']
            ],
            'zip_file': str(zip_path),
            'zip_size_kb': zip_path.stat().st_size / 1024,
            'manufacturing_ready': package['manufacturing_ready'],
            'cost_estimates': cost_estimates['estimates'],
            'compatible_fabs': package['compatible_fabs']
        }

        return jsonify(response)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v2/manufacture/download-gerber/<filename>', methods=['GET'])
@require_api_key("download_gerber")
def download_gerber(filename):
    """Download generated Gerber ZIP file"""
    try:
        temp_dir = Path(tempfile.gettempdir()) / 'circuit-ai' / 'gerbers'
        file_path = temp_dir / filename

        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404

        return send_file(
            file_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v2/manufacture/pnp', methods=['POST'])
@require_api_key("manufacture_pnp")
def generate_pnp():
    """
    Generate a Pick-and-Place (PnP) position CSV from a KiCad `.kicad_pcb`.

    Request (multipart/form-data):
    - pcb_file: KiCad PCB file upload

    Returns:
    - CSV content (text) + saved file path for packaging.
    """
    try:
        # Handle file upload only (PnP requires pcb geometry).
        if request.is_json:
            data = request.get_json() or {}
            pcb_path = data.get('pcb_path')
        else:
            if 'pcb_file' not in request.files:
                return jsonify({'error': 'pcb_file required'}), 400
            file = request.files['pcb_file']
            temp_dir = Path(tempfile.gettempdir()) / 'circuit-ai'
            temp_dir.mkdir(exist_ok=True)
            pcb_path = temp_dir / f"{uuid.uuid4().hex[:8]}.kicad_pcb"
            file.save(str(pcb_path))

        if not pcb_path:
            return jsonify({'error': 'pcb_path required'}), 400

        from src.engines.pnp_exporter import extract_pnp_rows_from_kicad_pcb, export_pnp_csv, export_pnp_csv_via_kicad_cli

        csv_text = export_pnp_csv_via_kicad_cli(str(pcb_path), units="mm")
        export_method = "kicad-cli" if csv_text else "geometry"
        if not csv_text:
            rows = extract_pnp_rows_from_kicad_pcb(str(pcb_path))
            csv_text = export_pnp_csv(rows)

        # Count rows (exclude header).
        count = 0
        try:
            r = _csv.reader(_io.StringIO(csv_text))
            header = next(r, None)
            for _ in r:
                count += 1
        except Exception:
            count = max(0, len([ln for ln in csv_text.splitlines() if ln.strip()]) - 1)

        out_dir = Path(tempfile.gettempdir()) / 'circuit-ai' / 'pnp'
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{Path(str(pcb_path)).stem}-pnp.csv"
        out_path = out_dir / filename
        out_path.write_text(csv_text, encoding="utf-8")

        return jsonify(
            {
                "status": "success",
                "export_method": export_method,
                "count": count,
                "csv": csv_text,
                "csv_file": str(out_path),
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v2/report/dfm', methods=['POST'])
@require_api_key("report_dfm")
def dfm_report():
    """
    Generate an audit-style DFM report (Markdown) from an uploaded KiCad PCB.
    Optionally includes BOM/gerbers/PnP metadata when provided.
    """
    try:
        # Upload KiCad PCB.
        if 'pcb_file' not in request.files:
            return jsonify({'error': 'pcb_file required'}), 400
        file = request.files['pcb_file']
        temp_dir = Path(tempfile.gettempdir()) / 'circuit-ai'
        temp_dir.mkdir(exist_ok=True)
        pcb_path = temp_dir / f"{uuid.uuid4().hex[:8]}.kicad_pcb"
        file.save(str(pcb_path))

        hints = request.form.get('hints')
        if hints:
            import json as _json
            hints = _json.loads(hints)
        else:
            hints = None

        # Run validation workflow (same engine as validate-kicad endpoint).
        result = workflow_engine.execute_validation_workflow(kicad_file=str(pcb_path), hints=hints)

        # Convert to the same response format used by /api/v2/workflow/validate-kicad.
        response = {"status": result.status, "next_steps": result.next_steps}
        if result.validation_issues:
            critical = [i for i in result.validation_issues if i.severity == 'critical']
            errors = [i for i in result.validation_issues if i.severity == 'error']
            warnings = [i for i in result.validation_issues if i.severity == 'warning']
            response['validation'] = {
                'issues_count': len(result.validation_issues),
                'critical': len(critical),
                'errors': len(errors),
                'warnings': len(warnings),
                'issues': [
                    {
                        'severity': i.severity,
                        'component': i.component,
                        'issue': i.issue,
                        'solution': i.solution,
                        'physics': i.physics if hasattr(i, 'physics') else None
                    }
                    for i in result.validation_issues
                ]
            }
            response['manufacturing_ready'] = (len(critical) == 0 and len(errors) == 0 and result.status not in ['error', 'validation_failed', 'validation_partial'])
        else:
            response['validation'] = {'issues_count': 0, 'critical': 0, 'errors': 0, 'warnings': 0, 'issues': []}
            response['manufacturing_ready'] = False if result.status in ['error', 'validation_failed'] else True

        # Best-effort geometry
        try:
            from src.engines.kicad_pcb_geometry import extract_pcb_geometry
            response['pcb_geometry'] = extract_pcb_geometry(str(pcb_path))
        except Exception:
            pass

        # Render report markdown.
        from src.engines.dfm_report import render_dfm_report_markdown
        md = render_dfm_report_markdown(
            title=f"DFM Preflight — {Path(str(pcb_path)).stem}",
            validation_response=response,
        )

        out_dir = Path(tempfile.gettempdir()) / 'circuit-ai' / 'reports'
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{Path(str(pcb_path)).stem}-dfm-report.md"
        out_path = out_dir / filename
        out_path.write_text(md, encoding="utf-8")

        return jsonify(
            {
                "status": "success",
                "report_md": md,
                "report_file": str(out_path),
                "validation": response.get("validation"),
                "manufacturing_ready": response.get("manufacturing_ready"),
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v2/manufacture/package', methods=['POST'])
@require_api_key("manufacture_package")
def manufacture_package():
    """
    Build a single ZIP containing:
    - DFM_REPORT.md
    - BOM.csv (best-effort: prefers netlist, falls back to footprint/value grouping from PCB geometry)
    - PnP.csv
    - Gerbers.zip (NOTE: may be placeholder if KiCad CLI is not installed)

    Request (multipart/form-data):
    - pcb_file: required
    - netlist_file: optional (preferred for accurate BOM)
    - sch_file: optional (used to generate netlist via `kicad-cli` when netlist_file omitted)
    """
    try:
        if 'pcb_file' not in request.files:
            return jsonify({'error': 'pcb_file required'}), 400
        pcb_file = request.files['pcb_file']
        temp_dir = Path(tempfile.gettempdir()) / 'circuit-ai'
        temp_dir.mkdir(exist_ok=True)
        pcb_path = temp_dir / f"{uuid.uuid4().hex[:8]}.kicad_pcb"
        pcb_file.save(str(pcb_path))

        # Optional netlist upload for more accurate BOM.
        netlist_path = None
        if 'netlist_file' in request.files:
            nf = request.files['netlist_file']
            netlist_path = temp_dir / f"{uuid.uuid4().hex[:8]}.net"
            nf.save(str(netlist_path))

        # Optional schematic upload: if provided and netlist missing, try generating one.
        sch_path = None
        if 'sch_file' in request.files:
            sf = request.files['sch_file']
            sch_path = temp_dir / f"{uuid.uuid4().hex[:8]}.kicad_sch"
            sf.save(str(sch_path))

        netlist_export_method = "upload" if netlist_path else None
        netlist_export_error = None
        if netlist_path is None and sch_path is not None and shutil.which("kicad-cli"):
            try:
                netlist_path = temp_dir / f"{uuid.uuid4().hex[:8]}.net"
                subprocess.run(
                    [
                        "kicad-cli",
                        "sch",
                        "export",
                        "netlist",
                        "--format",
                        "kicadsexpr",
                        "--output",
                        str(netlist_path),
                        str(sch_path),
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=120,
                )
                netlist_export_method = "kicad-cli"
            except Exception as e:
                netlist_path = None
                netlist_export_method = "failed"
                netlist_export_error = str(e)

        strict = (request.form.get("strict") or "").strip().lower() in ("1", "true", "yes", "on")
        allow_incomplete = (request.form.get("allow_incomplete") or "").strip().lower() in ("1", "true", "yes", "on")
        if allow_incomplete:
            strict = False

        intake_id = (request.form.get("intake_id") or "").strip() or None
        hints = request.form.get("hints")
        if hints:
            import json as _json
            hints = _json.loads(hints)
        elif intake_id:
            hints = _load_hints_from_intake_id(intake_id)
        else:
            hints = None

        readiness = None
        if intake_id:
            req = _load_requirements_from_intake_id(intake_id)
            if isinstance(req, dict):
                try:
                    from src.engines.requirements_intake import evaluate_requirements
                    readiness = evaluate_requirements(req)
                except Exception:
                    readiness = None
        block = _should_block_for_intake(readiness, strict=strict)
        if block:
            return jsonify(block), 400

        result = _build_manufacturing_package(
            pcb_path=pcb_path,
            netlist_path=netlist_path,
            hints=hints,
            intake_id=intake_id,
            netlist_export_method=netlist_export_method,
            netlist_export_error=netlist_export_error,
        )
        if readiness:
            result["readiness"] = readiness
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v2/manufacture/download-package/<filename>', methods=['GET'])
@require_api_key("download_package")
def download_package(filename):
    try:
        packages_dir = Path(tempfile.gettempdir()) / 'circuit-ai' / 'packages'
        file_path = packages_dir / filename

        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404

        return send_file(
            file_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# V2 API - REQUIREMENTS INTAKE (iterative constraints)
# ============================================================================

def _intake_dir() -> Path:
    return Path(tempfile.gettempdir()) / "circuit-ai" / "intakes"

def _load_hints_from_intake_id(intake_id: str) -> Optional[Dict[str, Any]]:
    """
    Best-effort load of a previously compiled intake's `hints.json`.
    """
    if not intake_id:
        return None
    try:
        p = _intake_dir() / intake_id / "hints.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def _load_requirements_from_intake_id(intake_id: str) -> Optional[Dict[str, Any]]:
    if not intake_id:
        return None
    try:
        p = _intake_dir() / intake_id / "requirements.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def _load_intake_json(intake_id: str, filename: str) -> Optional[Dict[str, Any]]:
    if not intake_id or not filename:
        return None
    try:
        p = _intake_dir() / intake_id / filename
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def _diff_sets(a: List[str], b: List[str]) -> Dict[str, List[str]]:
    sa = set([str(x) for x in a if str(x)])
    sb = set([str(x) for x in b if str(x)])
    return {"added": sorted(sb - sa), "removed": sorted(sa - sb)}


def _render_revision_diff_md(diff: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Revision Diff")
    lines.append("")
    lines.append(f"- Project: `{diff.get('project_id')}`")
    lines.append(f"- From revision: `{diff.get('from_revision_id')}`")
    lines.append(f"- To revision: `{diff.get('to_revision_id')}`")
    lines.append("")
    lines.append("## Readiness")
    lines.append(f"- from: `{diff.get('from_readiness')}`")
    lines.append(f"- to: `{diff.get('to_readiness')}`")
    lines.append("")
    lines.append("## Quality")
    lines.append(f"- from: `{diff.get('from_quality')}`")
    lines.append(f"- to: `{diff.get('to_quality')}`")
    lines.append("")
    lines.append("## Blockers")
    blockers = diff.get("blockers") or {}
    for k in ("added", "removed"):
        vals = blockers.get(k) or []
        if vals:
            lines.append(f"- {k}: `{', '.join(vals[:12])}`" + (" …" if len(vals) > 12 else ""))
    if not (blockers.get("added") or blockers.get("removed")):
        lines.append("- No blocker changes.")
    lines.append("")
    lines.append("## Issues")
    issues = diff.get("issues") or {}
    for k in ("added", "removed"):
        vals = issues.get(k) or []
        if vals:
            lines.append(f"- {k}: `{', '.join(vals[:12])}`" + (" …" if len(vals) > 12 else ""))
    if not (issues.get("added") or issues.get("removed")):
        lines.append("- No issue-type changes.")
    lines.append("")
    lines.append("## Notes")
    lines.append("- Diffs are based on stored intake artifacts (readiness/blockers/issue types).")
    return "\n".join(lines).rstrip() + "\n"


def _build_manufacturing_package(
    *,
    pcb_path: Path,
    netlist_path: Optional[Path],
    hints: Optional[Dict[str, Any]],
    intake_id: Optional[str],
    netlist_export_method: Optional[str],
    netlist_export_error: Optional[str],
) -> Dict[str, Any]:
    """
    Core implementation shared by multiple endpoints.
    """
    # 1) Validation response (for report)
    validation = workflow_engine.execute_validation_workflow(kicad_file=str(pcb_path), hints=hints)
    validation_resp = {"status": validation.status, "next_steps": validation.next_steps, "manufacturing_ready": False, "validation": {"issues": []}}
    if validation.validation_issues:
        validation_resp["validation"]["issues"] = [
            {"severity": i.severity, "component": i.component, "issue": i.issue, "solution": i.solution, "physics": i.physics if hasattr(i, 'physics') else None}
            for i in validation.validation_issues
        ]

    # 2) PnP CSV (prefer KiCad CLI export)
    from src.engines.pnp_exporter import extract_pnp_rows_from_kicad_pcb, export_pnp_csv, export_pnp_csv_via_kicad_cli
    pnp_csv = export_pnp_csv_via_kicad_cli(str(pcb_path), units="mm")
    pnp_export_method = "kicad-cli" if pnp_csv else "geometry"
    if not pnp_csv:
        pnp_rows = extract_pnp_rows_from_kicad_pcb(str(pcb_path))
        pnp_csv = export_pnp_csv(pnp_rows)

    # 3) BOM CSV (prefer netlist; fall back to PCB geometry grouping)
    bom_summary = None
    bom_csv = None
    if netlist_path:
        from engines.bom_generator import BOMGenerator
        bg = BOMGenerator()
        bom = bg.generate_bom(str(netlist_path), include_pricing=False)
        if bom.get("status") == "success":
            bom_summary = bom.get("summary")
            bom_csv = bg.export_csv(bom)

    if bom_csv is None:
        from src.engines.kicad_pcb_geometry import extract_pcb_geometry
        geom = extract_pcb_geometry(str(pcb_path))
        items: Dict[Tuple[str, str], List[str]] = {}
        for fp in (geom.get("footprints") or []):
            if not isinstance(fp, dict):
                continue
            key = (str(fp.get("value") or ""), str(fp.get("footprint") or ""))
            items.setdefault(key, []).append(str(fp.get("ref") or "?"))
        lines = ["References,Value,Footprint,Quantity"]
        for (value, footprint), refs in sorted(items.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            refs = sorted(set(refs))
            lines.append(f"\"{' '.join(refs)}\",\"{value}\",\"{footprint}\",{len(refs)}")
        bom_csv = "\n".join(lines) + "\n"
        bom_summary = {"total_components": sum(len(v) for v in items.values()), "unique_parts": len(items)}

    # 4) Gerbers ZIP
    from engines.gerber_generator import GerberGenerator
    gg = GerberGenerator()
    gerb_pkg = gg.generate_gerber_package(str(pcb_path))
    export_method = gerb_pkg.get("export_method", "unknown")

    gerbers_dir = Path(tempfile.gettempdir()) / 'circuit-ai' / 'gerbers'
    gerbers_dir.mkdir(parents=True, exist_ok=True)
    gerbers_zip_name = f"{pcb_path.stem}-gerbers.zip"
    gerbers_zip_path = gerbers_dir / gerbers_zip_name
    gg.create_gerber_zip(gerb_pkg, output_path=str(gerbers_zip_path))

    # 5) Report markdown
    from src.engines.dfm_report import render_dfm_report_markdown
    report_md = render_dfm_report_markdown(
        title=f"DFM Preflight — {pcb_path.stem}",
        validation_response=validation_resp,
        bom_summary=bom_summary,
        pnp_csv_filename="PnP.csv",
        gerber_zip_filename="Gerbers.zip",
        export_method=export_method,
        pnp_export_method=pnp_export_method,
        netlist_export_method=netlist_export_method,
    )

    # 6) Package zip
    from src.engines.package_builder import build_package_zip
    packages_dir = Path(tempfile.gettempdir()) / 'circuit-ai' / 'packages'
    packages_dir.mkdir(parents=True, exist_ok=True)
    pkg_name = f"{pcb_path.stem}-package.zip"
    pkg_path = packages_dir / pkg_name
    kicad_cli_version = None
    if shutil.which("kicad-cli"):
        try:
            kicad_cli_version = subprocess.check_output(["kicad-cli", "--version"], text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            kicad_cli_version = None
    pkg = build_package_zip(
        out_path=pkg_path,
        report_md=report_md,
        bom_csv=bom_csv,
        pnp_csv=pnp_csv,
        gerbers_zip_path=gerbers_zip_path,
        metadata={
            "kicad_cli_version": kicad_cli_version,
            "gerbers_export_method": export_method,
            "pnp_export_method": pnp_export_method,
            "netlist_export_method": netlist_export_method,
            "netlist_export_error": netlist_export_error,
            "intake_id": intake_id,
        },
    )

    return {
        "status": "success",
        "export_method": export_method,
        "pnp_export_method": pnp_export_method,
        "netlist_export_method": netlist_export_method,
        "netlist_export_error": netlist_export_error,
        "package_file": str(pkg.zip_path),
        "download_url": f"/api/v2/manufacture/download-package/{pkg.zip_path.name}",
        "manifest": pkg.manifest,
    }


def _should_block_for_intake(readiness: Optional[Dict[str, Any]], *, strict: bool) -> Optional[Dict[str, Any]]:
    """
    Decide whether to block package generation due to insufficient requirements readiness.

    In strict mode we require at least 'reviewable'. 'draft' means critical constraints are missing.
    """
    if not strict:
        return None
    if not readiness:
        return {"error": "strict mode requires intake readiness, but none was provided"}
    if readiness.get("readiness_level") == "draft":
        return {"error": "requirements not ready (draft)", "readiness": readiness}
    return None


def _save_intake_artifacts(intake_id: str, artifacts: Dict[str, Any]) -> Dict[str, str]:
    """
    Writes known artifacts to disk (best-effort) and returns saved paths.
    """
    out_dir = _intake_dir() / intake_id
    out_dir.mkdir(parents=True, exist_ok=True)

    saved: Dict[str, str] = {}
    for key, filename in (
        ("requirements", "requirements.json"),
        ("evidence", "evidence.json"),
        ("hints", "hints.json"),
        ("lane_checks", "lane_checks.json"),
        ("capabilities", "capabilities.json"),
        ("questions_md", "questions.md"),
        ("assumptions_md", "assumptions.md"),
        ("risk_register_md", "risk_register.md"),
        ("sow_md", "SOW.md"),
    ):
        if key not in artifacts:
            continue
        path = out_dir / filename
        val = artifacts[key]
        if isinstance(val, (dict, list)):
            path.write_text(json.dumps(val, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        else:
            path.write_text(str(val).rstrip() + "\n", encoding="utf-8")
        saved[key] = str(path)
    return saved


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_exec(query: str, params: Tuple[Any, ...] = ()) -> None:
    con = _open_usage_db()
    try:
        _init_usage_schema(con)
        con.execute(query, params)
        con.commit()
    finally:
        con.close()


def _db_fetchone(query: str, params: Tuple[Any, ...] = ()) -> Optional[Tuple[Any, ...]]:
    con = _open_usage_db()
    try:
        _init_usage_schema(con)
        return con.execute(query, params).fetchone()
    finally:
        con.close()


def _db_fetchall(query: str, params: Tuple[Any, ...] = ()) -> List[Tuple[Any, ...]]:
    con = _open_usage_db()
    try:
        _init_usage_schema(con)
        return con.execute(query, params).fetchall()
    finally:
        con.close()


@app.route("/api/v2/intake/template", methods=["GET"])
@require_api_key("intake_template")
def intake_template():
    lane = (request.args.get("lane") or "generic").strip()
    design_intent = (request.args.get("design_intent") or "").strip() or None
    from src.engines.requirements_intake import LANES, DESIGN_INTENTS, template_for_lane

    if lane not in LANES:
        return jsonify({"error": f"unknown lane: {lane}", "lanes": sorted(LANES.keys())}), 400
    req = template_for_lane(lane)
    if design_intent:
        if design_intent not in DESIGN_INTENTS:
            return jsonify({"error": f"unknown design_intent: {design_intent}", "design_intents": sorted(DESIGN_INTENTS.keys())}), 400
        req["meta"]["design_intent"] = design_intent
    return jsonify(
        {
            "status": "success",
            "lane": lane,
            "design_intents": sorted(DESIGN_INTENTS.keys()),
            "requirements": req,
        }
    )


@app.route("/api/v2/intake/compile", methods=["POST"])
@require_api_key("intake_compile")
def intake_compile():
    """
    Compile a requirements JSON into:
    - Circuit-AI `hints` (structured inputs for validation)
    - questions/assumptions/risk register
    - an SOW (scope + exclusions + acceptance criteria)

    Request:
    - JSON body: { "requirements": {...} }
      OR multipart/form-data with `requirements_file`
    """
    try:
        requirements = None
        evidence = None
        if request.is_json:
            payload = request.get_json() or {}
            requirements = payload.get("requirements")
            evidence = payload.get("evidence")
        else:
            if "requirements_file" in request.files:
                rf = request.files["requirements_file"]
                requirements = json.loads(rf.read().decode("utf-8", errors="strict"))
            if "netlist_file" in request.files:
                # Optional file-backed evidence extraction
                try:
                    nf = request.files["netlist_file"]
                    temp_dir = Path(tempfile.gettempdir()) / "circuit-ai"
                    temp_dir.mkdir(exist_ok=True)
                    net_path = temp_dir / f"{uuid.uuid4().hex[:8]}.net"
                    nf.save(str(net_path))
                    from src.engines.evidence_extractor import extract_evidence_from_kicad_netlist

                    evidence = extract_evidence_from_kicad_netlist(net_path)
                except Exception:
                    evidence = None

        if not isinstance(requirements, dict):
            return jsonify({"error": "requirements object required"}), 400

        from src.engines.requirements_intake import (
            LANES,
            DESIGN_INTENTS,
            build_questions_and_assumptions,
            compile_to_circuit_ai_hints,
            evaluate_requirements,
            run_lane_checks,
            build_capability_matrix,
            render_sow,
        )

        lane = ((requirements.get("meta") or {}).get("lane") or "generic").strip()
        design_intent = ((requirements.get("meta") or {}).get("design_intent") or "prototype").strip()
        if lane not in LANES:
            return jsonify({"error": f"unknown lane: {lane}", "lanes": sorted(LANES.keys())}), 400
        if design_intent not in DESIGN_INTENTS:
            return jsonify({"error": f"unknown design_intent: {design_intent}", "design_intents": sorted(DESIGN_INTENTS.keys())}), 400

        hints = compile_to_circuit_ai_hints(requirements)
        questions, assumptions, risks = build_questions_and_assumptions(requirements)
        readiness = evaluate_requirements(requirements)
        lane_checks = run_lane_checks(requirements)
        capabilities = build_capability_matrix(requirements, readiness=readiness, lane_checks=lane_checks)
        sow = render_sow(requirements, questions, assumptions, risks)

        artifacts = {
            "requirements": requirements,
            "evidence": evidence if isinstance(evidence, dict) else None,
            "hints": hints,
            "lane_checks": lane_checks,
            "capabilities": capabilities,
            "questions_md": "\n".join([f"- {q}" for q in questions]) + ("\n" if questions else ""),
            "assumptions_md": "\n".join([f"- {a}" for a in assumptions]) + ("\n" if assumptions else ""),
            "risk_register_md": "\n".join([f"- {r}" for r in risks]) + ("\n" if risks else ""),
            "sow_md": sow,
        }

        intake_id = uuid.uuid4().hex[:10]
        saved_paths = _save_intake_artifacts(intake_id, artifacts)

        return jsonify(
            {
                "status": "success",
                "intake_id": intake_id,
                "lane": lane,
                "readiness": readiness,
                "lane_checks": lane_checks,
                "capabilities": capabilities,
                "evidence": evidence if isinstance(evidence, dict) else None,
                "hints": hints,
                "questions": questions,
                "assumptions": assumptions,
                "risks": risks,
                "sow_md": sow,
                "saved_paths": saved_paths,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/v2/intake/<intake_id>", methods=["GET"])
@require_api_key("intake_get")
def intake_get(intake_id: str):
    out_dir = _intake_dir() / intake_id
    if not out_dir.exists():
        return jsonify({"error": "not found"}), 404

    def read_text(name: str) -> Optional[str]:
        p = out_dir / name
        if p.exists():
            return p.read_text(encoding="utf-8", errors="replace")
        return None

    def read_json(name: str) -> Optional[Dict[str, Any]]:
        p = out_dir / name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    return jsonify(
        {
            "status": "success",
            "intake_id": intake_id,
            "requirements": read_json("requirements.json"),
            "evidence": read_json("evidence.json"),
            "hints": read_json("hints.json"),
            "lane_checks": read_json("lane_checks.json"),
            "capabilities": read_json("capabilities.json"),
            "questions_md": read_text("questions.md"),
            "assumptions_md": read_text("assumptions.md"),
            "risk_register_md": read_text("risk_register.md"),
            "sow_md": read_text("SOW.md"),
        }
    )


# ============================================================================
# V2 API - SIMULATION (SPICE / ngspice)
# ============================================================================

@app.route("/api/v2/simulate/spice", methods=["POST"])
@require_api_key("simulate_spice")
def simulate_spice():
    """
    Run a SPICE netlist using ngspice if available.

    Request:
      - multipart/form-data with `netlist_file` (text) OR JSON {"netlist_text": "..."}
      - optional: timeout_s (int)
    """
    try:
        netlist_text = None
        timeout_s = 60
        if request.is_json:
            payload = request.get_json() or {}
            netlist_text = payload.get("netlist_text")
            timeout_s = int(payload.get("timeout_s") or timeout_s)
        else:
            if "netlist_file" in request.files:
                nf = request.files["netlist_file"]
                netlist_text = nf.read().decode("utf-8", errors="replace")
            if request.form.get("timeout_s"):
                timeout_s = int(request.form.get("timeout_s") or timeout_s)

        if not netlist_text or not isinstance(netlist_text, str):
            return jsonify({"error": "netlist_text required"}), 400

        from src.engines.spice_runner import run_ngspice

        result = run_ngspice(netlist_text=netlist_text, timeout_s=timeout_s)
        if not result.get("ok"):
            # 501 is appropriate when the host does not support the requested operation.
            if result.get("error") == "ngspice_not_available":
                return jsonify(result), 501
        return jsonify({"status": "success", "result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# V2 API - CONSOLIDATED EE QUALITY REPORT
# ============================================================================

@app.route("/api/v2/report/ee-quality", methods=["POST"])
@require_api_key("report_ee_quality")
def report_ee_quality():
    """
    Generate a consolidated EE quality report (readiness + checks + capability matrix),
    optionally grounded by file-backed evidence (KiCad netlist, PCB).

    Request:
      - JSON: { "requirements": {...}, "evidence": {... optional ...} }
      OR multipart/form-data:
        - requirements_file (json) OR requirements (json string)
        - optional: netlist_file (.net), pcb_file (.kicad_pcb)
    """
    try:
        requirements = None
        evidence = None
        pcb_path = None

        if request.is_json:
            payload = request.get_json() or {}
            requirements = payload.get("requirements")
            evidence = payload.get("evidence")
        else:
            if request.form.get("requirements"):
                try:
                    requirements = json.loads(request.form.get("requirements") or "{}")
                except Exception:
                    requirements = None
            if requirements is None and "requirements_file" in request.files:
                rf = request.files["requirements_file"]
                requirements = json.loads(rf.read().decode("utf-8", errors="strict"))

            if "netlist_file" in request.files:
                try:
                    nf = request.files["netlist_file"]
                    temp_dir = Path(tempfile.gettempdir()) / "circuit-ai"
                    temp_dir.mkdir(exist_ok=True)
                    net_path = temp_dir / f"{uuid.uuid4().hex[:8]}.net"
                    nf.save(str(net_path))
                    from src.engines.evidence_extractor import extract_evidence_from_kicad_netlist

                    evidence = extract_evidence_from_kicad_netlist(net_path)
                except Exception:
                    evidence = None

            if "pcb_file" in request.files:
                pf = request.files["pcb_file"]
                temp_dir = Path(tempfile.gettempdir()) / "circuit-ai"
                temp_dir.mkdir(exist_ok=True)
                pcb_path = temp_dir / f"{uuid.uuid4().hex[:8]}.kicad_pcb"
                pf.save(str(pcb_path))

        if not isinstance(requirements, dict):
            return jsonify({"error": "requirements object required"}), 400
        if isinstance(evidence, dict):
            requirements = dict(requirements)
            requirements["evidence"] = evidence

        from src.engines.requirements_intake import (
            build_questions_and_assumptions,
            build_capability_matrix,
            evaluate_requirements,
            render_sow,
            run_lane_checks,
        )
        from src.engines.ee_quality_report import render_ee_quality_report_md

        questions, assumptions, risks = build_questions_and_assumptions(requirements)
        readiness = evaluate_requirements(requirements)
        lane_checks = run_lane_checks(requirements)
        capabilities = build_capability_matrix(requirements, readiness=readiness, lane_checks=lane_checks)
        sow_md = render_sow(requirements, questions, assumptions, risks)

        layout_report_md = None
        if pcb_path is not None:
            try:
                from src.engines.layout_advisor import render_layout_advice_md

                layout_report_md = render_layout_advice_md(Path(pcb_path))
            except Exception:
                layout_report_md = None

        report_md = render_ee_quality_report_md(
            requirements=requirements,
            readiness=readiness,
            lane_checks=lane_checks,
            capabilities=capabilities,
            sow_md=sow_md,
            layout_report_md=layout_report_md,
        )

        return jsonify(
            {
                "status": "success",
                "readiness": readiness,
                "lane_checks": lane_checks,
                "capabilities": capabilities,
                "questions": questions,
                "assumptions": assumptions,
                "risks": risks,
                "report_md": report_md,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# V2 API - MECHANICAL BOM (catalog-driven)
# ============================================================================

@app.route("/api/v2/mechanical/bom", methods=["POST"])
@require_api_key("mechanical_bom")
def mechanical_bom():
    """
    Build candidate mechanical BOMs from a local catalog (Shopee-friendly).

    Request JSON:
      {
        "work_area_mm": [w, h],
        "accuracy_mm": 0.25,
        "prefer": "cheapest" | "balanced"
      }
    """
    try:
        if not request.is_json:
            return jsonify({"error": "JSON body required"}), 400
        payload = request.get_json() or {}
        work_area = payload.get("work_area_mm") or [100, 100]
        w = int(work_area[0]) if isinstance(work_area, list) and len(work_area) >= 2 else 100
        h = int(work_area[1]) if isinstance(work_area, list) and len(work_area) >= 2 else 100
        accuracy_mm = float(payload.get("accuracy_mm") or 0.25)
        prefer = str(payload.get("prefer") or "cheapest").strip().lower()
        if prefer not in ("cheapest", "balanced"):
            prefer = "cheapest"

        from src.engines.mechanical_catalog import (
            build_candidate_boms,
            catalog_default_path,
            load_catalog_jsonl,
        )

        repo_root = Path(__file__).resolve().parent
        catalog_path = catalog_default_path(repo_root)
        catalog = load_catalog_jsonl(catalog_path)
        result = build_candidate_boms(catalog=catalog, work_area_mm=(w, h), accuracy_mm=accuracy_mm, prefer=prefer)
        result["catalog_path"] = str(catalog_path)
        result["catalog_items"] = len(catalog)
        return jsonify({"status": "success", "result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# V2 API - LAYOUT ADVICE (KiCad / pcbnew)
# ============================================================================

@app.route("/api/v2/layout/advice", methods=["POST"])
@require_api_key("layout_advice")
def layout_advice():
    """
    Generate heuristic layout advice + a pcbnew helper script.

    Request:
      - multipart/form-data with `pcb_file` (.kicad_pcb)
    """
    try:
        if "pcb_file" not in request.files:
            return jsonify({"error": "pcb_file required"}), 400
        pcb_file = request.files["pcb_file"]
        temp_dir = Path(tempfile.gettempdir()) / "circuit-ai"
        temp_dir.mkdir(exist_ok=True)
        pcb_path = temp_dir / f"{uuid.uuid4().hex[:8]}.kicad_pcb"
        pcb_file.save(str(pcb_path))

        from src.engines.layout_advisor import render_layout_advice_md, render_pcbnew_script, summarize_board

        report_md = render_layout_advice_md(pcb_path)
        script_py = render_pcbnew_script(pcb_path)
        summary = summarize_board(pcb_path)

        return jsonify(
            {
                "status": "success",
                "board": summary.get("board"),
                "report_md": report_md,
                "pcbnew_script_py": script_py,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# V2 API - PROTOTYPE 3D (OpenSCAD text + wiring plan)
# ============================================================================

@app.route("/api/v2/prototype3d/package", methods=["POST"])
@require_api_key("prototype3d_package")
def prototype3d_package():
    """
    Generate a prototype-mode 3D mounting plate OpenSCAD stub + wiring plan.

    Request:
      - multipart/form-data with `pcb_file` (.kicad_pcb)
      - optional: `requirements` JSON (string) OR `requirements_file` upload
    """
    try:
        if "pcb_file" not in request.files:
            return jsonify({"error": "pcb_file required"}), 400
        pcb_file = request.files["pcb_file"]
        temp_dir = Path(tempfile.gettempdir()) / "circuit-ai"
        temp_dir.mkdir(exist_ok=True)
        pcb_path = temp_dir / f"{uuid.uuid4().hex[:8]}.kicad_pcb"
        pcb_file.save(str(pcb_path))

        requirements = None
        if request.form.get("requirements"):
            try:
                requirements = json.loads(request.form.get("requirements") or "{}")
            except Exception:
                requirements = None
        if requirements is None and "requirements_file" in request.files:
            try:
                rf = request.files["requirements_file"]
                requirements = json.loads(rf.read().decode("utf-8", errors="strict"))
            except Exception:
                requirements = None

        from src.engines.prototype3d_generator import build_prototype3d_artifacts

        artifacts = build_prototype3d_artifacts(pcb_path, requirements=requirements if isinstance(requirements, dict) else None)
        return jsonify({"status": "success", "artifacts": artifacts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# V2 API - ROBOT MVP (probe plan + G-code + runlog)
# ============================================================================

@app.route("/api/v2/robot/probe-plan/template", methods=["GET"])
@require_api_key("robot_probe_plan_template")
def robot_probe_plan_template():
    from src.engines.cam.probe_plan import probe_plan_template
    return jsonify({"status": "success", "template": probe_plan_template()})


@app.route("/api/v2/robot/probe-plan", methods=["POST"])
@require_api_key("robot_probe_plan")
def robot_probe_plan():
    """
    Build a software-only probe plan from a KiCad PCB:
    - resolves refs to footprint centroids (best-effort)
    - outputs G-code with pauses (human-in-the-loop)
    - outputs a runlog CSV template

    Request: multipart/form-data
      - pcb_file: required (.kicad_pcb)
      - plan: optional JSON string (see /template)
    """
    try:
        if "pcb_file" not in request.files:
            return jsonify({"error": "pcb_file required"}), 400

        plan = None
        if request.form.get("plan"):
            try:
                plan = json.loads(request.form.get("plan") or "{}")
            except Exception:
                plan = None
        if not isinstance(plan, dict):
            plan = {}

        pcb_file = request.files["pcb_file"]
        temp_dir = Path(tempfile.gettempdir()) / "circuit-ai"
        temp_dir.mkdir(exist_ok=True)
        pcb_path = temp_dir / f"{uuid.uuid4().hex[:8]}.kicad_pcb"
        pcb_file.save(str(pcb_path))

        from src.engines.cam.probe_plan import (
            build_probe_gcode,
            build_probe_points,
            render_probe_report_md,
            render_runlog_csv,
        )

        points = build_probe_points(pcb_path, plan=plan)
        gcode = build_probe_gcode(
            points,
            travel_z=float(plan.get("travel_z") or 5.0),
            work_z=float(plan.get("work_z") or -0.1),
            feed_xy=int(plan.get("feed_xy") or 1200),
            feed_z=int(plan.get("feed_z") or 120),
            home_first=bool(plan.get("home_first", True)),
            auto_plunge=bool(plan.get("auto_plunge", False)),
        )
        runlog_csv = render_runlog_csv(points)
        report_md = render_probe_report_md(
            pcb_filename=pcb_file.filename or pcb_path.name,
            points=points,
            gcode_preview=gcode,
            dry_run=not bool(plan.get("auto_plunge", False)),
        )

        return jsonify(
            {
                "status": "success",
                "points": [p.__dict__ for p in points],
                "gcode": gcode,
                "runlog_csv": runlog_csv,
                "report_md": report_md,
                "notes": [
                    "Footprint centroid probing is best-effort. For pad-level probing you need calibration + pad geometry mapping.",
                    "Always test with pen-in-air / probe lifted before touching a PCB.",
                ],
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# V2 API - PROJECTS (iteration & revision tracking)
# ============================================================================

@app.route("/api/v2/projects", methods=["POST"])
@require_api_key("projects_create")
def projects_create():
    """
    Create a project container for iterative work.

    Request JSON:
    - name: required
    - lane: optional (generic|power|rf|automotive|compliance)
    - design_intent: optional (prototype|professional)
    """
    if not request.is_json:
        return jsonify({"error": "JSON body required"}), 400
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400

    from src.engines.requirements_intake import LANES, DESIGN_INTENTS

    lane = (data.get("lane") or "generic").strip()
    design_intent = (data.get("design_intent") or "prototype").strip()
    if lane not in LANES:
        return jsonify({"error": f"unknown lane: {lane}", "lanes": sorted(LANES.keys())}), 400
    if design_intent not in DESIGN_INTENTS:
        return jsonify({"error": f"unknown design_intent: {design_intent}", "design_intents": sorted(DESIGN_INTENTS.keys())}), 400

    project_id = uuid.uuid4().hex[:10]
    _db_exec(
        "INSERT INTO projects (id, created_at, name, lane, design_intent) VALUES (?, ?, ?, ?, ?)",
        (project_id, _utc_now(), name, lane, design_intent),
    )
    return jsonify({"status": "success", "project_id": project_id, "name": name, "lane": lane, "design_intent": design_intent})


@app.route("/api/v2/projects/<project_id>", methods=["GET"])
@require_api_key("projects_get")
def projects_get(project_id: str):
    row = _db_fetchone("SELECT id, created_at, name, lane, design_intent FROM projects WHERE id=?", (project_id,))
    if not row:
        return jsonify({"error": "not found"}), 404
    latest = _db_fetchone(
        "SELECT id, created_at, intake_id, notes FROM project_revisions WHERE project_id=? ORDER BY created_at DESC LIMIT 1",
        (project_id,),
    )
    return jsonify(
        {
            "status": "success",
            "project": {"id": row[0], "created_at": row[1], "name": row[2], "lane": row[3], "design_intent": row[4]},
            "latest_revision": {"id": latest[0], "created_at": latest[1], "intake_id": latest[2], "notes": latest[3]} if latest else None,
        }
    )


@app.route("/api/v2/projects/<project_id>/revisions", methods=["GET"])
@require_api_key("projects_revisions_list")
def projects_revisions_list(project_id: str):
    rows = _db_fetchall(
        "SELECT id, created_at, intake_id, notes FROM project_revisions WHERE project_id=? ORDER BY created_at ASC",
        (project_id,),
    )
    return jsonify(
        {
            "status": "success",
            "project_id": project_id,
            "revisions": [{"id": r[0], "created_at": r[1], "intake_id": r[2], "notes": r[3]} for r in rows],
        }
    )


@app.route("/api/v2/projects/<project_id>/revisions", methods=["POST"])
@require_api_key("projects_revision_create")
def projects_revision_create(project_id: str):
    """
    Create a new revision.

    Request JSON:
    - requirements: optional (if omitted, server uses project lane/design_intent template)
    - notes: optional
    """
    if not request.is_json:
        return jsonify({"error": "JSON body required"}), 400
    data = request.get_json() or {}
    notes = (data.get("notes") or "").strip()

    proj = _db_fetchone("SELECT lane, design_intent, name FROM projects WHERE id=?", (project_id,))
    if not proj:
        return jsonify({"error": "project not found"}), 404
    lane, design_intent, proj_name = proj[0], proj[1], proj[2]

    from src.engines.requirements_intake import (
        LANES,
        DESIGN_INTENTS,
        template_for_lane,
        compile_to_circuit_ai_hints,
        build_questions_and_assumptions,
        evaluate_requirements,
        render_sow,
    )
    if lane not in LANES or design_intent not in DESIGN_INTENTS:
        return jsonify({"error": "project has invalid lane/design_intent"}), 500

    requirements = data.get("requirements")
    if not isinstance(requirements, dict):
        requirements = template_for_lane(lane)
        requirements["meta"]["design_intent"] = design_intent
        requirements["meta"]["project_name"] = proj_name or ""

    hints = compile_to_circuit_ai_hints(requirements)
    questions, assumptions, risks = build_questions_and_assumptions(requirements)
    readiness = evaluate_requirements(requirements)
    sow = render_sow(requirements, questions, assumptions, risks)

    intake_id = uuid.uuid4().hex[:10]
    _save_intake_artifacts(
        intake_id,
        {
            "requirements": requirements,
            "hints": hints,
            "questions_md": "\n".join([f"- {q}" for q in questions]) + ("\n" if questions else ""),
            "assumptions_md": "\n".join([f"- {a}" for a in assumptions]) + ("\n" if assumptions else ""),
            "risk_register_md": "\n".join([f"- {r}" for r in risks]) + ("\n" if risks else ""),
            "sow_md": sow,
        },
    )

    revision_id = uuid.uuid4().hex[:10]
    _db_exec(
        "INSERT INTO project_revisions (id, created_at, project_id, requirements_json, intake_id, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (revision_id, _utc_now(), project_id, json.dumps(requirements), intake_id, notes),
    )
    return jsonify(
        {
            "status": "success",
            "project_id": project_id,
            "revision_id": revision_id,
            "intake_id": intake_id,
            "readiness": readiness,
            "questions": questions,
            "risks": risks,
            "sow_md": sow,
            "hints": hints,
        }
    )


@app.route("/api/v2/projects/<project_id>/build-package", methods=["POST"])
@require_api_key("projects_build_package")
def projects_build_package(project_id: str):
    """
    Convenience wrapper: build a manufacturing package using the latest (or specified) revision's intake_id/hints.
    """
    revision_id = (request.form.get("revision_id") or "").strip() or None
    if revision_id:
        row = _db_fetchone(
            "SELECT id, intake_id FROM project_revisions WHERE id=? AND project_id=?",
            (revision_id, project_id),
        )
    else:
        row = _db_fetchone(
            "SELECT id, intake_id FROM project_revisions WHERE project_id=? ORDER BY created_at DESC LIMIT 1",
            (project_id,),
        )
    if not row or not row[1]:
        return jsonify({"error": "no revision/intake found"}), 400
    resolved_revision_id = row[0]
    intake_id = row[1]

    # Validate optional caller-provided intake_id, but do not require it.
    provided_intake_id = (request.form.get("intake_id") or "").strip() or None
    if provided_intake_id and provided_intake_id != intake_id:
        return jsonify({"error": "intake_id does not match revision"}), 400

    # Save uploads similarly to /manufacture/package.
    if 'pcb_file' not in request.files:
        return jsonify({'error': 'pcb_file required'}), 400
    pcb_file = request.files['pcb_file']
    temp_dir = Path(tempfile.gettempdir()) / 'circuit-ai'
    temp_dir.mkdir(exist_ok=True)
    pcb_path = temp_dir / f"{uuid.uuid4().hex[:8]}.kicad_pcb"
    pcb_file.save(str(pcb_path))

    netlist_path = None
    if 'netlist_file' in request.files:
        nf = request.files['netlist_file']
        netlist_path = temp_dir / f"{uuid.uuid4().hex[:8]}.net"
        nf.save(str(netlist_path))

    sch_path = None
    if 'sch_file' in request.files:
        sf = request.files['sch_file']
        sch_path = temp_dir / f"{uuid.uuid4().hex[:8]}.kicad_sch"
        sf.save(str(sch_path))

    netlist_export_method = "upload" if netlist_path else None
    netlist_export_error = None
    if netlist_path is None and sch_path is not None and shutil.which("kicad-cli"):
        try:
            netlist_path = temp_dir / f"{uuid.uuid4().hex[:8]}.net"
            subprocess.run(
                [
                    "kicad-cli",
                    "sch",
                    "export",
                    "netlist",
                    "--format",
                    "kicadsexpr",
                    "--output",
                    str(netlist_path),
                    str(sch_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
            )
            netlist_export_method = "kicad-cli"
        except Exception as e:
            netlist_path = None
            netlist_export_method = "failed"
            netlist_export_error = str(e)

    hints = _load_hints_from_intake_id(intake_id)

    strict = (request.form.get("strict") or "").strip().lower() not in ("0", "false", "no", "off")
    allow_incomplete = (request.form.get("allow_incomplete") or "").strip().lower() in ("1", "true", "yes", "on")
    if allow_incomplete:
        strict = False

    readiness = None
    req = _load_requirements_from_intake_id(intake_id)
    lane_checks = None
    capabilities = None
    if isinstance(req, dict):
        try:
            from src.engines.requirements_intake import evaluate_requirements, run_lane_checks, build_capability_matrix
            readiness = evaluate_requirements(req)
            lane_checks = run_lane_checks(req)
            capabilities = build_capability_matrix(req, readiness=readiness, lane_checks=lane_checks)
        except Exception:
            readiness = None
    block = _should_block_for_intake(readiness, strict=strict)
    if block:
        return jsonify(block), 400

    result = _build_manufacturing_package(
        pcb_path=pcb_path,
        netlist_path=netlist_path,
        hints=hints,
        intake_id=intake_id,
        netlist_export_method=netlist_export_method,
        netlist_export_error=netlist_export_error,
    )
    if readiness:
        result["readiness"] = readiness
    if lane_checks:
        result["lane_checks"] = lane_checks
    if capabilities:
        result["capabilities"] = capabilities

    # Persist a build record for traceability.
    try:
        build_id = uuid.uuid4().hex[:10]
        _db_exec(
            "INSERT INTO project_builds (id, created_at, project_id, revision_id, package_file, manifest_json) VALUES (?, ?, ?, ?, ?, ?)",
            (build_id, _utc_now(), project_id, resolved_revision_id, result.get("package_file"), json.dumps(result.get("manifest") or {})),
        )
        result["project_build_id"] = build_id
        result["project_id"] = project_id
        result["revision_id"] = resolved_revision_id
    except Exception:
        pass

    return jsonify(result)


@app.route("/api/v2/projects/<project_id>/diff", methods=["GET"])
@require_api_key("projects_diff")
def projects_diff(project_id: str):
    """
    Diff two project revisions (readiness/quality/blockers/issues).

    Query params:
      - from: revision_id
      - to: revision_id
    """
    from_rev = (request.args.get("from") or "").strip()
    to_rev = (request.args.get("to") or "").strip()
    if not from_rev or not to_rev:
        return jsonify({"error": "from and to revision ids required"}), 400

    a = _db_fetchone("SELECT intake_id FROM project_revisions WHERE id=? AND project_id=?", (from_rev, project_id))
    b = _db_fetchone("SELECT intake_id FROM project_revisions WHERE id=? AND project_id=?", (to_rev, project_id))
    if not a or not a[0] or not b or not b[0]:
        return jsonify({"error": "revision not found or missing intake_id"}), 404

    intake_a = str(a[0])
    intake_b = str(b[0])

    req_a = _load_requirements_from_intake_id(intake_a) or {}
    req_b = _load_requirements_from_intake_id(intake_b) or {}

    lane_checks_a = _load_intake_json(intake_a, "lane_checks.json") or {}
    lane_checks_b = _load_intake_json(intake_b, "lane_checks.json") or {}

    try:
        from src.engines.requirements_intake import evaluate_requirements, run_lane_checks
    except Exception:
        evaluate_requirements = None
        run_lane_checks = None

    def compute_readiness_and_checks(req: Dict[str, Any], lc: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
        readiness_local: Dict[str, Any] = {}
        lc_local: Dict[str, Any] = lc or {}
        if callable(evaluate_requirements) and isinstance(req, dict):
            try:
                readiness_local = evaluate_requirements(req)
            except Exception:
                readiness_local = {}
        if (not isinstance(lc_local, dict) or not isinstance(lc_local.get("quality"), dict)) and callable(run_lane_checks):
            try:
                lc_local = run_lane_checks(req)
            except Exception:
                lc_local = lc or {}
        return readiness_local, lc_local

    readiness_a, lane_checks_a = compute_readiness_and_checks(req_a, lane_checks_a)
    readiness_b, lane_checks_b = compute_readiness_and_checks(req_b, lane_checks_b)

    blockers_a = list((readiness_a or {}).get("blockers") or [])
    blockers_b = list((readiness_b or {}).get("blockers") or [])

    issues_a = [str(i.get("type") or "") for i in (lane_checks_a.get("issues") or []) if isinstance(i, dict)]
    issues_b = [str(i.get("type") or "") for i in (lane_checks_b.get("issues") or []) if isinstance(i, dict)]

    qa = (lane_checks_a.get("quality") or {}) if isinstance(lane_checks_a.get("quality"), dict) else {}
    qb = (lane_checks_b.get("quality") or {}) if isinstance(lane_checks_b.get("quality"), dict) else {}
    from_quality = f"{qa.get('grade')}:{qa.get('score')}"
    to_quality = f"{qb.get('grade')}:{qb.get('score')}"

    diff = {
        "project_id": project_id,
        "from_revision_id": from_rev,
        "to_revision_id": to_rev,
        "from_intake_id": intake_a,
        "to_intake_id": intake_b,
        "from_readiness": (readiness_a or {}).get("readiness_level"),
        "to_readiness": (readiness_b or {}).get("readiness_level"),
        "from_quality": from_quality,
        "to_quality": to_quality,
        "blockers": _diff_sets(blockers_a, blockers_b),
        "issues": _diff_sets(issues_a, issues_b),
    }
    diff["diff_md"] = _render_revision_diff_md(diff)
    return jsonify({"status": "success", "diff": diff})


# ============================================================================
# V1 API - ORIGINAL ENDPOINTS
# ============================================================================

@app.route('/', methods=['GET'])
def index():
    """Landing page or API documentation"""
    # Serve landing page for browser requests, JSON for API clients
    if 'text/html' in request.headers.get('Accept', ''):
        return app.send_static_file('index.html')

    # Return JSON API docs for curl/API clients
    return jsonify({
        'service': 'Circuit-AI API',
        'version': '0.4.0',
        'description': 'Complete Arduino/IoT project assistant: Validate circuits, export to Fritzing, optimize inventory, get build instructions, follow structured learning paths, and professional PCB validation',
        'endpoints': {
            '=== V2 API - UNIFIED WORKFLOW ENGINE ===': '',
            'POST /api/v2/workflow/beginner': 'Complete beginner workflow (learning paths + projects)',
            'POST /api/v2/workflow/complete': 'End-to-end workflow (recipe → instructions → validation)',
            'POST /api/v2/workflow/validate-kicad': 'Professional KiCAD PCB validation',
            'GET /api/v2/intake/template': 'Requirements intake template',
            'POST /api/v2/intake/compile': 'Compile intake (readiness + questions + capability matrix)',
            'POST /api/v2/report/ee-quality': 'Consolidated EE quality report (optionally with netlist/pcb evidence)',
            'POST /api/v2/layout/advice': 'Heuristic layout advice + pcbnew helper script',
            'POST /api/v2/prototype3d/package': 'Prototype-mode OpenSCAD stub + wiring plan',
            'POST /api/v2/simulate/spice': 'Run SPICE netlist via ngspice (if installed)',
            '=== V1 API - CORE FEATURES ===': '',
            'GET /api/health': 'Health check',
            'GET /api/components': 'List available components',
            'POST /api/validate': 'Validate circuit design',
            'POST /api/export/fritzing': 'Export to Fritzing .fzz file',
            'POST /api/design': 'Complete design workflow',
            'POST /api/recipes/analyze-inventory': 'Analyze inventory value',
            'POST /api/recipes/generate': 'Generate project recipes from inventory',
            'POST /api/recipes/shopping-list': 'Get shopping list for project',
            'POST /api/recipes/filter': 'Advanced recipe filtering (difficulty, time, budget)',
            'POST /api/recipes/budget-optimize': 'Optimize project selection for budget',
            'GET /api/instructions': 'List projects with build instructions',
            'GET /api/instructions/<project_name>': 'Get detailed build instructions',
            'GET /api/learning-paths': 'List all learning paths',
            'GET /api/learning-paths/<path_id>': 'Get detailed learning path curriculum',
            'POST /api/learning-paths/recommend': 'Get personalized learning recommendations',
            'POST /api/pricing/component': 'Get real-time component pricing',
            'GET /api/pricing/market/<project_name>': 'Get market pricing for project'
        },
        'examples': {
            'validate': {
                'endpoint': '/api/validate',
                'method': 'POST',
                'body': {
                    'microcontroller': 'arduino_uno',
                    'components': ['bme280', 'servo_sg90'],
                    'external_power': False
                }
            },
            'recipes': {
                'endpoint': '/api/recipes/generate',
                'method': 'POST',
                'body': {
                    'inventory': [
                        {'id': 'arduino_uno', 'condition': 'used', 'quantity': 1},
                        {'id': 'bme280', 'condition': 'new', 'quantity': 1}
                    ],
                    'top_n': 5,
                    'validate': True
                }
            }
        },
        'value_proposition': [
            '🎓 EDUCATION → PROFESSIONAL: Complete workflow integration',
            '✓ V2 API: Unified workflows (beginner → hobbyist → professional)',
            '✓ Learn → Build → Validate → Manufacture (end-to-end)',
            '✓ Professional KiCAD PCB validation (MNA solver, power tree)',
            '✓ Validates circuits BEFORE you build them (saves $$$)',
            '✓ Catches voltage mismatches, trace drops, power issues',
            '✓ Quantitative fixes: "Widen trace to 2mm" (not "traces too thin")',
            '✓ Turn junk drawer into valuable projects (29 recipes)',
            '✓ Step-by-step build instructions with wiring diagrams',
            '✓ 5 structured learning paths (106 hours of curriculum)',
            '✓ Real-time component pricing (DigiKey integration)',
            '✓ Market pricing from eBay/Etsy comparables',
            '✓ Exports to professional tools (Fritzing)',
            '✓ FREE tier: Basic validation + recipe browsing',
            '✓ PRO tier ($9/mo): Full workflows + KiCAD validation + API'
        ],
        'features': {
            'v2_unified_workflows': 'Complete journey: Learn → Build → Validate → Manufacture',
            'kicad_validation': 'Professional PCB validation (MNA solver, power tree analysis)',
            'circuit_validation': 'Prevent costly mistakes before building',
            'quantitative_fixes': 'Physics-based solutions with exact measurements',
            'fritzing_export': 'Professional diagrams for documentation',
            'recipe_optimizer': 'Turn spare parts into valuable projects (29 recipes)',
            'inventory_analysis': 'Know the value of what you have',
            'shopping_lists': 'Minimize costs for missing parts',
            'build_instructions': 'Step-by-step assembly guides with wiring diagrams',
            'learning_paths': '5 complete curriculums from beginner to advanced',
            'real_time_pricing': 'DigiKey API + eBay market data',
            'advanced_filtering': 'Filter by difficulty, time, budget, ROI',
            'budget_optimization': 'Find best project for your budget and goals',
            'skill_based_routing': 'Personalized workflows based on skill level'
        },
        'stats': {
            'total_endpoints': 20,
            'v2_workflow_endpoints': 3,
            'v1_endpoints': 17,
            'project_recipes': 29,
            'learning_paths': 5,
            'learning_modules': 22,
            'total_curriculum_hours': 106,
            'components_supported': 23,
            'fritzing_mappings': 19,
            'user_skill_levels': 5
        }
    })


if __name__ == '__main__':
    print("="*70)
    print("  CIRCUIT-AI API SERVER v0.4.0")
    print("  🎓 EDUCATION → PROFESSIONAL: UNIFIED WORKFLOWS")
    print("="*70)
    print()
    print("Starting server on http://localhost:5000")
    print()
    print("=" * 70)
    print("V2 API - UNIFIED WORKFLOW ENGINE 🚀")
    print("=" * 70)
    print("Complete end-to-end workflows:")
    print("  POST /api/v2/workflow/beginner      - Complete beginner workflow")
    print("  POST /api/v2/workflow/complete      - End-to-end (recipe→instructions→validation)")
    print("  POST /api/v2/workflow/validate-kicad - Professional KiCAD PCB validation")
    print()
    print("Features:")
    print("  ✓ Learn → Build → Validate → Manufacture")
    print("  ✓ Skill-based routing (BEGINNER → PROFESSIONAL)")
    print("  ✓ KiCAD integration (MNA solver, power tree analysis)")
    print("  ✓ Quantitative fixes: 'Widen trace to 2mm'")
    print()
    print("=" * 70)
    print("V1 API - CORE FEATURES")
    print("=" * 70)
    print()
    print("Core Endpoints:")
    print("  GET  /                              - API documentation")
    print("  GET  /api/health                    - Health check")
    print("  GET  /api/components                - List components")
    print()
    print("Circuit Validation:")
    print("  POST /api/validate                  - Validate circuit design")
    print("  POST /api/export/fritzing           - Export to Fritzing")
    print("  POST /api/design                    - Complete workflow")
    print()
    print("Recipe Optimizer (29 projects):")
    print("  POST /api/recipes/analyze-inventory - Analyze inventory value")
    print("  POST /api/recipes/generate          - Generate project recipes")
    print("  POST /api/recipes/filter            - Advanced filtering")
    print("  POST /api/recipes/budget-optimize   - Budget optimization")
    print("  POST /api/recipes/shopping-list     - Get shopping list")
    print()
    print("Build Instructions:")
    print("  GET  /api/instructions              - List available projects")
    print("  GET  /api/instructions/<project>    - Get step-by-step guide")
    print()
    print("Learning Paths (106 hours curriculum):")
    print("  GET  /api/learning-paths            - List all paths")
    print("  GET  /api/learning-paths/<id>       - Get detailed curriculum")
    print("  POST /api/learning-paths/recommend  - Get recommendations")
    print()
    print("Pricing Service:")
    print("  POST /api/pricing/component         - Component pricing (DigiKey)")
    print("  GET  /api/pricing/market/<project>  - Market pricing (eBay)")
    print()
    print("=" * 70)
    print("Try:")
    print("  curl http://localhost:5000/")
    print("  curl http://localhost:5000/api/health")
    print()
    print("=" * 70)
    print()

    import os
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'
    app.run(debug=debug, host='0.0.0.0', port=port)
