"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AgentItem, EvolutionCard, MissionRow, MissionSummary, Snapshot, EventItem, STATUS_LABEL, TERMINAL } from "./lib/types";
import { activeAgentKey, deriveAgents, eventMeta } from "./lib/derive";
import { playCue } from "./lib/sound";
import { WorkforceGraph } from "./components/WorkforceGraph";
import { MetricsRail } from "./components/MetricsRail";
import { Timeline } from "./components/Timeline";
import { ConversationPanel } from "./components/ConversationPanel";
import { ReasoningCards } from "./components/ReasoningCards";
import { ApprovalPanel } from "./components/ApprovalPanel";
import { EvolutionPanel } from "./components/EvolutionPanel";
import { CompletionOverlay } from "./components/CompletionOverlay";
import { MissionControls } from "./components/MissionControls";
import { RingStatus } from "./components/RingStatus";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DEMO_OBJECTIVE = "Launch a secure AI-powered customer support portal.";

type Tab = "timeline" | "conversation" | "reasoning";

export default function MissionControl() {
  const [objective, setObjective] = useState(DEMO_OBJECTIVE);
  const [connected, setConnected] = useState<boolean | null>(null);
  const [agents, setAgents] = useState<AgentItem[]>([]);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [streamPaused, setStreamPaused] = useState(false);
  const [deciding, setDeciding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [evolution, setEvolution] = useState<EvolutionCard[]>([]);
  const [summary, setSummary] = useState<MissionSummary | null>(null);
  const [tab, setTab] = useState<Tab>("timeline");
  const [soundOn, setSoundOn] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [showOverlay, setShowOverlay] = useState(false);
  const [sponsors, setSponsors] = useState<string[]>([]);

  const missionIdRef = useRef<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);
  const seenSeq = useRef<Set<number>>(new Set());
  const soundRef = useRef(false);
  const prevStatusRef = useRef<string | null>(null);

  useEffect(() => {
    soundRef.current = soundOn;
  }, [soundOn]);

  // Reduced-motion + high-contrast: reflect OS preferences onto <html> so CSS
  // and the SVG particle logic can respond.
  useEffect(() => {
    const rm = window.matchMedia("(prefers-reduced-motion: reduce)");
    const hc = window.matchMedia("(prefers-contrast: more)");
    const apply = () => {
      setReducedMotion(rm.matches);
      document.documentElement.classList.toggle("reduce-motion", rm.matches);
      document.documentElement.classList.toggle("high-contrast", hc.matches);
    };
    apply();
    rm.addEventListener("change", apply);
    hc.addEventListener("change", apply);
    return () => {
      rm.removeEventListener("change", apply);
      hc.removeEventListener("change", apply);
    };
  }, []);

  const fetchEvolution = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/evolution/agents`);
      if (res.ok) setEvolution((await res.json()) as EvolutionCard[]);
    } catch {
      /* ignore */
    }
  }, []);

  const fetchSummary = useCallback(async (missionId: string) => {
    try {
      const res = await fetch(`${API_URL}/api/missions/${missionId}/summary`);
      if (res.ok) setSummary((await res.json()) as MissionSummary);
    } catch {
      /* ignore */
    }
  }, []);

  const refreshSnapshot = useCallback(async (missionId: string) => {
    try {
      const res = await fetch(`${API_URL}/api/missions/${missionId}`);
      if (res.ok) setSnapshot((await res.json()) as Snapshot);
    } catch {
      /* transient */
    }
  }, []);

  // Returns true only when the event is newly seen (drives live sound cues).
  const appendEvent = useCallback((item: EventItem): boolean => {
    if (seenSeq.current.has(item.seq)) return false;
    seenSeq.current.add(item.seq);
    setEvents((current) => [...current, item].sort((a, b) => a.seq - b.seq));
    return true;
  }, []);

  const cueFor = (item: EventItem) => {
    if (!soundRef.current) return;
    const t = item.type;
    if (t === "agent.message") playCue("message");
    else if (t === "governance.blocked" || t === "mission.rejected") playCue("block");
    else if (t === "approval.requested" || t === "mission.paused") playCue("approval");
    else if (t === "mission.completed") playCue("complete");
    else if (t.startsWith("agent.version")) playCue("evolve");
  };

  // After "completed", two things land shortly after (paced): first the evolution
  // summary, then the cited.md publish event a beat later. Poll until BOTH are in
  // so the REPORT/PUBLISHED chip and the mission.published timeline entry are never
  // missed by stopping the instant the summary appears.
  const pollEvolution = useCallback(async (missionId: string) => {
    let sawSummary = false;
    let sawPublish = false;
    for (let attempt = 0; attempt < 12; attempt += 1) {
      await new Promise((r) => window.setTimeout(r, attempt === 0 ? 500 : 800));
      void fetchEvolution();
      // Pull post-completion events (evolution + cited.md publish) into the timeline.
      try {
        const evRes = await fetch(`${API_URL}/api/missions/${missionId}/events`);
        if (evRes.ok) {
          const items = (await evRes.json()) as EventItem[];
          items.forEach(appendEvent);
          if (items.some((e) => e.type === "mission.published" || e.type === "publish.failed")) {
            sawPublish = true;
          }
        }
      } catch {
        /* transient */
      }
      try {
        const res = await fetch(`${API_URL}/api/missions/${missionId}/summary`);
        if (res.ok) {
          const s = (await res.json()) as MissionSummary;
          setSummary(s);
          if (s.top_performer) sawSummary = true;
        }
      } catch {
        /* transient */
      }
      if (sawSummary && sawPublish) break; // evolution + publish both captured
    }
  }, [fetchEvolution, appendEvent]);

  const openStream = useCallback(
    (missionId: string) => {
      sourceRef.current?.close();
      const source = new EventSource(`${API_URL}/api/missions/${missionId}/stream`);
      sourceRef.current = source;
      setStreaming(true);
      setStreamPaused(false);
      source.onmessage = (message) => {
        let item: EventItem;
        try {
          item = JSON.parse(message.data) as EventItem;
        } catch {
          return; // ignore keep-alive / non-JSON frames instead of crashing the handler
        }
        setError((e) => (e ? null : e)); // a live message means the stream recovered
        const isNew = appendEvent(item);
        if (isNew) cueFor(item);
        void refreshSnapshot(missionId);
        if (item.type.startsWith("mission.") && TERMINAL.has(item.type.replace("mission.", ""))) {
          source.close();
          setStreaming(false);
          void pollEvolution(missionId);
        }
      };
      source.onerror = () => {
        // The browser auto-reconnects an EventSource while readyState is CONNECTING;
        // only surface a hint. A CLOSED state is the normal end-of-stream close.
        if (source.readyState === EventSource.CONNECTING) {
          setError("Live stream reconnecting…");
        } else {
          setStreaming(false);
        }
      };
    },
    [appendEvent, refreshSnapshot, pollEvolution],
  );

  const loadMission = useCallback(
    async (missionId: string) => {
      missionIdRef.current = missionId;
      seenSeq.current = new Set();
      setEvents([]);
      const [snapRes, evRes] = await Promise.all([
        fetch(`${API_URL}/api/missions/${missionId}`),
        fetch(`${API_URL}/api/missions/${missionId}/events`),
      ]);
      let status: string | undefined;
      if (snapRes.ok) {
        const snap = (await snapRes.json()) as Snapshot;
        setSnapshot(snap);
        status = snap.mission.status;
        prevStatusRef.current = status ?? null;
      }
      if (evRes.ok) {
        const list = (await evRes.json()) as EventItem[];
        list.forEach(appendEvent);
        if (status && !TERMINAL.has(status)) openStream(missionId);
      }
    },
    [appendEvent, openStream],
  );

  // Initial load.
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/dashboard`);
        if (!res.ok) throw new Error();
        const dash = await res.json();
        setConnected(true);
        setAgents(dash.agents ?? []);
        setSponsors(dash.sponsors ?? []);
        void fetchEvolution();
        const missions = (dash.missions ?? []) as MissionRow[];
        if (missions.length > 0) {
          await loadMission(missions[0].id);
          void fetchSummary(missions[0].id);
        }
      } catch {
        setConnected(false);
      }
    })();
    return () => sourceRef.current?.close();
  }, [loadMission, fetchEvolution, fetchSummary]);

  // Completion overlay: pop only on a live transition into a terminal state.
  useEffect(() => {
    const s = snapshot?.mission.status;
    if (s && TERMINAL.has(s) && prevStatusRef.current && !TERMINAL.has(prevStatusRef.current)) {
      setShowOverlay(true);
    }
    if (s) prevStatusRef.current = s;
  }, [snapshot]);

  async function startMission(nextObjective: string) {
    setError(null);
    sourceRef.current?.close();
    seenSeq.current = new Set();
    setEvents([]);
    setSnapshot(null);
    setSummary(null);
    setShowOverlay(false);
    prevStatusRef.current = "created";
    try {
      const res = await fetch(`${API_URL}/api/missions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ objective: nextObjective, budget_usd: 5 }),
      });
      if (!res.ok) throw new Error(`Mission could not be created (${res.status})`);
      const mission = await res.json();
      missionIdRef.current = mission.id;
      await refreshSnapshot(mission.id);
      openStream(mission.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reach the API on :8000.");
    }
  }

  async function decide(action: "approve" | "reject") {
    const approvalId = snapshot?.pending_approval?.id;
    if (!approvalId) return;
    setDeciding(true);
    try {
      const res = await fetch(`${API_URL}/api/approvals/${approvalId}/${action}`, { method: "POST" });
      if (res.ok) setSnapshot((await res.json()) as Snapshot);
    } catch {
      setError("Could not submit the decision.");
    } finally {
      setDeciding(false);
    }
  }

  async function decideVersion(versionId: string, action: "approve" | "reject") {
    try {
      await fetch(`${API_URL}/api/evolution/versions/${versionId}/${action}`, { method: "POST" });
      await fetchEvolution();
    } catch {
      setError("Could not submit the upgrade decision.");
    }
  }

  // Mission controls -----------------------------------------------------------
  const pauseStream = () => {
    sourceRef.current?.close();
    setStreaming(false);
    setStreamPaused(true);
  };
  const resumeStream = () => {
    const id = missionIdRef.current;
    if (id) openStream(id);
  };
  const cancelStream = () => {
    sourceRef.current?.close();
    setStreaming(false);
    setStreamPaused(false);
  };
  const restartMission = () => void startMission(objective);

  // Derived view models --------------------------------------------------------
  const roster = snapshot?.agents ?? agents;
  const nameOf = useCallback(
    (key: string) => roster.find((a) => a.key === key)?.name ?? key,
    [roster],
  );
  const status = snapshot?.mission.status ?? "created";
  const pending = snapshot?.pending_approval ?? null;
  const isPaused = status === "waiting_approval" && pending !== null;
  const busy = streaming || (!!status && !TERMINAL.has(status) && status !== "created");

  const activeKey = useMemo(
    () => (streaming && !isPaused ? activeAgentKey(events) : isPaused ? activeAgentKey(events) : null),
    [events, streaming, isPaused],
  );
  const agentViews = useMemo(
    () => deriveAgents(roster, evolution, events, activeKey),
    [roster, evolution, events, activeKey],
  );
  const primary = agentViews.find((a) => a.provider);
  const liveCount = agentViews.filter((a) => ["working", "waiting_approval"].includes(a.status)).length;
  const govCount = useMemo(() => events.filter((e) => eventMeta(e).governance).length, [events]);
  const published = useMemo(() => events.find((e) => e.type === "mission.published") ?? null, [events]);
  const publishedUrl = (published?.payload?.url as string | undefined) || undefined;

  const connLabel = connected === false ? "API offline" : connected ? "API connected" : "Connecting…";

  return (
    <main>
      <header className="masthead">
        <div className="mast-id">
          <span className="eyebrow">SWARMOPS</span>
          <h1>Living Workforce</h1>
          <p>A real-time operations plane for an autonomous AI workforce under deterministic governance.</p>
        </div>
        <div className="mast-side">
          <div className="chip env" title="Active LLM environment">
            <span className="chip-k">ENV</span>
            {primary ? `${primary.provider} · ${primary.model}` : "mock · standby"}
          </div>
          <div className="chip gov" title="Governance decisions this mission">
            <span className="chip-k">GOV</span>
            {govCount} checks
          </div>
          <RingStatus />
          {sponsors.length > 0 ? (
            <div className="chip tools" title="Sponsor tools in use">
              <span className="chip-k">TOOLS</span>
              {sponsors.map((s) => s[0].toUpperCase() + s.slice(1)).join(" · ")}
            </div>
          ) : null}
          {published ? (
            publishedUrl ? (
              <a className="chip pub" href={publishedUrl} target="_blank" rel="noreferrer" title="Mission report published to cited.md">
                <span className="chip-k">PUBLISHED</span> cited.md ↗
              </a>
            ) : (
              <div className="chip pub" title="Mission report generated (set CITED_API_KEY to publish)">
                <span className="chip-k">REPORT</span> ready
              </div>
            )
          ) : null}
          <div className={`chip conn ${connected === false ? "down" : connected ? "up" : ""}`}>
            <span className="dot" /> {connLabel}
          </div>
          <div className={`chip status ${status}`}>{STATUS_LABEL[status] ?? status}</div>
        </div>
      </header>

      <MetricsRail
        metrics={snapshot?.metrics}
        statusLabel={STATUS_LABEL[status] ?? status}
        provider={primary?.provider ?? null}
        reducedMotion={reducedMotion}
      />

      <div className="stage">
        <section className="panel graph-panel">
          <div className="panel-head">
            <h2>AI Workforce</h2>
            <span>{liveCount > 0 ? `${liveCount} active` : `${agentViews.length} agents`}</span>
          </div>
          <WorkforceGraph agents={agentViews} reducedMotion={reducedMotion} />
        </section>

        <section className="panel feed-panel">
          <div className="panel-head tabs" role="tablist" aria-label="Activity views">
            <button role="tab" aria-selected={tab === "timeline"} className={tab === "timeline" ? "on" : ""} onClick={() => setTab("timeline")}>
              Timeline
            </button>
            <button role="tab" aria-selected={tab === "conversation"} className={tab === "conversation" ? "on" : ""} onClick={() => setTab("conversation")}>
              Conversation
            </button>
            <button role="tab" aria-selected={tab === "reasoning"} className={tab === "reasoning" ? "on" : ""} onClick={() => setTab("reasoning")}>
              Reasoning
            </button>
            <span className="feed-state">
              {streaming ? (isPaused ? "Paused · approval" : "Streaming") : streamPaused ? "Paused" : TERMINAL.has(status) ? "Done" : "Idle"}
            </span>
          </div>
          <div className="feed-body">
            {tab === "timeline" ? <Timeline events={events} nameOf={nameOf} reducedMotion={reducedMotion} /> : null}
            {tab === "conversation" ? <ConversationPanel events={events} nameOf={nameOf} reducedMotion={reducedMotion} /> : null}
            {tab === "reasoning" ? <ReasoningCards agents={agentViews} /> : null}
          </div>
        </section>
      </div>

      <EvolutionPanel
        evolution={evolution}
        summary={summary}
        showSummary={TERMINAL.has(status)}
        onDecideVersion={decideVersion}
      />

      {error ? <div className="error-bar">{error}</div> : null}

      <MissionControls
        objective={objective}
        setObjective={setObjective}
        state={{ connected, busy, streaming, streamPaused, hasMission: !!missionIdRef.current, soundOn }}
        onLaunch={() => void startMission(objective)}
        onDemo={() => {
          setObjective(DEMO_OBJECTIVE);
          void startMission(DEMO_OBJECTIVE);
        }}
        onPause={pauseStream}
        onResume={resumeStream}
        onCancel={cancelStream}
        onRestart={restartMission}
        onToggleSound={() => setSoundOn((v) => !v)}
      />

      {isPaused && pending ? <ApprovalPanel pending={pending} deciding={deciding} onDecide={decide} /> : null}

      {showOverlay ? (
        <CompletionOverlay
          status={status}
          metrics={snapshot?.metrics}
          summary={summary}
          reducedMotion={reducedMotion}
          onClose={() => setShowOverlay(false)}
        />
      ) : null}
    </main>
  );
}
