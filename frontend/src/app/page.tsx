"use client";
import React, { useState } from "react";
import dynamic from "next/dynamic";
import { motion, AnimatePresence } from "framer-motion";
import { MessageSquare, Bot, LayoutDashboard, Mic, Settings, Zap } from "lucide-react";
import { Toaster } from "react-hot-toast";

type Tab = "chat" | "agents" | "dashboard" | "voice";

const PanelLoading = () => (
  <div className="flex h-full items-center justify-center text-sm" style={{ color: "var(--text-muted)" }}>
    Loading panel...
  </div>
);

const ChatPanel = dynamic(() => import("@/components/chat/ChatPanel").then((mod) => mod.ChatPanel), {
  ssr: false,
  loading: () => <PanelLoading />,
});

const Dashboard = dynamic(() => import("@/components/dashboard/Dashboard").then((mod) => mod.Dashboard), {
  ssr: false,
  loading: () => <PanelLoading />,
});

const AgentPanel = dynamic(() => import("@/components/agents/AgentPanel").then((mod) => mod.AgentPanel), {
  ssr: false,
  loading: () => <PanelLoading />,
});

const VoiceUI = dynamic(() => import("@/components/voice/VoiceUI").then((mod) => mod.VoiceUI), {
  ssr: false,
  loading: () => <PanelLoading />,
});

const ENABLE_ADVANCED_TABS = process.env.NEXT_PUBLIC_ENABLE_ADVANCED_TABS === "true";

const TABS: { id: Tab; icon: React.ReactNode; label: string }[] = ENABLE_ADVANCED_TABS
  ? [
      { id: "chat",      icon: <MessageSquare size={18} />, label: "Chat"      },
      { id: "agents",    icon: <Bot           size={18} />, label: "Agents"    },
      { id: "voice",     icon: <Mic           size={18} />, label: "Voice"     },
      { id: "dashboard", icon: <LayoutDashboard size={18}/>, label: "Dashboard" },
    ]
  : [
      { id: "chat",      icon: <MessageSquare size={18} />, label: "Chat"      },
      { id: "dashboard", icon: <LayoutDashboard size={18}/>, label: "Dashboard" },
    ];

function renderPanel(tab: Tab): React.ReactNode {
  if (tab === "chat") {
    return <ChatPanel />;
  }
  if (tab === "dashboard") {
    return <Dashboard />;
  }
  if (!ENABLE_ADVANCED_TABS) {
    return <ChatPanel />;
  }
  if (tab === "agents") {
    return <AgentPanel />;
  }
  return <VoiceUI />;
}

export default function Home() {
  const [tab, setTab] = useState<Tab>("chat");

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg)" }}>
      <Toaster position="top-right" toastOptions={{
        style: { background: "var(--bg-elevated)", color: "var(--text)",
                 border: "1px solid var(--border)", fontSize: 13 },
      }} />

      {/* Sidebar */}
      <aside className="w-14 flex flex-col items-center py-4 gap-1 border-r flex-shrink-0"
             style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}>
        {/* Logo */}
        <motion.div whileHover={{ scale: 1.05 }}
          className="w-9 h-9 rounded-xl flex items-center justify-center mb-3 cursor-pointer"
          style={{ background: "linear-gradient(135deg,#3b82f6,#06b6d4)",
                   boxShadow: "0 0 16px rgba(59,130,246,0.3)" }}>
          <Zap size={17} className="text-white" />
        </motion.div>

        {/* Nav */}
        <nav className="flex flex-col gap-1 flex-1">
          {TABS.map(t => (
            <motion.button key={t.id} onClick={() => setTab(t.id)}
              whileHover={{ scale: 1.06 }} whileTap={{ scale: 0.95 }}
              title={t.label}
              className="w-10 h-10 rounded-xl flex items-center justify-center relative transition-colors"
              style={{
                background: tab === t.id ? "rgba(59,130,246,0.2)" : "transparent",
                color: tab === t.id ? "#60a5fa" : "var(--text-dim)",
                border: tab === t.id ? "1px solid rgba(59,130,246,0.3)" : "1px solid transparent",
              }}>
              {t.icon}
              {tab === t.id && (
                <motion.div layoutId="activeDot"
                  className="absolute -right-[5px] w-1 h-4 rounded-full"
                  style={{ background: "#3b82f6" }} />
              )}
            </motion.button>
          ))}
        </nav>

        {/* Settings */}
        <motion.button whileHover={{ scale: 1.06 }} whileTap={{ scale: 0.95 }}
          title="Settings"
          className="w-10 h-10 rounded-xl flex items-center justify-center"
          style={{ color: "var(--text-dim)" }}>
          <Settings size={18} />
        </motion.button>
      </aside>

      {/* Main panel */}
      <main className="flex-1 min-w-0 relative overflow-hidden">
        <AnimatePresence mode="wait">
          <motion.div key={tab} className="absolute inset-0"
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -12 }}
            transition={{ duration: 0.18, ease: "easeOut" }}>
            {renderPanel(tab)}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
