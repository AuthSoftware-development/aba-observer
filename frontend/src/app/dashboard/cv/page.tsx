"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, StatCard } from "@/components/ui/card";
import { Select } from "@/components/ui/input";

export default function CVPage() {
  const [file, setFile] = useState<File | null>(null);
  const [confidence, setConfidence] = useState("0.5");
  const [fps, setFps] = useState("2");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any>(null);

  async function handleAnalyze() {
    if (!file) return;
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("video", file);
      fd.append("confidence", confidence);
      fd.append("sample_fps", fps);
      const data = await apiFetch("/api/cv/analyze", { method: "POST", body: fd });
      setResults(data);
    } catch {}
    setLoading(false);
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">CV Analytics</h1>

      <Card className="mb-6">
        <h2 className="text-sm font-semibold mb-1">Person Detection & Tracking</h2>
        <p className="text-xs text-zinc-500 mb-4">CPU-only, no cloud — all processing stays on this device.</p>

        <label className="block border-2 border-dashed border-zinc-700 rounded-lg p-8 text-center cursor-pointer hover:border-blue-500 transition-colors mb-4">
          <p className="text-sm text-zinc-400">{file ? `${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)` : "Drop video for CV analysis"}</p>
          <input type="file" accept="video/*" className="hidden" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </label>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-xs text-zinc-500">Confidence:</label>
            <Select value={confidence} onChange={(e) => setConfidence(e.target.value)} className="w-28">
              <option value="0.3">Low (0.3)</option>
              <option value="0.4">Medium (0.4)</option>
              <option value="0.5">Default (0.5)</option>
              <option value="0.7">High (0.7)</option>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-zinc-500">Sample FPS:</label>
            <Select value={fps} onChange={(e) => setFps(e.target.value)} className="w-24">
              <option value="1">1 fps</option>
              <option value="2">2 fps</option>
              <option value="5">5 fps</option>
              <option value="10">10 fps</option>
            </Select>
          </div>
          <Button onClick={handleAnalyze} disabled={!file || loading} className="ml-auto">
            {loading ? "Analyzing..." : "Analyze"}
          </Button>
        </div>
      </Card>

      {results && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Unique People" value={results.summary.total_unique_people} />
            <StatCard label="Max Concurrent" value={results.summary.max_concurrent_people} />
            <StatCard label="Avg Per Frame" value={results.summary.avg_people_per_frame} />
            <StatCard label="Frames Analyzed" value={results.video_info.frames_analyzed} />
          </div>

          <Card>
            <h3 className="text-sm font-semibold mb-2">Person Count Over Time</h3>
            <div className="flex items-end h-24 gap-px">
              {results.timeline.map((t: any, i: number) => {
                const max = Math.max(...results.timeline.map((s: any) => s.person_count), 1);
                const h = t.person_count > 0 ? Math.max(8, (t.person_count / max) * 100) : 0;
                return <div key={i} className="flex-1 bg-blue-500/70 rounded-t-sm" style={{ height: `${h}%` }} title={`t=${t.timestamp}s: ${t.person_count}`} />;
              })}
            </div>
            <div className="flex justify-between text-[10px] text-zinc-500 mt-1">
              <span>0s</span>
              <span>{results.video_info.duration_seconds}s</span>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
