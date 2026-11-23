import Link from "next/link";
import { ChevronRight, FileImage, SearchX } from "lucide-react";

import { StatusBadge } from "@/components/status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatRelativeTime } from "@/lib/utils";
import type { PrescriptionBrief } from "@/lib/api/types";

interface PrescriptionsTableProps {
  prescriptions: PrescriptionBrief[];
  hasFilters?: boolean;
}

export function PrescriptionsTable({
  prescriptions,
  hasFilters = false,
}: PrescriptionsTableProps) {
  if (prescriptions.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <div className="bg-muted flex size-12 items-center justify-center rounded-full">
          {hasFilters ? (
            <SearchX className="text-muted-foreground size-6" />
          ) : (
            <FileImage className="text-muted-foreground size-6" />
          )}
        </div>
        <div>
          <p className="font-medium">
            {hasFilters ? "No matching prescriptions" : "No prescriptions yet"}
          </p>
          <p className="text-muted-foreground mt-1 text-sm">
            {hasFilters
              ? "Try a different search term or clear the filters."
              : "Upload your first prescription to get started."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-2/5">File</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="hidden md:table-cell">Patient</TableHead>
          <TableHead className="hidden lg:table-cell">Doctor</TableHead>
          <TableHead className="hidden md:table-cell">Uploaded</TableHead>
          <TableHead className="w-10" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {prescriptions.map((prescription) => (
          <TableRow key={prescription.id} className="group">
            <TableCell>
              <Link
                href={`/prescriptions/${prescription.id}`}
                className="flex items-center gap-3"
              >
                <div className="bg-muted flex size-9 shrink-0 items-center justify-center rounded-md">
                  <FileImage className="text-muted-foreground size-4" />
                </div>
                <div className="min-w-0">
                  <p className="truncate font-medium group-hover:underline">
                    {prescription.original_filename}
                  </p>
                  <p className="text-muted-foreground text-xs">
                    {prescription.patient_name ?? "Unprocessed"}
                  </p>
                </div>
              </Link>
            </TableCell>
            <TableCell>
              <StatusBadge status={prescription.status} />
            </TableCell>
            <TableCell className="hidden md:table-cell">
              {prescription.patient_name ?? "—"}
            </TableCell>
            <TableCell className="hidden lg:table-cell">
              {prescription.doctor_name ?? "—"}
            </TableCell>
            <TableCell className="text-muted-foreground hidden md:table-cell">
              {formatRelativeTime(prescription.created_at)}
            </TableCell>
            <TableCell>
              <ChevronRight className="text-muted-foreground size-4 transition-transform group-hover:translate-x-0.5" />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
