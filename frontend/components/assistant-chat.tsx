"use client";

import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import {
  Paperclip,
  Send,
  Sparkles,
  Square,
  User,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { PrescriptionBrief } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const QUICK_PROMPTS = [
  "Explain my medications in simple terms",
  "What side effects should I watch for?",
  "How should I take these medications?",
  "Summarize this prescription",
];

const DISCLAIMER =
  "AI assistant — informational only. Never change medication without consulting a doctor or pharmacist.";

/** Escape HTML, then render the rare bold the model may still emit. */
function renderAssistantText(text: string): string {
  const escaped = text
    .replace(/&/g, "&")
    .replace(/</g, "<")
    .replace(/>/g, ">");
  return escaped.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

interface ChatBubble {
  role: "user" | "assistant";
  answer: string;
  keyPoints?: string[];
  followUps?: string[];
}

interface AssistantChatProps {
  prescriptions: PrescriptionBrief[];
}

export function AssistantChat({ prescriptions }: AssistantChatProps) {
  const [messages, setMessages] = useState<ChatBubble[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [prescriptionId, setPrescriptionId] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const updateLastAssistant = (bubble: Partial<ChatBubble>) => {
    setMessages((previous) => {
      const next = [...previous];
      next[next.length - 1] = { ...next[next.length - 1], ...bubble };
      return next;
    });
  };

  const send = async (rawText: string) => {
    const text = rawText.trim();
    if (!text || thinking) return;

    const history = messages
      .filter((bubble) => bubble.answer)
      .slice(-10)
      .map((bubble) => ({
        role: bubble.role,
        content: bubble.role === "assistant" ? bubble.answer : bubble.answer,
      }));

    setMessages((previous) => [
      ...previous,
      { role: "user", answer: text },
      { role: "assistant", answer: "" },
    ]);
    setInput("");
    setThinking(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch("/api/assistant/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          prescription_id: prescriptionId || undefined,
          history,
        }),
        signal: controller.signal,
      });

      const payload = await response.json().catch(() => null);
      if (!response.ok || !payload?.answer) {
        throw new Error(
          payload?.error?.message ||
            payload?.detail ||
            `Request failed (${response.status})`,
        );
      }

      updateLastAssistant({
        answer: payload.answer,
        keyPoints: payload.key_points ?? [],
        followUps: payload.follow_ups ?? [],
      });
    } catch (error) {
      if ((error as Error).name === "AbortError") {
        updateLastAssistant({ answer: "Generation stopped." });
      } else {
        toast.error((error as Error).message || "The assistant is unavailable.");
        updateLastAssistant({
          answer: "Sorry — the assistant could not be reached. Try again.",
        });
      }
    } finally {
      setThinking(false);
      abortRef.current = null;
    }
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void send(input);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send(input);
    }
  };

  return (
    <div className="flex h-[calc(100vh-11rem)] min-h-[32rem] flex-col rounded-xl border bg-card">
      {/* Context selector */}
      <div className="flex flex-wrap items-center gap-3 border-b p-3">
        <div className="text-muted-foreground flex items-center gap-2 text-sm">
          <Paperclip className="size-4" />
          <span className="hidden sm:inline">Ground in prescription:</span>
          <span className="sm:hidden">Context:</span>
        </div>
        <select
          value={prescriptionId}
          onChange={(event) => {
            setPrescriptionId(event.target.value);
            if (messages.length > 0) {
              setMessages([]);
              toast.info("Context changed — conversation cleared");
            }
          }}
          className="border-input bg-background h-8 max-w-xs rounded-md border px-2 text-sm outline-none"
          aria-label="Prescription context"
        >
          <option value="">No prescription context</option>
          {prescriptions.map((prescription) => (
            <option key={prescription.id} value={prescription.id}>
              {prescription.original_filename}
              {prescription.patient_name
                ? ` — ${prescription.patient_name}`
                : ""}
            </option>
          ))}
        </select>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <p className="text-muted-foreground max-w-md text-sm">
              Ask anything about medications and prescriptions. Pick a
              prescription above to ground the answers in its extracted data.
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {QUICK_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => void send(prompt)}
                  className="hover:bg-accent hover:text-accent-foreground rounded-full border px-3 py-1.5 text-xs transition-colors"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((bubble, index) => (
          <div
            key={index}
            className={cn(
              "flex items-start gap-3",
              bubble.role === "user" ? "flex-row-reverse" : "",
            )}
          >
            <div
              className={cn(
                "flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                bubble.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted",
              )}
            >
              {bubble.role === "user" ? (
                <User className="size-4" />
              ) : (
                <Sparkles className="size-4" />
              )}
            </div>
            <div className="max-w-[80%] space-y-2">
              <div
                className={cn(
                  "rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap [&_strong]:font-semibold",
                  bubble.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted",
                )}
                {...(bubble.role === "assistant"
                  ? {
                      dangerouslySetInnerHTML: {
                        __html:
                          renderAssistantText(bubble.answer) ||
                          (thinking && index === messages.length - 1
                            ? "…"
                            : ""),
                      },
                    }
                  : { children: bubble.answer })}
              />
              {bubble.role === "assistant" &&
                (bubble.keyPoints?.length ?? 0) > 0 && (
                  <ul className="space-y-1 pl-1">
                    {bubble.keyPoints!.map((point, pointIndex) => (
                      <li
                        key={pointIndex}
                        className="text-muted-foreground flex items-start gap-2 text-xs"
                      >
                        <Zap className="text-primary mt-0.5 size-3 shrink-0" />
                        {point}
                      </li>
                    ))}
                  </ul>
                )}
              {bubble.role === "assistant" &&
                (bubble.followUps?.length ?? 0) > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {bubble.followUps!.map((followUp, chipIndex) => (
                      <button
                        key={chipIndex}
                        type="button"
                        onClick={() => void send(followUp)}
                        disabled={thinking}
                        className="hover:bg-accent hover:text-accent-foreground rounded-full border px-2.5 py-1 text-xs transition-colors disabled:opacity-50"
                      >
                        {followUp}
                      </button>
                    ))}
                  </div>
                )}
            </div>
          </div>
        ))}
      </div>

      {/* Composer */}
      <div className="border-t p-3">
        <form onSubmit={onSubmit} className="flex items-end gap-2">
          <Textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask about medications, dosages, side effects…"
            rows={1}
            className="max-h-32 min-h-9 resize-none"
            disabled={thinking}
          />
          {thinking ? (
            <Button
              type="button"
              variant="destructive"
              size="icon"
              onClick={() => abortRef.current?.abort()}
              aria-label="Stop generating"
            >
              <Square className="size-4" />
            </Button>
          ) : (
            <Button type="submit" size="icon" disabled={!input.trim()}>
              <Send className="size-4" />
              <span className="sr-only">Send message</span>
            </Button>
          )}
        </form>
        <p className="text-muted-foreground mt-2 text-xs">{DISCLAIMER}</p>
      </div>
    </div>
  );
}
