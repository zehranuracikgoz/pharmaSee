import clsx from "clsx";

interface Props {
  momentum?: number | null;
  size? : "sm" | "md" | "lg";
}

export default function MomentumBadge({ momentum, size = "md" }: Props) {
  if (momentum == null) {
    return (
      <span className={clsx("inline-flex items-center rounded-full bg-surface2 text-muted font-mono",
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
        isPositive && isStrong && "bg-success/20 text-success ring-1 ring-success/40",
        isPositive && !isStrong && "bg-success/10 text-success",
        !isPositive && isStrong && "bg-danger/20 text-danger ring-1 ring-danger/40",
        !isPositive && !isStrong && "bg-danger/10 text-danger",
      )}
    >
      {isPositive ? "▲" : "▼"} {Math.abs(momentum).toFixed(2)}%
    </span>
  );

}