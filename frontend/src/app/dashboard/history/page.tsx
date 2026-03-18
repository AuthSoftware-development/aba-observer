"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { formatTime } from "@/lib/utils";

export default function HistoryPage() {
  const [items, setItems] = useState<any[]>([]);

  useEffect(() => { loadHistory(); }, []);

  async function loadHistory() {
    try { setItems(await apiFetch("/api/history")); } catch {}
  }

  async function deleteItem(filename: string) {
    if (!confirm("Delete this analysis?")) return;
    await apiFetch(`/api/history/${filename}`, { method: "DELETE" });
    loadHistory();
  }

  async function downloadReport(filename: string) {
    try {
      const blob = await apiFetch(`/api/aba/report/${filename}`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = `report_${filename.replace(".enc", "")}.pdf`; a.click();
    } catch (err: any) {
      alert("Report error: " + err.message);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Data History</h1>
        <Button variant="secondary" size="sm" onClick={loadHistory}>Refresh</Button>
      </div>

      {items.length === 0 ? (
        <Card className="text-center py-10 text-zinc-500">No collected data yet.</Card>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <Card key={item.filename} className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium">{formatTime(item.analyzed_at)}</div>
                <div className="text-xs text-zinc-500">
                  {item.setting || "Session"} &middot; {item.events} events &middot; {item.chains} chains &middot; {item.provider}
                  {item.analyzed_by ? ` &middot; by ${item.analyzed_by}` : ""}
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" onClick={() => downloadReport(item.filename)}>PDF</Button>
                <Button variant="danger" size="sm" onClick={() => deleteItem(item.filename)}>Delete</Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
