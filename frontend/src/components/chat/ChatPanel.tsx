"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Mic, MicOff, Send, Trash2, Zap } from "lucide-react";
import toast from "react-hot-toast";

import { SuperAISocket, chatAPI, type ChatRequest, type ChatResponse, type WSMessage, voiceAPI } from "@/lib/api";
import { useChatStore, useSettingsStore, useVoiceStore } from "@/lib/store";
import { cn } from "@/lib/utils";

import { MessageBubble } from "./MessageBubble";

export function ChatPanel() {
  const {
    messages,
    sessionId,
    isLoading,
    isStreaming,
    addMessage,
    updateMessage,
    appendToken,
    setLoading,
    setStreaming,
    setSessionId,
    clearMessages,
  } = useChatStore();
  const { streamingEnabled, temperature, maxTokens, model } = useSettingsStore();
  const { isRecording, setRecording, setAmplitude, setTranscript } = useVoiceStore();

  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const wsRef = useRef<SuperAISocket | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
    }
  }, [input]);

  useEffect(() => {
    return () => {
      wsRef.current?.disconnect();
    };
  }, []);

  const buildRequest = useCallback(
    (prompt: string): ChatRequest => ({
      prompt,
      session_id: sessionId || undefined,
      temperature,
      max_tokens: maxTokens,
      force_model: model || undefined,
    }),
    [maxTokens, model, sessionId, temperature],
  );

  const sendREST = useCallback(
    async (request: ChatRequest, assistantId: string) => {
      const response: ChatResponse = await chatAPI.send(request);
      if (!sessionId) {
        setSessionId(response.session_id);
      }
      updateMessage(assistantId, {
        content: response.answer,
        task_type: response.task_type,
        model: response.model_used,
        latency_ms: response.latency_ms,
        response_id: response.response_id,
        isStreaming: false,
      });
    },
    [sessionId, setSessionId, updateMessage],
  );

  const streamWS = useCallback(
    async (request: ChatRequest, assistantId: string) => {
      if (!wsRef.current) {
        wsRef.current = new SuperAISocket();
        await wsRef.current.connect();
      }

      const socket = wsRef.current;
      setStreaming(true);

      return new Promise<void>((resolve, reject) => {
        const onToken = (message: WSMessage) => {
          if (message.type === "token") {
            appendToken(assistantId, message.data);
          }
        };
        const onDone = (message: WSMessage) => {
          if (message.type !== "done") {
            return;
          }
          if (!sessionId) {
            setSessionId(message.data.session_id);
          }
          updateMessage(assistantId, {
            task_type: message.data.task_type,
            model: message.data.model_used,
            latency_ms: message.data.latency_ms,
            response_id: message.data.response_id,
            isStreaming: false,
          });
          socket.off("token", onToken);
          socket.off("done", onDone);
          socket.off("error", onError);
          resolve();
        };
        const onError = (message: WSMessage) => {
          if (message.type !== "error") {
            return;
          }
          socket.off("token", onToken);
          socket.off("done", onDone);
          socket.off("error", onError);
          reject(new Error(message.data));
        };

        socket.on("token", onToken);
        socket.on("done", onDone);
        socket.on("error", onError);
        socket.send(request);
      });
    },
    [appendToken, sessionId, setSessionId, setStreaming, updateMessage],
  );

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isLoading) {
        return;
      }

      const request = buildRequest(text);
      setInput("");
      addMessage({ role: "user", content: text });
      const assistantId = addMessage({ role: "assistant", content: "", isStreaming: streamingEnabled });
      setLoading(true);

      try {
        if (streamingEnabled) {
          await streamWS(request, assistantId);
        } else {
          await sendREST(request, assistantId);
        }
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "Error";
        updateMessage(assistantId, { content: `Warning: ${message}`, isStreaming: false });
        toast.error(message);
      } finally {
        setLoading(false);
        setStreaming(false);
      }
    },
    [
      addMessage,
      buildRequest,
      isLoading,
      sendREST,
      setLoading,
      setStreaming,
      streamWS,
      streamingEnabled,
      updateMessage,
    ],
  );

  const toggleVoice = async () => {
    if (isRecording) {
      mediaRef.current?.stop();
      setRecording(false);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);

      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };
      recorder.onstop = async () => {
        const mimeType = recorder.mimeType || chunksRef.current[0]?.type || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: mimeType });
        stream.getTracks().forEach((track) => track.stop());
        try {
          const { transcript } = await voiceAPI.stt(blob);
          if (transcript) {
            setTranscript(transcript);
            await sendMessage(transcript);
          }
        } catch {
          toast.error("Voice transcription failed");
        }
        setAmplitude(0);
      };

      recorder.start();
      mediaRef.current = recorder;
      setRecording(true);
    } catch {
      toast.error("Microphone permission denied");
    }
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage(input);
    }
  };

  return (
    <div className="flex h-full flex-col" style={{ background: "var(--bg)" }}>
      <div
        className="flex items-center justify-between border-b px-5 py-3"
        style={{ borderColor: "var(--border)", background: "var(--bg-card)" }}
      >
        <div className="flex items-center gap-2">
          <Zap size={15} className="text-cyan-400" />
          <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>
            SuperAI V9
          </span>
          {isStreaming && (
            <motion.span
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ repeat: Infinity, duration: 1 }}
              className="rounded-full px-2 py-0.5 text-xs"
              style={{
                background: "rgba(6,182,212,0.12)",
                color: "#06b6d4",
                border: "1px solid rgba(6,182,212,0.25)",
              }}
            >
              streaming
            </motion.span>
          )}
        </div>
        <button
          onClick={clearMessages}
          className="rounded-lg p-1.5 transition-colors hover:bg-white/5"
          style={{ color: "var(--text-muted)" }}
          title="Clear chat"
        >
          <Trash2 size={15} />
        </button>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
        <AnimatePresence initial={false}>
          {messages.length === 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex h-full select-none flex-col items-center justify-center gap-3"
            >
              <div
                className="flex h-14 w-14 items-center justify-center rounded-2xl"
                style={{ background: "rgba(6,182,212,0.1)", border: "1px solid rgba(6,182,212,0.2)" }}
              >
                <Zap size={24} className="text-cyan-400" />
              </div>
              <p className="text-sm" style={{ color: "var(--text-muted)" }}>
                Ask SuperAI V9 anything
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {["Write Python code", "Explain quantum computing", "Search latest AI news"].map((sample) => (
                  <button
                    key={sample}
                    onClick={() => void sendMessage(sample)}
                    className="rounded-lg border px-3 py-1.5 text-xs transition-colors hover:bg-blue-600/10"
                    style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
                  >
                    {sample}
                  </button>
                ))}
              </div>
            </motion.div>
          )}
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      <div className="border-t px-4 py-3" style={{ borderColor: "var(--border)", background: "var(--bg-card)" }}>
        <div
          className="flex items-end gap-2 rounded-xl border px-3 py-2.5 transition-colors"
          style={{
            background: "var(--bg-elevated)",
            borderColor: isStreaming ? "rgba(6,182,212,0.4)" : "var(--border)",
          }}
        >
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            disabled={isLoading}
            placeholder="Ask anything... (Enter to send, Shift+Enter for new line)"
            className="flex-1 resize-none bg-transparent text-sm leading-relaxed outline-none"
            style={{ color: "var(--text)", maxHeight: 180 }}
          />

          <button
            onClick={toggleVoice}
            className={cn("flex-shrink-0 rounded-lg p-1.5 transition-all", isRecording ? "animate-pulse text-red-400" : "")}
            style={{ color: isRecording ? undefined : "var(--text-muted)" }}
            title={isRecording ? "Stop recording" : "Voice input"}
          >
            {isRecording ? <MicOff size={17} /> : <Mic size={17} />}
          </button>

          <button
            onClick={() => void sendMessage(input)}
            disabled={isLoading || !input.trim()}
            className="flex-shrink-0 rounded-lg p-1.5 transition-all"
            style={{
              background: isLoading || !input.trim() ? "rgba(59,130,246,0.2)" : "var(--primary)",
              color: "white",
              opacity: isLoading || !input.trim() ? 0.4 : 1,
            }}
          >
            {isLoading ? <Loader2 size={17} className="animate-spin" /> : <Send size={17} />}
          </button>
        </div>
        <p className="mt-1.5 text-center text-[11px]" style={{ color: "var(--text-dim)" }}>
          SuperAI V9 · Multi-modal AI · Rate responses with stars to improve
        </p>
      </div>
    </div>
  );
}
