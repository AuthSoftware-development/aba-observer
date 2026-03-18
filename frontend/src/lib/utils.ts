import { clsx, type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

export function formatTime(timestamp: string | number): string {
  if (!timestamp) return "N/A";
  const d = typeof timestamp === "number" ? new Date(timestamp * 1000) : new Date(timestamp);
  return d.toLocaleString();
}
