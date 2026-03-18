"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { getUser, clearAuth } from "@/lib/api";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: "\u25A0" },
  { href: "/dashboard/upload", label: "Upload & Analyze", icon: "\u2191" },
  { href: "/dashboard/cv", label: "CV Analytics", icon: "\u25CB" },
  { href: "/dashboard/cameras", label: "Cameras", icon: "\u25C9" },
  { href: "/dashboard/history", label: "Data History", icon: "\u2630" },
  { href: "/dashboard/consent", label: "Consent", icon: "\u2714" },
  { href: "/dashboard/retail", label: "Retail", icon: "\u2302" },
  { href: "/dashboard/security", label: "Security", icon: "\u26A0" },
  { href: "/dashboard/search", label: "Search", icon: "\u2315" },
  { href: "/dashboard/audit", label: "Audit Log", icon: "\u2691" },
  { href: "/dashboard/settings", label: "Settings", icon: "\u2699" },
];

export function Sidebar() {
  const pathname = usePathname();
  const user = getUser();

  function handleLogout() {
    clearAuth();
    window.location.href = "/login";
  }

  return (
    <aside className="fixed left-0 top-0 h-full w-56 bg-zinc-950 border-r border-zinc-800 flex flex-col z-20">
      <div className="p-4 border-b border-zinc-800">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">
            I
          </div>
          <div>
            <div className="text-sm font-semibold text-zinc-100">The I</div>
            <div className="text-[10px] text-zinc-500">Intelligent Video Analytics</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 py-2 overflow-y-auto">
        {navItems.map((item) => {
          const active = pathname === item.href || (item.href !== "/dashboard" && pathname?.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 px-4 py-2 text-sm transition-colors",
                active
                  ? "bg-blue-600/10 text-blue-400 border-r-2 border-blue-500"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
              )}
            >
              <span className="w-5 text-center text-xs">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="p-3 border-t border-zinc-800">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs font-medium text-zinc-300">{user?.username}</div>
            <div className="text-[10px] text-zinc-500">{user?.role}</div>
          </div>
          <button
            onClick={handleLogout}
            className="text-xs text-red-400 hover:text-red-300"
          >
            Logout
          </button>
        </div>
      </div>
    </aside>
  );
}
