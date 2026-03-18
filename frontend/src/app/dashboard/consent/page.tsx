"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";

export default function ConsentPage() {
  const [consents, setConsents] = useState<any[]>([]);
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("aba");
  const [role, setRole] = useState("client");
  const [source, setSource] = useState("");
  const [guardian, setGuardian] = useState("");

  useEffect(() => { loadConsents(); }, []);

  async function loadConsents() {
    try { setConsents(await apiFetch("/api/consent")); } catch {}
  }

  async function createConsent() {
    if (!name) return;
    await apiFetch("/api/consent", {
      method: "POST",
      body: JSON.stringify({ person_name: name, domain, role, consent_source: source, guardian_name: guardian || undefined }),
    });
    setName(""); setSource(""); setGuardian("");
    loadConsents();
  }

  async function revokeConsent(id: string) {
    if (!confirm("Revoke consent and delete all face embeddings?")) return;
    await apiFetch(`/api/consent/${id}`, { method: "DELETE" });
    loadConsents();
  }

  async function enrollFace(consentId: string, files: FileList) {
    const fd = new FormData();
    for (const f of files) fd.append("photos", f);
    try {
      const r = await apiFetch(`/api/consent/${consentId}/enroll`, { method: "POST", body: fd });
      alert(`Enrolled ${r.embeddings_stored} embeddings from ${r.photos_processed} photos`);
      loadConsents();
    } catch (err: any) { alert(err.message); }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Consent Management</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-3">
          {consents.length === 0 ? (
            <Card className="text-center py-10 text-zinc-500">No consent records.</Card>
          ) : (
            consents.map((c) => (
              <Card key={c.consent_id} className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium">{c.person_name}</div>
                  <div className="text-xs text-zinc-500">
                    {c.domain}/{c.role} &middot; {c.consent_source || "N/A"} &middot;
                    {c.enrolled ? ` Enrolled (${c.embedding_count} embeddings)` : " Not enrolled"}
                    {c.guardian_name ? ` &middot; Guardian: ${c.guardian_name}` : ""}
                  </div>
                </div>
                <div className="flex gap-2 items-center">
                  {!c.enrolled && (
                    <label className="text-xs text-blue-400 cursor-pointer hover:text-blue-300">
                      Enroll
                      <input type="file" accept="image/*" multiple className="hidden"
                        onChange={(e) => e.target.files && enrollFace(c.consent_id, e.target.files)} />
                    </label>
                  )}
                  {c.enrolled && <span className="text-xs text-green-400">Enrolled</span>}
                  <Button variant="danger" size="sm" onClick={() => revokeConsent(c.consent_id)}>Revoke</Button>
                </div>
              </Card>
            ))
          )}
        </div>

        <Card>
          <h3 className="text-sm font-semibold mb-3">New Consent Record</h3>
          <div className="space-y-2">
            <Input placeholder="Person name" value={name} onChange={(e) => setName(e.target.value)} />
            <Select value={domain} onChange={(e) => setDomain(e.target.value)}>
              <option value="aba">ABA Therapy</option>
              <option value="retail">Retail</option>
              <option value="security">Security</option>
            </Select>
            <Select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="client">Client</option>
              <option value="therapist">Therapist</option>
              <option value="employee">Employee</option>
            </Select>
            <Input placeholder="Consent source (e.g., signed form)" value={source} onChange={(e) => setSource(e.target.value)} />
            <Input placeholder="Guardian name (if minor)" value={guardian} onChange={(e) => setGuardian(e.target.value)} />
            <Button onClick={createConsent} className="w-full">Create Consent</Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
