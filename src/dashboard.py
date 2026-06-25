"""
Password-protected web dashboard for Job Radar.
- GET /          → login form
- POST /login    → sets cookie
- GET /digest    → today's digest
- GET /saved     → saved jobs
- POST /rerun    → trigger a custom rerun
"""
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (
    Flask, request, redirect, url_for, render_template_string,
    make_response, jsonify,
)

from config import DELIVERY, DATA
from pipeline import run as run_pipeline

DIGESTS_DIR = DATA / "digests"
DIGESTS_DIR.mkdir(exist_ok=True)
SAVED_FILE = DATA / "saved_jobs.json"
APP_LOG = DATA / "dashboard.log"

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", secrets.token_hex(32))

PASSWORD = DELIVERY["dashboard"]["password"]
COOKIE_NAME = "jr_session"


# ──── simple signed-cookie auth (no DB, no sessions) ────────────────
def _sign(value: str) -> str:
    sig = hmac.new(app.secret_key.encode(), value.encode(),
                   hashlib.sha256).hexdigest()[:32]
    return f"{value}.{sig}"


def _verify(signed: str) -> str | None:
    if "." not in signed:
        return None
    value, sig = signed.rsplit(".", 1)
    expected = hmac.new(app.secret_key.encode(), value.encode(),
                        hashlib.sha256).hexdigest()[:32]
    if hmac.compare_digest(sig, expected):
        return value
    return None


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        c = request.cookies.get(COOKIE_NAME)
        if not c or not _verify(c):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


# ──── templates (kept inline so we stay zero-dep) ───────────────────
BASE_CSS = """
:root { --bg:#0f172a; --card:#1e293b; --text:#e2e8f0; --muted:#94a3b8;
  --accent:#38bdf8; --good:#22c55e; --warn:#f59e0b; --bad:#ef4444; }
* { box-sizing:border-box; }
body { margin:0; font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',
  system-ui,sans-serif; background:var(--bg); color:var(--text); }
header { background:var(--card); padding:18px 24px; display:flex;
  justify-content:space-between; align-items:center; border-bottom:1px solid #334155;}
header h1 { margin:0; font-size:20px; }
header h1 span { color:var(--accent); }
.container { max-width:1100px; margin:0 auto; padding:24px; }
.toolbar { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:24px; }
.btn { background:var(--accent); color:#0f172a; border:0; padding:9px 16px;
  border-radius:8px; cursor:pointer; font-weight:600; text-decoration:none;
  display:inline-block; font-size:14px; }
.btn:hover { filter:brightness(1.1); }
.btn.secondary { background:#334155; color:var(--text); }
.btn.danger { background:var(--bad); color:#fff; }
.job { background:var(--card); border-radius:12px; padding:20px;
  margin-bottom:16px; border-left:4px solid var(--accent); }
.job .head { display:flex; justify-content:space-between; align-items:flex-start;
  gap:16px; flex-wrap:wrap; }
.job h2 { margin:0 0 6px 0; font-size:18px; }
.job .meta { color:var(--muted); font-size:13px; margin-bottom:10px; }
.score { background:var(--accent); color:#0f172a; padding:4px 10px;
  border-radius:6px; font-weight:700; font-size:13px; }
.skills { display:flex; flex-wrap:wrap; gap:6px; margin:8px 0; }
.chip { background:#0f172a; border:1px solid #334155; padding:3px 9px;
  border-radius:999px; font-size:11px; color:var(--text); }
.chip.ats { background:#7c2d12; border-color:#9a3412; color:#fed7aa; }
.reasons { color:var(--muted); font-size:13px; margin:8px 0 12px 0; }
.actions { display:flex; gap:8px; flex-wrap:wrap; }
.empty { text-align:center; padding:60px 20px; color:var(--muted); }
.login-box { max-width:380px; margin:80px auto; padding:32px;
  background:var(--card); border-radius:12px; }
.login-box h2 { margin:0 0 20px 0; }
.login-box input { width:100%; padding:11px; border-radius:6px; border:1px solid #334155;
  background:#0f172a; color:var(--text); margin-bottom:14px; font-size:14px; }
.login-box .btn { width:100%; }
.error { color:var(--bad); margin-bottom:10px; font-size:13px; }
input[type=number] { background:#0f172a; color:var(--text); border:1px solid #334155;
  padding:7px 10px; border-radius:6px; width:80px; }
"""

