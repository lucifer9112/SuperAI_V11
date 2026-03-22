/**
 * SuperAI V9 — frontend/src/lib/store.ts
 * Global state with Zustand. Chat + Agents + Settings + System.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ChatResponse, AgentRunResponse, SystemStatus, FeedbackStats } from "./api";

export type Role = "user" | "assistant" | "system";

export interface Message {
  id:          string;
  role:        Role;
  content:     string;
  timestamp:   number;
  task_type?:  string;
  model?:      string;
  latency_ms?: number;
  response_id?: string;
  isStreaming?: boolean;
  feedback?:   number;   // V9: user rating 1-5
}

// ── Chat ──────────────────────────────────────────────────────────
interface ChatStore {
  messages:    Message[];
  sessionId:   string | null;
  isLoading:   boolean;
  isStreaming:  boolean;
  addMessage:   (m: Omit<Message, "id" | "timestamp">) => string;
  updateMessage:(id: string, patch: Partial<Message>) => void;
  appendToken:  (id: string, token: string) => void;
  setFeedback:  (id: string, score: number) => void;
  setLoading:   (v: boolean) => void;
  setStreaming:  (v: boolean) => void;
  setSessionId: (id: string) => void;
  clearMessages:() => void;
}

export const useChatStore = create<ChatStore>()((set) => ({
  messages:   [],
  sessionId:  null,
  isLoading:  false,
  isStreaming: false,

  addMessage: (m) => {
    const id = crypto.randomUUID();
    set(s => ({ messages: [...s.messages, { ...m, id, timestamp: Date.now() }] }));
    return id;
  },
  updateMessage: (id, patch) =>
    set(s => ({ messages: s.messages.map(m => m.id === id ? { ...m, ...patch } : m) })),
  appendToken: (id, token) =>
    set(s => ({ messages: s.messages.map(m => m.id === id ? { ...m, content: m.content + token } : m) })),
  setFeedback: (id, score) =>
    set(s => ({ messages: s.messages.map(m => m.id === id ? { ...m, feedback: score } : m) })),
  setLoading:   (v) => set({ isLoading: v }),
  setStreaming:  (v) => set({ isStreaming: v }),
  setSessionId: (id) => set({ sessionId: id }),
  clearMessages:() => set({ messages: [], sessionId: null }),
}));

// ── Agents ────────────────────────────────────────────────────────
interface AgentStore {
  runs:     AgentRunResponse[];
  activeId: string | null;
  addRun:   (r: AgentRunResponse) => void;
  setActive:(id: string | null) => void;
}

export const useAgentStore = create<AgentStore>()((set) => ({
  runs:     [],
  activeId: null,
  addRun:   (r) => set(s => ({ runs: [r, ...s.runs].slice(0, 30) })),
  setActive:(id) => set({ activeId: id }),
}));

// ── Settings (persisted) ──────────────────────────────────────────
interface SettingsStore {
  theme:            "dark" | "light";
  streamingEnabled: boolean;
  voiceEnabled:     boolean;
  soundFx:          boolean;
  temperature:      number;
  maxTokens:        number;
  model:            string;
  setTheme:         (t: "dark" | "light") => void;
  setStreaming:      (v: boolean) => void;
  setVoice:         (v: boolean) => void;
  setSoundFx:       (v: boolean) => void;
  setTemperature:   (v: number) => void;
  setMaxTokens:     (v: number) => void;
  setModel:         (m: string) => void;
}

const SETTINGS_STORAGE_KEY = "superai-v11-settings";
const LEGACY_SETTINGS_STORAGE_KEY = "superai-v9-settings";

function readLegacySettings(): Partial<SettingsStore> {
  if (typeof window === "undefined") {
    return {};
  }

  try {
    const raw = window.localStorage.getItem(LEGACY_SETTINGS_STORAGE_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw) as unknown;
    let state: Partial<SettingsStore> = {};
    if (parsed && typeof parsed === "object" && "state" in parsed) {
      state = ((parsed as { state?: Partial<SettingsStore> }).state ?? {}) as Partial<SettingsStore>;
    } else if (parsed && typeof parsed === "object") {
      state = parsed as Partial<SettingsStore>;
    }
    window.localStorage.removeItem(LEGACY_SETTINGS_STORAGE_KEY);
    return state;
  } catch {
    return {};
  }
}

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      theme:            "dark",
      streamingEnabled: true,
      voiceEnabled:     false,
      soundFx:          true,
      temperature:      0.7,
      maxTokens:        512,
      model:            "",
      ...readLegacySettings(),
      setTheme:         (t) => set({ theme: t }),
      setStreaming:      (v) => set({ streamingEnabled: v }),
      setVoice:         (v) => set({ voiceEnabled: v }),
      setSoundFx:       (v) => set({ soundFx: v }),
      setTemperature:   (v) => set({ temperature: v }),
      setMaxTokens:     (v) => set({ maxTokens: v }),
      setModel:         (m) => set({ model: m }),
    }),
    { name: SETTINGS_STORAGE_KEY }
  )
);

// ── System ────────────────────────────────────────────────────────
interface SystemStore {
  status:      SystemStatus | null;
  fbStats:     FeedbackStats | null;
  setStatus:   (s: SystemStatus) => void;
  setFbStats:  (s: FeedbackStats) => void;
}

export const useSystemStore = create<SystemStore>()((set) => ({
  status:     null,
  fbStats:    null,
  setStatus:  (s) => set({ status: s }),
  setFbStats: (s) => set({ fbStats: s }),
}));

// ── Voice UI ──────────────────────────────────────────────────────
interface VoiceStore {
  isRecording:    boolean;
  isPlaying:      boolean;
  amplitude:      number;
  transcript:     string;
  setRecording:   (v: boolean) => void;
  setPlaying:     (v: boolean) => void;
  setAmplitude:   (v: number) => void;
  setTranscript:  (t: string) => void;
}

export const useVoiceStore = create<VoiceStore>()((set) => ({
  isRecording:  false,
  isPlaying:    false,
  amplitude:    0,
  transcript:   "",
  setRecording: (v) => set({ isRecording: v }),
  setPlaying:   (v) => set({ isPlaying: v }),
  setAmplitude: (v) => set({ amplitude: v }),
  setTranscript:(t) => set({ transcript: t }),
}));
