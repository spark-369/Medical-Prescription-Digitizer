"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";
import type { PrescriptionStatus } from "@/lib/api/types";

const FILTERS: Array<{ label: string; value: string | null }> = [
  { label: "All", value: null },
  { label: "Completed", value: "completed" },
  { label: "Processing", value: "processing" },
  { label: "Failed", value: "failed" },
];

export function StatusFilter({ active }: { active: PrescriptionStatus | null }) {
  const searchParams = useSearchParams();
  const search = searchParams.get("search") ?? "";

  const hrefFor = (value: string | null) => {
    const params = new URLSearchParams();
    if (value) params.set("status", value);
    if (search) params.set("search", search);
    const query = params.toString();
    return query ? `/prescriptions?${query}` : "/prescriptions";
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {FILTERS.map((filter) => {
        const isActive = (active ?? null) === filter.value;
        return (
          <Link
            key={filter.label}
            href={hrefFor(filter.value)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
              isActive
                ? "bg-primary text-primary-foreground border-transparent"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            {filter.label}
          </Link>
        );
      })}
    </div>
  );
}
