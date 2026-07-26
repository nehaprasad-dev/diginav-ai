/**
 * SSE client with exponential backoff reconnect.
 */

import { getStreamUrl } from "./api";
import type { AgentEvent } from "./types";

export type ConnectionStatus = "connecting" | "connected" | "reconnecting" | "disconnected";

export interface SseClientOptions {
  sessionId: string;
  onEvent: (event: AgentEvent) => void;
  onStatus?: (status: ConnectionStatus) => void;
  onError?: (error: Event) => void;
}

const MAX_BACKOFF_MS = 15_000;
const BASE_BACKOFF_MS = 500;

function isAgentEvent(value: unknown): value is AgentEvent {
  return (
    typeof value === "object" &&
    value !== null &&
    "type" in value &&
    typeof (value as { type: unknown }).type === "string"
  );
}

export class SseClient {
  private source: EventSource | null = null;
  private retries = 0;
  private closed = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(private readonly options: SseClientOptions) {}

  connect(): void {
    this.closed = false;
    this.open();
  }

  close(): void {
    this.closed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.source) {
      this.source.close();
      this.source = null;
    }
    this.options.onStatus?.("disconnected");
  }

  private open(): void {
    if (this.closed) return;

    if (this.source) {
      this.source.close();
      this.source = null;
    }

    this.options.onStatus?.(this.retries === 0 ? "connecting" : "reconnecting");

    const source = new EventSource(getStreamUrl(this.options.sessionId));
    this.source = source;

    source.onopen = () => {
      this.retries = 0;
      this.options.onStatus?.("connected");
    };

    source.onmessage = (message) => {
      this.handleRaw(message.data);
    };

    // Named SSE event types from the backend (`event:` field).
    const namedTypes = [
      "token",
      "intent_detected",
      "workflow_started",
      "step_update",
      "awaiting_human",
      "workflow_completed",
      "error",
    ] as const;

    for (const type of namedTypes) {
      source.addEventListener(type, (message) => {
        const data = (message as MessageEvent).data;
        this.handleRaw(typeof data === "string" ? data : String(data));
      });
    }

    source.onerror = (error) => {
      this.options.onError?.(error);
      source.close();
      this.source = null;
      if (!this.closed) {
        this.scheduleReconnect();
      }
    };
  }

  private handleRaw(raw: string): void {
    if (!raw || raw.startsWith(":")) return;
    try {
      const parsed: unknown = JSON.parse(raw);
      if (isAgentEvent(parsed)) {
        this.options.onEvent(parsed);
      }
    } catch {
      // Ignore malformed frames; keep the stream alive.
    }
  }

  private scheduleReconnect(): void {
    this.options.onStatus?.("reconnecting");
    const delay = Math.min(
      MAX_BACKOFF_MS,
      BASE_BACKOFF_MS * 2 ** this.retries,
    );
    this.retries += 1;
    this.reconnectTimer = setTimeout(() => this.open(), delay);
  }
}
