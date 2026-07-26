"use client";

import { Button } from "@/components/ui/button";
import type { FlowId } from "@/lib/types";
import type { ActiveWorkflow } from "@/lib/store";

interface Indicator {
  id: FlowId | "annual";
  label: string;
  score: number;
  detail: string;
  flowPrompt?: string;
}

interface ComplianceHealthCardProps {
  workflow: ActiveWorkflow | null;
  onStartFlow: (prompt: string) => void;
  disabled?: boolean;
}

function buildIndicators(workflow: ActiveWorkflow | null): {
  score: number;
  indicators: Indicator[];
} {
  const completedFlow = workflow?.status === "completed" ? workflow.flowId : null;
  const runningFlow =
    workflow && workflow.status !== "completed" && workflow.status !== "failed"
      ? workflow.flowId
      : null;

  const indicators: Indicator[] = [
    {
      id: "incorporation",
      label: "Incorporation",
      score:
        completedFlow === "incorporation"
          ? 95
          : runningFlow === "incorporation"
            ? 55
            : 35,
      detail:
        completedFlow === "incorporation"
          ? "Company incorporation flow completed."
          : "SPICe+ incorporation not finished yet.",
      flowPrompt: "Incorporate my private limited company",
    },
    {
      id: "gst_filing",
      label: "GST",
      score:
        completedFlow === "gst_filing"
          ? 92
          : runningFlow === "gst_filing"
            ? 50
            : 40,
      detail:
        completedFlow === "gst_filing"
          ? "Latest GSTR-3B flow completed."
          : "GST filing health needs attention.",
      flowPrompt: "File my Q4 GST return",
    },
    {
      id: "se_license",
      label: "Labor",
      score:
        completedFlow === "se_license"
          ? 90
          : runningFlow === "se_license"
            ? 48
            : 38,
      detail:
        completedFlow === "se_license"
          ? "Shops & Establishment license issued."
          : "Labor license status is incomplete.",
      flowPrompt: "Help me get a Shops & Establishment license",
    },
    {
      id: "annual",
      label: "Annual Filings",
      score: 45,
      detail: "Annual ROC filings are tracked in a later release.",
    },
  ];

  const score = Math.round(
    indicators.reduce((sum, item) => sum + item.score, 0) / indicators.length,
  );

  return { score, indicators };
}

function tone(score: number): string {
  if (score >= 80) return "text-status-success";
  if (score >= 50) return "text-status-blocked";
  return "text-destructive";
}

export function ComplianceHealthCard({
  workflow,
  onStartFlow,
  disabled,
}: ComplianceHealthCardProps) {
  const { score, indicators } = buildIndicators(workflow);

  return (
    <div className="rounded-lg border border-border bg-background p-4">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Compliance health
          </p>
          <p className={`mt-1 text-3xl font-semibold ${tone(score)}`}>{score}</p>
        </div>
        <p className="max-w-[12rem] text-right text-xs text-muted-foreground">
          Snapshot based on this session&apos;s workflow activity.
        </p>
      </div>

      <div className="mt-4 space-y-3">
        {indicators.map((item) => (
          <div key={item.id} className="space-y-1">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium">{item.label}</p>
              <p className={`text-sm font-medium ${tone(item.score)}`}>
                {item.score}
              </p>
            </div>
            <p className="text-xs text-muted-foreground">{item.detail}</p>
            {item.flowPrompt ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                disabled={disabled}
                onClick={() => onStartFlow(item.flowPrompt!)}
              >
                Start this flow
              </Button>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
