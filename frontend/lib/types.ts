/**
 * Shared TypeScript types for the DigiNav AI frontend.
 *
 * These types mirror the backend pydantic models and define the
 * contract carried over Server-Sent Events between the FastAPI
 * backend and the Next.js UI.
 *
 * Source of truth: `.kiro/specs/diginav-mvp-chat-dashboard/design.md`
 * (section "Event Schema").
 */

/** Supported regulatory flows in the Week 1 MVP. */
export type FlowId = "incorporation" | "gst_filing" | "se_license";

/** Lifecycle status for a single workflow step. */
export type StepStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "blocked_awaiting_human";

/** Terminal status for a workflow as a whole. */
export type WorkflowStatus =
  | "running"
  | "awaiting_human"
  | "completed"
  | "failed";

/**
 * Summary of a step included in the initial `workflow_started` event so
 * the dashboard can render the full plan immediately.
 */
export interface StepSummary {
  idx: number;
  id: string;
  title: string;
  requiresHuman?: boolean;
}

/**
 * Full snapshot of a workflow as returned by
 * `GET /api/workflows/:id` (used for rehydration on refresh).
 */
export interface WorkflowSnapshot {
  workflowId: string;
  sessionId: string;
  flowId: FlowId;
  status: WorkflowStatus;
  currentStepIdx: number;
  steps: Array<{
    idx: number;
    id: string;
    title: string;
    status: StepStatus;
    subStatus?: string | null;
    startedAt?: string | null;
    endedAt?: string | null;
  }>;
  output?: Record<string, unknown> | null;
  startedAt: string;
  updatedAt: string;
  completedAt?: string | null;
}

/** Chat message persisted server-side and rendered in the chat panel. */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: string;
  /** True while assistant tokens are still streaming in. */
  streaming?: boolean;
}

/* -------------------------------------------------------------------------- */
/* AgentEvent discriminated union                                              */
/* -------------------------------------------------------------------------- */

/** A partial LLM token for the currently streaming assistant message. */
export interface TokenEvent {
  type: "token";
  /** Text delta to append to the message body. */
  text: string;
  /** ID of the assistant message the token belongs to. */
  messageId: string;
}

/** Intent classification result emitted before a workflow starts. */
export interface IntentDetectedEvent {
  type: "intent_detected";
  flow: FlowId;
  /** Classifier confidence in [0, 1]. */
  confidence: number;
}

/** Sent once a workflow has been created and is about to begin. */
export interface WorkflowStartedEvent {
  type: "workflow_started";
  workflowId: string;
  flow: FlowId;
  steps: StepSummary[];
}

/** Per-step state transition or sub-status refresh. */
export interface StepUpdateEvent {
  type: "step_update";
  workflowId: string;
  stepIdx: number;
  status: StepStatus;
  /**
   * Live one-line status (e.g. "Validating director DIN...").
   * Updated at least every 2 seconds while status is `in_progress`.
   */
  subStatus?: string;
}

/** Workflow is paused awaiting an explicit human Approve/Reject. */
export interface AwaitingHumanEvent {
  type: "awaiting_human";
  workflowId: string;
  stepIdx: number;
  /** User-facing prompt describing what needs approval. */
  prompt: string;
  /**
   * Client-supplied nonce for idempotent resume calls.
   * The frontend echoes this back in POST /api/workflows/:id/resume.
   */
  approvalId?: string;
}

/** Workflow has reached its final step successfully. */
export interface WorkflowCompletedEvent {
  type: "workflow_completed";
  workflowId: string;
  /**
   * Flow-specific output payload (e.g. `{ cin: "U72900MH..." }`,
   * `{ arn: "..." }`, `{ licenseNumber: "..." }`).
   */
  output: Record<string, unknown>;
}

/** Any error surfaced to the client over the stream. */
export interface ErrorEvent {
  type: "error";
  message: string;
  correlationId: string;
  /**
   * When true, the workflow state is preserved and the UI should
   * offer retry. When false, the workflow is marked failed.
   */
  recoverable: boolean;
}

/**
 * The discriminated union shared between the SSE transport and the
 * Zustand store reducer.
 */
export type AgentEvent =
  | TokenEvent
  | IntentDetectedEvent
  | WorkflowStartedEvent
  | StepUpdateEvent
  | AwaitingHumanEvent
  | WorkflowCompletedEvent
  | ErrorEvent;

/** Narrow an AgentEvent to a specific type. */
export function isAgentEvent<T extends AgentEvent["type"]>(
  event: AgentEvent,
  type: T,
): event is Extract<AgentEvent, { type: T }> {
  return event.type === type;
}
