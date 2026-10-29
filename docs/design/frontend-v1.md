# Fixwright frontend v1: design

Date: 2026-10-29. Status: approved.

## 1. Goal

A web interface for Fixwright that works like a real internal tool for a support team and doubles as a public demo. A visitor (for example a recruiter) opens https://fixwright.onrender.com, clicks one button, and can run the whole flow: create an incident, let the agent analyze it, approve or reject the result.

Success criteria:

- A visitor with no key reaches a working page in one click.
- A reviewer never loses a pending analysis by closing the tab.
- Every decision records who made it (`demo`, `admin`, `api` now; a person's email after SSO).
- Cost of the public demo is capped per day.
- The MCP server, Swagger, curl, the existing tests and the evals keep working unchanged.

Out of scope (non-goals): single sign-on (SSO) and per-person identity, a remote MCP endpoint with OAuth (both planned as the next step after this design), editing or deleting incidents from the UI, search, filters, pagination, server-side rendering, browser end-to-end tests (Playwright), changing the agent prompt.

## 2. Architecture

- Stack: React + Vite + TypeScript, Tailwind CSS, shadcn/ui components, React Router, TanStack Query for data fetching and loading states.
- Code lives in `frontend/` in the same repository.
- Same origin. FastAPI serves the built files (`frontend/dist`) under `/ui/`. Any `/ui/...` path that is not a file returns `index.html` so deep links and refreshes work. `GET /` redirects to `/ui/`. All API paths stay as they are.
- If `frontend/dist` does not exist (tests, backend-only development), `/ui/` returns 404 and the API works normally.
- Docker: multi-stage build. Stage 1 (`node`, LTS) runs `npm ci` and `npm run build`. Stage 2 is the current Python image and copies only `frontend/dist`. Node is not in the final image. Render settings do not change.
- Local development: terminal 1 runs `uvicorn app.main:app --reload` (port 8000), terminal 2 runs `npm run dev` in `frontend/` (Vite, port 5173). Vite is configured with `base: "/ui/"` and proxies `/incidents`, `/analyses`, `/auth` and `/health` to port 8000, so the browser sees one origin and cookies work locally.

## 3. Authentication and roles

Two ways in, one session mechanism:

| Door | Endpoint | Role |
|---|---|---|
| "Try the demo" button | `POST /auth/demo` | `demo` |
| "Sign in with API key" link | `POST /auth/login` with `{"api_key": "..."}` | `admin` |
| `X-API-Key` header on any request (MCP, curl, Swagger) | unchanged | `api` |

Session:

- Starlette `SessionMiddleware`: a signed cookie (`fixwright_session`), signed with `SESSION_SECRET`. The cookie holds only `{"role": ...}`, never the API key.
- Lifetime 8 hours, `HttpOnly`, `SameSite=Strict`, `Secure` unless `SESSION_HTTPS_ONLY=false` (local `.env` and docker-compose set it to false because they use plain http).
- If `SESSION_SECRET` is not set or is shorter than 32 characters, the app refuses to start with a clear error (fail closed). Render keeps serving the previous deploy if a new one fails, so a missing secret cannot take the live demo down, but it must be added before merging.
- `POST /auth/logout` clears the session. `GET /auth/me` returns `{"role": "demo", "demo_analyses_left": 27}` or `{"role": "admin"}`, or 401 when there is no session.
- `POST /auth/login` compares the key with `secrets.compare_digest`, returns 401 on a wrong key.

Authorization (`require_auth` replaces `require_api_key` and returns the caller's role):

- A valid `X-API-Key` header wins and gives role `api`. A wrong key is 401 even if a session cookie is present.
- Otherwise a valid session gives its role. No key and no session is 401 with `WWW-Authenticate: APIKey`, as before this change.
- CSRF: requests authenticated by the session cookie with a method other than GET, HEAD or OPTIONS must carry the header `X-Fixwright-Client: web`, otherwise 403. `POST /auth/demo`, `POST /auth/login` and `POST /auth/logout` require the same header. Other sites cannot add custom headers to cross-site requests, and `SameSite=Strict` stops the cookie from being sent from other sites in the first place.
- `PUT /incidents/{id}` and `DELETE /incidents/{id}` return 403 for `demo`.

Demo limits (constants in `app/config.py`):

| Limit | Value | Response when hit |
|---|---|---|
| Analyses started by `demo`, all demo sessions together, per UTC day | 30 | 429 `Daily demo limit reached` |
| Incidents created by `demo` per UTC day | 20 | 429 `Daily demo limit reached` |
| Description length for `demo` | 1000 characters | 422 |

The analysis limit counts `incident_analyses` rows with `requested_by = 'demo'` created today. An analysis is counted when its pending row is written (end of the agent run), so a few parallel requests can exceed 30 by one or two. Accepted: the cost impact is negligible and the Anthropic Console spend limit stays as a second guard. `admin` and `api` have no limits.

## 4. Backend changes

### 4.1 Pending analyses are stored right away

Before this change, an analysis reached `incident_analyses` only after the decision. Until then it existed only in the checkpointer and could be found only by `thread_id`.

New flow: `agent <-> tools -> respond -> record_pending -> approval (interrupt) -> save`.

- `record_pending` (new node) inserts the row with `status = 'pending'`, the analysis, `similar_incidents`, `requested_by` and `created_at`. It runs once: the checkpoint after it means resuming does not run it again.
- `save` becomes `UPDATE incident_analyses SET status, reviewer_comment, reviewed_at = now(), decided_by WHERE thread_id = %s AND status = 'pending'`. If no row is updated, the decision lost a race and the endpoint returns 409. This also fixes the known gap where two simultaneous decisions gave 500.
- `AgentState` gets `requested_by`. The decision passed to `Command(resume=...)` gets `decided_by`.
- `search_similar_incidents` keeps `status = 'approved'`, so pending and rejected analyses never reach the agent.

### 4.2 `similar_incidents`

`record_pending` reads the `search_similar_incidents` tool results from the messages in the state and stores them as a JSON list: `incident_id`, `similarity`, `has_approved_analysis`. If an incident appears in several searches, the highest similarity is kept. Error results are skipped. This gives the UI structured data instead of parsing the agent's evidence sentences.

### 4.3 Schema (`db/schema.sql`, stays idempotent)

- `incident_analyses.status` allows `pending`: drop and re-add the check constraint `incident_analyses_status_check` with `('pending', 'approved', 'rejected')`.
- `incident_analyses.reviewed_at`: drop `NOT NULL` and the default (empty while pending).
- New columns with `ADD COLUMN IF NOT EXISTS`: `incident_analyses.created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `requested_by VARCHAR(255)`, `decided_by VARCHAR(255)`, `similar_incidents JSONB NOT NULL DEFAULT '[]'`; `incidents.created_by VARCHAR(255)`, `incidents.created_at TIMESTAMPTZ NOT NULL DEFAULT now()` (needed for the demo retention in section 9).
- Existing rows: `created_at` becomes the migration time; the other new columns stay empty. Analyses that were pending before this change have no row and do not appear in the queue (a handful, accepted).
- The `CREATE TABLE` statements are updated too so a fresh database matches.

### 4.4 Endpoints

| Method | Path | Returns |
|---|---|---|
| GET | `/incidents` | existing fields plus `latest_status` (`pending`, `approved`, `rejected` or null), newest first |
| GET | `/incidents/{id}` | one incident, 404 if missing |
| GET | `/incidents/{id}/analyses` | all analyses for the incident, newest first: `thread_id`, status, analysis, `similar_incidents`, comment, `requested_by`, `decided_by`, `created_at`, `reviewed_at` |
| GET | `/analyses?status=pending` | pending analyses, oldest first: `thread_id`, `incident_id`, incident description, probable cause, `created_at`. Only `pending` is accepted (422 otherwise). |
| POST | `/auth/demo`, `/auth/login`, `/auth/logout` | see section 3 |
| GET | `/auth/me` | see section 3 |

`POST /incidents` stores `created_by`, `POST /incidents/{id}/analyze` passes `requested_by`, `POST /analyses/{thread_id}/decision` passes `decided_by`. The responses of the existing endpoints stay compatible, so the MCP server needs no change.

## 5. Screens

Principle: as few buttons as possible, one primary action per state, plain words instead of technical values. UI text is in English.

Three working pages plus a static privacy notice (`/ui/privacy`, section 9), no sidebar. A thin top bar on every page except sign in: logo on the left, a "Demo" badge for demo sessions and a sign-out icon on the right.

1. Sign in, `/ui/login`: product name, one sentence, a large "Try the demo" button with "No sign-up. Up to 30 demo analyses per day." under it, and a small "Sign in with API key" link that reveals a key field.
2. Home, `/ui`: a "Waiting for your decision" section with one card per pending analysis (incident ID, short probable cause, how long it has waited), shown only when there is something pending. Below it the incident list (ID, description, latest status badge) and one "New incident" button that opens a small dialog. Clicking a card or a row opens the detail page.
3. Incident detail, `/ui/incidents/{id}`: the incident, then exactly one primary action depending on state:
   - no analysis yet: "Analyze" (for demo, "27 analyses left today" under it). While running: "Analyzing… this takes 10 to 30 seconds".
   - last analysis decided: its result (status badge, probable cause, who decided and when) and "Analyze again".
   - pending: the analysis (probable cause, suggested steps), "Similar incidents" (links with a "Strong match" or "Possible match" label, the raw score in a tooltip, an "approved analysis" note where it applies), the agent's evidence sentences, and "Approve" / "Reject". The comment field is behind an "Add a comment" link.
   - History of earlier analyses in a collapsed section.

Similarity labels: 0.55 and above "Strong match" (precision 1.00 in the retrieval eval), 0.45 to 0.55 "Possible match". Below 0.45 nothing is stored or shown.

Messages: session expired returns to sign in with "Your session expired. Sign in again."; demo limit shows "Today's demo limit is reached. Try again tomorrow."; an analysis decided elsewhere shows "This analysis was already decided." and reloads the page. Light and dark mode follow the system setting.

## 6. Testing and CI

- pytest (backend): sessions and roles, wrong key, missing session, CSRF header (403), demo limits (429) and the 403 on PUT/DELETE for demo, `record_pending` and `similar_incidents`, the atomic decision (409), the new endpoints, `/` redirect and the `/ui/` fallback (with a temporary dist folder). Existing tests are updated where the flow changed and must still pass. Tests keep using the fake model and fake embeddings.
- Vitest + React Testing Library (frontend), with mocked API responses: demo button leads to the home page, the right single action is shown per state, labels map scores correctly, the 401 and 429 messages appear.
- TypeScript type check, ESLint and `npm run build` run in CI.
- CI: a new `frontend` job in `.github/workflows/tests.yml`, parallel to `test`. Both become required checks in the "Protect main" ruleset.
- Dependabot: add the `npm` ecosystem for `/frontend`, grouped minor and patch, same weekly schedule and 7-day cooldown as pip.
- Manual check before each PR: both terminals locally, click through the flow; `docker compose up --build` before the PR that changes the Dockerfile.

## 7. Deployment

- Render: add `SESSION_SECRET` (new random value, different from local) before merging the first PR that needs it.
- `.env` locally: add `SESSION_SECRET` and `SESSION_HTTPS_ONLY=false`. docker-compose passes both.
- README: new "Web interface" section (screenshot, demo button, limits), endpoints table updated, Getting Started gets the Node steps.

## 8. Delivery order

1. Backend PR: schema, `record_pending` and atomic `save`, `similar_incidents`, new GET endpoints, sessions, roles, CSRF, demo limits, tests. Usable through Swagger before any UI exists.
2. Frontend PR: `frontend/` app, FastAPI serving under `/ui/`, Dockerfile stage, CI job, Dependabot npm, README.
3. Ruleset update (GitHub UI) after the `frontend` job has run once.

## 9. Security and privacy

Threat model: an anonymous visitor who can call every endpoint directly (not only through the UI), a malicious website the reviewer happens to visit, a demo user who writes hostile text, and someone who wants to run up the AI bill. The live deployment is a public demo: it must never hold real company or personal data.

Web security:

- Security headers on every response: `Content-Security-Policy` (`default-src 'self'`, no inline scripts, `frame-ancestors 'none'`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `Strict-Transport-Security` when served over HTTPS. This blocks clickjacking and limits the damage of any injected script.
- All text that comes from users or from the model (descriptions, probable cause, steps, evidence, comments) is rendered as plain text. No `dangerouslySetInnerHTML`, no Markdown or HTML rendering in v1. React escapes text by default; a lint rule forbids `dangerouslySetInnerHTML`.
- No CORS configuration: browsers keep refusing cross-site reads, which is the safe default.
- Unhandled errors return a generic message; stack traces never reach the client.
- SQL stays parameterized (`%s` placeholders) everywhere, as in the existing code.

AI-specific:

- Prompt injection: a demo user can write instructions into an incident description, and that text can also reach other analyses through similar-incident search. The agent only has read-only tools (`get_incident`, `search_similar_incidents`), so the worst outcome is a misleading analysis, and every analysis still needs a human decision before it is stored as approved. Accepted for v1; demo data retention (below) limits how long injected text stays around.
- Cost: demo limits (section 3) plus the spend limit in the Anthropic Console.

Privacy (KVKK / GDPR minded):

- Collect as little as possible: no sign-up, no names, no email, no analytics or tracking.
- The sign-in page and the "New incident" dialog say: "Demo data is public. Do not enter personal or confidential information. Demo data is deleted after 7 days."
- Retention: on every container start (the Dockerfile `CMD`, like the embedding backfill) and once a day while running, a cleanup deletes demo-created incidents older than 7 days (their analyses go with them through `ON DELETE CASCADE`), analyses requested by `demo` older than 7 days, and the LangGraph checkpoints of those threads (`PostgresSaver.delete_thread`), because checkpoints also contain the incident text and model messages.
- Only one cookie, the session cookie, which is strictly necessary for signing in. No consent banner is needed for it, but it is described in the privacy notice.
- A short privacy notice at `/ui/privacy` (linked from the sign-in page): what is processed (incident text, session cookie, IP addresses in hosting logs), why (running the demo), where (Render, Neon, Anthropic, Voyage AI), how long (7 days for demo data), and a contact address.
- LangSmith tracing stays off in production, so demo text is not sent to another provider.
- Check the data-use settings of the Anthropic and Voyage AI accounts so API inputs are not used for training, and note the result in the privacy notice.

Supply chain and repository:

- `npm ci` with a committed lockfile; Dependabot for npm with the same 7-day cooldown as pip.
- Enable GitHub secret scanning and push protection (free for public repositories), so a key pasted into a commit is blocked before it reaches GitHub.
- Before each PR is merged, run a security review of the diff (Claude Code `/security-review`, or the Trail of Bits `differential-review`, `insecure-defaults` and `supply-chain-risk-auditor` plugins if installed).

Tests for this section: security headers present, the cleanup deletes only old demo data and its checkpoints, the UI never uses `dangerouslySetInnerHTML` (lint).

## 10. Risks and accepted gaps

- Everyone with the API key is the same `admin`; per-person identity comes with SSO.
- Demo users can write offensive text that other visitors see; the admin can delete it with the API, and it disappears after 7 days.
- Demo users see every incident, including ones created by the admin. The live database is therefore demo-only.
- This design reduces legal risk but is not legal advice. Before Fixwright handles real customer data, a KVKK/GDPR review by a lawyer is needed (data processing agreements, cross-border transfer rules, VERBİS).
- Demo approvals are used as evidence by the agent (otherwise the demo cannot show the RAG loop). Demo rows are tagged and can be removed with one SQL statement.
- The agent's evidence sentences may still contain raw scores; changing the prompt needs an agent eval run and is left for later.
- No rate limit on `/auth/login`; the key is 43 random characters.