"use client";

export function SkeletonChat() {
  return (
    <div className="flex h-full flex-col gap-3 p-4">
      <div className="h-10 w-40 animate-pulse rounded bg-muted" />
      <div className="mt-6 space-y-3">
        <div className="ml-auto h-12 w-2/3 animate-pulse rounded-2xl bg-muted" />
        <div className="h-16 w-3/4 animate-pulse rounded-2xl bg-muted" />
        <div className="ml-auto h-10 w-1/2 animate-pulse rounded-2xl bg-muted" />
      </div>
    </div>
  );
}
