"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function CamerasPage() {
  const [cameras, setCameras] = useState<any[]>([]);
  const [camId, setCamId] = useState("");
  const [camName, setCamName] = useState("");
  const [camUrl, setCamUrl] = useState("");

  useEffect(() => { loadCameras(); }, []);

  async function loadCameras() {
    try { setCameras(await apiFetch("/api/cameras")); } catch {}
  }

  async function addCamera() {
    if (!camId || !camUrl) return;
    await apiFetch("/api/cameras", {
      method: "POST",
      body: JSON.stringify({ camera_id: camId, name: camName || camId, rtsp_url: camUrl }),
    });
    setCamId(""); setCamName(""); setCamUrl("");
    loadCameras();
  }

  async function removeCamera(id: string) {
    await apiFetch(`/api/cameras/${id}`, { method: "DELETE" });
    loadCameras();
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Cameras</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-3">
          {cameras.length === 0 ? (
            <Card className="text-center py-10 text-zinc-500">No cameras connected.</Card>
          ) : (
            cameras.map((cam) => (
              <Card key={cam.camera_id} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className={`w-2.5 h-2.5 rounded-full ${cam.connected ? "bg-green-500" : "bg-red-400"}`} />
                  <div>
                    <div className="text-sm font-medium">{cam.name}</div>
                    <div className="text-xs text-zinc-500">{cam.rtsp_url}</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-zinc-400">{cam.connected ? `${cam.fps} fps` : "disconnected"}</span>
                  <Button variant="danger" size="sm" onClick={() => removeCamera(cam.camera_id)}>Remove</Button>
                </div>
              </Card>
            ))
          )}
        </div>

        <Card>
          <h3 className="text-sm font-semibold mb-3">Add RTSP Camera</h3>
          <div className="space-y-2">
            <Input placeholder="Camera ID (e.g., lobby-1)" value={camId} onChange={(e) => setCamId(e.target.value)} />
            <Input placeholder="Name (e.g., Lobby Camera)" value={camName} onChange={(e) => setCamName(e.target.value)} />
            <Input placeholder="rtsp://user:pass@ip:554/stream" value={camUrl} onChange={(e) => setCamUrl(e.target.value)} />
            <Button onClick={addCamera} className="w-full">Add Camera</Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
