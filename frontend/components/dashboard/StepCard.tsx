"use client";

import { motion } from "framer-motion";

import { cn } from "@/lib/utils";
import type { StepStatus } from "@/lib/types";
import type { WorkflowStepState } from "@/lib/store";

interface StepCardProps {
  step: WorkflowStepState;
}

const STATUS_LABEL: Record<StepStatus, string> = {
  pending: "Pending",
  in_progress: "In progress",
  completed: "Completed",
  blocked_awaiting_human: "Awaiting approval",
};

export function StepCard({ step }: StepCardProps) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={cn(
        "rounded-lg border px-3 py-3",
        step.status === "in_progress" && "border-status-progress/40 bg-status-progress/5",
        step.status === "completed" && "border-status-success/30 bg-status-success/5",
        step.status === "blocked_awaiting_human" &&
          "border-status-blocked/40 bg-status-blocked/5",
        step.status === "pending" && "border-border bg-background",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-foreground">
            {step.idx + 1}. {step.title}
          </p>
          {step.subStatus ? (
            <p className="mt-1 text-xs text-muted-foreground">{step.subStatus}</p>
          ) : null}
        </div>
        <span
          className={cn(
            "shrink-0 text-[11px] font-medium uppercase tracking-wide",
            step.status === "in_progress" && "text-status-progress",
            step.status === "completed" && "text-status-success",
            step.status === "blocked_awaiting_human" && "text-status-blocked",
            step.status === "pending" && "text-status-pending",
          )}
        >
          {STATUS_LABEL[step.status]}
        </span>
      </div>
    </motion.div>
  );
}
