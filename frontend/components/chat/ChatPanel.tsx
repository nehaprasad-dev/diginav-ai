"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { SuggestedPrompts } from "@/components/chat/SuggestedPrompts";
import { TypingIndicator } from "@/components/chat/TypingIndicator";
import { useDigiNavStore } from "@/lib/store";

interface ChatPanelProps {
  onSend: (message: string) => Promise<void>;
  sending: boolean;
  onSampleFlow: () => Promise<void>;
}

export function ChatPanel({ onSend, sending, onSampleFlow }: ChatPanelProps) {
  const messages = useDigiNavStore((s) => s.messages);
  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || sending) return;
    setDraft("");
    await onSend(text);
  }

  const showSuggestions = messages.length === 0;
  const isStreaming = messages.some((m) => m.streaming);

  return (
    <section className="flex h-full min-h-0 flex-col border-r border-border bg-background">
      <header className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <h1 className="text-base font-semibold tracking-tight">DigiNav AI</h1>
          <p className="text-xs text-muted-foreground">
            Indian compliance, in plain language
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={sending}
          onClick={() => void onSampleFlow()}
        >
          Try a sample flow
        </Button>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {showSuggestions ? (
          <div className="mx-auto max-w-md space-y-4 pt-8">
            <p className="text-center text-sm text-muted-foreground">
              Describe what you need — incorporation, GST filing, or a Shops
              &amp; Establishment license.
            </p>
            <SuggestedPrompts
              disabled={sending}
              onSelect={(prompt) => void onSend(prompt)}
            />
          </div>
        ) : (
          messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))
        )}
        {sending && !isStreaming ? <TypingIndicator /> : null}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={handleSubmit}
        className="border-t border-border p-4"
      >
        <div className="flex gap-2">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Ask DigiNav…"
            disabled={sending}
            className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
          />
          <Button type="submit" disabled={sending || !draft.trim()}>
            Send
          </Button>
        </div>
      </form>
    </section>
  );
}
