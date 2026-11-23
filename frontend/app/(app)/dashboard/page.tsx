import Link from "next/link";

import { auth } from "@/auth";
import { PrescriptionsTable } from "@/components/prescriptions-table";
import { StatsCards } from "@/components/stats-cards";
import { UploadDialog } from "@/components/upload-dialog";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiFetch } from "@/lib/api/server";
import type { Stats } from "@/lib/api/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "Dashboard — Prescription Digitizer" };

export default async function DashboardPage() {
  const [stats, session] = await Promise.all([
    apiFetch<Stats>("/prescriptions/stats"),
    auth(),
  ]);

  const firstName = (session?.user?.name ?? "").split(" ")[0] || "there";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Welcome back, {firstName}
          </h1>
          <p className="text-muted-foreground text-sm">
            Overview of your prescription digitization activity.
          </p>
        </div>
        <UploadDialog />
      </div>

      <StatsCards stats={stats} />

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Recent prescriptions</CardTitle>
              <CardDescription>
                The five most recent uploads and their status.
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" asChild>
              <Link href="/prescriptions">View all</Link>
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <PrescriptionsTable prescriptions={stats.recent} />
        </CardContent>
      </Card>
    </div>
  );
}
