"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [domain, setDomain] = useState("");
  const [results, setResults] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { loadStats(); }, []);

  async function loadStats() {
    try { setStats(await apiFetch("/api/search/stats")); } catch {}
  }

  async function handleSearch() {
    if (!query.trim()) return;
    setLoading(true);
    try {
      setResults(await apiFetch("/api/search/natural", { method: "POST", body: JSON.stringify({ query, domain }) }));
    } catch {}
    setLoading(false);
  }

  const severityColor = (s: string) =>
    s === "high" ? "text-red-400" : s === "medium" ? "text-amber-400" : "text-zinc-400";

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Search</h1>

      <Card className="mb-6">
        <div className="flex gap-3">
          <Input
            placeholder='Natural language search (e.g., "show me all falls")'
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="flex-1"
          />
          <Select value={domain} onChange={(e) => setDomain(e.target.value)} className="w-32">
            <option value="">All</option>
            <option value="aba">ABA</option>
            <option value="retail">Retail</option>
            <option value="security">Security</option>
          </Select>
          <Button onClick={handleSearch} disabled={loading}>
            {loading ? "..." : "Search"}
          </Button>
        </div>
      </Card>

      {results && (
        <div className="space-y-2 mb-6">
          <p className="text-xs text-zinc-500">{results.total} results</p>
          {results.results.map((r: any, i: number) => (
            <Card key={i}>
              <div className="flex justify-between items-start">
                <div>
                  <span className={`text-xs font-medium ${severityColor(r.severity)}`}>
                    {(r.event_type || "").replace(/_/g, " ")}
                  </span>
                  <span className="text-xs text-blue-400 ml-2">{r.domain}</span>
                </div>
              </div>
              <p className="text-sm mt-1">{r.description}</p>
              {r.person_name && <p className="text-xs text-zinc-500 mt-1">Person: {r.person_name}</p>}
            </Card>
          ))}
        </div>
      )}

      {stats && (
        <Card>
          <h3 className="text-sm font-semibold mb-2">Index Stats</h3>
          <div className="text-xs text-zinc-400 space-y-1">
            <p>Total events: {stats.total_events}</p>
            <p>By domain: {Object.entries(stats.by_domain || {}).map(([k, v]) => `${k}: ${v}`).join(", ") || "none"}</p>
            <p>By type: {Object.entries(stats.by_type || {}).map(([k, v]) => `${k}: ${v}`).join(", ") || "none"}</p>
          </div>
        </Card>
      )}
    </div>
  );
}
