import {
  CheckCircle2,
  FileText,
  Loader2,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import type { Stats } from "@/lib/api/types";

interface StatCard {
  title: string;
  value: number;
  icon: LucideIcon;
  accent: string;
  iconAccent: string;
}

export function StatsCards({ stats }: { stats: Stats }) {
  const completed = stats.by_status["completed"] ?? 0;
  const active =
    (stats.by_status["processing"] ?? 0) +
    (stats.by_status["queued"] ?? 0) +
    (stats.by_status["uploaded"] ?? 0);
  const failed = stats.by_status["failed"] ?? 0;

  const cards: StatCard[] = [
    {
      title: "Total prescriptions",
      value: stats.total,
      icon: FileText,
      accent: "text-blue-600 bg-blue-100 dark:bg-blue-500/15",
      iconAccent: "text-blue-600 dark:text-blue-400",
    },
    {
      title: "Completed",
      value: completed,
      icon: CheckCircle2,
      accent: "text-emerald-600 bg-emerald-100 dark:bg-emerald-500/15",
      iconAccent: "text-emerald-600 dark:text-emerald-400",
    },
    {
      title: "In progress",
      value: active,
      icon: Loader2,
      accent: "text-amber-600 bg-amber-100 dark:bg-amber-500/15",
      iconAccent: "text-amber-600 dark:text-amber-400",
    },
    {
      title: "Failed",
      value: failed,
      icon: XCircle,
      accent: "text-red-600 bg-red-100 dark:bg-red-500/15",
      iconAccent: "text-red-600 dark:text-red-400",
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.title} className="gap-0 py-0">
          <CardContent className="flex items-center gap-4 p-5">
            <div
              className={`flex size-11 shrink-0 items-center justify-center rounded-lg ${card.accent}`}
            >
              <card.icon
                className={`size-5 ${card.iconAccent} ${
                  card.title === "In progress" ? "animate-pulse" : ""
                }`}
              />
            </div>
            <div>
              <p className="text-muted-foreground text-sm font-medium">
                {card.title}
              </p>
              <p className="text-2xl font-semibold tabular-nums">
                {card.value}
              </p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
