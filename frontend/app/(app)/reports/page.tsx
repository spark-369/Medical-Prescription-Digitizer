import { ReportsView } from "@/components/reports-view";
import { apiFetch } from "@/lib/api/server";
import type { AiReport } from "@/lib/api/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "AI Reports — Prescription Digitizer" };

export default async function ReportsPage() {
  const reports = await apiFetch<AiReport[]>("/reports");

  return <ReportsView initial={reports} />;
}
