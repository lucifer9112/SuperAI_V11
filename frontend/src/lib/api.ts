import axios, { AxiosInstance } from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_BASE_URL = (process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000")
  .replace("https://", "wss://")
  .replace("http://", "ws://");

const AUDIO_EXTENSIONS: Record<string, string> = {
  "audio/mpeg": "mp3",
  "audio/mp3": "mp3",
  "audio/mp4": "m4a",
  "audio/ogg": "ogg",
  "audio/wav": "wav",
  "audio/wave": "wav",
  "audio/webm": "webm",
  "audio/x-wav": "wav",
};

export interface APIResponse<T = unknown> {
  success: boolean;
  request_id: string;
  data: T;
  error?: string;
  meta?: Record<string, unknown>;
}

export interface ChatRequest {
  prompt: string;
  session_id?: string;
  temperature?: number;
  max_tokens?: number;
  force_model?: string;
  force_task?: string;
  stream?: boolean;
}

export interface ChatResponse {
  answer: string;
  session_id: string;
  task_type: string;
  model_used: string;
  tokens_used: number;
  latency_ms: number;
  response_id: string;
}

export interface STTResult {
  transcript: string;
  language?: string;
  confidence?: number;
}

export interface AgentRunRequest {
  goal: string;
  session_id?: string;
  autonomy_level?: 1 | 2 | 3;
  max_iterations?: number;
  tools?: string[];
  share_context?: boolean;
}

export interface AgentStep {
  step: number;
  action: string;
  thought: string;
  result: string;
  success: boolean;
}

export interface AgentRunResponse {
  agent_id: string;
  goal: string;
  session_id: string;
  status: string;
  steps: AgentStep[];
  final_answer: string | null;
  iterations: number;
}

export interface MemoryEntry {
  id: string;
  content: string;
  score: number;
  priority: number;
  timestamp: string;
  source: string;
  decay: number;
}

export interface SystemStatus {
  status: string;
  version: string;
  environment: string;
  uptime_s: number;
  cpu_pct: number;
  ram_pct: number;
  gpu_info: string | null;
  models_loaded: string[];
  requests_total: number;
  avg_latency_ms: number;
  feedback_count: number;
}

export interface FeedbackStats {
  total_7d: number;
  avg_score: number;
  negative_7d: number;
  positive_7d: number;
  total_all: number;
}

function makeClient(): AxiosInstance {
  const client = axios.create({
    baseURL: API_BASE_URL,
    timeout: 120_000,
    headers: { "Content-Type": "application/json" },
  });

  client.interceptors.response.use(
    (response) => {
      if (response.config.responseType === "blob" || response.config.responseType === "arraybuffer") {
        return response;
      }

      if (response.data && typeof response.data === "object" && "success" in response.data) {
        if (!response.data.success) {
          throw new Error(response.data.error || "API error");
        }
      }

      return response;
    },
    (error) => {
      const payload = error.response?.data;
      const detail = Array.isArray(payload?.detail)
        ? payload.detail.map((item: { msg?: string }) => item?.msg || "Validation error").join(", ")
        : payload?.detail;
      throw new Error(detail || payload?.error || payload?.message || error.message || "Network error");
    },
  );

  return client;
}

function audioFilenameForBlob(blob: Blob): string {
  const mimeType = (blob.type || "audio/webm").split(";")[0].trim().toLowerCase();
  const extension = AUDIO_EXTENSIONS[mimeType] || "webm";
  return `recording.${extension}`;
}

const http = makeClient();

export const chatAPI = {
  send: async (request: ChatRequest): Promise<ChatResponse> =>
    (await http.post<APIResponse<ChatResponse>>("/api/v1/chat/", request)).data.data,
  history: async (sessionId: string, limit = 20) =>
    (await http.get("/api/v1/chat/history", { params: { session_id: sessionId, limit } })).data.data,
  clear: async (sessionId: string) =>
    http.delete("/api/v1/chat/history", { params: { session_id: sessionId } }),
};

export const agentAPI = {
  run: async (request: AgentRunRequest): Promise<AgentRunResponse> =>
    (await http.post<APIResponse<AgentRunResponse>>("/api/v1/agents/run", request)).data.data,
  status: async (agentId: string) => (await http.get(`/api/v1/agents/${agentId}`)).data.data,
  cancel: async (agentId: string) => http.delete(`/api/v1/agents/${agentId}`),
};

export const memoryAPI = {
  search: async (query: string, sessionId?: string, topK = 5) =>
    (await http.post("/api/v1/memory/search", { query, session_id: sessionId, top_k: topK })).data.data,
  store: async (content: string, sessionId?: string, tags: string[] = [], priority = 1.0) =>
    (await http.post("/api/v1/memory/store", { content, session_id: sessionId, tags, priority })).data.data,
  reinforce: async (id: string, boost = 0.1) =>
    (await http.post(`/api/v1/memory/${id}/reinforce`, null, { params: { boost } })).data.data,
};

export const systemAPI = {
  status: async (): Promise<SystemStatus> =>
    (await http.get<APIResponse<SystemStatus>>("/api/v1/system/status")).data.data,
  config: async () => (await http.get("/api/v1/system/config")).data.data,
};

export const feedbackAPI = {
  submit: async (responseId: string, score: number, comment = "", sessionId?: string) =>
    (await http.post("/api/v1/feedback/", { response_id: responseId, score, comment, session_id: sessionId })).data.data,
  stats: async (): Promise<FeedbackStats> =>
    (await http.get("/api/v1/feedback/stats")).data.data,
};

export const voiceAPI = {
  tts: async (text: string): Promise<Blob> =>
    (await http.post("/api/v1/voice/tts", { text }, { responseType: "blob" })).data as Blob,
  stt: async (blob: Blob): Promise<STTResult> => {
    const formData = new FormData();
    formData.append("audio", blob, audioFilenameForBlob(blob));
    return (await axios.post(`${API_BASE_URL}/api/v1/voice/stt`, formData)).data.data;
  },
  status: async () => (await http.get("/api/v1/voice/status")).data.data,
};

export type WSMessage =
  | { type: "token"; data: string }
  | { type: "done"; data: ChatResponse }
  | { type: "error"; data: string }
  | { type: "pong" };

export class SuperAISocket {
  private ws: WebSocket | null = null;
  private handlers = new Map<string, ((message: WSMessage) => void)[]>();

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(`${WS_BASE_URL}/ws/chat`);
      this.ws.onopen = () => resolve();
      this.ws.onerror = (event) => reject(event);
      this.ws.onmessage = (event) => {
        try {
          const message: WSMessage = JSON.parse(event.data);
          this.emit(message.type, message);
        } catch {
          // Ignore malformed frames and keep the socket alive.
        }
      };
    });
  }

  send(request: ChatRequest): void {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      throw new Error("WS not connected");
    }
    this.ws.send(JSON.stringify({ type: "chat", payload: request }));
  }

  on(event: string, handler: (message: WSMessage) => void): void {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, []);
    }
    this.handlers.get(event)!.push(handler);
  }

  off(event: string, handler: (message: WSMessage) => void): void {
    this.handlers.set(event, (this.handlers.get(event) || []).filter((candidate) => candidate !== handler));
  }

  disconnect(): void {
    this.ws?.close();
    this.ws = null;
  }

  private emit(event: string, message: WSMessage): void {
    (this.handlers.get(event) || []).forEach((handler) => handler(message));
    (this.handlers.get("*") || []).forEach((handler) => handler(message));
  }
}