LOGIN_HTML = """<!doctype html><html><head><title>Job Radar — Login</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{{css|safe}}</style></head><body>
<div class="login-box">
  <h2>🔒 Job Radar</h2>
  {% if error %}<div class="error">{{error}}</div>{% endif %}
  <form method="POST" action="/login">
    <input type="password" name="password" placeholder="Password"
           autofocus required>
    <button class="btn" type="submit">Unlock</button>
  </form>
</div></body></html>"""

DIGEST_HTML = """<!doctype html><html><head><title>Job Radar — Digest</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{{css|safe}}</style></head><body>
<header><h1>📡 Job Radar <span>· Raj</span></h1>
<div style="font-size:13px;color:var(--muted)">
  {{generated}} · window {{hours}}h · {{delivered}} jobs</div>
<div><a class="btn secondary" href="/logout">Logout</a></div>
</header>
<div class="container">
  <div class="toolbar">
    <form method="POST" action="/rerun" style="display:flex;gap:8px;align-items:center">
      <span style="color:var(--muted);font-size:13px">Custom rerun:</span>
      <input type="number" name="hours" value="24" min="1" max="720">
      <span style="color:var(--muted);font-size:13px">hours</span>
      <label style="font-size:13px;color:var(--muted)">
        <input type="checkbox" name="global"> global
      </label>
      <button class="btn" type="submit">🔄 Rerun</button>
    </form>
    <a class="btn secondary" href="/saved">💾 Saved</a>
  </div>
  {% if not jobs %}
  <div class="empty">
    <h3>No matching jobs in current window</h3>
    <p>Try a custom rerun with a longer window (e.g. 168h / 7 days)
       or enable global search.</p>
  </div>
  {% endif %}
  {% for j in jobs %}
  <div class="job">
    <div class="head">
      <div>
        <h2>{{loop.index}}. {{j.title}}</h2>
        <div class="meta">
          🏢 {{j.company or 'Unknown'}} · 📍 {{j.location}}
          {% if j.remote_ok %}· 🏠 Remote{% endif %}
          {% if j.salary_eur %}· 💶 €{{"{:,}".format(j.salary_eur)}}{% endif %}
          {% if j._age_hours is not none %}· ⏱ {{j._age_hours}}h ago{% endif %}
          · {{j.source}}
        </div>
      </div>
      <div class="score">{{j.score}}</div>
    </div>
    {% if j.matched_skills %}
    <div class="skills">
      {% for s in j.matched_skills[:8] %}<span class="chip">{{s}}</span>{% endfor %}
    </div>
    {% endif %}
    {% if j.ats_keywords_to_add %}
    <div class="skills">
      <span style="color:var(--warn);font-size:12px;align-self:center">📝 Add to resume:</span>
      {% for s in j.ats_keywords_to_add[:6] %}<span class="chip ats">{{s}}</span>{% endfor %}
    </div>
    {% endif %}
    <div class="reasons">{{" • ".join(j.reasons[:4])}}</div>
    <div class="actions">
      {% if j.url %}<a class="btn" href="{{j.url}}" target="_blank" rel="noopener">🔗 Apply</a>{% endif %}
      <form method="POST" action="/save" style="display:inline">
        <input type="hidden" name="job_id" value="{{j.id}}">
        <button class="btn secondary" type="submit">💾 Save</button>
      </form>
    </div>
  </div>
  {% endfor %}
</div></body></html>"""

