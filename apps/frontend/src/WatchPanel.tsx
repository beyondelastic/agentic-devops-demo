import { useEffect, useMemo, useRef, useState } from "react";

export type WatchResult = {
  trial_id?: string | null;
  trial_title?: string | null;
  trial_condition?: string | null;
  score: number;
  prev_score?: number | null;
  is_new?: boolean;
  reason: string;
  scored_at?: string | null;
};

export type WatchProfile = {
  age?: number | null;
  sex?: string | null;
  condition?: string | null;
  stage?: string | null;
  location?: string | null;
  prior_treatments?: string[];
};

export type WatchSearch = {
  condition?: string | null;
  location?: string | null;
  age?: number | null;
  sex?: string | null;
  phase?: string | null;
  limit?: number;
};

export type Watch = {
  id: string;
  name: string;
  profile: WatchProfile;
  search: WatchSearch;
  created_at: string;
  last_checked?: string | null;
  results: WatchResult[];
};

type ConnState = "connecting" | "live" | "stalled";

export default function WatchPanel() {
  const [watches, setWatches] = useState<Watch[]>([]);
  const [conn, setConn] = useState<ConnState>("connecting");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [showTrialForm, setShowTrialForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [addingTrial, setAddingTrial] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  // watch_id -> timestamp (ms) of latest last_checked we've seen, used to flash cards on update.
  const [updatedAt, setUpdatedAt] = useState<Record<string, number>>({});
  const lastCheckedRef = useRef<Record<string, string>>({});
  const lastEventAtRef = useRef<number>(Date.now());

  useEffect(() => {
    const es = new EventSource("/api/watches/stream");
    es.onopen = () => setConn("live");
    es.onmessage = (ev) => {
      lastEventAtRef.current = Date.now();
      setConn("live");
      try {
        const data = JSON.parse(ev.data) as Watch[];
        // Detect which watches just got a fresh tick.
        const flashed: Record<string, number> = {};
        const now = Date.now();
        for (const w of data) {
          const prev = lastCheckedRef.current[w.id];
          if (w.last_checked && w.last_checked !== prev) {
            if (prev !== undefined) flashed[w.id] = now;
            lastCheckedRef.current[w.id] = w.last_checked;
          }
        }
        if (Object.keys(flashed).length > 0) {
          setUpdatedAt((u) => ({ ...u, ...flashed }));
        }
        setWatches(data);
      } catch (err) {
        console.warn("watch stream parse error", err);
      }
    };
    es.onerror = () => setConn("stalled");

    const stallCheck = setInterval(() => {
      if (Date.now() - lastEventAtRef.current > 30_000) setConn("stalled");
    }, 5_000);

    return () => {
      es.close();
      clearInterval(stallCheck);
    };
  }, []);

  async function deleteWatch(id: string) {
    if (!confirm("Delete this watch?")) return;
    try {
      const r = await fetch(`/api/watches/${id}`, { method: "DELETE" });
      if (!r.ok && r.status !== 204) throw new Error(`HTTP ${r.status}`);
      setWatches((ws) => ws.filter((w) => w.id !== id));
    } catch (err) {
      setError(`Delete failed: ${(err as Error).message}`);
    }
  }

  async function createWatch(payload: NewWatchPayload) {
    setCreating(true);
    setError(null);
    try {
      const r = await fetch("/api/watches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setShowForm(false);
    } catch (err) {
      setError(`Create failed: ${(err as Error).message}`);
    } finally {
      setCreating(false);
    }
  }

  async function addTrial(payload: NewTrialPayload) {
    setAddingTrial(true);
    setError(null);
    try {
      const r = await fetch("/api/trials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const trial = await r.json();
      setShowTrialForm(false);
      setToast(
        `Added trial ${trial.id} — next watcher tick will pick it up and emit a NEW pill.`,
      );
      setTimeout(() => setToast(null), 8000);
    } catch (err) {
      setError(`Add trial failed: ${(err as Error).message}`);
    } finally {
      setAddingTrial(false);
    }
  }

  const sorted = useMemo(
    () => [...watches].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [watches],
  );

  return (
    <div className="flex flex-col h-full bg-slate-50">
      <div className="px-6 py-4 border-b bg-white flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-800">Trial Watch</h2>
          <p className="text-xs text-slate-500">
            Saved patient profiles, continuously rescored by an in-cluster Llama-3.2-3B model.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ConnPill state={conn} />
          <button
            onClick={() => {
              setShowTrialForm((v) => !v);
              setShowForm(false);
            }}
            className="text-xs font-medium px-3 py-1.5 rounded-md border border-slate-300 text-slate-700 hover:bg-slate-100"
          >
            {showTrialForm ? "Cancel" : "+ Import trial"}
          </button>
          <button
            onClick={() => {
              setShowForm((v) => !v);
              setShowTrialForm(false);
            }}
            className="bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-500 hover:to-blue-500 text-white text-xs font-medium px-3 py-1.5 rounded-md shadow-sm"
          >
            {showForm ? "Cancel" : "+ New watch"}
          </button>
        </div>
      </div>

      {showForm && (
        <div className="px-6 py-4 border-b bg-indigo-50/40">
          <NewWatchForm onSubmit={createWatch} submitting={creating} />
        </div>
      )}

      {showTrialForm && (
        <div className="px-6 py-4 border-b bg-emerald-50/40">
          <NewTrialForm onSubmit={addTrial} submitting={addingTrial} />
        </div>
      )}

      {toast && (
        <div className="px-6 py-2 text-xs text-emerald-800 bg-emerald-50 border-b border-emerald-100">
          {toast}
        </div>
      )}

      {error && (
        <div className="px-6 py-2 text-xs text-red-700 bg-red-50 border-b border-red-100">
          {error}
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-3">
        {sorted.length === 0 && (
          <div className="max-w-xl mx-auto text-center text-slate-500 text-sm pt-12">
            <div className="text-4xl mb-3">🔭</div>
            <div className="font-medium text-slate-700">No watches yet.</div>
            <div className="text-xs mt-1">
              Create one to have the in-cluster model score new trials against a patient
              profile every couple of minutes.
            </div>
          </div>
        )}
        {sorted.map((w) => (
          <WatchCard
            key={w.id}
            watch={w}
            expanded={expanded === w.id}
            flashedAt={updatedAt[w.id] ?? null}
            onToggle={() => setExpanded(expanded === w.id ? null : w.id)}
            onDelete={() => deleteWatch(w.id)}
          />
        ))}
      </div>
    </div>
  );
}

function ConnPill({ state }: { state: ConnState }) {
  const label = state === "live" ? "live" : state === "stalled" ? "reconnecting…" : "connecting…";
  const dot =
    state === "live"
      ? "bg-emerald-500"
      : state === "stalled"
        ? "bg-amber-400 animate-pulse"
        : "bg-slate-400 animate-pulse";
  return (
    <span className="flex items-center gap-1.5 text-[11px] text-slate-600 bg-white border border-slate-200 rounded-full px-2.5 py-1">
      <span className={"w-1.5 h-1.5 rounded-full " + dot} />
      {label}
    </span>
  );
}

function WatchCard({
  watch,
  expanded,
  flashedAt,
  onToggle,
  onDelete,
}: {
  watch: Watch;
  expanded: boolean;
  flashedAt: number | null;
  onToggle: () => void;
  onDelete: () => void;
}) {
  const top = watch.results.reduce<WatchResult | null>(
    (best, r) => (best == null || r.score > best.score ? r : best),
    null,
  );
  const newCount = watch.results.filter((r) => r.is_new).length;

  // Pulse for ~6s after a fresh tick lands.
  const [pulsing, setPulsing] = useState(false);
  useEffect(() => {
    if (flashedAt == null) return;
    setPulsing(true);
    const t = setTimeout(() => setPulsing(false), 6000);
    return () => clearTimeout(t);
  }, [flashedAt]);

  return (
    <div
      className={
        "bg-white border rounded-xl shadow-sm transition-colors duration-700 " +
        (pulsing ? "border-indigo-300 ring-2 ring-indigo-100" : "border-slate-200")
      }
    >
      <div className="px-4 py-3 flex items-center gap-3">
        <button
          onClick={onToggle}
          className="flex-1 min-w-0 text-left flex items-center gap-3"
        >
          <ScoreBadge score={top?.score ?? null} />
          <div className="min-w-0 flex-1">
            <div className="text-sm font-semibold text-slate-800 truncate flex items-center gap-2">
              <span className="truncate">{watch.name}</span>
              {newCount > 0 && (
                <span className="text-[10px] uppercase tracking-wider font-bold bg-indigo-600 text-white rounded px-1.5 py-0.5">
                  {newCount} new
                </span>
              )}
              {top != null && <TierLabel score={top.score} />}
            </div>
            <div className="text-[11px] text-slate-500 truncate">
              {profileSummary(watch.profile)}
            </div>
          </div>
          <div className="text-[11px] text-slate-400 hidden md:block text-right">
            <div>
              {watch.results.length} result{watch.results.length === 1 ? "" : "s"}
            </div>
            <div>{watch.last_checked ? relTime(watch.last_checked) : "not yet checked"}</div>
          </div>
          <span className="text-slate-400 text-xs">{expanded ? "▾" : "▸"}</span>
        </button>
        <button
          onClick={onDelete}
          title="Delete watch"
          className="text-slate-400 hover:text-red-600 text-sm px-2"
        >
          ✕
        </button>
      </div>

      {expanded && (
        <div className="border-t bg-slate-50/50 px-4 py-3 space-y-2">
          {watch.results.length === 0 ? (
            <div className="text-xs text-slate-500 italic">
              No scoring results yet — the watcher will fill these in on its next tick.
            </div>
          ) : (
            <ul className="space-y-2">
              {[...watch.results]
                .sort((a, b) => b.score - a.score)
                .map((r, i) => (
                  <li
                    key={(r.trial_id ?? "x") + i}
                    className="bg-white border border-slate-200 rounded-lg px-3 py-2 flex items-start gap-3"
                  >
                    <ScoreBadge score={r.score} />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-slate-800 truncate flex items-center gap-2">
                        <span className="truncate">
                          {r.trial_title || r.trial_id || "Unknown trial"}
                        </span>
                        {r.is_new && (
                          <span className="text-[9px] uppercase tracking-wider font-bold bg-indigo-600 text-white rounded px-1.5 py-0.5 shrink-0">
                            new
                          </span>
                        )}
                        <DeltaBadge score={r.score} prev={r.prev_score ?? null} />
                      </div>
                      <div className="text-[11px] text-slate-500 truncate">
                        {r.trial_id}
                        {r.trial_condition ? ` · ${r.trial_condition}` : ""}
                      </div>
                      <div className="text-xs text-slate-700 mt-1">{r.reason}</div>
                    </div>
                  </li>
                ))}
            </ul>
          )}
          <div className="text-[10px] text-slate-400 pt-1 flex flex-wrap gap-x-4 gap-y-0.5">
            <span>id: {watch.id}</span>
            <span>created: {fmtDate(watch.created_at)}</span>
            <span>
              last checked:{" "}
              {watch.last_checked ? fmtDate(watch.last_checked) : "—"}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function TierLabel({ score }: { score: number }) {
  const [label, cls] =
    score >= 80
      ? ["Strong match", "text-emerald-700 bg-emerald-50 border-emerald-200"]
      : score >= 60
        ? ["Possible match", "text-amber-700 bg-amber-50 border-amber-200"]
        : ["Unlikely", "text-slate-600 bg-slate-50 border-slate-200"];
  return (
    <span
      className={
        "text-[10px] uppercase tracking-wider font-semibold border rounded-full px-2 py-0.5 shrink-0 " +
        cls
      }
    >
      {label}
    </span>
  );
}

function DeltaBadge({ score, prev }: { score: number; prev: number | null }) {
  if (prev == null || prev === score) return null;
  const diff = score - prev;
  const up = diff > 0;
  const cls = up
    ? "text-emerald-700 bg-emerald-50 border-emerald-200"
    : "text-rose-700 bg-rose-50 border-rose-200";
  return (
    <span
      className={
        "text-[10px] font-semibold border rounded-full px-1.5 py-0.5 shrink-0 " + cls
      }
      title={`Previous score: ${prev}`}
    >
      {up ? "▲" : "▼"} {Math.abs(diff)}
    </span>
  );
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score == null)
    return (
      <span className="w-10 h-10 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center text-[10px] text-slate-400 shrink-0">
        …
      </span>
    );
  const tier =
    score >= 80
      ? "bg-emerald-100 text-emerald-800 border-emerald-200"
      : score >= 60
        ? "bg-amber-100 text-amber-800 border-amber-200"
        : "bg-slate-100 text-slate-700 border-slate-200";
  return (
    <span
      className={
        "w-10 h-10 rounded-lg border flex items-center justify-center text-sm font-semibold shrink-0 " +
        tier
      }
    >
      {score}
    </span>
  );
}

function profileSummary(p: WatchProfile): string {
  const parts: string[] = [];
  if (p.age) parts.push(`${p.age}`);
  if (p.sex) parts.push(p.sex);
  if (p.condition) parts.push(p.condition);
  if (p.stage) parts.push(`stage ${p.stage}`);
  if (p.location) parts.push(p.location);
  return parts.join(" · ");
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function relTime(iso: string): string {
  try {
    const ms = Date.now() - new Date(iso).getTime();
    if (ms < 60_000) return "just now";
    const mins = Math.floor(ms / 60_000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  } catch {
    return iso;
  }
}

// ---------- New watch form -------------------------------------------------

type NewWatchPayload = {
  name: string;
  profile: WatchProfile;
  search: WatchSearch;
};

function NewWatchForm({
  onSubmit,
  submitting,
}: {
  onSubmit: (p: NewWatchPayload) => void;
  submitting: boolean;
}) {
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [sex, setSex] = useState("");
  const [condition, setCondition] = useState("");
  const [stage, setStage] = useState("");
  const [location, setLocation] = useState("");
  const [searchCondition, setSearchCondition] = useState("");
  const [limit, setLimit] = useState("5");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !condition.trim()) return;
    onSubmit({
      name: name.trim(),
      profile: {
        age: age ? Number(age) : null,
        sex: sex || null,
        condition: condition.trim(),
        stage: stage || null,
        location: location || null,
      },
      search: {
        condition: searchCondition.trim() || condition.trim(),
        limit: Number(limit) || 5,
      },
    });
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-3 gap-3">
      <FormField label="Watch name *" className="md:col-span-3">
        <input
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Aunt Helen — NSCLC"
          className="form-input"
        />
      </FormField>
      <FormField label="Condition *">
        <input
          required
          value={condition}
          onChange={(e) => setCondition(e.target.value)}
          placeholder="non-small cell lung cancer"
          className="form-input"
        />
      </FormField>
      <FormField label="Age">
        <input
          type="number"
          value={age}
          onChange={(e) => setAge(e.target.value)}
          className="form-input"
        />
      </FormField>
      <FormField label="Sex">
        <select value={sex} onChange={(e) => setSex(e.target.value)} className="form-input">
          <option value="">—</option>
          <option value="female">female</option>
          <option value="male">male</option>
        </select>
      </FormField>
      <FormField label="Stage">
        <input
          value={stage}
          onChange={(e) => setStage(e.target.value)}
          placeholder="3"
          className="form-input"
        />
      </FormField>
      <FormField label="Location">
        <input
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="Cleveland, OH"
          className="form-input"
        />
      </FormField>
      <FormField label="Search override (optional)">
        <input
          value={searchCondition}
          onChange={(e) => setSearchCondition(e.target.value)}
          placeholder="defaults to condition"
          className="form-input"
        />
      </FormField>
      <FormField label="Max trials">
        <input
          type="number"
          min="1"
          max="20"
          value={limit}
          onChange={(e) => setLimit(e.target.value)}
          className="form-input"
        />
      </FormField>
      <div className="md:col-span-3 flex justify-end pt-1">
        <button
          type="submit"
          disabled={submitting}
          className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-md shadow-sm disabled:opacity-50"
        >
          {submitting ? "Creating…" : "Create watch"}
        </button>
      </div>
    </form>
  );
}

function FormField({
  label,
  children,
  className = "",
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={"block " + className}>
      <span className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
        {label}
      </span>
      {children}
    </label>
  );
}

// ---------- Import trial form ---------------------------------------------

type NewTrialPayload = {
  title: string;
  condition: string;
  phase?: string;
  location?: string;
  age_min?: number;
  age_max?: number;
  sex?: string;
};

function NewTrialForm({
  onSubmit,
  submitting,
}: {
  onSubmit: (p: NewTrialPayload) => void;
  submitting: boolean;
}) {
  const [title, setTitle] = useState("");
  const [condition, setCondition] = useState("");
  const [phase, setPhase] = useState("Phase 2");
  const [location, setLocation] = useState("");
  const [ageMin, setAgeMin] = useState("18");
  const [ageMax, setAgeMax] = useState("80");
  const [sex, setSex] = useState("all");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !condition.trim()) return;
    onSubmit({
      title: title.trim(),
      condition: condition.trim(),
      phase: phase || undefined,
      location: location || undefined,
      age_min: ageMin ? Number(ageMin) : undefined,
      age_max: ageMax ? Number(ageMax) : undefined,
      sex: sex || undefined,
    });
  }

  function quickFill() {
    setTitle("Phase 3 EGFR-TKI + Anti-PD-L1 in NSCLC");
    setCondition("Non-Small Cell Lung Cancer");
    setPhase("Phase 3");
    setLocation("Cleveland, OH");
    setAgeMin("50");
    setAgeMax("75");
    setSex("all");
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-3 gap-3">
      <div className="md:col-span-3 flex items-center justify-between">
        <p className="text-xs text-slate-600">
          Inject a synthetic trial. The watcher's next tick will pick it up via{" "}
          <code className="bg-white px-1 rounded">search_trials</code> and emit a NEW pill on
          any matching watch.
        </p>
        <button
          type="button"
          onClick={quickFill}
          className="text-[11px] text-indigo-700 hover:underline"
        >
          fill with NSCLC example
        </button>
      </div>
      <FormField label="Title *" className="md:col-span-2">
        <input
          required
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Phase 3 EGFR-TKI + Anti-PD-L1 in NSCLC"
          className="form-input"
        />
      </FormField>
      <FormField label="Phase">
        <select
          value={phase}
          onChange={(e) => setPhase(e.target.value)}
          className="form-input"
        >
          <option>Phase 1</option>
          <option>Phase 2</option>
          <option>Phase 3</option>
          <option>Phase 4</option>
        </select>
      </FormField>
      <FormField label="Condition *">
        <input
          required
          value={condition}
          onChange={(e) => setCondition(e.target.value)}
          placeholder="Non-Small Cell Lung Cancer"
          className="form-input"
        />
      </FormField>
      <FormField label="Location">
        <input
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="Cleveland, OH"
          className="form-input"
        />
      </FormField>
      <FormField label="Sex">
        <select value={sex} onChange={(e) => setSex(e.target.value)} className="form-input">
          <option value="all">all</option>
          <option value="female">female</option>
          <option value="male">male</option>
        </select>
      </FormField>
      <FormField label="Age min">
        <input
          type="number"
          min="0"
          max="120"
          value={ageMin}
          onChange={(e) => setAgeMin(e.target.value)}
          className="form-input"
        />
      </FormField>
      <FormField label="Age max">
        <input
          type="number"
          min="0"
          max="120"
          value={ageMax}
          onChange={(e) => setAgeMax(e.target.value)}
          className="form-input"
        />
      </FormField>
      <div className="md:col-span-3 flex justify-end pt-1">
        <button
          type="submit"
          disabled={submitting}
          className="bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium px-4 py-2 rounded-md shadow-sm disabled:opacity-50"
        >
          {submitting ? "Importing…" : "Import trial"}
        </button>
      </div>
    </form>
  );
}
