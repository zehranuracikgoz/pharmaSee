import clsx from "clsx";

interface Props {
  momentum?: number | null;
  size? : "sm" | "md" | "lg";
}

export default function MomentumBadge({ momentum, size = "md" }: Props) {
  if (momentum == null) {
    return (
      <span className={clsx("inline-flex items-center rounded-full bg-slate-100 text-slate-400 font-mono",
        size === "sm" && "px-2 py-0.5 text-xs",
        size === "md" && "px-3 py-1 text-sm",
        size === "lg" && "px-4 py-1.5 text-base",
      )}>
        N/A
      </span>
    );
  }

  const isPositive = momentum >= 0;
  const isStrong = Math.abs(momentum) >= 15;

  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full font-mono font-semibold",
        size === "sm" && "px-2 py-0.5 text-xs",
        size === "md" && "px-3 py-1 text-sm",
        size === "lg" && "px-4 py-1.5 text-base",
        isPositive && isStrong && "bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/40",
        isPositive && !isStrong && "bg-emerald-500/10 text-emerald-500",
        !isPositive && isStrong && "bg-rose-500/20 text-rose-400 ring-1 ring-rose-500/40",
        !isPositive && !isStrong && "bg-rose-500/10 text-rose-500",
      )}
    >
      {isPositive ? "▲" : "▼"} {Math.abs(momentum).toFixed(2)}%
    </span>
  );

}