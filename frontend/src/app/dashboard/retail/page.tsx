"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { Card, StatCard } from "@/components/ui/card";

export default function RetailPage() {
  const [stores, setStores] = useState<any[]>([]);
  const [exceptions, setExceptions] = useState<any[]>([]);

  useEffect(() => {
    apiFetch("/api/retail/stores").then(setStores).catch(() => {});
    apiFetch("/api/pos/exceptions").then(setExceptions).catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Retail Analytics</h1>

      <h2 className="text-lg font-semibold mb-3">Stores</h2>
      {stores.length === 0 ? (
        <Card className="text-center py-6 text-zinc-500 mb-6">No stores configured. Use the API to create one.</Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          {stores.map((s) => (
            <Card key={s.store_id}>
              <div className="text-sm font-medium">{s.name}</div>
              <div className="text-xs text-zinc-500">
                Capacity: {s.capacity} &middot; POS: {s.pos_system} &middot; Zones: {s.zones}
              </div>
            </Card>
          ))}
        </div>
      )}

      <h2 className="text-lg font-semibold mb-3">POS Exceptions (Today)</h2>
      {exceptions.length === 0 ? (
        <Card className="text-center py-6 text-zinc-500">No exceptions today.</Card>
      ) : (
        <div className="space-y-2">
          {exceptions.map((e, i) => (
            <Card key={i} className="flex items-center justify-between">
              <div>
                <span className={`text-xs font-medium ${e.severity === "high" ? "text-red-400" : e.severity === "medium" ? "text-amber-400" : "text-zinc-400"}`}>
                  {e.type}
                </span>
                <p className="text-sm mt-0.5">{e.reason}</p>
              </div>
              <span className="text-xs text-zinc-500">{e.transaction?.register_id}</span>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
