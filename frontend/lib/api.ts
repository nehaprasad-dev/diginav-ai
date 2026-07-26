/**
 * Thin fetch wrappers for the DigiNav FastAPI backend.
 */

import type { FlowId, WorkflowSnapshot } from "./types";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function parseJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!text) {
    return {} as T;
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError("Invalid JSON response", response.status, text);
  }
}

export interface ChatResponse {
  streamUrl: string;
  workflowId: string | null;
  intent: FlowId | "general_chat";
  confidence: number;
}

export async function postChat(params: {
  sessionId: string;
  messageId: string;
  message: string;
}): Promise<ChatResponse> {
  const response = await fetch(`${BACKEND_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      sessionId: params.sessionId,
      messageId: params.messageId,
      message: params.message,
    }),
  });

  const data = await parseJson<ChatResponse & { detail?: unknown }>(response);
  if (!response.ok) {
    throw new ApiError(
      typeof data.detail === "string" ? data.detail : "Chat request failed",
      response.status,
      data,
    );
  }
  return data;
}

export async function getWorkflow(workflowId: string): Promise<WorkflowSnapshot> {
  const response = await fetch(
    `${BACKEND_URL}/api/workflows/${encodeURIComponent(workflowId)}`,
  );
  const data = await parseJson<WorkflowSnapshot & { detail?: unknown }>(response);
  if (!response.ok) {
    throw new ApiError(
      typeof data.detail === "string" ? data.detail : "Failed to load workflow",
      response.status,
      data,
    );
  }
  return data;
}

export async function resumeWorkflow(params: {
  workflowId: string;
  approved: boolean;
  approvalId?: string;
}): Promise<{ workflowId: string; status: string; accepted: boolean }> {
  const response = await fetch(
    `${BACKEND_URL}/api/workflows/${encodeURIComponent(params.workflowId)}/resume`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        approved: params.approved,
        approvalId: params.approvalId,
      }),
    },
  );

  const data = await parseJson<{
    workflowId: string;
    status: string;
    accepted: boolean;
    detail?: unknown;
  }>(response);

  if (!response.ok) {
    throw new ApiError(
      typeof data.detail === "string" ? data.detail : "Resume failed",
      response.status,
      data,
    );
  }
  return data;
}

export interface AdminStats {
  sessions: number;
  workflowsStarted: number;
  workflowsCompleted: number;
  workflowsFailed: number;
  workflowsAwaitingHuman: number;
}

export interface AdminEvent {
  id: number;
  sessionId: string;
  eventType: string;
  flowId: string | null;
  promptHash: string | null;
  durationMs: number | null;
  metadata: Record<string, unknown> | null;
  createdAt: string | null;
}

export async function getAdminStats(token: string): Promise<AdminStats> {
  const response = await fetch(`${BACKEND_URL}/api/admin/stats`, {
    headers: { "X-Admin-Token": token },
  });
  const data = await parseJson<AdminStats & { detail?: unknown }>(response);
  if (!response.ok) {
    throw new ApiError(
      typeof data.detail === "string" ? data.detail : "Admin stats failed",
      response.status,
      data,
    );
  }
  return data;
}

export async function getAdminEvents(
  token: string,
): Promise<{ events: AdminEvent[] }> {
  const response = await fetch(`${BACKEND_URL}/api/admin/events`, {
    headers: { "X-Admin-Token": token },
  });
  const data = await parseJson<{ events: AdminEvent[]; detail?: unknown }>(
    response,
  );
  if (!response.ok) {
    throw new ApiError(
      typeof data.detail === "string" ? data.detail : "Admin events failed",
      response.status,
      data,
    );
  }
  return data;
}

export function getBackendUrl(): string {
  return BACKEND_URL;
}

export function getStreamUrl(sessionId: string): string {
  return `${BACKEND_URL}/api/stream/${encodeURIComponent(sessionId)}`;
}
