"use client";

import { useState } from "react";

import { HumanApprovalGate } from "@/components/dashboard/HumanApprovalGate";
import { StepCard } from "@/components/dashboard/StepCard";
import { ComplianceHealthCard } from "@/components/dashboard/ComplianceHealthCard";
import { Button } from "@/components/ui/button";
import { useDigiNavStore } from "@/lib/store";

interface WorkflowDashboardProps {
  onApprove: (approved: boolean) => Promise<void>;
  onStartFlow: (prompt: string) => Promise<void>;
  sending: boolean;
}

function downloadOutput(output: Record<string, unknown>, flowId: string) {
  const lines = [
    "DigiNav AI — Compliance Certificate (Demo)",
    `Flow: ${flowId}`,
    `Generated: ${new Date().toISOString()}`,
    "",
    ...Object.entries(output).map(([key, value]) => `${key}: ${String(value)}`),
    "",
    "This is a simulated demo output, not an official government document.",
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `diginav-${flowId}-certificate.txt`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function WorkflowDashboard({
  onApprove,
  onStartFlow,
  sending,
}: WorkflowDashboardProps) {
  const workflow = useDigiNavStore((s) => s.workflow);
  const [approvalBusy, setApprovalBusy] = useState(false);

  async function handleDecision(approved: boolean) {
    setApprovalBusy(true);
    try {
      await onApprove(approved);
    } finally {
      setApprovalBusy(false);
    }
  }

  return (
    <section className="flex h-full min-h-0 flex-col bg-muted/30">
      <header className="border-b border-border px-4 py-3">
        <h2 className="text-base font-semibold tracking-tight">Workflow</h2>
        <p className="text-xs text-muted-foreground">
          Live progress for the active regulatory flow
        </p>
      </header>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        <ComplianceHealthCard
          workflow={workflow}
          disabled={sending}
          onStartFlow={(prompt) => void onStartFlow(prompt)}
        />

        {!workflow ? (
          <div className="rounded-lg border border-dashed border-border bg-background px-4 py-10 text-center">
            <p className="text-sm text-muted-foreground">
              Start a chat message to launch a workflow. Progress will appear
              here in real time.
            </p>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-sm font-medium capitalize">
                  {workflow.flowId.replaceAll("_", " ")}
                </p>
                <p className="text-xs text-muted-foreground">
                  Status: {workflow.status.replaceAll("_", " ")}
                </p>
              </div>
            </div>

            <div className="space-y-2">
              {workflow.steps.map((step) => (
                <StepCard key={step.id} step={step} />
              ))}
            </div>

            {workflow.status === "awaiting_human" && workflow.awaitingPrompt ? (
              <HumanApprovalGate
                prompt={workflow.awaitingPrompt}
                busy={approvalBusy}
                onApprove={() => void handleDecision(true)}
                onReject={() => void handleDecision(false)}
              />
            ) : null}

            {workflow.status === "completed" && workflow.output ? (
              <div className="rounded-lg border border-status-success/30 bg-status-success/5 p-4">
                <p className="text-sm font-medium text-foreground">
                  Workflow completed
                </p>
                <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                  {Object.entries(workflow.output).map(([key, value]) => (
                    <li key={key}>
                      <span className="font-medium text-foreground">{key}:</span>{" "}
                      {String(value)}
                    </li>
                  ))}
                </ul>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-3"
                  onClick={() =>
                    downloadOutput(workflow.output ?? {}, workflow.flowId)
                  }
                >
                  Download certificate
                </Button>
              </div>
            ) : null}
          </>
        )}
      </div>
    </section>
  );
}
