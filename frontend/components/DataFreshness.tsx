import { Clock } from "lucide-react";

export default function DataFreshness() {
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-muted whitespace-nowrap">
      <Clock className="h-3 w-3" aria-hidden="true" />
      Data updated daily at 02:00 UTC
    </span>
  );
}
