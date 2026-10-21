# Sentinel — 3-Minute Demo Video Script (production)

6 parts × 30s = 3:00. Record each part as its own ~30s screen capture and its own
ElevenLabs voiceover, then hand them to the assembly step (see end) to stitch into
one cinematic 3-minute film.

- **Narration language:** English (judges).
- **Voice (ElevenLabs):** a calm, authoritative, documentary-thriller narrator
  (e.g. "Adam" / "Daniel" / any deep neutral voice). Suggested settings:
  Stability ~55, Similarity ~75, Style low–moderate, Speed ~0.97.
- **Pauses:** the `...` in the text are deliberate beats — ElevenLabs honors them.
  For stronger pauses via API/SSML you can use `<break time="0.5s"/>`.
- **Pace target:** ~60–70 words per part so there's room to breathe on visuals.
- **Capture:** browser full-screen, bookmark bar hidden, 1080p, cursor visible.
  Pin the API to 127.0.0.1 (already done) so the backend never drops mid-take.

---

## PART 1 — HOOK (0:00–0:30)
**Screen:** Open on the idle **SIMULATED FEED** (night door), then pull up to the
dashboard showing the title + tagline "AI-powered security decisions. Human-controlled authority."
**Lower-third caption:** `Ring today: it watches. It never acts.`

**🎙️ Voiceover:**
> This is a Ring camera, at eleven thirty at night. It can see everything... and do nothing. It records. It notifies. Then it waits for a human — for every decision. Sentinel changes that. It turns Ring into an AI security officer: one that understands what it sees, enforces security policy, and acts — but never on its own. AI-powered decisions. Human-controlled authority.

---

## PART 2 — HOW IT WORKS (0:30–1:00)
**Screen:** The four status chips. Slowly move the cursor across them; pause on
**BEDROCK — LIVE · AWS — CONNECTED**. Then the pipeline row.
**Lower-third caption:** `Eyes · Understanding · Authority · Human`

**🎙️ Voiceover:**
> Four parts, one principle. Ring is the eyes — it senses motion at the door. Amazon Bedrock is the understanding — a live AWS connection that turns the scene into a structured observation. SwarmOps is the authority — a deterministic policy engine. And a human holds final approval. Here's the rule that makes it safe: intelligence may be probabilistic... but authority must be deterministic. The AI never decides. It only describes.

---

## PART 3 — THE INCIDENT (1:00–1:30)
**Screen:** Click **▶ RUN SECURITY SCENARIO**. Let the incident card render — the
alert camera with the hooded figure and the red **PERSON 92%** box, then **RISK 87 / CRITICAL**.
**Lower-third caption:** `RISK 87 / 100 — CRITICAL`

**🎙️ Voiceover:**
> Eleven forty-two PM. Building closed. Ring detects repeated motion at the front door. Bedrock looks at the scene: a person in a dark hood, lingering, trying the handle — flagged at ninety-two percent confidence. SwarmOps scores the risk deterministically: eighty-seven out of a hundred. Critical. No visitor expected. No access request. No credential. Every signal says the same thing.

---

## PART 4 — THE WINNER MOMENT (1:30–2:00)
**Screen:** Scroll to the centerpiece: **AI PROPOSED ACTION: GRANT TEMPORARY ACCESS**
→ big glowing **DENIED** + the green **SAFE ACTION INSTEAD** callout.
**Lower-third caption:** `AI said: open the door. Policy said: NO.`

**🎙️ Voiceover:**
> Now the moment that matters. The AI proposes an action: grant temporary access — open the door. In most AI products, that would simply... happen. But this recommendation is untrusted. It has to pass policy. SwarmOps evaluates it... and denies it. Outside hours. No visitor. No credential. Risk too high. The AI recommended opening the door. The security policy stopped it.

---

## PART 5 — HUMAN AUTHORITY + EXACTLY ONCE (2:00–2:30)
**Screen:** The **SEND WARNING** card → click **APPROVE** → the green checklist
(WARNING APPROVED · ACTION EXECUTED · **EXACTLY ONCE** · AUDIT RECORDED) →
click **Replay the exact same request** → **DUPLICATE EXECUTION BLOCKED**.
**Lower-third caption:** `Human-approved · Executed exactly once`

**🎙️ Voiceover:**
> Denial isn't the end. A safer action — warning the security officer — needs a human. As the officer, I approve it. The warning fires exactly once, and it's written to an immutable audit trail. And watch this: replay the exact same command — a retry, or an attacker — and Sentinel blocks the duplicate. No second action. No double execution. The guarantee holds.

---

## PART 6 — CLOSE (2:30–3:00)
**Screen:** The result banner **THREAT DETECTED → UNSAFE ACTION DENIED → SECURITY NOTIFIED**,
then a slow pan down the full **INCIDENT TIMELINE**, ending back on the title + tagline.
**Lower-third caption:** `Detected → Denied → Notified`

**🎙️ Voiceover:**
> Three seconds tell the whole story. Threat detected. Unsafe action denied. Security notified. Every step — sensed, understood, judged, approved, executed — recorded, and defensible. Ring gives it eyes. Bedrock gives it understanding. SwarmOps gives it boundaries. And a human stays in command. This is how AI should act in the physical world: with intelligence it can use... and authority it can never abuse. Sentinel. The AI security officer for Ring.

---

## Assembly handoff (for the stitching step)
Deliver into one folder and share the path:
- `part1.mp4 … part6.mp4` — screen recordings (1080p, each ~30s, no audio needed).
- `vo1.mp3 … vo6.mp3` — the matching ElevenLabs voiceovers.
- (optional) `music.mp3` — a tense, royalty-free ambient bed.

The stitching step will: mux each VO onto its clip, normalize/duck audio under the
VO, add ~0.3s crossfades between parts, lay the lower-third captions, drop the music
bed low (−18 dB under VO), and concatenate into `sentinel_demo_3min.mp4`.

Tip: if a clip runs longer/shorter than its VO, that's fine — assembly trims each
part to its VO length (plus a short tail) so the final lands on 3:00.
