"use client";

import { FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  getAdminEvents,
  getAdminStats,
  type AdminEvent,
  type AdminStats,
} from "@/lib/api";

export default function AdminPage() {
  const [token, setToken] = useState("");
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [events, setEvents] = useState<AdminEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const [nextStats, nextEvents] = await Promise.all([
        getAdminStats(token),
        getAdminEvents(token),
      ]);
      setStats(nextStats);
      setEvents(nextEvents.events);
    } catch (err) {
      setStats(null);
      setEvents([]);
      setError(err instanceof Error ? err.message : "Failed to load admin data");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-4xl px-4 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">DigiNav Admin</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Secret-gated analytics for pilot sessions. No PII is stored.
      </p>

      <form onSubmit={load} className="mt-6 flex flex-wrap items-end gap-2">
        <label className="flex min-w-[16rem] flex-1 flex-col gap-1 text-sm">
          <span className="text-muted-foreground">Admin token</span>
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            className="rounded-md border border-input bg-background px-3 py-2 outline-none focus-visible:ring-2 focus-visible:ring-ring"
            placeholder="X-Admin-Token"
            required
          />
        </label>
        <Button type="submit" disabled={loading || !token.trim()}>
          {loading ? "Loading…" : "Load"}
        </Button>
      </form>

      {error ? (
        <p className="mt-4 text-sm text-destructive">{error}</p>
      ) : null}

      {stats ? (
        <section className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[
            ["Sessions", stats.sessions],
            ["Workflows started", stats.workflowsStarted],
            ["Completed", stats.workflowsCompleted],
            ["Failed", stats.workflowsFailed],
            ["Awaiting human", stats.workflowsAwaitingHuman],
          ].map(([label, value]) => (
            <div
              key={String(label)}
              className="rounded-lg border border-border bg-background px-4 py-3"
            >
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="mt-1 text-2xl font-semibold">{value}</p>
            </div>
          ))}
        </section>
      ) : null}

      {events.length > 0 ? (
        <section className="mt-8">
          <h2 className="text-base font-semibold">Last 50 events</h2>
          <div className="mt-3 overflow-x-auto rounded-lg border border-border">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-muted/50 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">Time</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Flow</th>
                  <th className="px-3 py-2">Session</th>
                </tr>
              </thead>
              <tbody>
                {events.map((item) => (
                  <tr key={item.id} className="border-t border-border">
                    <td className="px-3 py-2 whitespace-nowrap">
                      {item.createdAt
                        ? new Date(item.createdAt).toLocaleString()
                        : "—"}
                    </td>
                    <td className="px-3 py-2">{item.eventType}</td>
                    <td className="px-3 py-2">{item.flowId ?? "—"}</td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {item.sessionId.slice(0, 8)}…
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </main>
  );
}
