"use client";

import { useState, useEffect } from "react";
import { apiFetch, getToken } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, StatCard } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { formatDuration } from "@/lib/utils";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [provider, setProvider] = useState("gemini");
  const [providers, setProviders] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch("/api/providers").then(setProviders).catch(() => {});
  }, []);

  async function handleAnalyze() {
    if (!file) return;
    setLoading(true);
    setError("");
    setResults(null);
    try {
      const fd = new FormData();
      fd.append("video", file);
      fd.append("provider", provider);
      const data = await apiFetch("/api/analyze", { method: "POST", body: fd });
      setResults(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const r = results?.results || results;
  const session = r?.session_summary || {};

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Upload & Analyze</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <h2 className="text-sm font-semibold mb-4">Upload Session Video</h2>
          <label className="block border-2 border-dashed border-zinc-700 rounded-lg p-10 text-center cursor-pointer hover:border-blue-500 transition-colors">
            <p className="text-sm text-zinc-400">{file ? `${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)` : "Drop video or click to browse"}</p>
            <input type="file" accept="video/*" className="hidden" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </label>

          <div className="flex items-center gap-4 mt-4">
            <Select value={provider} onChange={(e) => setProvider(e.target.value)} className="w-48">
              {providers.map((p) => (
                <option key={p.name} value={p.name} disabled={!p.available}>
                  {p.label} {p.available ? "" : "(unavailable)"}
                </option>
              ))}
            </Select>
            <Button onClick={handleAnalyze} disabled={!file || loading}>
              {loading ? "Analyzing..." : "Analyze"}
            </Button>
          </div>
          {error && <p className="text-xs text-red-400 mt-2">{error}</p>}
        </Card>

        <Card>
          <h3 className="text-sm font-semibold mb-2">Provider Status</h3>
          {providers.map((p) => (
            <div key={p.name} className="flex items-center gap-2 py-1">
              <span className={`w-2 h-2 rounded-full ${p.available ? "bg-green-500" : "bg-red-400"}`} />
              <span className="text-xs text-zinc-300">{p.label}</span>
            </div>
          ))}
          {providers.some((p) => p.name === "gemini" && p.available) && (
            <p className="text-[10px] text-amber-400 mt-2">Gemini sends video to Google — use local provider for real PHI.</p>
          )}
        </Card>
      </div>

      {r && (
        <div className="mt-6 space-y-4">
          <h2 className="text-lg font-semibold">Results</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Setting" value={session.setting || "N/A"} />
            <StatCard label="Duration" value={session.duration_seconds ? formatDuration(session.duration_seconds) : "N/A"} />
            <StatCard label="Events" value={r.events?.length || 0} />
            <StatCard label="ABC Chains" value={r.abc_chains?.length || 0} />
          </div>

          {r.abc_chains?.length > 0 && (
            <Card>
              <h3 className="text-sm font-semibold mb-3">ABC Chains</h3>
              {r.abc_chains.map((ch: any, i: number) => (
                <div key={i} className="grid grid-cols-3 gap-3 mb-3">
                  <div className="bg-blue-950/30 rounded-lg p-3">
                    <div className="text-xs font-bold text-blue-400 mb-1">Antecedent</div>
                    <div className="text-xs">[{ch.antecedent?.timestamp}] {ch.antecedent?.description}</div>
                  </div>
                  <div className="bg-amber-950/30 rounded-lg p-3">
                    <div className="text-xs font-bold text-amber-400 mb-1">Behavior</div>
                    <div className="text-xs">[{ch.behavior?.timestamp}] {ch.behavior?.description}</div>
                  </div>
                  <div className="bg-green-950/30 rounded-lg p-3">
                    <div className="text-xs font-bold text-green-400 mb-1">Consequence</div>
                    <div className="text-xs">[{ch.consequence?.timestamp}] {ch.consequence?.description}</div>
                  </div>
                </div>
              ))}
            </Card>
          )}

          {r.frequency_summary && Object.keys(r.frequency_summary).length > 0 && (
            <Card>
              <h3 className="text-sm font-semibold mb-3">Behavior Frequencies</h3>
              {Object.entries(r.frequency_summary).map(([behavior, val]: [string, any]) => {
                const count = typeof val === "object" ? val.count : val;
                return (
                  <div key={behavior} className="flex items-center justify-between py-1.5 border-b border-zinc-800 last:border-0">
                    <span className="text-xs capitalize">{behavior.replace(/_/g, " ")}</span>
                    <span className="text-xs font-mono text-zinc-400">{count}</span>
                  </div>
                );
              })}
            </Card>
          )}

          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={() => {
              const blob = new Blob([JSON.stringify(results, null, 2)], { type: "application/json" });
              const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "analysis.json"; a.click();
            }}>Download JSON</Button>
            <Button variant="secondary" size="sm" onClick={() => {
              const events = r.events || [];
              const headers = ["timestamp", "event_type", "category", "description"];
              const csv = [headers.join(","), ...events.map((e: any) => headers.map((h) => `"${(e[h] || "").toString().replace(/"/g, '""')}"`).join(","))].join("\n");
              const blob = new Blob([csv], { type: "text/csv" });
              const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "events.csv"; a.click();
            }}>Download CSV</Button>
          </div>
        </div>
      )}
    </div>
  );
}
