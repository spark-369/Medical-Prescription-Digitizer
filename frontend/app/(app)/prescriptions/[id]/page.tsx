import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { auth } from "@/auth";
import { InsightsPanel } from "@/components/insights-panel";
import { LiveStatus } from "@/components/live-status";
import { PrescriptionActions } from "@/components/prescription-actions";
import { StatusBadge } from "@/components/status-badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiError, apiFetch } from "@/lib/api/server";
import type { Prescription } from "@/lib/api/types";
import { displayModelName, formatBytes, formatDate } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function PrescriptionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const session = await auth();

  let prescription: Prescription;
  try {
    prescription = await apiFetch<Prescription>(`/prescriptions/${id}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    throw error;
  }

  const isActive =
    prescription.status === "uploaded" ||
    prescription.status === "queued" ||
    prescription.status === "processing";

  const details: Array<[string, string]> = [
    ["Patient", prescription.patient_name ?? "—"],
    ["Age", prescription.patient_age != null ? String(prescription.patient_age) : "—"],
    ["Doctor", prescription.doctor_name ?? "—"],
    ["Prescribed", prescription.prescribed_date ?? "—"],
    ["File", prescription.original_filename],
    ["Size", formatBytes(prescription.file_size)],
    ["Uploaded", formatDate(prescription.created_at)],
    ["Completed", formatDate(prescription.completed_at)],
    ["Model", displayModelName(prescription.model_name)],
    [
      "Confidence",
      prescription.confidence != null
        ? `${Math.round(prescription.confidence * 100)}%`
        : "—",
    ],
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link
            href="/prescriptions"
            className="text-muted-foreground hover:text-foreground"
            aria-label="Back to prescriptions"
          >
            <ArrowLeft className="size-5" />
          </Link>
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
              {prescription.original_filename}
              <StatusBadge status={prescription.status} />
            </h1>
            <p className="text-muted-foreground text-sm">
              Uploaded {formatDate(prescription.created_at)}
            </p>
          </div>
        </div>
        <PrescriptionActions id={prescription.id} canReprocess={!isActive} />
      </div>

      {(isActive || prescription.status === "failed") && (
        <Card>
          <CardContent>
            {prescription.status === "failed" && prescription.error && (
              <p className="text-destructive mb-3 text-sm">{prescription.error}</p>
            )}
            <LiveStatus
              prescriptionId={prescription.id}
              accessToken={session?.accessToken}
              status={prescription.status}
            />
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Original document</CardTitle>
            <CardDescription>{prescription.mime_type}</CardDescription>
          </CardHeader>
          <CardContent>
            <a
              href={`/api/files/${prescription.id}`}
              target="_blank"
              rel="noopener noreferrer"
              title="Open full size in a new tab"
              className="group relative block overflow-hidden rounded-lg border"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`/api/files/${prescription.id}`}
                alt={`Original prescription ${prescription.original_filename}`}
                className="max-h-[520px] w-full object-contain transition-transform group-hover:scale-[1.01]"
              />
              <span className="bg-background/80 text-muted-foreground absolute right-3 bottom-3 rounded-md px-2 py-1 text-xs opacity-0 transition-opacity group-hover:opacity-100">
                Click to enlarge
              </span>
            </a>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Extracted data</CardTitle>
              <CardDescription>
                Parsed by{" "}
                {prescription.model_name
                  ? displayModelName(prescription.model_name)
                  : "the vision model"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3 text-sm">
                {details.map(([label, value]) => (
                  <div key={label} className="contents">
                    <dt className="text-muted-foreground">{label}</dt>
                    <dd className="truncate font-medium">{value}</dd>
                  </div>
                ))}
              </dl>
              {prescription.notes && (
                <p className="text-muted-foreground mt-4 text-sm">
                  <span className="text-foreground font-medium">Notes: </span>
                  {prescription.notes}
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Medications</CardTitle>
              <CardDescription>
                {prescription.items.length} item
                {prescription.items.length === 1 ? "" : "s"} extracted
              </CardDescription>
            </CardHeader>
            <CardContent>
              {prescription.items.length === 0 ? (
                <p className="text-muted-foreground text-sm">
                  No medications extracted yet.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Medication</TableHead>
                      <TableHead>Dosage</TableHead>
                      <TableHead>Frequency</TableHead>
                      <TableHead>Duration</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {prescription.items.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="font-medium">
                          {item.medication}
                        </TableCell>
                        <TableCell>{item.dosage ?? "—"}</TableCell>
                        <TableCell>{item.frequency ?? "—"}</TableCell>
                        <TableCell>{item.duration ?? "—"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <InsightsPanel
        prescriptionId={prescription.id}
        prescriptionStatus={prescription.status}
        insightsStatus={prescription.ai_insights_status}
        insights={prescription.ai_insights}
        generatedAt={prescription.ai_insights_generated_at}
      />
    </div>
  );
}

