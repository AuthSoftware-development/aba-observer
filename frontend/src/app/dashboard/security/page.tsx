"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { Card } from "@/components/ui/card";

export default function SecurityPage() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [rules, setRules] = useState<any[]>([]);
  const [accessEvents, setAccessEvents] = useState<any[]>([]);

  useEffect(() => {
    apiFetch("/api/security/alerts/history").then(setAlerts).catch(() => {});
    apiFetch("/api/security/alerts").then(setRules).catch(() => {});
    apiFetch("/api/access-control/events").then(setAccessEvents).catch(() => {});
  }, []);

  const severityColor = (s: string) =>
    s === "high" ? "text-red-400 bg-red-400/10" : s === "medium" ? "text-amber-400 bg-amber-400/10" : "text-zinc-400 bg-zinc-400/10";

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Security</h1>

      <h2 className="text-lg font-semibold mb-3">Alert Rules ({rules.length})</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
        {rules.map((r) => (
          <Card key={r.rule_id}>
            <div className="flex justify-between">
              <span className="text-sm font-medium">{r.name}</span>
              <span className={`text-xs px-2 py-0.5 rounded ${r.enabled ? "bg-green-400/10 text-green-400" : "bg-zinc-700 text-zinc-400"}`}>
                {r.enabled ? "Active" : "Disabled"}
              </span>
            </div>
            <div className="text-xs text-zinc-500 mt-1">
              Trigger: {r.event_type} &middot; Min severity: {r.severity_min} &middot; Notify: {(r.notify || []).join(", ")}
            </div>
          </Card>
        ))}
        {rules.length === 0 && <Card className="text-center py-6 text-zinc-500">No alert rules configured.</Card>}
      </div>

      <h2 className="text-lg font-semibold mb-3">Recent Alerts ({alerts.length})</h2>
      <div className="space-y-2 mb-6">
        {alerts.slice(0, 20).map((a, i) => (
          <Card key={i}>
            <div className="flex justify-between items-start">
              <span className={`text-xs font-medium px-2 py-0.5 rounded ${severityColor(a.event?.severity)}`}>
                {(a.event?.type || "").replace(/_/g, " ")}
              </span>
              <span className="text-xs text-zinc-500">
                {a.fired_at ? new Date(a.fired_at * 1000).toLocaleTimeString() : ""}
              </span>
            </div>
            <p className="text-sm mt-1">{a.event?.description}</p>
            <p className="text-xs text-zinc-500 mt-0.5">Rule: {a.rule_name}</p>
          </Card>
        ))}
        {alerts.length === 0 && <Card className="text-center py-6 text-zinc-500">No alerts fired.</Card>}
      </div>

      <h2 className="text-lg font-semibold mb-3">Access Events ({accessEvents.length})</h2>
      <div className="space-y-2">
        {accessEvents.slice(0, 20).map((e, i) => (
          <Card key={i} className="flex items-center justify-between">
            <div>
              <span className="text-xs font-medium text-zinc-300">{e.event_type}</span>
              <span className="text-xs text-zinc-500 ml-2">{e.door_id}</span>
              {e.person_name && <span className="text-xs text-zinc-400 ml-2">{e.person_name}</span>}
            </div>
            <span className="text-xs text-zinc-500">{e.badge_id}</span>
          </Card>
        ))}
        {accessEvents.length === 0 && <Card className="text-center py-6 text-zinc-500">No access events.</Card>}
      </div>
    </div>
  );
}
