/**
 * White-label branding configuration.
 *
 * Override these values to rebrand the app for different customers.
 * Set via environment variables or a branding.json config file.
 */

export interface BrandConfig {
  appName: string;
  tagline: string;
  logoText: string; // Short text shown in logo mark (1-3 chars)
  primaryColor: string;
  primaryDark: string;
  accentColor: string;
  backgroundColor: string;
  surfaceColor: string;
  textColor: string;
  textSecondary: string;
  errorColor: string;
  warningColor: string;
  successColor: string;
  borderRadius: number;
  fontFamily: string;
  apiBaseUrl: string;
  supportEmail: string;
  privacyUrl: string;
  termsUrl: string;
  hipaaEnabled: boolean;
  showPoweredBy: boolean; // Show "Powered by The I" in OEM mode
}

// Default branding (The I)
export const DEFAULT_BRAND: BrandConfig = {
  appName: "The I",
  tagline: "Intelligent Video Analytics",
  logoText: "I",
  primaryColor: "#2563eb",
  primaryDark: "#1d4ed8",
  accentColor: "#3b82f6",
  backgroundColor: "#0f172a",
  surfaceColor: "#1e293b",
  textColor: "#f1f5f9",
  textSecondary: "#94a3b8",
  errorColor: "#ef4444",
  warningColor: "#f59e0b",
  successColor: "#22c55e",
  borderRadius: 12,
  fontFamily: "System",
  apiBaseUrl: "https://localhost:3017",
  supportEmail: "",
  privacyUrl: "",
  termsUrl: "",
  hipaaEnabled: true,
  showPoweredBy: false,
};

// Example OEM configs
export const OEM_BRANDS: Record<string, Partial<BrandConfig>> = {
  // ABA clinic branding
  "aba-clinic": {
    appName: "ABA Vision",
    tagline: "AI-Powered Session Analytics",
    logoText: "AV",
    primaryColor: "#7c3aed",
    primaryDark: "#6d28d9",
    accentColor: "#8b5cf6",
    hipaaEnabled: true,
    showPoweredBy: true,
  },
  // Retail branding
  "retail-analytics": {
    appName: "StoreView",
    tagline: "Smart Store Analytics",
    logoText: "SV",
    primaryColor: "#059669",
    primaryDark: "#047857",
    accentColor: "#10b981",
    hipaaEnabled: false,
    showPoweredBy: true,
  },
  // Security branding
  "security-pro": {
    appName: "GuardAI",
    tagline: "Intelligent Security Monitoring",
    logoText: "G",
    primaryColor: "#dc2626",
    primaryDark: "#b91c1c",
    accentColor: "#ef4444",
    hipaaEnabled: false,
    showPoweredBy: true,
  },
};

let _activeBrand: BrandConfig = { ...DEFAULT_BRAND };

export function setBrand(brandKey: string) {
  const overrides = OEM_BRANDS[brandKey];
  if (overrides) {
    _activeBrand = { ...DEFAULT_BRAND, ...overrides };
  }
}

export function setBrandConfig(config: Partial<BrandConfig>) {
  _activeBrand = { ...DEFAULT_BRAND, ...config };
}

export function getBrand(): BrandConfig {
  return _activeBrand;
}
