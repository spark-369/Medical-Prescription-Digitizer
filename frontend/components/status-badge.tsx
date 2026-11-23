import { Badge } from "@/components/ui/badge";
import type { PrescriptionStatus } from "@/lib/api/types";

const STATUS_CONFIG: Record<
  PrescriptionStatus,
  { label: string; className: string }
> = {
  uploaded: { label: "Uploaded", className: "bg-muted text-muted-foreground" },
  queued: { label: "Queued", className: "bg-blue-100 text-blue-800" },
  processing: { label: "Processing", className: "bg-amber-100 text-amber-800" },
  completed: { label: "Completed", className: "bg-emerald-100 text-emerald-800" },
  failed: { label: "Failed", className: "bg-red-100 text-red-800" },
};

export function StatusBadge({ status }: { status: PrescriptionStatus }) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.uploaded;
  return (
    <Badge variant="secondary" className={config.className}>
      {config.label}
    </Badge>
  );
}
