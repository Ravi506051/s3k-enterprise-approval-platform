"""Fictional purchase approval workspace with demo authentication and role checks."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get("APPROVAL_DB", ROOT / "approvals.sqlite3"))
FILES = {"/", "/index.html", "/styles.css", "/app.js"}
SESSIONS: dict[str, tuple[int, datetime]] = {}
DEMO_PIN = "2468"  # Fictional demo credentials only; never use this pattern for real accounts.
ROLES = {"employee", "manager", "finance", "department_head"}


def utcnow():
    return datetime.now(timezone.utc)


def iso(value=None):
    return (value or utcnow()).isoformat(timespec="seconds")


@contextmanager
def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def pin_hash(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), 120_000).hex()


def route_for(amount: int) -> list[str]:
    if amount <= 25_000:
        return ["manager"]
    if amount <= 100_000:
        return ["manager", "finance"]
    return ["manager", "finance", "department_head"]


def initialize():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
          role TEXT NOT NULL, department TEXT NOT NULL,
          pin_salt TEXT NOT NULL, pin_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS requests (
          id INTEGER PRIMARY KEY AUTOINCREMENT, requester_id INTEGER NOT NULL REFERENCES users(id),
          title TEXT NOT NULL, amount INTEGER NOT NULL, department TEXT NOT NULL,
          justification TEXT NOT NULL, has_docs INTEGER NOT NULL,
          status TEXT NOT NULL, stage TEXT NOT NULL, route_json TEXT NOT NULL,
          stage_index INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          due_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit (
          id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER NOT NULL REFERENCES requests(id),
          actor_id INTEGER NOT NULL REFERENCES users(id), action TEXT NOT NULL,
          note TEXT NOT NULL, at TEXT NOT NULL
        );
        """)
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            users = [
                (1, "Ravi Mehta", "ravi.employee@example.test", "employee", "Operations"),
                (2, "Asha Nair", "asha.manager@example.test", "manager", "Operations"),
                (3, "Nikhil Shah", "nikhil.finance@example.test", "finance", "Finance"),
                (4, "Meera Rao", "meera.head@example.test", "department_head", "Operations"),
                (5, "Tara Sen", "tara.employee@example.test", "employee", "Marketing"),
                (6, "Dev Verma", "dev.manager@example.test", "manager", "Marketing"),
                (7, "Isha Kapoor", "isha.head@example.test", "department_head", "Marketing"),
            ]
            for uid, name, email, role, department in users:
                salt = secrets.token_hex(16)
                db.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?)",
                           (uid, name, email, role, department, salt, pin_hash(DEMO_PIN, salt)))
        if db.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 0:
            samples = [
                (1, "Warehouse scanner replacement", 18_500, "Operations", "Replace a failing handheld scanner used for dispatch.", 1, "Pending", "manager", 0, -1),
                (1, "Packaging line inspection kit", 68_000, "Operations", "Inspection kit for batch quality checks.", 1, "Pending", "finance", 1, 2),
                (1, "Conveyor service contract", 145_000, "Operations", "Annual maintenance contract for the material handling line.", 0, "Incomplete", "employee", 0, 3),
                (5, "Campaign analytics licence", 42_000, "Marketing", "Annual reporting subscription for a fictional campaign.", 1, "Pending", "manager", 0, 1),
            ]
            for requester_id, title, amount, department, justification, has_docs, status, stage, stage_index, due_offset in samples:
                created = iso(utcnow() - timedelta(days=2))
                route = json.dumps(route_for(amount))
                cur = db.execute("""INSERT INTO requests
                    (requester_id,title,amount,department,justification,has_docs,status,stage,route_json,stage_index,created_at,updated_at,due_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (requester_id, title, amount, department, justification, has_docs,
                     status, stage, route, stage_index, created, created, iso(utcnow() + timedelta(days=due_offset))))
                db.execute("INSERT INTO audit(request_id,actor_id,action,note,at) VALUES(?,?,?,?,?)",
                           (cur.lastrowid, requester_id, "submitted", "Fictional sample request", created))


def user_public(row):
    return {key: row[key] for key in ("id", "name", "email", "role", "department")}


def can_view(user, request):
    if user["id"] == request["requester_id"]:
        return True
    if user["role"] in {"manager", "department_head"}:
        return user["department"] == request["department"]
    return user["role"] == "finance"


def can_decide(user, request):
    return (request["status"] == "Pending" and user["role"] == request["stage"] and
            (user["role"] == "finance" or user["department"] == request["department"]))


def risk_hints(request):
    hints = []
    if not request["has_docs"]:
        hints.append("Required supporting document is missing. Final approval is blocked.")
    if request["amount"] > 100_000:
        hints.append("Above ₹1,00,000: manager, Finance and department head must review.")
    elif request["amount"] > 25_000:
        hints.append("Above ₹25,000: manager and Finance must review.")
    if "urgent" in request["justification"].lower():
        hints.append("Urgency is mentioned. Confirm the business deadline; it does not bypass policy.")
    return hints or ["No rule-based risk flag; an approver must still review."]


def serialize(request, db, user):
    item = dict(request)
    item["has_docs"] = bool(item["has_docs"])
    item["route"] = json.loads(item.pop("route_json"))
    item["requester"] = db.execute("SELECT name FROM users WHERE id=?", (item["requester_id"],)).fetchone()[0]
    item["can_decide"] = can_decide(user, request)
    item["can_edit_docs"] = user["id"] == request["requester_id"] and request["status"] == "Incomplete"
    item["overdue"] = item["status"] not in {"Approved", "Rejected"} and item["due_at"] < iso()
    item["hints"] = risk_hints(request)
    return item


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        print("Approval demo:", fmt % args)

    def send_json(self, data, status=HTTPStatus.OK, cookie=None):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def current_user(self, db):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            token = cookie["demo_session"].value
        except (KeyError, Exception):
            return None
        session = SESSIONS.get(token)
        if not session or session[1] < utcnow():
            SESSIONS.pop(token, None)
            return None
        return db.execute("SELECT * FROM users WHERE id=?", (session[0],)).fetchone()

    def read_json(self):
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size <= 16_384:
            raise ValueError("Invalid request size")
        obj = json.loads(self.rfile.read(size))
        if not isinstance(obj, dict):
            raise ValueError("Expected an object")
        return obj

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            with connect() as db:
                user = self.current_user(db)
                if not user:
                    return self.send_json({"error": "Sign in to the demo workspace"}, HTTPStatus.UNAUTHORIZED)
                if path == "/api/me":
                    return self.send_json({"user": user_public(user)})
                if path == "/api/state":
                    rows = db.execute("SELECT * FROM requests ORDER BY updated_at DESC,id DESC").fetchall()
                    visible = [serialize(row, db, user) for row in rows if can_view(user, row)]
                    audit = [dict(row) for row in db.execute("""SELECT audit.*,users.name AS actor FROM audit
                        JOIN users ON users.id=audit.actor_id ORDER BY audit.id DESC LIMIT 80""")]
                    audit = [row for row in audit if any(item["id"] == row["request_id"] for item in visible)][:15]
                    metrics = {"visible": len(visible), "pending": sum(i["can_decide"] for i in visible),
                               "incomplete": sum(i["status"] == "Incomplete" for i in visible),
                               "overdue": sum(i["overdue"] for i in visible)}
                    return self.send_json({"user": user_public(user), "requests": visible, "audit": audit, "metrics": metrics})
                match = re.fullmatch(r"/api/requests/(\d+)", path)
                if match:
                    row = db.execute("SELECT * FROM requests WHERE id=?", (int(match[1]),)).fetchone()
                    if not row or not can_view(user, row):
                        return self.send_json({"error": "Request not found"}, HTTPStatus.NOT_FOUND)
                    audit = [dict(record) for record in db.execute("""SELECT audit.*,users.name AS actor FROM audit
                        JOIN users ON users.id=audit.actor_id WHERE request_id=? ORDER BY audit.id DESC""", (row["id"],))]
                    return self.send_json({"request": serialize(row, db, user), "audit": audit})
            return self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        if path not in FILES:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).netloc != self.headers.get("Host"):
            return self.send_json({"error": "Cross-origin request blocked"}, HTTPStatus.FORBIDDEN)
        try:
            data = self.read_json()
            with connect() as db:
                if path == "/api/login":
                    email = str(data.get("email", "")).strip().lower()
                    pin = str(data.get("pin", ""))
                    user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
                    if not user or not hmac.compare_digest(pin_hash(pin, user["pin_salt"]), user["pin_hash"]):
                        return self.send_json({"error": "Incorrect demo account or PIN"}, HTTPStatus.UNAUTHORIZED)
                    token = secrets.token_urlsafe(32)
                    SESSIONS[token] = (user["id"], utcnow() + timedelta(hours=8))
                    return self.send_json({"user": user_public(user)}, cookie=f"demo_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800")
                user = self.current_user(db)
                if not user:
                    return self.send_json({"error": "Sign in to continue"}, HTTPStatus.UNAUTHORIZED)
                if path == "/api/logout":
                    cookie = SimpleCookie(); cookie.load(self.headers.get("Cookie", ""))
                    if "demo_session" in cookie:
                        SESSIONS.pop(cookie["demo_session"].value, None)
                    return self.send_json({"ok": True}, cookie="demo_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0")
                if path == "/api/requests":
                    if user["role"] != "employee":
                        return self.send_json({"error": "Only employees create requests"}, HTTPStatus.FORBIDDEN)
                    title = str(data.get("title", "")).strip()[:120]
                    justification = str(data.get("justification", "")).strip()[:1500]
                    amount = int(data.get("amount", 0))
                    has_docs = data.get("has_docs") is True
                    if len(title) < 5 or len(justification) < 15 or not 0 < amount <= 10_000_000:
                        raise ValueError("Title, valid amount and justification of at least 15 characters are required")
                    duplicate = db.execute("""SELECT id FROM requests WHERE requester_id=? AND lower(title)=lower(?)
                        AND amount=? AND created_at>? ORDER BY id DESC LIMIT 1""",
                        (user["id"], title, amount, iso(utcnow()-timedelta(days=30)))).fetchone()
                    if duplicate:
                        return self.send_json({"error": f"Possible duplicate of REQ-{duplicate['id']:04d}; review that request first"}, HTTPStatus.CONFLICT)
                    route = route_for(amount)
                    status, stage = ("Pending", "manager") if has_docs else ("Incomplete", "employee")
                    stamp = iso()
                    cur = db.execute("""INSERT INTO requests
                        (requester_id,title,amount,department,justification,has_docs,status,stage,route_json,stage_index,created_at,updated_at,due_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (user["id"], title, amount, user["department"], justification, int(has_docs),
                         status, stage, json.dumps(route), 0, stamp, stamp, iso(utcnow()+timedelta(days=5))))
                    db.execute("INSERT INTO audit(request_id,actor_id,action,note,at) VALUES(?,?,?,?,?)",
                               (cur.lastrowid, user["id"], "submitted", "Documents attached" if has_docs else "Awaiting documents", stamp))
                    return self.send_json({"id": cur.lastrowid, "status": status, "route": route}, HTTPStatus.CREATED)
                if path == "/api/assistant":
                    question = str(data.get("question", ""))[:500]
                    number = re.search(r"\b(?:REQ-)?(\d{1,6})\b", question, re.I)
                    if number:
                        row = db.execute("SELECT * FROM requests WHERE id=?", (int(number[1]),)).fetchone()
                        if not row or not can_view(user, row):
                            return self.send_json({"answer": "I cannot show that request. Check the number or your access."})
                        return self.send_json({"answer": f"REQ-{row['id']:04d} is {row['status'].lower()}. Current step: {row['stage'].replace('_',' ')}. No approval is made by this assistant."})
                    return self.send_json({"answer": "Policy: up to ₹25,000 needs a manager; ₹25,001–₹1,00,000 needs manager and Finance; above ₹1,00,000 also needs department head. Missing documents block approval. Ask about REQ-0001 for a recorded status."})
                match = re.fullmatch(r"/api/requests/(\d+)/(documents|decision)", path)
                if not match:
                    return self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                request_id, action = int(match[1]), match[2]
                row = db.execute("SELECT * FROM requests WHERE id=?", (request_id,)).fetchone()
                if not row or not can_view(user, row):
                    return self.send_json({"error": "Request not found"}, HTTPStatus.NOT_FOUND)
                if action == "documents":
                    if user["id"] != row["requester_id"] or row["status"] != "Incomplete" or data.get("has_docs") is not True:
                        return self.send_json({"error": "Only the requester may confirm missing documents"}, HTTPStatus.FORBIDDEN)
                    db.execute("UPDATE requests SET has_docs=1,status='Pending',stage='manager',updated_at=? WHERE id=?", (iso(), request_id))
                    event, note = "documents_confirmed", "Supporting document marked present in demo"
                else:
                    if not can_decide(user, row):
                        return self.send_json({"error": "This approval step is not assigned to your role"}, HTTPStatus.FORBIDDEN)
                    decision = str(data.get("decision", ""))
                    note = str(data.get("note", "")).strip()[:500]
                    if decision not in {"approve", "reject"} or (decision == "reject" and len(note) < 8):
                        raise ValueError("Choose approve/reject; rejection requires a reason")
                    if not row["has_docs"]:
                        return self.send_json({"error": "Missing documents block approval"}, HTTPStatus.CONFLICT)
                    if decision == "reject":
                        db.execute("UPDATE requests SET status='Rejected',stage='done',updated_at=? WHERE id=?", (iso(), request_id))
                        event = "rejected"
                    else:
                        route = json.loads(row["route_json"])
                        next_index = row["stage_index"] + 1
                        if next_index >= len(route):
                            db.execute("UPDATE requests SET status='Approved',stage='done',stage_index=?,updated_at=? WHERE id=?",
                                       (next_index, iso(), request_id))
                        else:
                            db.execute("UPDATE requests SET stage=?,stage_index=?,updated_at=? WHERE id=?",
                                       (route[next_index], next_index, iso(), request_id))
                        event = "approved_stage"
                    note = note or f"Reviewed by {user['role'].replace('_',' ')}"
                db.execute("INSERT INTO audit(request_id,actor_id,action,note,at) VALUES(?,?,?,?,?)",
                           (request_id, user["id"], event, note, iso()))
                return self.send_json({"id": request_id, "ok": True})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)


if __name__ == "__main__":
    initialize()
    port = int(os.environ.get("PORT", "8767"))
    host = "0.0.0.0" if "PORT" in os.environ else "127.0.0.1"
    print(f"Approval demo listening on http://{host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
