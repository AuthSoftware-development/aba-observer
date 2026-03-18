import { cn } from "@/lib/utils";

export function Card({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("rounded-xl border border-zinc-800 bg-zinc-900 p-4", className)} {...props}>
      {children}
    </div>
  );
}

export function StatCard({ label, value, className }: { label: string; value: string | number; className?: string }) {
  return (
    <Card className={cn("flex flex-col gap-1", className)}>
      <span className="text-xs text-zinc-500 uppercase tracking-wide">{label}</span>
      <span className="text-xl font-bold text-zinc-100">{value}</span>
    </Card>
  );
}
