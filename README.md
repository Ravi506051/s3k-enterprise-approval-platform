# Axis — Enterprise Request & Approval Platform

A functional, fictional purchase-request prototype for **S3K Case Study 03 / AI Platforms**. It has demo sign-in, server-side authorization, amount-based approval routes, document-presence checks, duplicate detection, a scoped status/policy assistant and an audit trail.

## Run locally

```powershell
python server.py
```

Open `http://127.0.0.1:8767/`. Python 3.10+ standard library is the only requirement. SQLite is initialized automatically. Set `APPROVAL_DB` to use another database location.

## Demo accounts

Choose an account on the login screen. All use the fictional demo PIN **2468**.

| Role | Account |
| --- | --- |
| Employee, Operations | `ravi.employee@example.test` |
| Manager, Operations | `asha.manager@example.test` |
| Finance | `nikhil.finance@example.test` |
| Department head, Operations | `meera.head@example.test` |
| Employee, Marketing | `tara.employee@example.test` |
| Manager, Marketing | `dev.manager@example.test` |
| Department head, Marketing | `isha.head@example.test` |

Create a request as an employee, then sign in as each approver in sequence. Requests up to ₹25,000 need a manager; ₹25,001–₹1,00,000 need manager and Finance; above ₹1,00,000 also need a department head. Missing documents hold a request before approval. “Document present” is a **demo confirmation**, not a file upload.

The prototype uses server-side sessions and authorization checks, but it is **not production authentication**: demo PINs are public, sessions are in memory, and there is no SSO, CSRF token, rate limiting or tenant isolation. Never use real financial data. See [CASE_STUDY.md](CASE_STUDY.md) for design and UAT.

## API

`POST /api/login`, `POST /api/logout`, `GET /api/me`, `GET /api/state`, `GET /api/requests/{id}`, `POST /api/requests`, `POST /api/requests/{id}/documents`, `POST /api/requests/{id}/decision`, `POST /api/assistant`.
