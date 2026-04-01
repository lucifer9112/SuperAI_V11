"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, User, Star, Clock, Zap } from "lucide-react";
import toast from "react-hot-toast";

import { feedbackAPI } from "@/lib/api";
import { useChatStore, type Message } from "@/lib/store";
import { cn, formatMs } from "@/lib/utils";

interface Props {
  message: Message;
}

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
      toast.success(score >= 4 ? "Thanks for the positive feedback!" : "Feedback noted, we'll improve!");
    } catch {
      toast.error("Couldn't save feedback");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className={cn("group flex gap-3", isUser && "flex-row-reverse")}
    >
      <div
        className={cn(
          "flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl",
          isUser ? "border border-blue-500/40 bg-blue-600/80" : "border border-cyan-500/30 bg-cyan-900/60",
        )}
      >
        {isUser ? <User size={14} className="text-blue-200" /> : <Bot size={14} className="text-cyan-300" />}
      </div>

      <div className={cn("flex max-w-[80%] flex-col gap-1.5", isUser && "items-end")}>
        <div
          className={cn(
            "rounded-2xl border px-4 py-3 text-sm leading-relaxed",
            isUser ? "rounded-tr-sm border-blue-500/25 bg-blue-600/15 text-blue-50" : "rounded-tl-sm border-[rgba(99,179,237,0.12)] bg-[#0d1520] text-slate-200",
          )}
        >
          {isUser ? (
            <span className="whitespace-pre-wrap">{message.content}</span>
          ) : (
            <div className="prose-dark">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content || " "}</ReactMarkdown>
              {message.isStreaming && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse rounded bg-cyan-400" />}
            </div>
          )}
        </div>

        {!isUser && !message.isStreaming && (
          <div className="flex items-center gap-3 px-1">
            <div className="flex items-center gap-2 text-[11px] text-[#5d7a9a]">
              {message.task_type && (
                <span className="flex items-center gap-1">
                  <Zap size={9} className="text-cyan-600" />
                  {message.task_type}
                </span>
              )}
              {message.model && (
                <span className="max-w-[110px] truncate" title={message.model}>
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

            {message.response_id && (
              <div
                className={cn(
                  "flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100",
                  message.feedback && "opacity-100",
                )}
              >
                {[1, 2, 3, 4, 5].map((score) => (
                  <button
                    key={score}
                    onClick={() => handleFeedback(score)}
                    disabled={!!message.feedback || submitting}
                    className="p-0.5 transition-colors"
                  >
                    <Star
                      size={11}
                      className={cn(
                        "transition-colors",
                        message.feedback && score <= message.feedback
                          ? "fill-yellow-400 text-yellow-400"
                          : "text-[#2d4a6a] hover:text-yellow-400",
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
