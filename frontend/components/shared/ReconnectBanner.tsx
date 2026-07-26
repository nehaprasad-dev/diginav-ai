"use client";

import type { ConnectionStatus } from "@/lib/sse";

interface ReconnectBannerProps {
  status: ConnectionStatus;
  error?: string | null;
}

export function ReconnectBanner({ status, error }: ReconnectBannerProps) {
  if (status === "connected" && !error) return null;

  const message =
    error ??
    (status === "reconnecting"
      ? "Reconnecting…"
      : status === "connecting"
        ? "Connecting…"
        : status === "disconnected"
          ? "Disconnected from DigiNav"
          : null);

  if (!message) return null;

  return (
    <div className="border-b border-border bg-status-blocked/10 px-4 py-2 text-center text-xs text-foreground">
      {message}
    </div>
  );
}
