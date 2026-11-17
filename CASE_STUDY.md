# Case 03 — Enterprise Request & Approval Platform

## Product opportunity

In the fictional 100-person company, approximately 90 purchase requests per month arrive through email and spreadsheets. A manager approves by email, Finance checks budgets and attachments, and employees ask for status. Baselines: five working days per approval cycle and 28% initially incomplete requests. The third product KPI below measures visibility and access, which the current process lacks.

Users are employees, departmental managers, Finance reviewers, department heads, workflow administrators and auditors. Major inefficiencies are repeated manual entry, unclear handoffs and duplicate submissions; approvals are also hard to audit, and one employee could receive another employee's data if a status assistant is not scoped.

## Three product KPIs

| KPI | Definition | Baseline / proposed target | Management value |
| --- | --- | --- | --- |
| Median approval cycle | Working days from complete submission to final human decision | 5 days / under 3 days | Measures speed without rewarding incomplete or bypassed reviews. |
| First-pass completeness | Submissions with all required fields and evidence on first attempt | 72% / above 90% | Reduces rework for Finance and employees. |
| Status self-service rate | Status views answered in the portal / all status inquiries | To establish / above 80% | Shows whether employees can find accurate status without interrupting approvers. |

Targets are discovery hypotheses, not claims about this demo's measured results.

## Discovery questions

1. Which purchase categories, budgets and policies define routing, and who owns each rule change?
2. What evidence is mandatory at each amount or exception level, and which document types are accepted?
3. How are managers and department heads mapped when employees change teams or delegates cover absences?
4. What does Finance need to inspect before approval, and which system is the budget source of truth?
5. Which existing identity provider, ERP, procurement and notification systems must integrate?
6. Which employee and request fields are confidential, and what may each role or assistant reveal?
7. How should duplicate submissions, SLA escalation, exception overrides and audit retention work?

## Workflow and policy safeguards

1. The employee signs in and enters purpose, amount, justification and document-presence confirmation. The prototype enforces valid values and flags a likely duplicate by requester, title and amount within 30 days.
2. The route is derived from **server-side policy**: ≤₹25,000 → manager; ₹25,001–₹1,00,000 → manager → Finance; >₹1,00,000 → manager → Finance → department head. A request missing documents is `Incomplete` and cannot reach final approval.
3. Each assigned approver reviews and records a decision. A rejection requires a reason. The next stage appears only after approval by the correct role. The assistant can suggest a policy risk, but it cannot decide.
4. The employee sees their own status. Managers and heads see only their department; Finance sees the shared finance queue. The backend enforces this on list, detail and assistant requests. Every submission, document confirmation and decision is auditable.

The working UI uses a login screen and an approval workspace with pending requests, route, document state, rule-based risk hints and next action. A production implementation would replace fictional accounts with SSO, mapped approvers, budget integration, real document upload, event notifications and durable sessions.

## UI prompt and design decisions

Initial prompt to Codex: “Build a purchase-request workspace with role-based visibility and the brief's three amount bands. Show policy route, missing documents, pending approvals and AI suggestions. A model must never approve.” Refinement: require backend authorization on direct URL and assistant access, duplicate detection, audit entries and explicit demo credentials.

The interface gives the active human approver a distinct decision control, keeps the route visible next to each request and marks the policy review as rule-based. A person can switch fictional roles to demonstrate each handoff. The app does not imply that toggling the document checkbox uploads a file.

## Architecture

- **Frontend:** semantic HTML, responsive CSS and browser JavaScript, calling same-origin JSON APIs.
- **API:** Python prototype with server-side session cookies and role checks on every request. A production version would use a framework, OIDC/SSO, CSRF protection, rate limits, authorization tests and structured logs.
- **Database:** SQLite tables for users, requests and immutable decision events; use managed PostgreSQL with migrations and tenant keys for a real SaaS deployment.
- **AI integration:** current risk hints and assistant are deterministic. A future LLM could summarize the request and retrieve approved policy text with source citations. It must not receive unnecessary employee data or call the approval endpoint.
- **Deployment:** containerized API, TLS, secret management, managed database, backups, monitoring, audit retention and staged rollout with Finance UAT.

## UAT scenarios

| Scenario | Steps | Expected outcome |
| --- | --- | --- |
| Unauthorized access | Sign in as Marketing employee Tara and request Ravi's Operations request directly or ask assistant for its ID. | Detail returns not found; assistant gives no title, amount or status. |
| Incorrect route / AI suggestion | Create requests at ₹25,000, ₹25,001 and ₹1,00,001; attempt a Finance decision before manager approval. | Server assigns the exact required stages and rejects a decision from the wrong role. Suggestions never change route or approve. |
| Duplicate / missing documents | Submit same title and amount twice; submit a request without documents and try to approve. | Duplicate is rejected with original ID. Incomplete request stays on hold; only requester can confirm document presence in the demo. |

This repository was generated with OpenAI Codex at Ravi Kumar Rao's request to build the remaining case studies. The user can inspect and present the work, but must not describe AI-generated implementation as personally written code. All accounts and requests are fictional.
