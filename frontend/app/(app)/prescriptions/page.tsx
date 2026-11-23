import { Suspense } from "react";

import { PrescriptionsTable } from "@/components/prescriptions-table";
import { SearchInput } from "@/components/search-input";
import { StatusFilter } from "@/components/status-filter";
import { UploadDialog } from "@/components/upload-dialog";
import { Pagination } from "@/components/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "@/lib/api/server";
import type { PrescriptionList } from "@/lib/api/types";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 20;

export const metadata = { title: "Prescriptions — Prescription Digitizer" };

export default async function PrescriptionsPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; status?: string; search?: string }>;
}) {
  const { page: pageParam, status, search } = await searchParams;
  const page = Math.max(1, Number.parseInt(pageParam ?? "1", 10) || 1);
  const validStatuses = [
    "uploaded",
    "queued",
    "processing",
    "completed",
    "failed",
  ] as const;
  const statusFilter = validStatuses.includes(status as never)
    ? (status as (typeof validStatuses)[number])
    : null;

  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("page_size", String(PAGE_SIZE));
  if (statusFilter) params.set("status", statusFilter);
  if (search) params.set("search", search);

  const list = await apiFetch<PrescriptionList>(
    `/prescriptions?${params.toString()}`,
  );
  const totalPages = Math.max(1, Math.ceil(list.total / PAGE_SIZE));

  const buildHref = (nextPage: number) => {
    const next = new URLSearchParams();
    next.set("page", String(nextPage));
    if (statusFilter) next.set("status", statusFilter);
    if (search) next.set("search", search);
    return `/prescriptions?${next.toString()}`;
  };

  const hasFilters = Boolean(statusFilter || search);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Prescriptions</h1>
          <p className="text-muted-foreground text-sm">
            {list.total} prescription{list.total === 1 ? "" : "s"} total
          </p>
        </div>
        <UploadDialog />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <StatusFilter active={statusFilter} />
        <Suspense fallback={<Skeleton className="h-9 w-full sm:w-72" />}>
          <SearchInput placeholder="Search patient, doctor or file…" />
        </Suspense>
      </div>

      <div className="rounded-xl border">
        <PrescriptionsTable
          prescriptions={list.items}
          hasFilters={hasFilters}
        />
      </div>

      <Pagination page={page} totalPages={totalPages} buildHref={buildHref} />
    </div>
  );
}
