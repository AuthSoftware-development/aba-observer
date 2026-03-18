"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, StatCard } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";

export default function SettingsPage() {
  const [username, setUsername] = useState("");
  const [pin, setPin] = useState("");
  const [role, setRole] = useState("rbt");
  const [createMsg, setCreateMsg] = useState("");
  const [compliance, setCompliance] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);

  useEffect(() => {
    apiFetch("/api/compliance").then(setCompliance).catch(() => {});
    apiFetch("/api/system/status").then(setStatus).catch(() => {});
  }, []);

  async function createUser() {
    if (!username || pin.length < 4) { setCreateMsg("Username + PIN 4+ required"); return; }
    try {
      const r = await apiFetch("/api/auth/create-user", {
        method: "POST", body: JSON.stringify({ username, pin, role }),
      });
      setCreateMsg(`Created ${r.created} (${r.role})`);
      setUsername(""); setPin("");
    } catch (err: any) { setCreateMsg(err.message); }
  }

  async function toggleCompliance(mode: string, enabled: boolean) {
    try {
      await apiFetch(`/api/compliance/${mode}`, { method: "PUT", body: JSON.stringify({ enabled }) });
      const updated = await apiFetch("/api/compliance");
      setCompliance(updated);
    } catch {}
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Settings</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <h2 className="text-sm font-semibold mb-4">Create User</h2>
          <div className="space-y-2">
            <Input placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
            <Input type="password" placeholder="PIN (4+ chars)" value={pin} onChange={(e) => setPin(e.target.value)} />
            <Select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="rbt">RBT</option>
              <option value="bcba">BCBA</option>
              <option value="admin">Admin</option>
            </Select>
            <Button onClick={createUser} className="w-full">Create User</Button>
          </div>
          {createMsg && <p className="text-xs mt-2 text-zinc-400">{createMsg}</p>}
        </Card>

        <Card>
          <h2 className="text-sm font-semibold mb-4">Compliance Modes</h2>
          {compliance && Object.entries(compliance).map(([mode, cfg]: [string, any]) => (
            <div key={mode} className="flex items-center justify-between py-2 border-b border-zinc-800 last:border-0">
              <div>
                <div className="text-sm font-medium">{mode.toUpperCase()}</div>
                <div className="text-[10px] text-zinc-500">{cfg.description}</div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  className="sr-only peer"
                  checked={cfg.enabled}
                  onChange={(e) => toggleCompliance(mode, e.target.checked)}
                />
                <div className="w-9 h-5 bg-zinc-700 peer-checked:bg-blue-600 rounded-full after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-full" />
              </label>
            </div>
          ))}
        </Card>

        {status && (
          <Card className="lg:col-span-2">
            <h2 className="text-sm font-semibold mb-4">System</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatCard label="Version" value={status.version} />
              <StatCard label="Python" value={status.python} />
              <StatCard label="OS" value={status.os} />
              <StatCard label="Endpoints" value="78" />
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
