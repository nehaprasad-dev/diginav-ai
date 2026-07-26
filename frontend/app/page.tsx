"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ChatPanel } from "@/components/chat/ChatPanel";
import { WorkflowDashboard } from "@/components/dashboard/WorkflowDashboard";
import { ReconnectBanner } from "@/components/shared/ReconnectBanner";
import { SkeletonChat } from "@/components/shared/SkeletonChat";
import { SkeletonDashboard } from "@/components/shared/SkeletonDashboard";
import { getWorkflow, postChat, resumeWorkflow } from "@/lib/api";
import { SseClient } from "@/lib/sse";
import { useDigiNavStore } from "@/lib/store";

function newId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function Home() {
  const sessionId = useDigiNavStore((s) => s.sessionId);
  const hydrated = useDigiNavStore((s) => s.hydrated);
  const connectionStatus = useDigiNavStore((s) => s.connectionStatus);
  const lastError = useDigiNavStore((s) => s.lastError);

  const addUserMessage = useDigiNavStore((s) => s.addUserMessage);
  const applyEvent = useDigiNavStore((s) => s.applyEvent);
  const applySnapshot = useDigiNavStore((s) => s.applySnapshot);
  const setConnectionStatus = useDigiNavStore((s) => s.setConnectionStatus);
  const setLastError = useDigiNavStore((s) => s.setLastError);

  const [sending, setSending] = useState(false);
  const sseRef = useRef<SseClient | null>(null);

  const rehydrateWorkflow = useCallback(async () => {
    const active = useDigiNavStore.getState().workflow;
    if (!active?.workflowId) return;
    try {
      const snapshot = await getWorkflow(active.workflowId);
      applySnapshot(snapshot);
    } catch {
      // Snapshot restore is best-effort; SSE will continue live updates.
    }
  }, [applySnapshot]);

  useEffect(() => {
    if (!hydrated) return;

    const client = new SseClient({
      sessionId,
      onEvent: (event) => applyEvent(event),
      onStatus: (status) => {
        setConnectionStatus(status);
        if (status === "connected") {
          void rehydrateWorkflow();
        }
      },
    });
    sseRef.current = client;
    client.connect();

    return () => {
      client.close();
      sseRef.current = null;
    };
  }, [
    applyEvent,
    hydrated,
    rehydrateWorkflow,
    sessionId,
    setConnectionStatus,
  ]);

  async function sendMessage(message: string) {
    const text = message.trim();
    if (!text) return;

    const messageId = newId();
    addUserMessage({
      id: messageId,
      role: "user",
      content: text,
      createdAt: new Date().toISOString(),
    });

    setSending(true);
    setLastError(null);
    try {
      const response = await postChat({
        sessionId,
        messageId,
        message: text,
      });
      if (response.workflowId) {
        // Seed a placeholder until workflow_started arrives over SSE.
        const current = useDigiNavStore.getState().workflow;
        if (!current || current.workflowId !== response.workflowId) {
          try {
            const snapshot = await getWorkflow(response.workflowId);
            applySnapshot(snapshot);
          } catch {
            // Ignore; SSE workflow_started will populate shortly.
          }
        }
      }
    } catch (error) {
      const messageText =
        error instanceof Error ? error.message : "Failed to send message";
      setLastError(messageText);
    } finally {
      setSending(false);
    }
  }

  async function handleApproval(approved: boolean) {
    const active = useDigiNavStore.getState().workflow;
    if (!active?.workflowId) return;

    try {
      await resumeWorkflow({
        workflowId: active.workflowId,
        approved,
        approvalId: active.approvalId ?? undefined,
      });
    } catch (error) {
      const messageText =
        error instanceof Error ? error.message : "Approval failed";
      setLastError(messageText);
    }
  }

  async function handleSampleFlow() {
    await sendMessage("Incorporate my private limited company");
  }

  if (!hydrated) {
    return (
      <main className="grid h-screen grid-cols-1 md:grid-cols-2">
        <SkeletonChat />
        <SkeletonDashboard />
      </main>
    );
  }

  return (
    <main className="flex h-screen flex-col">
      <ReconnectBanner status={connectionStatus} error={lastError} />
      <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-2">
        <ChatPanel
          sending={sending}
          onSend={sendMessage}
          onSampleFlow={handleSampleFlow}
        />
        <WorkflowDashboard
          sending={sending}
          onApprove={handleApproval}
          onStartFlow={sendMessage}
        />
      </div>
    </main>
  );
}
