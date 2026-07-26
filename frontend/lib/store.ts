/**
 * Zustand store for chat, workflow, and connection state.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

import type {
  AgentEvent,
  ChatMessage,
  FlowId,
  StepStatus,
  WorkflowSnapshot,
  WorkflowStatus,
} from "./types";
import type { ConnectionStatus } from "./sse";

export interface WorkflowStepState {
  idx: number;
  id: string;
  title: string;
  status: StepStatus;
  subStatus?: string | null;
  requiresHuman?: boolean;
  startedAt?: string | null;
  endedAt?: string | null;
}

export interface ActiveWorkflow {
  workflowId: string;
  flowId: FlowId;
  status: WorkflowStatus;
  currentStepIdx: number;
  steps: WorkflowStepState[];
  output?: Record<string, unknown> | null;
  awaitingPrompt?: string | null;
  approvalId?: string | null;
  awaitingStepIdx?: number | null;
}

interface DigiNavState {
  sessionId: string;
  messages: ChatMessage[];
  workflow: ActiveWorkflow | null;
  connectionStatus: ConnectionStatus;
  lastError: string | null;
  hydrated: boolean;

  setHydrated: (value: boolean) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  setLastError: (message: string | null) => void;
  addUserMessage: (message: ChatMessage) => void;
  applyEvent: (event: AgentEvent) => void;
  applySnapshot: (snapshot: WorkflowSnapshot) => void;
  clearWorkflow: () => void;
  resetSession: () => void;
}

function createSessionId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function upsertStreamingMessage(
  messages: ChatMessage[],
  messageId: string,
  text: string,
): ChatMessage[] {
  const index = messages.findIndex((m) => m.id === messageId);
  if (index === -1) {
    return [
      ...messages,
      {
        id: messageId,
        role: "assistant",
        content: text,
        createdAt: new Date().toISOString(),
        streaming: true,
      },
    ];
  }

  const next = [...messages];
  const current = next[index];
  next[index] = {
    ...current,
    content: `${current.content}${text}`,
    streaming: true,
  };
  return next;
}

function finalizeStreaming(messages: ChatMessage[]): ChatMessage[] {
  return messages.map((m) =>
    m.streaming ? { ...m, streaming: false } : m,
  );
}

export const useDigiNavStore = create<DigiNavState>()(
  persist(
    (set, get) => ({
      sessionId: createSessionId(),
      messages: [],
      workflow: null,
      connectionStatus: "disconnected",
      lastError: null,
      hydrated: false,

      setHydrated: (value) => set({ hydrated: value }),

      setConnectionStatus: (status) => set({ connectionStatus: status }),

      setLastError: (message) => set({ lastError: message }),

      addUserMessage: (message) =>
        set((state) => ({
          messages: [...state.messages, message],
          lastError: null,
        })),

      applySnapshot: (snapshot) => {
        set({
          workflow: {
            workflowId: snapshot.workflowId,
            flowId: snapshot.flowId,
            status: snapshot.status,
            currentStepIdx: snapshot.currentStepIdx,
            steps: snapshot.steps.map((step) => ({
              idx: step.idx,
              id: step.id,
              title: step.title,
              status: step.status,
              subStatus: step.subStatus,
              startedAt: step.startedAt,
              endedAt: step.endedAt,
            })),
            output: snapshot.output,
            awaitingPrompt:
              snapshot.status === "awaiting_human"
                ? snapshot.steps.find(
                    (s) => s.status === "blocked_awaiting_human",
                  )?.title ?? "Approve to continue"
                : null,
            approvalId: null,
            awaitingStepIdx:
              snapshot.status === "awaiting_human"
                ? snapshot.currentStepIdx
                : null,
          },
        });
      },

      clearWorkflow: () => set({ workflow: null }),

      resetSession: () =>
        set({
          sessionId: createSessionId(),
          messages: [],
          workflow: null,
          lastError: null,
        }),

      applyEvent: (event) => {
        switch (event.type) {
          case "token": {
            set((state) => ({
              messages: upsertStreamingMessage(
                state.messages,
                event.messageId,
                event.text,
              ),
            }));
            break;
          }
          case "intent_detected": {
            // Intent is informational; workflow_started seeds the dashboard.
            break;
          }
          case "workflow_started": {
            set((state) => ({
              messages: finalizeStreaming(state.messages),
              workflow: {
                workflowId: event.workflowId,
                flowId: event.flow,
                status: "running",
                currentStepIdx: 0,
                steps: event.steps.map((step) => ({
                  idx: step.idx,
                  id: step.id,
                  title: step.title,
                  status: "pending" as StepStatus,
                  requiresHuman: step.requiresHuman,
                })),
                output: null,
                awaitingPrompt: null,
                approvalId: null,
                awaitingStepIdx: null,
              },
            }));
            break;
          }
          case "step_update": {
            const current = get().workflow;
            if (!current || current.workflowId !== event.workflowId) return;

            const steps = current.steps.map((step) =>
              step.idx === event.stepIdx
                ? {
                    ...step,
                    status: event.status,
                    subStatus: event.subStatus ?? step.subStatus,
                  }
                : step,
            );

            set({
              workflow: {
                ...current,
                currentStepIdx: event.stepIdx,
                steps,
                status:
                  event.status === "blocked_awaiting_human"
                    ? "awaiting_human"
                    : current.status === "awaiting_human" &&
                        event.status === "completed"
                      ? "running"
                      : current.status,
              },
            });
            break;
          }
          case "awaiting_human": {
            const current = get().workflow;
            if (!current || current.workflowId !== event.workflowId) return;
            set({
              workflow: {
                ...current,
                status: "awaiting_human",
                awaitingPrompt: event.prompt,
                approvalId: event.approvalId ?? null,
                awaitingStepIdx: event.stepIdx,
              },
            });
            break;
          }
          case "workflow_completed": {
            const current = get().workflow;
            if (!current || current.workflowId !== event.workflowId) return;
            set((state) => ({
              messages: finalizeStreaming(state.messages),
              workflow: {
                ...current,
                status: "completed",
                output: event.output,
                awaitingPrompt: null,
                approvalId: null,
                awaitingStepIdx: null,
              },
            }));
            break;
          }
          case "error": {
            set((state) => ({
              messages: finalizeStreaming(state.messages),
              lastError: event.message,
              workflow: state.workflow
                ? {
                    ...state.workflow,
                    status: event.recoverable
                      ? state.workflow.status
                      : "failed",
                    awaitingPrompt: event.recoverable
                      ? state.workflow.awaitingPrompt
                      : null,
                  }
                : null,
            }));
            break;
          }
          default:
            break;
        }
      },
    }),
    {
      name: "diginav-session",
      partialize: (state) => ({
        sessionId: state.sessionId,
        messages: state.messages.map((m) => ({
          ...m,
          streaming: false,
        })),
        workflow: state.workflow
          ? {
              ...state.workflow,
              // approvalId is only valid for the live process; keep prompt.
            }
          : null,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHydrated(true);
      },
    },
  ),
);
