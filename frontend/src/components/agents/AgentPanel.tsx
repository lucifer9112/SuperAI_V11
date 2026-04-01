"use client";
import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Play, CheckCircle, XCircle, ChevronDown, ChevronRight, Share2, Loader2 } from "lucide-react";
import toast from "react-hot-toast";

import { agentAPI, type AgentRunResponse, type AgentStep } from "@/lib/api";
import { useAgentStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const LEVELS = {
  1: { label: "Suggest", color: "rgba(59,130,246,0.15)", border: "rgba(59,130,246,0.3)" },
  2: { label: "Assisted", color: "rgba(6,182,212,0.15)", border: "rgba(6,182,212,0.3)" },
  3: { label: "Autonomous", color: "rgba(168,85,247,0.15)", border: "rgba(168,85,247,0.3)" },
} as const;

export function AgentPanel() {
  const [goal, setGoal] = useState("");
  const [autonomy, setAutonomy] = useState<1 | 2 | 3>(2);
  const [maxIter, setMaxIter] = useState(8);
  const [shareCtx, setShareCtx] = useState(true);
  const [running, setRunning] = useState(false);
  const [currentRun, setCurrentRun] = useState<AgentRunResponse | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const { addRun } = useAgentStore();

  const handleRun = async () => {
    if (!goal.trim()) return;
    setRunning(true);
    setCurrentRun(null);
    try {
      const result = await agentAPI.run({
        goal,
        autonomy_level: autonomy,
        max_iterations: maxIter,
        share_context: shareCtx,
      });
      setCurrentRun(result);
      addRun(result);
      toast.success(`Agent ${result.status} - ${result.iterations} steps`);
    } catch (e: any) {
      toast.error(e.message || "Agent failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4" style={{ background: "var(--bg)" }}>
      <div>
        <h2 className="text-base font-semibold" style={{ color: "var(--text)" }}>
          Autonomous Agent
        </h2>
        <p className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>
          V11: multi-agent shared context bus enabled
        </p>
      </div>

      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
          Goal
        </label>
        <textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          rows={3}
          placeholder="e.g. Research the latest AI papers and summarize the top 3 findings"
          className="w-full resize-none rounded-xl border p-3 text-sm outline-none transition-colors"
          style={{ background: "var(--bg-elevated)", borderColor: "var(--border)", color: "var(--text)" }}
        />
      </div>

      <div className="grid grid-cols-3 gap-2">
        {([1, 2, 3] as const).map((level) => (
          <button
            key={level}
            onClick={() => setAutonomy(level)}
            className="rounded-xl border p-2.5 text-left text-xs transition-all"
            style={{
              background: autonomy === level ? LEVELS[level].color : "var(--bg-elevated)",
              borderColor: autonomy === level ? LEVELS[level].border : "var(--border)",
              color: "var(--text)",
            }}
          >
            <div className="font-medium">{LEVELS[level].label}</div>
          </button>
        ))}
      </div>

      <div className="flex items-center gap-4">
        <div className="flex flex-1 items-center gap-2">
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            Max steps: {maxIter}
          </span>
          <input
            type="range"
            min={3}
            max={25}
            value={maxIter}
            onChange={(e) => setMaxIter(Number(e.target.value))}
            className="flex-1 accent-cyan-500"
          />
        </div>
        <button
          onClick={() => setShareCtx((value) => !value)}
          className={cn("flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-all")}
          style={{
            background: shareCtx ? "rgba(6,182,212,0.1)" : "var(--bg-elevated)",
            borderColor: shareCtx ? "rgba(6,182,212,0.3)" : "var(--border)",
            color: shareCtx ? "#06b6d4" : "var(--text-muted)",
          }}
          title="Share context between agents"
        >
          <Share2 size={11} /> {shareCtx ? "Context ON" : "Context OFF"}
        </button>
      </div>

      <motion.button
        onClick={handleRun}
        disabled={running || !goal.trim()}
        whileTap={{ scale: 0.97 }}
        className="flex items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-medium transition-all"
        style={{
          background: running || !goal.trim() ? "rgba(59,130,246,0.2)" : "var(--primary)",
          color: "white",
          opacity: running || !goal.trim() ? 0.5 : 1,
        }}
      >
        {running ? (
          <>
            <Loader2 size={15} className="animate-spin" />
            Running...
          </>
        ) : (
          <>
            <Play size={15} /> Run Agent
          </>
        )}
      </motion.button>

      <AnimatePresence>
        {currentRun && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-3">
            <div
              className={cn("flex items-center gap-2 rounded-xl border px-3 py-2.5 text-sm")}
              style={{
                background:
                  currentRun.status === "completed"
                    ? "rgba(16,185,129,0.08)"
                    : currentRun.status === "failed"
                      ? "rgba(239,68,68,0.08)"
                      : "rgba(245,158,11,0.08)",
                borderColor:
                  currentRun.status === "completed"
                    ? "rgba(16,185,129,0.25)"
                    : currentRun.status === "failed"
                      ? "rgba(239,68,68,0.25)"
                      : "rgba(245,158,11,0.25)",
                color:
                  currentRun.status === "completed"
                    ? "#10b981"
                    : currentRun.status === "failed"
                      ? "#ef4444"
                      : "#f59e0b",
              }}
            >
              {currentRun.status === "completed" ? <CheckCircle size={14} /> : <XCircle size={14} />}
              <span className="capitalize font-medium">{currentRun.status}</span>
              <span className="ml-auto text-xs opacity-70">
                {currentRun.iterations} steps - {currentRun.agent_id}
              </span>
            </div>

            {currentRun.final_answer && (
              <div
                className="rounded-xl border p-3 text-sm"
                style={{ background: "var(--bg-card)", borderColor: "var(--border)", color: "var(--text)" }}
              >
                <p className="mb-1 text-[11px]" style={{ color: "var(--text-muted)" }}>
                  Final Answer
                </p>
                <p className="whitespace-pre-wrap leading-relaxed">{currentRun.final_answer}</p>
              </div>
            )}

            {currentRun.steps.length > 0 && (
              <div className="flex flex-col gap-1">
                <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                  Step breakdown
                </p>
                {currentRun.steps.map((step) => (
                  <StepCard
                    key={step.step}
                    step={step}
                    expanded={expanded === step.step}
                    onToggle={() => setExpanded((previous) => (previous === step.step ? null : step.step))}
                  />
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function StepCard({
  step,
  expanded,
  onToggle,
}: {
  step: AgentStep;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div
      className="cursor-pointer overflow-hidden rounded-xl border transition-colors hover:border-cyan-500/20"
      style={{ borderColor: "var(--border)", background: "var(--bg-card)" }}
      onClick={onToggle}
    >
      <div className="flex items-center gap-2 px-3 py-2 text-xs">
        <span className={cn("h-1.5 w-1.5 flex-shrink-0 rounded-full", step.success ? "bg-green-400" : "bg-red-400")} />
        <span className="font-medium" style={{ color: "var(--text)" }}>
          Step {step.step}
        </span>
        <span style={{ color: "var(--text-muted)" }}>{step.action}</span>
        <span className="ml-auto" style={{ color: "var(--text-dim)" }}>
          {expanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        </span>
      </div>
      <AnimatePresence>
        {expanded && (
          <motion.div initial={{ height: 0 }} animate={{ height: "auto" }} exit={{ height: 0 }} className="overflow-hidden">
            <div className="space-y-1.5 px-3 pb-2.5 text-xs" style={{ borderTop: "1px solid var(--border)" }}>
              {step.thought && (
                <p className="pt-2">
                  <span style={{ color: "var(--text-muted)" }}>Thought: </span>
                  <span style={{ color: "var(--text)" }}>{step.thought}</span>
                </p>
              )}
              <p>
                <span style={{ color: "var(--text-muted)" }}>Result: </span>
                <span className="whitespace-pre-wrap" style={{ color: "var(--text)" }}>
                  {step.result}
                </span>
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
