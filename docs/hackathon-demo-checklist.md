# Hackathon Demo Checklist

## Prerequisites
- Python 3.11, Node 20+, PostgreSQL 16 running locally.
- Database role + databases are created by `make db-create` (role `swarmops`, databases `swarmops` and `swarmops_test`). It assumes `psql postgres` connects as a superuser (default on Postgres.app / Homebrew). If your setup differs, copy `apps/api/.env.example` to `apps/api/.env` and set `DATABASE_URL` / `TEST_DATABASE_URL` to a role that works for you.

## Startup (once)
```bash
make install     # backend venv + deps, frontend deps
make db-create   # role + databases (idempotent)
make migrate     # alembic upgrade head
make seed        # organization, 6 agents, policies (idempotent)
```

## Run — needs TWO separate terminals
```bash
make api          # terminal 1 → http://localhost:8000  (verify: curl localhost:8000/health)
make web          # terminal 2 → http://localhost:3000
```
Keep both running. If the API terminal is closed or reused, the dashboard shows **API offline** and the mission buttons are disabled.

## Database reset (between rehearsals)
```bash
make db-reset     # drop → migrate → seed
```
This clears missions/events and restores a clean org + agents.

## Demo timing
- Controlled by `DEMO_EVENT_DELAY_MS` (default `650`).
- For a snappy stage demo set `DEMO_EVENT_DELAY_MS=200` before `make api`.
- `0` makes the workflow instant (used by tests).

## Exact click sequence
1. Open http://localhost:3000. Confirm the header shows **API connected** (green).
2. Click **▶ Run demo mission** (uses "Launch a secure AI-powered customer support portal.").
3. Watch agents activate: CEO → Product Manager → Finance → Developer, events streaming in the timeline.
4. A **HUMAN APPROVAL REQUIRED** banner appears for `production.deploy → support-portal-v1` (risk 70). The mission status reads **Awaiting approval**; Developer shows **waiting**.
5. (Optional) Refresh the page — the paused state and timeline are restored from the backend.
6. Click **Approve deploy**. The mission resumes; `deploy.succeeded` appears.
7. A **governance.blocked** event appears (unauthorized `customer_database.export`), highlighted; the Blocked metric becomes **1**. The mission continues.
8. QA finds an issue → Developer fixes it → QA passes.
9. Mission status becomes **Completed**; all six agents show **done**; the completion overlay appears (Esc or click to dismiss).
10. **Evolution runs:** the Mission Summary and Self-Evolving Workforce panel populate — each agent shows a version/score/trend, and any high-risk upgrade shows **Upgrade pending governance** with Approve/Reject (approve one to see it activate to the next version).

## Expected governance events
- `governance.decision` → `approval_required` for `production.deploy` (policy `deployment.production.human_approval`, risk 70).
- `approval.requested` → `mission.paused`.
- `approval.granted` → `deploy.succeeded` (after you approve).
- `governance.decision` → `block` + `governance.blocked` for `customer_database.export` (policy `data.production_export.restricted`, risk 95).

## Expected approval behavior
- The mission does not proceed past step 4 until you click Approve/Reject.
- **Reject** instead of Approve → mission stops safely at **Rejected**, no deploy occurs.
- Clicking Approve twice → second call returns HTTP 409 (already resolved).

## Expected final metrics
- **Events:** ~40 (≈20 workflow milestones + per-agent thinking/reasoning/message + evolution) · **Blocked:** 1 · **Approvals:** 1 · **Cost / Budget:** $0.82 / $5.00 · tasks done ≥ 1.
- After completion: 6 performance reports, and at least one agent version proposed/activated (visible in the Self-Evolving Workforce panel).

## Troubleshooting
- **Header shows "API offline" / mission buttons disabled:** the API isn't running (often its terminal was reused for another command) or CORS origin mismatch. Start `make api` in its own terminal; verify `http://localhost:8000/health`; ensure `CORS_ORIGINS` includes `http://localhost:3000`.
- **`role "swarmops" does not exist`:** run `make db-create` (or set `DATABASE_URL` to a role that exists in your Postgres).
- **`make migrate` fails:** Postgres not running or `DATABASE_URL` wrong. Check `psql "$DATABASE_URL" -c 'select 1'`.
- **`make test` errors on the database:** set `TEST_DATABASE_URL` to a real, empty test database.
- **Dashboard empty / no agents:** run `make seed`.
- **Nothing streams after starting a mission:** confirm the browser can reach `:8000` (open `http://localhost:8000/health`).
- **Want a faster demo:** lower `DEMO_EVENT_DELAY_MS`.
