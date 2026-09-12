# Sentinel — 3-minute demo script

**Setup:** API on `:8000`, web on `:3000`, open **http://localhost:3000/sentinel**.
Press **RESET DEMO** once before recording. No API keys required (Ring runs on the
documented Playground simulator; Bedrock perception on a deterministic Mock).
On-screen caption to show: *"Ring events replayed from the simulator; every decision
and action executes against the real backend."*

| Time | On screen | What to say |
|------|-----------|-------------|
| **0:00–0:15** | The `/sentinel` header: ON DUTY, SaitALCorp Office, ENTRANCE MONITORED. | "Most security cameras just record. The question at a closed door at midnight isn't *was there motion* — it's *what do we do about it, and who's allowed to decide.*" |
| **0:15–0:35** | Provider row lights up: RING · BEDROCK · SWARMOPS · ALEXA+ MCP. | "Sentinel is an AI security officer. Ring gives it eyes, Amazon Bedrock gives it understanding, SwarmOps gives it boundaries, and a human keeps authority." |
| **0:35–1:00** | Press **START DEMO**. Timeline fills: 23:42 / 23:44 / 23:47 motion. | "A real, HMAC-signed Ring event enters the backend — three motion events at a closed entrance, correlated into one incident, not three noisy alerts." |
| **1:00–1:25** | Incident card + AI OBSERVATION. | "Bedrock reads the scene and returns a *structured observation* — person present, prolonged, repeated. It describes; it has no authority." |
| **1:25–1:50** | Risk CRITICAL; AI RECOMMENDATION: GRANT TEMPORARY ACCESS. | "The AI even recommends granting temporary access. Here's where every other demo would just… do it." |
| **1:50–2:05** | Centerpiece flips to **SWARMOPS POLICY — DENIED** + four reasons. | "SwarmOps denies it. Deterministically. Outside hours, no verified visitor, no access request, no credential. The AI *cannot* override this rule." |
| **2:05–2:25** | SEND WARNING → HUMAN APPROVAL REQUIRED → click **APPROVE** (as security officer). | "For a warning, it asks a human with the right role. I approve it — and only now does it act." |
| **2:25–2:40** | ACTION EXECUTED → click **Replay** → **DUPLICATE BLOCKED**. | "Executed exactly once. I replay the exact same request — duplicate blocked. No double actions, ever." |
| **2:40–2:52** | Timeline: full chain incident → observation → risk → denied → approved → executed. | "Every step is on an append-only audit trail — observation, decision, policy version, approval, execution." |
| **2:52–3:00** | Closing card. | *"Ring gave AI eyes. Bedrock gave it understanding. SwarmOps gave it boundaries. Sentinel turns all three into an AI security officer you can trust."* |

## Reproduce it yourself
- `make install && make db-create && make demo`, then `make api` and `make web`.
- Open `/sentinel`, **START DEMO**, **APPROVE**, **Replay**.
- Or headless: `POST /api/sentinel/demo/start` → `POST /api/sentinel/approve` → `POST /api/sentinel/propose` (same `action_request_id`) → `GET /api/sentinel/timeline`.

## Honesty notes (say if asked)
- The scene is a scripted reproduction of a 23:42 incident; the **Ring events are ingested for real** (signature-verified) and **every decision/execution runs against the real backend**.
- No real smart lock is actuated — physical access stays a governed, default-denied action.
