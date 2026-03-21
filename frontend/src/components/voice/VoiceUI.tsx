"use client";

import React, { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Mic, MicOff, Square, Volume2 } from "lucide-react";
import toast from "react-hot-toast";

import { voiceAPI } from "@/lib/api";
import { useChatStore, useVoiceStore } from "@/lib/store";

const BAR_COUNT = 32;

export function VoiceUI() {
  const { isRecording, isPlaying, transcript, setRecording, setPlaying, setAmplitude, setTranscript } = useVoiceStore();
  const { setLoading } = useChatStore();

  const [bars, setBars] = useState<number[]>(Array(BAR_COUNT).fill(4));
  const [ttsText, setTtsText] = useState("");
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number>(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);

  useEffect(() => {
    if (!isRecording) {
      cancelAnimationFrame(animFrameRef.current);
      setBars(Array(BAR_COUNT).fill(4));
      return;
    }

    const tick = () => {
      if (analyserRef.current) {
        const data = new Uint8Array(analyserRef.current.frequencyBinCount);
        analyserRef.current.getByteFrequencyData(data);
        const step = Math.max(1, Math.floor(data.length / BAR_COUNT));
        setBars(
          Array.from({ length: BAR_COUNT }, (_, index) => {
            const value = data[index * step] / 255;
            return Math.max(4, Math.round(value * 80));
          }),
        );
        setAmplitude(data.reduce((sum, current) => sum + current, 0) / data.length / 255);
      } else {
        setBars((current) => current.map(() => Math.max(4, Math.round(Math.random() * 30 + 4))));
      }
      animFrameRef.current = requestAnimationFrame(tick);
    };

    animFrameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animFrameRef.current);
  }, [isRecording, setAmplitude]);

  useEffect(() => {
    return () => {
      cancelAnimationFrame(animFrameRef.current);
      audioRef.current?.pause();
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
      }
    };
  }, []);

  const processAudio = async (blob: Blob) => {
    setLoading(true);
    try {
      const { transcript: nextTranscript } = await voiceAPI.stt(blob);
      setTranscript(nextTranscript);
      if (nextTranscript) {
        const preview = nextTranscript.length > 40 ? `${nextTranscript.slice(0, 40)}...` : nextTranscript;
        toast.success(`Heard: "${preview}"`);
      }
    } catch {
      toast.error("Transcription failed");
    } finally {
      setLoading(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        await audioContext.close();
        analyserRef.current = null;
        const mimeType = recorder.mimeType || chunksRef.current[0]?.type || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: mimeType });
        await processAudio(blob);
      };

      recorder.start();
      mediaRef.current = recorder;
      setRecording(true);
    } catch {
      toast.error("Microphone access denied");
    }
  };

  const stopRecording = () => {
    mediaRef.current?.stop();
    setRecording(false);
  };

  const speak = async () => {
    if (!ttsText.trim()) {
      return;
    }

    setPlaying(true);
    try {
      const blob = await voiceAPI.tts(ttsText);
      if (audioRef.current) {
        audioRef.current.pause();
      }
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
      }

      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioUrlRef.current = url;
      audioRef.current = audio;
      audio.onended = () => setPlaying(false);
      await audio.play();
    } catch {
      toast.error("TTS failed");
      setPlaying(false);
    }
  };

  const stopPlayback = () => {
    audioRef.current?.pause();
    setPlaying(false);
  };

  return (
    <div className="flex h-full flex-col gap-6 p-5" style={{ background: "var(--bg)" }}>
      <div>
        <h2 className="text-base font-semibold" style={{ color: "var(--text)" }}>
          Voice Interface
        </h2>
        <p className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>
          Speak to SuperAI V9 for real-time transcription
        </p>
      </div>

      <div className="flex flex-col items-center gap-6 py-6">
        <div className="flex h-20 items-center gap-[2px]">
          {bars.map((height, index) => (
            <motion.div
              key={index}
              animate={{ height: isRecording ? height : 4 }}
              transition={{ duration: 0.05, ease: "easeOut" }}
              className="w-1.5 rounded-full"
              style={{
                background: isRecording
                  ? `rgba(6,182,212,${0.4 + (height / 80) * 0.6})`
                  : "rgba(99,179,237,0.15)",
                minHeight: 4,
              }}
            />
          ))}
        </div>

        <motion.button
          onClick={isRecording ? stopRecording : startRecording}
          whileTap={{ scale: 0.93 }}
          className="relative flex h-20 w-20 items-center justify-center rounded-full"
          style={{
            background: isRecording ? "rgba(239,68,68,0.15)" : "rgba(6,182,212,0.1)",
            border: isRecording ? "2px solid rgba(239,68,68,0.6)" : "2px solid rgba(6,182,212,0.35)",
          }}
        >
          {isRecording && (
            <motion.div
              className="absolute inset-0 rounded-full"
              animate={{ scale: [1, 1.4, 1], opacity: [0.4, 0, 0.4] }}
              transition={{ repeat: Infinity, duration: 1.5 }}
              style={{ border: "2px solid rgba(239,68,68,0.4)" }}
            />
          )}
          {isRecording ? <MicOff size={28} className="text-red-400" /> : <Mic size={28} className="text-cyan-400" />}
        </motion.button>

        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          {isRecording ? "Listening... tap to stop" : "Tap to speak"}
        </p>
      </div>

      <AnimatePresence>
        {transcript && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border p-3 text-sm"
            style={{ background: "var(--bg-card)", borderColor: "var(--border)", color: "var(--text)" }}
          >
            <p className="mb-1 text-[11px]" style={{ color: "var(--text-muted)" }}>
              Transcript
            </p>
            <p>{transcript}</p>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="mt-auto flex flex-col gap-2">
        <p className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
          Text-to-Speech
        </p>
        <textarea
          value={ttsText}
          onChange={(event) => setTtsText(event.target.value)}
          rows={3}
          placeholder="Type text to speak aloud..."
          className="w-full resize-none rounded-xl border p-3 text-sm outline-none"
          style={{ background: "var(--bg-elevated)", borderColor: "var(--border)", color: "var(--text)" }}
        />
        <div className="flex gap-2">
          <button
            onClick={speak}
            disabled={!ttsText.trim() || isPlaying}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-medium transition-all"
            style={{ background: "var(--primary)", color: "white", opacity: !ttsText.trim() || isPlaying ? 0.4 : 1 }}
          >
            <Volume2 size={15} /> {isPlaying ? "Playing..." : "Speak"}
          </button>
          {isPlaying && (
            <button
              onClick={stopPlayback}
              className="rounded-xl px-3 py-2.5 transition-all"
              style={{
                background: "rgba(239,68,68,0.15)",
                color: "#f87171",
                border: "1px solid rgba(239,68,68,0.3)",
              }}
            >
              <Square size={15} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
