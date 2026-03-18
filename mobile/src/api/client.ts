/**
 * API client for The I backend.
 * Handles authentication, token refresh, and all API calls.
 */

import * as SecureStore from "expo-secure-store";
import { getBrand } from "../config/branding";

const TOKEN_KEY = "thei_auth_token";
const USERNAME_KEY = "thei_username";
const ROLE_KEY = "thei_role";

class ApiClient {
  private token: string | null = null;
  private username: string | null = null;
  private role: string | null = null;

  get baseUrl(): string {
    return getBrand().apiBaseUrl;
  }

  get isAuthenticated(): boolean {
    return !!this.token;
  }

  get currentUser(): { username: string; role: string } | null {
    if (!this.username) return null;
    return { username: this.username, role: this.role || "rbt" };
  }

  async init() {
    this.token = await SecureStore.getItemAsync(TOKEN_KEY);
    this.username = await SecureStore.getItemAsync(USERNAME_KEY);
    this.role = await SecureStore.getItemAsync(ROLE_KEY);
  }

  private async fetch(path: string, options: RequestInit = {}): Promise<any> {
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };

    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }

    // Don't set Content-Type for FormData
    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    const res = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers,
    });

    if (res.status === 401) {
      // Try refresh
      if (path !== "/api/auth/refresh" && path !== "/api/auth/login") {
        const refreshed = await this.refreshToken();
        if (refreshed) {
          headers["Authorization"] = `Bearer ${this.token}`;
          const retry = await fetch(`${this.baseUrl}${path}`, { ...options, headers });
          return retry.json();
        }
      }
      await this.logout();
      throw new Error("Session expired");
    }

    return res.json();
  }

  // Auth
  async checkStatus(): Promise<{ setup_required: boolean; session_timeout: number }> {
    return this.fetch("/api/auth/status");
  }

  async setup(username: string, pin: string): Promise<any> {
    const data = await this.fetch("/api/auth/setup", {
      method: "POST",
      body: JSON.stringify({ username, pin }),
    });
    if (data.token) await this.saveAuth(data);
    return data;
  }

  async login(username: string, pin: string): Promise<any> {
    const data = await this.fetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, pin }),
    });
    if (data.token) await this.saveAuth(data);
    return data;
  }

  async refreshToken(): Promise<boolean> {
    try {
      const data = await this.fetch("/api/auth/refresh", { method: "POST" });
      if (data.token) {
        this.token = data.token;
        await SecureStore.setItemAsync(TOKEN_KEY, data.token);
        return true;
      }
    } catch {}
    return false;
  }

  async logout() {
    this.token = null;
    this.username = null;
    this.role = null;
    await SecureStore.deleteItemAsync(TOKEN_KEY);
    await SecureStore.deleteItemAsync(USERNAME_KEY);
    await SecureStore.deleteItemAsync(ROLE_KEY);
  }

  private async saveAuth(data: { token: string; username: string; role: string }) {
    this.token = data.token;
    this.username = data.username;
    this.role = data.role;
    await SecureStore.setItemAsync(TOKEN_KEY, data.token);
    await SecureStore.setItemAsync(USERNAME_KEY, data.username);
    await SecureStore.setItemAsync(ROLE_KEY, data.role);
  }

  // System
  async getSystemStatus(): Promise<any> {
    return this.fetch("/api/system/status");
  }

  // Cameras
  async getCameras(): Promise<any[]> {
    return this.fetch("/api/cameras");
  }

  async getCameraSnapshot(cameraId: string): Promise<Blob> {
    const res = await fetch(`${this.baseUrl}/api/cameras/${cameraId}/snapshot`, {
      headers: { Authorization: `Bearer ${this.token}` },
    });
    return res.blob();
  }

  // History
  async getHistory(): Promise<any[]> {
    return this.fetch("/api/history");
  }

  // Alerts
  async getAlertHistory(date?: string): Promise<any[]> {
    const q = date ? `?date=${date}` : "";
    return this.fetch(`/api/security/alerts/history${q}`);
  }

  async getAlertRules(): Promise<any[]> {
    return this.fetch("/api/security/alerts");
  }

  // Search
  async search(query: string, domain?: string): Promise<any> {
    return this.fetch("/api/search/natural", {
      method: "POST",
      body: JSON.stringify({ query, domain: domain || "" }),
    });
  }

  // Consent
  async getConsents(): Promise<any[]> {
    return this.fetch("/api/consent");
  }

  // Compliance
  async getCompliance(): Promise<any> {
    return this.fetch("/api/compliance");
  }

  // Retail
  async getStores(): Promise<any[]> {
    return this.fetch("/api/retail/stores");
  }

  async getPosExceptions(date?: string): Promise<any[]> {
    const q = date ? `?date=${date}` : "";
    return this.fetch(`/api/pos/exceptions${q}`);
  }
}

export const api = new ApiClient();
