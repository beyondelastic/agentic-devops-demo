import { useState, useRef, useEffect, useMemo } from "react";

type Profile = {
  id: string;
  name: string;
  emoji: string;
  age: string;
  sex: "male" | "female";
  primary_condition: string;
  location: string;
  highlights: string[];
  suggestions: string[];
};

type Message = {
  role: "user" | "assistant";
  content: string;
};

const PROFILES: Profile[] = [
  {
    id: "maria",
    name: "Maria R.",
    emoji: "🫁",
    age: "55",
    sex: "female",
    primary_condition: "non-small cell lung cancer",
    location: "Boston",
    highlights: ["EGFR L858R mutation", "ECOG 1", "No prior TKI"],
    suggestions: [
      "Find phase 2 or 3 trials I might qualify for.",
      "Which trials accept EGFR-mutant NSCLC patients?",
      "Are there options near Boston?",
    ],
  },
  {
    id: "james",
    name: "James O.",
    emoji: "🩸",
    age: "47",
    sex: "male",
    primary_condition: "relapsed diffuse large B-cell lymphoma",
    location: "Houston",
    highlights: ["3 prior lines", "LVEF 55%", "No CNS disease"],
    suggestions: [
      "Am I eligible for any CAR-T trials?",
      "What inclusion criteria should I check?",
      "List trials in Texas.",
    ],
  },
  {
    id: "linda",
    name: "Linda P.",
    emoji: "🩺",
    age: "62",
    sex: "female",
    primary_condition: "type 2 diabetes mellitus",
    location: "Chicago",
    highlights: ["HbA1c 8.4%", "BMI 31", "On metformin"],
    suggestions: [
      "Show me phase 3 diabetes trials.",
      "Which trials allow metformin background therapy?",
      "Anything for combination GLP-1 + SGLT2?",
    ],
  },
  {
    id: "robert",
    name: "Robert K.",
    emoji: "🧠",
    age: "71",
    sex: "male",
    primary_condition: "early Alzheimer's disease",
    location: "San Francisco",
    highlights: ["MMSE 26", "Amyloid PET +", "Study partner ready"],
    suggestions: [
      "Find anti-amyloid trials I could enroll in.",
      "What disqualifies a patient from these trials?",
      "Any options on the West Coast?",
    ],
  },
  {
    id: "sophia",
    name: "Sophia M.",
    emoji: "🎗️",
    age: "38",
    sex: "female",
    primary_condition: "metastatic melanoma",
    location: "New York",
    highlights: ["Stage IV", "Progressed on anti-PD-1", "Cutaneous"],
    suggestions: [
      "Trials for anti-PD-1 refractory melanoma?",
      "Compare bispecific vs CTLA-4 options.",
      "Any phase 2 trials near NYC?",
    ],
  },
  {
    id: "aisha",
    name: "Aisha N.",
    emoji: "💗",
    age: "28",
    sex: "female",
    primary_condition: "postpartum depression",
    location: "Seattle",
    highlights: ["EPDS 16", "6 months postpartum", "No SI"],
    suggestions: [
      "Any digital CBT trials I could join?",
      "What are the exclusion criteria?",
      "Trials in the Pacific Northwest?",
    ],
  },
];

