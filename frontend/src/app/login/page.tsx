"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, setAuth, isAuthenticated } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [pin, setPin] = useState("");
  const [setupMode, setSetupMode] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isAuthenticated()) { router.replace("/dashboard"); return; }
    apiFetch("/api/auth/status").then((d) => setSetupMode(d.setup_required)).catch(() => {});
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const endpoint = setupMode ? "/api/auth/setup" : "/api/auth/login";
      const data = await apiFetch(endpoint, {
        method: "POST",
        body: JSON.stringify({ username, pin }),
      });
      setAuth(data.token, data.username, data.role);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center text-white font-bold text-2xl mx-auto mb-4 shadow-lg shadow-blue-600/20">
            I
          </div>
          <h1 className="text-2xl font-bold text-white">The I</h1>
          <p className="text-sm text-zinc-400 mt-1">Intelligent Video Analytics</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-zinc-900 rounded-xl border border-zinc-800 p-6">
          <h2 className="text-base font-semibold text-white mb-1">
            {setupMode ? "First-Time Setup" : "Sign In"}
          </h2>
          {setupMode && (
            <p className="text-xs text-zinc-400 mb-4">Create your admin account.</p>
          )}

          <div className="space-y-3 mt-4">
            <Input
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
            />
            <Input
              type="password"
              placeholder="PIN (4+ characters)"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              autoComplete="current-password"
            />
          </div>

          {error && <p className="text-xs text-red-400 mt-2">{error}</p>}

          <Button type="submit" disabled={loading} className="w-full mt-4">
            {loading ? "..." : setupMode ? "Create Admin Account" : "Sign In"}
          </Button>
        </form>

        <div className="mt-4 p-3 bg-amber-950/30 border border-amber-800/40 rounded-lg">
          <p className="text-xs text-amber-400/80">
            <strong>HIPAA Notice:</strong> This system processes PHI. All access is logged.
          </p>
        </div>
      </div>
    </div>
  );
}
