"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { Card, StatCard } from "@/components/ui/card";

export default function DashboardPage() {
  const [status, setStatus] = useState<any>(null);

  useEffect(() => {
    apiFetch("/api/system/status").then(setStatus).catch(() => {});
  }, []);

  if (!status) return <p className="text-zinc-500">Loading...</p>;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Version" value={status.version} />
        <StatCard label="Cameras" value={`${status.cameras?.connected || 0}/${status.cameras?.total || 0}`} />
        <StatCard label="Search Events" value={status.search_index?.total_events || 0} />
        <StatCard label="Encrypted Results" value={status.storage?.encrypted_results || 0} />
      </div>

      <h2 className="text-lg font-semibold mb-3">Domains</h2>
      <div className="grid grid-cols-3 gap-4 mb-6">
        {Object.entries(status.domains || {}).map(([name, info]: [string, any]) => (
          <Card key={name}>
            <div className="text-xs text-zinc-500 uppercase">{name}</div>
            <div className="text-sm font-medium text-green-400 mt-1">{info.status}</div>
            <div className="text-xs text-zinc-500 mt-0.5">{info.endpoints} endpoints</div>
          </Card>
        ))}
      </div>

      {status.resources?.cpu_percent !== undefined && (
        <>
          <h2 className="text-lg font-semibold mb-3">Resources</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="CPU" value={`${status.resources.cpu_percent}%`} />
            <StatCard label="Memory" value={`${status.resources.memory_used_gb}/${status.resources.memory_total_gb} GB`} />
            <StatCard label="Disk" value={`${status.resources.disk_used_gb}/${status.resources.disk_total_gb} GB`} />
            <StatCard label="Python" value={status.python} />
          </div>
        </>
      )}
    </div>
  );
}
