# SwarmOps — 3-minute demo (voiceover + screen recording)

Production plan: generate the voiceover in ElevenLabs (one clip per segment), record a clean silent
screen capture, then combine. Total narration ≈ 420 words ≈ 2:48 (under the 3-minute limit).

## A. Voiceover script (paste into ElevenLabs, one clip per segment)

**S1 — Hook / problem (~20s)**
> AI agents are moving into the enterprise faster than anyone can govern them. They can deploy code, move money, and touch customer data — with none of the controls we demand of human employees. SwarmOps is the operating system for AI workforces. Govern. Audit. Evolve.

**S2 — Launch (~15s)**
> Six AI agents take on a real mission — launch a secure customer support portal. They reason through a large language model, coordinate over Band, and pull verified context from Senso.

**S3 — Governance pause (~23s)**
> Watch the Developer. It wants to deploy to production — and the mission pauses. A deterministic policy engine, with zero language model in the enforcement path, requires a human here. The model can propose the action, but it can never approve it. This is exactly what enterprises need.

**S4 — Approve (~12s)**
> I approve. The mission resumes and deploys — and every step is written to an append-only audit trail in PostgreSQL.

**S5 — Block (~20s)**
> Now an agent tries to export the production customer database. Blocked — instantly, deterministically, and permanently audited. No data leaves the system, no matter what the model decides.

**S6 — Complete (~22s)**
> QA finds a bug, the Developer fixes it, QA re-validates, Finance reports the cost. Mission complete — with a full, replayable record of every decision, approval, and dollar spent.

**S7 — Self-evolution (~30s)**
> Here's what makes SwarmOps different. The moment the mission ends, the workforce grades itself — scoring each agent from real, persisted mission data. The Product Manager proposed a high-risk upgrade, so it needs my approval, exactly like the production deploy did. Every version is immutable, data-only, and reversible. Agents improve over time — but they can never touch their own executable code.

**S8 — Tool use / resilience (~23s)**
> And every sponsor technology sits behind a resilient, pluggable adapter. Pioneer routes the model. Band carries the conversation. Senso supplies context. If any of them goes down, the mission still completes — because the governance layer stays completely provider-independent.

**S9 — Close (~15s)**
> SwarmOps. Self-improving, measurable, reversible — and governed the whole way down. The management layer that makes an AI workforce safe to run in a real company.

## B. On-screen actions (sync each to its segment)

| Seg | On screen |
|---|---|
| S1 | Idle dashboard (title, ENV + TOOLS chips visible). |
| S2 | Click **Run demo mission**; graph lights up; briefly point to ENV + TOOLS chips. |
| S3 | Approval side panel slides in (risk gauge). Hold here — the mission waits for you. |
| S4 | Click **Approve**; `deploy.succeeded` appears in the timeline. |
| S5 | `governance.blocked` (red) appears in the timeline; Blocked metric → 1. |
| S6 | QA issue → fix → pass; completion overlay appears with the stat tiles. |
| S7 | Dismiss overlay (Esc); scroll to Self-Evolving Workforce panel; click **Approve → v1.1** on the pending upgrade. |
| S8 | Point to the **TOOLS** chip (Pioneer · Band · Senso). |
| S9 | Wide shot of the dashboard / show the GitHub URL. |

## C. Production checklist

**Before recording**
- Clean state: `make db-reset`. Pacing: `DEMO_EVENT_DELAY_MS=800` in `apps/api/.env`, then `make demo`.
- Chips: set a real provider key (`OPENAI_API_KEY`/`GEMINI_API_KEY` + `LLM_PROVIDER`) and `BAND_API_KEY=demo SENSO_API_KEY=demo PIONEER_KEY=demo` so ENV + TOOLS show.
- Chrome full-screen, 100% zoom, bookmarks hidden. Do one dry run.

**Recording (silent)**
- macOS: Cmd+Shift+5 → record the Chrome window. No talking — voiceover goes on later.
- Play the ElevenLabs clips in headphones while recording so your clicks land on the right beats. Hold at the two approval gates as long as the VO needs.

**Combine (send both files back; assembled with ffmpeg)**
- Deliver: the screen recording (.mov/.mp4) + the ElevenLabs audio (one mp3 per segment, or one combined track).
- Assembly: mux audio onto video, align segments, optional title cards + subtitles → final .mp4 under 3:00.

**ElevenLabs tips**
- Pick one clear, confident voice; keep it consistent across all clips.
- Per-segment clips make alignment trivial (name them s1…s9).
- Moderate stability; leave a ~0.4s of silence at the end of each clip so segments don't clip together.