export default function App() {
  const [profileId, setProfileId] = useState<string>(PROFILES[0].id);
  const [overrides, setOverrides] = useState<Record<string, Partial<Profile>>>({});
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const profile = useMemo<Profile>(() => {
    const base = PROFILES.find((p) => p.id === profileId)!;
    return { ...base, ...(overrides[profileId] ?? {}) };
  }, [profileId, overrides]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  function newChat() {
    if (streaming) return;
    setMessages([]);
    setInput("");
  }

  function selectProfile(id: string) {
    if (streaming) return;
    setProfileId(id);
    setMessages([]);
    setInput("");
  }

  function patchProfile(patch: Partial<Profile>) {
    setOverrides((o) => ({ ...o, [profileId]: { ...(o[profileId] ?? {}), ...patch } }));
  }

  async function sendText(text: string) {
    if (!text.trim() || streaming) return;

    const userMsg = `Patient: ${profile.name}, age ${profile.age}, sex ${profile.sex}, condition "${profile.primary_condition}", location "${profile.location}". ${text.trim()}`;
    setMessages((m) => [
      ...m,
      { role: "user", content: text.trim() },
      { role: "assistant", content: "" },
    ]);
    setInput("");
    setStreaming(true);

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMsg }),
      });
      if (!resp.body) throw new Error("No response body");

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        setMessages((m) => {
          const next = [...m];
          next[next.length - 1] = {
            ...next[next.length - 1],
            content: next[next.length - 1].content + chunk,
          };
          return next;
        });
      }
    } catch (err) {
      setMessages((m) => {
        const next = [...m];
        next[next.length - 1] = {
          role: "assistant",
          content: `**Error:** ${(err as Error).message}`,
        };
        return next;
      });
    } finally {
      setStreaming(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <header className="bg-gradient-to-r from-indigo-700 via-blue-700 to-sky-600 text-white px-6 py-4 shadow-lg">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="bg-white/15 rounded-xl w-10 h-10 flex items-center justify-center text-2xl backdrop-blur">
              🧬
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight">Clinical Trial Matcher</h1>
              <p className="text-xs opacity-80">
                Powered by Microsoft Foundry agents · Azure App Platform
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <StatusPill streaming={streaming} />
            <span className="hidden md:inline opacity-70">Synthetic data only</span>
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-80 bg-white border-r flex flex-col">
          <div className="p-4 border-b">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Patient personas
            </h2>
            <p className="text-[11px] text-slate-400 mt-1">
              Select a synthetic patient to seed the agent.
            </p>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {PROFILES.map((p) => {
              const active = p.id === profileId;
              return (
                <button
                  key={p.id}
                  onClick={() => selectProfile(p.id)}
                  disabled={streaming}
                  className={
                    "w-full text-left px-3 py-2 rounded-lg transition flex items-start gap-3 " +
                    (active
                      ? "bg-indigo-50 ring-1 ring-indigo-300 shadow-sm"
                      : "hover:bg-slate-50")
                  }
                >
                  <span className="text-2xl leading-none mt-0.5">{p.emoji}</span>
                  <span className="flex-1 min-w-0">
                    <span
                      className={
                        "block text-sm font-semibold " +
                        (active ? "text-indigo-700" : "text-slate-800")
                      }
                    >
                      {p.name}
                    </span>
                    <span className="block text-[11px] text-slate-500 truncate">
                      {p.age} · {p.sex} · {p.location}
                    </span>
                    <span className="block text-xs text-slate-600 truncate mt-0.5">
                      {p.primary_condition}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>

          <div className="border-t p-4 bg-slate-50/50">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
              Profile details
            </h3>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Age">
                <input
                  className="w-full border border-slate-200 rounded px-2 py-1 text-sm bg-white"
                  value={profile.age}
                  onChange={(e) => patchProfile({ age: e.target.value })}
                />
              </Field>
              <Field label="Sex">
                <select
                  className="w-full border border-slate-200 rounded px-2 py-1 text-sm bg-white"
                  value={profile.sex}
                  onChange={(e) => patchProfile({ sex: e.target.value as "male" | "female" })}
                >
                  <option value="female">female</option>
                  <option value="male">male</option>
                </select>
              </Field>
            </div>
            <Field label="Condition">
              <input
                className="w-full border border-slate-200 rounded px-2 py-1 text-sm bg-white"
                value={profile.primary_condition}
                onChange={(e) => patchProfile({ primary_condition: e.target.value })}
              />
            </Field>
            <Field label="Location">
              <input
                className="w-full border border-slate-200 rounded px-2 py-1 text-sm bg-white"
                value={profile.location}
                onChange={(e) => patchProfile({ location: e.target.value })}
              />
            </Field>
            <div className="mt-2 flex flex-wrap gap-1">
              {profile.highlights.map((h) => (
                <span
                  key={h}
                  className="text-[10px] bg-indigo-50 text-indigo-700 border border-indigo-100 rounded-full px-2 py-0.5"
                >
                  {h}
                </span>
              ))}
            </div>
          </div>
        </aside>

        <main className="flex flex-col flex-1 min-w-0">
          <div className="px-6 py-3 border-b bg-white flex items-center justify-between gap-2">
            <div className="flex items-center gap-3 min-w-0">
              <div className="text-2xl">{profile.emoji}</div>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-slate-800 truncate">
                  {profile.name} <span className="text-slate-400 font-normal">·</span>{" "}
                  <span className="text-slate-600 font-normal">{profile.primary_condition}</span>
                </div>
                <div className="text-xs text-slate-500 truncate">
                  {profile.age} y/o {profile.sex} · {profile.location}
                </div>
              </div>
            </div>
            <button
              onClick={newChat}
              disabled={streaming}
              className="text-xs text-slate-600 hover:text-slate-900 border border-slate-200 hover:border-slate-300 rounded-md px-3 py-1.5 disabled:opacity-50"
            >
              + New chat
            </button>
          </div>

          <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
            {messages.length === 0 && <EmptyState profile={profile} onPick={sendText} />}
            {messages.map((m, i) => (
              <ChatBubble
                key={i}
                role={m.role}
                content={m.content}
                streaming={streaming && i === messages.length - 1 && m.role === "assistant"}
              />
            ))}
          </div>

          <div className="border-t bg-white px-6 py-4">
            {messages.length > 0 && !streaming && (
              <div className="flex flex-wrap gap-2 mb-3">
                {profile.suggestions.slice(0, 3).map((s) => (
                  <button
                    key={s}
                    onClick={() => sendText(s)}
                    className="text-xs text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-100 rounded-full px-3 py-1"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
            <div className="flex gap-2">
              <input
                className="flex-1 border border-slate-200 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 outline-none rounded-lg px-4 py-2.5 text-sm"
                placeholder={`Ask about trials for ${profile.name}…`}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") sendText(input);
                }}
                disabled={streaming}
              />
              <button
                onClick={() => sendText(input)}
                disabled={streaming || !input.trim()}
                className="bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-500 hover:to-blue-500 text-white px-5 py-2.5 rounded-lg text-sm font-medium shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {streaming ? "…" : "Send"}
              </button>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

function StatusPill({ streaming }: { streaming: boolean }) {
  return (
    <span className="flex items-center gap-1.5 bg-white/15 backdrop-blur border border-white/20 rounded-full px-3 py-1">
      <span
        className={
          "w-2 h-2 rounded-full " +
          (streaming ? "bg-amber-300 animate-pulse" : "bg-emerald-300")
        }
      />
      {streaming ? "Agent streaming" : "Agent ready"}
    </span>
  );
}

function EmptyState({ profile, onPick }: { profile: Profile; onPick: (s: string) => void }) {
  return (
    <div className="max-w-2xl mx-auto pt-8">
      <div className="bg-gradient-to-br from-indigo-50 via-white to-sky-50 border border-indigo-100 rounded-2xl p-6 shadow-sm">
        <div className="text-3xl mb-2">{profile.emoji}</div>
        <h2 className="text-lg font-semibold text-slate-800">
          Ask the agent about trials for {profile.name}
        </h2>
        <p className="text-sm text-slate-600 mt-1">
          The Foundry agent uses an OpenAPI tool to query our synthetic trial dataset and
          will tailor results to this patient's profile.
        </p>
        <div className="mt-4 grid sm:grid-cols-3 gap-2">
          {profile.suggestions.map((s) => (
            <button
              key={s}
              onClick={() => onPick(s)}
              className="text-left text-sm bg-white border border-slate-200 hover:border-indigo-300 hover:shadow-sm rounded-lg px-3 py-2 transition"
            >
              <span className="block text-indigo-600 text-[11px] uppercase tracking-wide font-semibold mb-1">
                Try
              </span>
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function ChatBubble({
  role,
  content,
  streaming,
}: {
  role: "user" | "assistant";
  content: string;
  streaming: boolean;
}) {
  const isUser = role === "user";
  return (
    <div className={"flex gap-3 " + (isUser ? "flex-row-reverse" : "")}>
      <div
        className={
          "w-8 h-8 rounded-full flex items-center justify-center text-sm shrink-0 " +
          (isUser
            ? "bg-slate-200 text-slate-700"
            : "bg-gradient-to-br from-indigo-500 to-blue-600 text-white")
        }
      >
        {isUser ? "🧑" : "🤖"}
      </div>
      <div
        className={
          "max-w-[80%] rounded-2xl px-4 py-3 text-sm shadow-sm " +
          (isUser
            ? "bg-indigo-600 text-white rounded-tr-sm"
            : "bg-white border border-slate-200 text-slate-800 rounded-tl-sm")
        }
      >
        {content ? (
          isUser ? (
            <div className="whitespace-pre-wrap">{content}</div>
          ) : (
            <Markdown text={content} />
          )
        ) : streaming ? (
          <TypingDots />
        ) : null}
      </div>
    </div>
  );
}

function TypingDots() {
  return (
    <div className="flex items-center gap-1 py-1">
      <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
      <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
      <span className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" />
    </div>
  );
}

/** Tiny markdown renderer: headings, bold, inline code, bullet/numbered lists, paragraphs. */
function Markdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const blocks: React.ReactNode[] = [];
  let listItems: { ordered: boolean; items: string[] } | null = null;

  const flushList = () => {
    if (!listItems) return;
    const ordered = listItems.ordered;
    const items = listItems.items;
    if (ordered) {
      blocks.push(
        <ol key={blocks.length} className="list-decimal pl-5 space-y-1 my-2">
          {items.map((it, i) => (
            <li key={i}>{renderInline(it)}</li>
          ))}
        </ol>,
      );
    } else {
      blocks.push(
        <ul key={blocks.length} className="list-disc pl-5 space-y-1 my-2">
          {items.map((it, i) => (
            <li key={i}>{renderInline(it)}</li>
          ))}
        </ul>,
      );
    }
    listItems = null;
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    const ulMatch = /^\s*[-*]\s+(.*)$/.exec(line);
    const olMatch = /^\s*\d+\.\s+(.*)$/.exec(line);
    const hMatch = /^(#{1,3})\s+(.*)$/.exec(line);

    if (ulMatch) {
      if (!listItems || listItems.ordered) {
        flushList();
        listItems = { ordered: false, items: [] };
      }
      listItems.items.push(ulMatch[1]);
    } else if (olMatch) {
      if (!listItems || !listItems.ordered) {
        flushList();
        listItems = { ordered: true, items: [] };
      }
      listItems.items.push(olMatch[1]);
    } else if (hMatch) {
      flushList();
      const level = hMatch[1].length;
      const cls =
        level === 1
          ? "text-base font-semibold mt-2 mb-1"
          : level === 2
            ? "text-sm font-semibold mt-2 mb-1"
            : "text-sm font-semibold text-slate-700 mt-2 mb-1";
      blocks.push(
        <div key={blocks.length} className={cls}>
          {renderInline(hMatch[2])}
        </div>,
      );
    } else if (line.trim() === "") {
      flushList();
    } else {
      flushList();
      blocks.push(
        <p key={blocks.length} className="my-1 leading-relaxed">
          {renderInline(line)}
        </p>,
      );
    }
  }
  flushList();
  return <div>{blocks}</div>;
}

function renderInline(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) {
      parts.push(
        <strong key={key++} className="font-semibold">
          {tok.slice(2, -2)}
        </strong>,
      );
    } else {
      parts.push(
        <code
          key={key++}
          className="bg-slate-100 text-slate-800 rounded px-1 py-0.5 text-[12px]"
        >
          {tok.slice(1, -1)}
        </code>,
      );
    }
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block mb-2 text-xs">
      <span className="block mb-1 font-medium text-slate-600">{label}</span>
      {children}
    </label>
  );
}
