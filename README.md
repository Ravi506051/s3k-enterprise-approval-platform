# Axis: Enterprise Request and Approval Platform

A purchase-request prototype for **S3K Internship 2026, Case Study 03: AI Platforms**. Axis demonstrates request intake, document checks, duplicate hints, amount-based approval routing, role-aware decisions, a scoped status assistant, and an audit trail.

**[Read the case study](CASE_STUDY.md)** · **[Download the source ZIP](downloads/s3k-enterprise-approval-platform.zip)**

## Run locally

Requires Python 3.10 or newer. No external packages or API keys are needed.

```powershell
python server.py
```

Open [http://127.0.0.1:8767/](http://127.0.0.1:8767/). SQLite is initialized automatically. Set `APPROVAL_DB` before launch if you want a different database path.

## Demo accounts

Select an account on the sign-in screen. Every fictional account uses PIN **2468**.

| Role | Account |
| --- | --- |
| Employee, Operations | `ravi.employee@example.test` |
| Manager, Operations | `asha.manager@example.test` |
| Finance | `nikhil.finance@example.test` |
| Department head, Operations | `meera.head@example.test` |
| Employee, Marketing | `tara.employee@example.test` |
| Manager, Marketing | `dev.manager@example.test` |
| Department head, Marketing | `isha.head@example.test` |

## Approval flow

| Request amount | Required approval route |
| --- | --- |
| Up to INR 25,000 | Manager |
| INR 25,001 to INR 100,000 | Manager, then Finance |
| Above INR 100,000 | Manager, Finance, then department head |

Sign in as an employee and create a request. Then sign in as each approver in route order to review it. Try a request with missing documents to see the hold state; the **Document present** checkbox is a demo confirmation, not a file upload. The app also surfaces potential duplicates for review rather than silently blocking a request.

The frontend is `index.html`, `styles.css`, and `app.js`. `server.py` provides the HTTP API, SQLite storage, sessions, and server-side role checks. [CASE_STUDY.md](CASE_STUDY.md) covers the problem, workflow, UI, KPIs, and UAT approach.

## API at a glance

`POST /api/login` · `POST /api/logout` · `GET /api/me` · `GET /api/state` · `GET /api/requests/{id}` · `POST /api/requests` · `POST /api/requests/{id}/documents` · `POST /api/requests/{id}/decision` · `POST /api/assistant`

## Prototype boundaries

Use fictional data only. The public demo PIN, in-memory sessions, and simplified document check are not suitable for production. The app has no SSO, CSRF protection, rate limiting, or tenant isolation. A production version would also need secure file storage, identity lifecycle controls, and policy governance.