SAVED_HTML = """<!doctype html><html><head><title>Job Radar — Saved</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{{css|safe}}</style></head><body>
<header><h1>💾 Saved Jobs <span>· {{count}}</span></h1>
<a class="btn secondary" href="/digest">← Back to digest</a></header>
<div class="container">
  {% if not jobs %}<div class="empty"><p>No saved jobs yet.</p></div>{% endif %}
  {% for j in jobs %}
  <div class="job">
    <div class="head">
      <div>
        <h2>{{j.title}}</h2>
        <div class="meta">🏢 {{j.company}} · 📍 {{j.location}}
          {% if j.url %}· <a href="{{j.url}}" target="_blank" style="color:var(--accent)">Apply</a>{% endif %}
        </div>
      </div>
      <div class="score">{{j.score}}</div>
    </div>
  </div>
  {% endfor %}
</div></body></html>"""


# ──── routes ─────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def root():
    return redirect(url_for("digest"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        pw = request.form.get("password", "")
        if hmac.compare_digest(pw, PASSWORD):
            resp = make_response(redirect(request.args.get("next") or "/digest"))
            resp.set_cookie(COOKIE_NAME, _sign("raj"),
                            max_age=60 * 60 * 24 * 7,
                            httponly=True, samesite="Lax")
            return resp
        error = "Wrong password."
    return render_template_string(LOGIN_HTML, css=BASE_CSS, error=error)


@app.route("/logout")
def logout():
    resp = make_response(redirect("/login"))
    resp.delete_cookie(COOKIE_NAME)
    return resp


@app.route("/digest")
@login_required
def digest():
    # find latest digest
    files = sorted(DIGESTS_DIR.glob("*.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    p = files[0] if files else None
    if not p:
        return render_template_string(DIGEST_HTML, css=BASE_CSS,
                                      jobs=[], generated="(no data yet)",
                                      hours=24, delivered=0)
    data = json.loads(p.read_text())
    return render_template_string(
        DIGEST_HTML, css=BASE_CSS, jobs=data.get("jobs", []),
        generated=datetime.fromisoformat(
            data.get("generated_at", "")).strftime("%Y-%m-%d %H:%M")
                  if data.get("generated_at") else "(no data)",
        hours=data.get("window_hours", 24),
        delivered=data.get("counts", {}).get("delivered", 0),
    )


@app.route("/saved")
@login_required
def saved():
    saved_ids = set()
    if SAVED_FILE.exists():
        try:
            saved_ids = set(json.loads(SAVED_FILE.read_text()))
        except Exception:
            pass
    # pull saved jobs from latest digest(s)
    jobs = []
    seen = set()
    for f in sorted(DIGESTS_DIR.glob("*.json"),
                    key=lambda p: p.stat().st_mtime, reverse=True)[:30]:
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        for j in d.get("jobs", []):
            if j.get("id") in saved_ids and j["id"] not in seen:
                jobs.append(j)
                seen.add(j["id"])
    return render_template_string(SAVED_HTML, css=BASE_CSS,
                                  jobs=jobs, count=len(jobs))


@app.route("/save", methods=["POST"])
@login_required
def save():
    jid = request.form.get("job_id", "")
    saved = set()
    if SAVED_FILE.exists():
        try:
            saved = set(json.loads(SAVED_FILE.read_text()))
        except Exception:
            pass
    saved.add(jid)
    SAVED_FILE.write_text(json.dumps(sorted(saved)))
    return redirect("/digest")


@app.route("/rerun", methods=["POST"])
@login_required
def rerun():
    try:
        hours = int(request.form.get("hours", 24))
    except ValueError:
        hours = 24
    hours = max(1, min(hours, 720))
    global_search = bool(request.form.get("global"))
    run_pipeline(hours=hours, global_search=global_search)
    return redirect("/digest")


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "ts": time.time()})


if __name__ == "__main__":
    app.run(host=DELIVERY["dashboard"]["host"],
            port=DELIVERY["dashboard"]["port"],
            debug=False)