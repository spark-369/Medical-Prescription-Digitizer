"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  CalendarClock,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";

import { generateInsightsAction } from "@/actions/prescriptions";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import type {
  Insights,
  InteractionSeverity,
  PrescriptionStatus,
  RiskLevel,
} from "@/lib/api/types";
import { formatDate } from "@/lib/utils";

const DISCLAIMER =
  "AI-generated content — informational only. Always verify with a pharmacist or physician.";

// Guards against double auto-generation (React strict mode re-runs effects).
const autoTriggered = new Set<string>();

const SEVERITY_STYLES: Record<InteractionSeverity, string> = {
  low: "bg-emerald-100 text-emerald-800",
  moderate: "bg-amber-100 text-amber-800",
  high: "bg-red-100 text-red-800",
  unknown: "bg-muted text-muted-foreground",
};

const RISK_LABELS: Record<RiskLevel, string> = {
  none: "No known risk",
  low: "Low risk",
  moderate: "Moderate risk",
  high: "High risk",
  unknown: "Needs review",
};

const RISK_STYLES: Record<RiskLevel, string> = {
  none: "bg-emerald-100 text-emerald-800",
  low: "bg-emerald-100 text-emerald-800",
  moderate: "bg-amber-100 text-amber-800",
  high: "bg-red-100 text-red-800",
  unknown: "bg-muted text-muted-foreground",
};

interface InsightsPanelProps {
  prescriptionId: string;
  prescriptionStatus: PrescriptionStatus;
  insightsStatus: "pending" | "ready" | "failed" | null;
  insights: Insights | null;
  generatedAt: string | null;
}

export function InsightsPanel({
  prescriptionId,
  prescriptionStatus,
  insightsStatus,
  insights,
  generatedAt,
}: InsightsPanelProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const autoRef = useRef(false);

  const completed = prescriptionStatus === "completed";
  const generating = insightsStatus === "pending";

  // Auto-generate the first time a completed prescription is viewed.
  useEffect(() => {
    if (!completed || insightsStatus !== null || autoRef.current) return;
    if (autoTriggered.has(prescriptionId)) return;
    autoRef.current = true;
    autoTriggered.add(prescriptionId);
    startTransition(async () => {
      const result = await generateInsightsAction(prescriptionId);
      if (!result.ok) {
        setError(result.error ?? "Could not start AI insights.");
        autoTriggered.delete(prescriptionId);
        autoRef.current = false;
      }
      router.refresh();
    });
  }, [completed, insightsStatus, prescriptionId, router]);

  // While generating, poll for the finished insights.
  useEffect(() => {
    if (!generating) return;
    const interval = setInterval(() => router.refresh(), 4000);
    return () => clearInterval(interval);
  }, [generating, router]);

  const onGenerate = () => {
    setError(null);
    startTransition(async () => {
      const result = await generateInsightsAction(prescriptionId);
      if (!result.ok) {
        setError(result.error ?? "Could not start AI insights.");
        return;
      }
      router.refresh();
    });
  };

  if (!completed && insightsStatus === null) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="text-primary size-5" />
          <h2 className="text-xl font-semibold tracking-tight">AI insights</h2>
        </div>
        {(insightsStatus === "ready" || insightsStatus === "failed") && (
          <Button
            variant="outline"
            size="sm"
            onClick={onGenerate}
            disabled={isPending || generating}
          >
            {isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />}
            {insightsStatus === "ready" ? "Regenerate" : "Try again"}
          </Button>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="size-4" />
          <AlertTitle>Could not generate AI insights</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {generating && (
        <Card>
          <CardContent className="flex items-center gap-3 py-8 text-sm">
            <Loader2 className="size-4 animate-spin" />
            Generating AI insights — summarizing, checking interactions and
            building the schedule. This takes a few seconds…
          </CardContent>
        </Card>
      )}

      {insightsStatus === "failed" && !generating && (
        <Alert variant="destructive">
          <AlertTriangle className="size-4" />
          <AlertTitle>AI insights failed</AlertTitle>
          <AlertDescription>
            The last generation attempt failed. Use “Try again” to retry.
          </AlertDescription>
        </Alert>
      )}

      {insightsStatus === "ready" && insights && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="size-4" />
                Patient-friendly summary
              </CardTitle>
              <CardDescription>
                Plain-language explanation
                {generatedAt ? ` · ${formatDate(generatedAt)}` : ""}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm leading-relaxed">{insights.summary}</p>
              {insights.key_points.length > 0 && (
                <ul className="space-y-1.5">
                  {insights.key_points.map((point, index) => (
                    <li
                      key={index}
                      className="text-muted-foreground flex items-start gap-2 text-sm"
                    >
                      <Zap className="text-primary mt-0.5 size-3.5 shrink-0" />
                      {point}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <ShieldCheck className="size-4" />
                    Safety check
                  </CardTitle>
                  <CardDescription>
                    Potential interactions and duplications
                  </CardDescription>
                </div>
                <Badge className={RISK_STYLES[insights.interactions.risk_level]}>
                  {RISK_LABELS[insights.interactions.risk_level]}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {insights.interactions.findings.length === 0 ? (
                <p className="text-muted-foreground text-sm">
                  No potential interactions flagged for this combination.
                </p>
              ) : (
                <ul className="space-y-3">
                  {insights.interactions.findings.map((finding, index) => (
                    <li key={index} className="rounded-lg border p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge
                          className={SEVERITY_STYLES[finding.severity]}
                          variant="secondary"
                        >
                          {finding.severity} severity
                        </Badge>
                        <span className="text-sm font-medium">
                          {finding.medications.join(" + ")}
                        </span>
                      </div>
                      <p className="mt-2 text-sm">{finding.description}</p>
                      <p className="text-muted-foreground mt-1 text-sm">
                        <span className="text-foreground font-medium">
                          Recommendation:{" "}
                        </span>
                        {finding.recommendation}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
              {insights.interactions.general_advice && (
                <p className="text-muted-foreground text-sm">
                  <span className="text-foreground font-medium">Advice: </span>
                  {insights.interactions.general_advice}
                </p>
              )}
              <p className="text-muted-foreground text-xs">{DISCLAIMER}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CalendarClock className="size-4" />
                Daily schedule
              </CardTitle>
              <CardDescription>
                Suggested timing derived from the prescribed frequency
              </CardDescription>
            </CardHeader>
            <CardContent>
              {insights.schedule.daily_plan.length === 0 ? (
                <p className="text-muted-foreground text-sm">
                  No schedule could be derived from this prescription.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Medication</TableHead>
                      <TableHead>When</TableHead>
                      <TableHead>Duration</TableHead>
                      <TableHead>Instructions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {insights.schedule.daily_plan.map((entry, index) => (
                      <TableRow key={index}>
                        <TableCell className="font-medium">
                          {entry.medication}
                        </TableCell>
                        <TableCell>
                          {entry.times.length > 0
                            ? entry.times.join(", ")
                            : "As needed"}
                        </TableCell>
                        <TableCell>
                          {entry.days > 0 ? `${entry.days} day(s)` : "—"}
                        </TableCell>
                        <TableCell className="text-muted-foreground whitespace-normal">
                          {entry.instructions ?? "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
              {insights.schedule.notes && (
                <p className="text-muted-foreground mt-3 text-sm">
                  {insights.schedule.notes}
                </p>
              )}
              <p className="text-muted-foreground mt-3 text-xs">{DISCLAIMER}</p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
