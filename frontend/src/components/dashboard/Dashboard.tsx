"use client";
import React, { useEffect } from "react";
import { motion } from "framer-motion";
import useSWR from "swr";
import { Cpu, HardDrive, Zap, Server, Star, Activity, Clock } from "lucide-react";
import { systemAPI, feedbackAPI } from "@/lib/api";
import { useSystemStore } from "@/lib/store";
import { cn, formatUptime, formatMs } from "@/lib/utils";

export function Dashboard() {
  const { data: status, isLoading, error } = useSWR("system-status", systemAPI.status, { refreshInterval: 8000 });
  const { data: fbStats }                  = useSWR("fb-stats", feedbackAPI.stats, { refreshInterval: 30000 });
  const { setStatus, setFbStats }          = useSystemStore();

  useEffect(() => { if (status) setStatus(status); }, [status]);
  useEffect(() => { if (fbStats) setFbStats(fbStats); }, [fbStats]);

  if (isLoading) return <Loading />;
  if (error || !status) return <ErrorState msg={error?.message || "Failed to load"} />;

  return (
    <div className="flex flex-col gap-4 p-4 overflow-y-auto h-full" style={{ background: "var(--bg)" }}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold" style={{ color: "var(--text)" }}>System Dashboard</h2>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            V{status.version} · {status.environment} · uptime {formatUptime(status.uptime_s)}
          </p>
        </div>
        <div className={cn("flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border")}
          style={{
            background: status.status === "ok" ? "rgba(16,185,129,0.08)" : "rgba(239,68,68,0.08)",
            borderColor: status.status === "ok" ? "rgba(16,185,129,0.3)" : "rgba(239,68,68,0.3)",
            color: status.status === "ok" ? "#10b981" : "#ef4444",
          }}>
          <motion.span animate={{ opacity: [1,0.3,1] }} transition={{ repeat: Infinity, duration: 2 }}
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: status.status === "ok" ? "#10b981" : "#ef4444" }} />
          {status.status}
        </div>
      </div>

      {/* Metric grid */}
      <div className="grid grid-cols-2 gap-3">
        <MetricCard icon={<Cpu size={14} />}    label="CPU"      value={`${status.cpu_pct.toFixed(1)}%`}   pct={status.cpu_pct} />
        <MetricCard icon={<HardDrive size={14}/>} label="RAM"    value={`${status.ram_pct.toFixed(1)}%`}   pct={status.ram_pct} />
        <MetricCard icon={<Activity size={14}/>}  label="Requests" value={status.requests_total.toLocaleString()} pct={null} />
        <MetricCard icon={<Clock size={14} />}  label="Avg latency" value={formatMs(status.avg_latency_ms)} pct={null} />
      </div>

      {/* GPU info */}
      {status.gpu_info && (
        <div className="rounded-xl p-3 border text-xs" style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}>
          <div className="flex items-center gap-2 mb-1">
            <Zap size={12} className="text-yellow-400" />
            <span className="font-medium" style={{ color: "var(--text)" }}>GPU</span>
          </div>
          <p className="font-mono" style={{ color: "var(--text-muted)" }}>{status.gpu_info}</p>
        </div>
      )}

      {/* Loaded models */}
      <div className="rounded-xl p-3 border" style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}>
        <div className="flex items-center gap-2 mb-2">
          <Server size={13} style={{ color: "var(--text-muted)" }} />
          <span className="text-xs font-medium" style={{ color: "var(--text)" }}>Loaded Models</span>
        </div>
        {status.models_loaded.length === 0 ? (
          <p className="text-xs" style={{ color: "var(--text-dim)" }}>No models loaded yet</p>
        ) : (
          <div className="flex flex-col gap-1">
            {status.models_loaded.map(m => (
              <div key={m} className="flex items-center gap-2 text-xs">
                <motion.span animate={{ opacity: [1,0.4,1] }} transition={{ repeat: Infinity, duration: 2 }}
                  className="w-1.5 h-1.5 rounded-full bg-green-400 flex-shrink-0" />
                <span className="truncate" style={{ color: "var(--text-muted)" }} title={m}>{m}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Feedback stats (V9 new) */}
      {fbStats && (
        <div className="rounded-xl p-3 border" style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}>
          <div className="flex items-center gap-2 mb-2">
            <Star size={13} className="text-yellow-400" />
            <span className="text-xs font-medium" style={{ color: "var(--text)" }}>Feedback (7 days)</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-lg p-2" style={{ background: "var(--bg-elevated)" }}>
              <p style={{ color: "var(--text-muted)" }}>Total</p>
              <p className="text-lg font-bold mt-0.5" style={{ color: "var(--text)" }}>{fbStats.total_7d}</p>
            </div>
            <div className="rounded-lg p-2" style={{ background: "var(--bg-elevated)" }}>
              <p style={{ color: "var(--text-muted)" }}>Avg score</p>
              <p className="text-lg font-bold mt-0.5" style={{ color: fbStats.avg_score >= 4 ? "#10b981" : fbStats.avg_score >= 3 ? "#f59e0b" : "#ef4444" }}>
                {fbStats.avg_score.toFixed(1)} ⭐
              </p>
            </div>
            <div className="rounded-lg p-2" style={{ background: "var(--bg-elevated)" }}>
              <p style={{ color: "var(--text-muted)" }}>Positive</p>
              <p className="font-semibold" style={{ color: "#10b981" }}>+{fbStats.positive_7d}</p>
            </div>
            <div className="rounded-lg p-2" style={{ background: "var(--bg-elevated)" }}>
              <p style={{ color: "var(--text-muted)" }}>Negative</p>
              <p className="font-semibold" style={{ color: "#ef4444" }}>-{fbStats.negative_7d}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({ icon, label, value, pct }: { icon: React.ReactNode; label: string; value: string; pct: number | null }) {
  const color = pct == null ? "#3b82f6" : pct > 90 ? "#ef4444" : pct > 70 ? "#f59e0b" : "#10b981";
  return (
    <div className="rounded-xl p-3 border flex flex-col gap-2"
      style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}>
      <div className="flex items-center gap-1.5 text-xs" style={{ color: "var(--text-muted)" }}>
        {icon} {label}
      </div>
      <p className="text-xl font-bold" style={{ color: "var(--text)" }}>{value}</p>
      {pct != null && (
        <div className="h-1 rounded-full overflow-hidden" style={{ background: "var(--bg-elevated)" }}>
          <motion.div className="h-full rounded-full"
            initial={{ width: 0 }} animate={{ width: `${Math.min(pct, 100)}%` }}
            transition={{ duration: 0.6 }}
            style={{ background: color }} />
        </div>
      )}
    </div>
  );
}

const Loading = () => (
  <div className="p-4 flex flex-col gap-3">
    {[...Array(4)].map((_,i) => (
      <motion.div key={i} className="h-16 rounded-xl" style={{ background: "var(--bg-card)" }}
        animate={{ opacity: [0.4,0.8,0.4] }} transition={{ repeat: Infinity, duration: 1.5, delay: i*0.1 }} />
    ))}
  </div>
);

const ErrorState = ({ msg }: { msg: string }) => (
  <div className="m-4 p-3 text-sm rounded-xl border"
    style={{ background: "rgba(239,68,68,0.08)", borderColor: "rgba(239,68,68,0.25)", color: "#f87171" }}>
    {msg}
  </div>
);
