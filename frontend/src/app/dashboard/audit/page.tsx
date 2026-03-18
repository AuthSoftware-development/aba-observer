"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { formatTime } from "@/lib/utils";

export default function AuditPage() {
  const [events, setEvents] = useState<any[]>([]);

  useEffect(() => { loadAudit(); }, []);

  async function loadAudit() {
    try { setEvents(await apiFetch("/api/audit")); } catch {}
  }

  const actionColor: Record<string, string> = {
    login: "text-green-400", login_failed: "text-red-400", access_denied: "text-red-400",
    analyze_upload: "text-blue-400", analyze_camera: "text-blue-400",
    create_user: "text-purple-400", reset_pin: "text-amber-400",
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Audit Log</h1>
        <Button variant="secondary" size="sm" onClick={loadAudit}>Refresh</Button>
      </div>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="bg-zinc-800 text-zinc-500 uppercase tracking-wide sticky top-0">
              <tr>
                <th className="px-4 py-2 text-left">Time</th>
                <th className="px-4 py-2 text-left">Action</th>
                <th className="px-4 py-2 text-left">User</th>
                <th className="px-4 py-2 text-left">IP</th>
                <th className="px-4 py-2 text-left">Details</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e, i) => (
                <tr key={i} className="border-b border-zinc-800 hover:bg-zinc-800/50">
                  <td className="px-4 py-2 text-zinc-500 whitespace-nowrap">{formatTime(e.timestamp)}</td>
                  <td className={`px-4 py-2 font-medium ${actionColor[e.action] || "text-zinc-400"}`}>{e.action}</td>
                  <td className="px-4 py-2">{e.user}</td>
                  <td className="px-4 py-2 text-zinc-500">{e.ip}</td>
                  <td className="px-4 py-2 text-zinc-500 max-w-xs truncate">{JSON.stringify(e.details)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {events.length === 0 && <p className="p-6 text-center text-zinc-500">No audit events.</p>}
        </div>
      </Card>
    </div>
  );
}
