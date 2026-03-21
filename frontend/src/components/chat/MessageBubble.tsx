"use client";
import React, { useState } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, User, Star, Clock, Cpu, Zap } from "lucide-react";
import { cn, formatMs } from "@/lib/utils";
import { useChatStore } from "@/lib/store";
import { feedbackAPI } from "@/lib/api";
import type { Message } from "@/lib/store";
import toast from "react-hot-toast";

interface Props { message: Message; }

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";
  const { setFeedback } = useChatStore();
  const [submitting, setSubmitting] = useState(false);

  const handleFeedback = async (score: number) => {
    if (!message.response_id || message.feedback) return;
    setSubmitting(true);
    try {
      await feedbackAPI.submit(message.response_id, score);
      setFeedback(message.id, score);
      toast.success(score >= 4 ? "Thanks! 🌟" : "Feedback noted, we'll improve!");
    } catch { toast.error("Couldn't save feedback"); }
    finally   { setSubmitting(false); }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className={cn("flex gap-3 group", isUser && "flex-row-reverse")}
    >
      {/* Avatar */}
      <div className={cn(
        "flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center",
        isUser
          ? "bg-blue-600/80 border border-blue-500/40"
          : "bg-cyan-900/60 border border-cyan-500/30"
      )}>
        {isUser ? <User size={14} className="text-blue-200" />
                : <Bot  size={14} className="text-cyan-300" />}
      </div>

      {/* Bubble */}
      <div className={cn("flex flex-col gap-1.5 max-w-[80%]", isUser && "items-end")}>
        <div className={cn(
          "rounded-2xl px-4 py-3 text-sm leading-relaxed border",
          isUser
            ? "bg-blue-600/15 border-blue-500/25 text-blue-50 rounded-tr-sm"
            : "bg-[#0d1520] border-[rgba(99,179,237,0.12)] text-slate-200 rounded-tl-sm"
        )}>
          {isUser ? (
            <span className="whitespace-pre-wrap">{message.content}</span>
          ) : (
            <div className="prose-dark">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content || " "}
              </ReactMarkdown>
              {message.isStreaming && (
                <span className="inline-block w-1.5 h-4 bg-cyan-400 animate-pulse ml-0.5 rounded" />
              )}
            </div>
          )}
        </div>

        {/* Meta row */}
        {!isUser && !message.isStreaming && (
          <div className="flex items-center gap-3 px-1">
            {/* Task / model / latency */}
            <div className="flex items-center gap-2 text-[11px] text-[#5d7a9a]">
              {message.task_type && (
                <span className="flex items-center gap-1">
                  <Zap size={9} className="text-cyan-600" />
                  {message.task_type}
                </span>
              )}
              {message.model && (
                <span className="truncate max-w-[110px]" title={message.model}>
                  {message.model.split("/").pop()}
                </span>
              )}
              {message.latency_ms != null && (
                <span className="flex items-center gap-1">
                  <Clock size={9} />
                  {formatMs(message.latency_ms)}
                </span>
              )}
            </div>

            {/* Star feedback */}
            {message.response_id && (
              <div className={cn(
                "flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity",
                message.feedback && "opacity-100"
              )}>
                {[1,2,3,4,5].map(s => (
                  <button key={s} onClick={() => handleFeedback(s)}
                    disabled={!!message.feedback || submitting}
                    className="p-0.5 transition-colors"
                  >
                    <Star size={11}
                      className={cn(
                        "transition-colors",
                        message.feedback && s <= message.feedback
                          ? "fill-yellow-400 text-yellow-400"
                          : "text-[#2d4a6a] hover:text-yellow-400"
                      )}
                    />
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}
