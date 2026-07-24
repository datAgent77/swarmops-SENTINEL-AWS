"use client";

import { FormEvent } from "react";

export type ControlState = {
  connected: boolean | null;
  busy: boolean;
  streaming: boolean;
  streamPaused: boolean;
  hasMission: boolean;
  soundOn: boolean;
};

export function MissionControls({
  objective,
  setObjective,
  state,
  onLaunch,
  onDemo,
  onPause,
  onResume,
  onCancel,
  onRestart,
  onToggleSound,
}: {
  objective: string;
  setObjective: (v: string) => void;
  state: ControlState;
  onLaunch: () => void;
  onDemo: () => void;
  onPause: () => void;
  onResume: () => void;
  onCancel: () => void;
  onRestart: () => void;
  onToggleSound: () => void;
}) {
  const offline = state.connected === false;
  const showLive = state.streaming || state.streamPaused;

  return (
    <form
      className="controls"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        onLaunch();
      }}
    >
      {showLive ? (
        <div className="ctl-live" role="group" aria-label="Mission controls">
          {state.streamPaused ? (
            <button type="button" className="ctl-btn" onClick={onResume} aria-label="Resume live stream" title="Resume">
              ▶ Resume
            </button>
          ) : (
            <button type="button" className="ctl-btn" onClick={onPause} aria-label="Pause live stream" title="Pause">
              ⏸ Pause
            </button>
          )}
          <button type="button" className="ctl-btn" onClick={onCancel} aria-label="Cancel live view" title="Detach">
            ⏹ Cancel
          </button>
        </div>
      ) : null}

      {state.hasMission ? (
        <button type="button" className="ctl-btn" onClick={onRestart} disabled={state.busy || offline} title="Restart mission">
          ↻ Restart
        </button>
      ) : null}

      <button
        type="button"
        className="btn solid-ok demo"
        disabled={state.busy || offline}
        onClick={onDemo}
      >
        ▶ Run demo mission
      </button>

      <input
        value={objective}
        onChange={(e) => setObjective(e.target.value)}
        aria-label="Mission objective"
        placeholder="Describe a mission objective…"
      />

      <button
        type="button"
        className={`ctl-toggle ${state.soundOn ? "on" : ""}`}
        onClick={onToggleSound}
        aria-pressed={state.soundOn}
        aria-label={state.soundOn ? "Mute sound cues" : "Enable sound cues"}
        title={state.soundOn ? "Sound on" : "Sound off"}
      >
        {state.soundOn ? "🔊" : "🔈"}
      </button>

      <button type="submit" className="btn solid-accent" disabled={state.busy || offline}>
        {state.busy ? "Mission running…" : "Launch mission"}
      </button>
    </form>
  );
}
