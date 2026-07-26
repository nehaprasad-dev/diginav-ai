"use client";

import { Button } from "@/components/ui/button";

interface HumanApprovalGateProps {
  prompt: string;
  busy?: boolean;
  onApprove: () => void;
  onReject: () => void;
}

export function HumanApprovalGate({
  prompt,
  busy,
  onApprove,
  onReject,
}: HumanApprovalGateProps) {
  return (
    <div className="rounded-lg border border-status-blocked/40 bg-status-blocked/5 p-4">
      <p className="text-sm font-medium text-foreground">Approval needed</p>
      <p className="mt-1 text-sm text-muted-foreground">{prompt}</p>
      <div className="mt-3 flex gap-2">
        <Button type="button" disabled={busy} onClick={onApprove}>
          Approve
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={busy}
          onClick={onReject}
        >
          Reject
        </Button>
      </div>
    </div>
  );
}
