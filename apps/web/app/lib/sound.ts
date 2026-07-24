// Tiny WebAudio cue engine. Disabled by default; the user opts in.
// No external assets — tones are synthesized so there's nothing to bundle.

let ctx: AudioContext | null = null;

function tone(freq: number, durMs: number, type: OscillatorType, gain: number) {
  try {
    if (!ctx) {
      const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      ctx = new AC();
    }
    if (ctx.state === "suspended") void ctx.resume();
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    osc.type = type;
    osc.frequency.value = freq;
    g.gain.setValueAtTime(0.0001, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(gain, ctx.currentTime + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + durMs / 1000);
    osc.connect(g);
    g.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + durMs / 1000);
  } catch {
    /* audio is best-effort; never throw into the UI */
  }
}

export type Cue = "message" | "approval" | "block" | "complete" | "evolve";

export function playCue(cue: Cue) {
  switch (cue) {
    case "message":
      return tone(520, 90, "sine", 0.04);
    case "approval":
      return tone(660, 220, "triangle", 0.06);
    case "block":
      return tone(180, 260, "sawtooth", 0.05);
    case "evolve":
      return tone(780, 160, "sine", 0.05);
    case "complete":
      tone(523, 130, "sine", 0.06);
      window.setTimeout(() => tone(659, 130, "sine", 0.06), 130);
      window.setTimeout(() => tone(784, 220, "sine", 0.06), 260);
      return;
  }
}
