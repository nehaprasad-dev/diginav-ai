"use client";

export function SkeletonDashboard() {
  return (
    <div className="space-y-3 p-4">
      <div className="h-28 animate-pulse rounded-lg bg-muted" />
      <div className="h-16 animate-pulse rounded-lg bg-muted" />
      <div className="h-16 animate-pulse rounded-lg bg-muted" />
      <div className="h-16 animate-pulse rounded-lg bg-muted" />
    </div>
  );
}
