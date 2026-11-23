"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

import { NEXT_PUBLIC_API_URL, API_V1 } from "@/lib/api/config";
import type { PrescriptionStatus } from "@/lib/api/types";

interface LiveStatusProps {
  prescriptionId: string;
  accessToken?: string;
  status: PrescriptionStatus;
}

interface StreamEvent {
  type: "snapshot" | "status" | "progress" | "completed" | "failed";
  status?: PrescriptionStatus;
  progress?: number;
  message?: string;
  error?: string;
}

const STAGE_MESSAGES: Record<number, string> = {
  5: "Task started",
  35: "Running vision model…",
  80: "Persisting extraction…",
  100: "Done",
};

export function LiveStatus({
  prescriptionId,
  accessToken,
  status,
}: LiveStatusProps) {
  const router = useRouter();
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("Waiting for the worker…");

  const isActive =
    status === "uploaded" || status === "queued" || status === "processing";

  useEffect(() => {
    if (!isActive || !accessToken) return;

    const url = `${NEXT_PUBLIC_API_URL}${API_V1}/prescriptions/${prescriptionId}/events?access_token=${encodeURIComponent(accessToken)}`;
    const source = new EventSource(url);

    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as StreamEvent;
        if (payload.type === "snapshot") {
          if (payload.status === "completed" || payload.status === "failed") {
            source.close();
            router.refresh();
            return;
          }
          setMessage("Waiting for the worker…");
        } else if (payload.type === "progress" || payload.type === "status") {
          if (typeof payload.progress === "number") {
            setProgress(payload.progress);
          }
          setMessage(payload.message ?? STAGE_MESSAGES[payload.progress ?? 0] ?? "Processing…");
        } else if (payload.type === "completed" || payload.type === "failed") {
          source.close();
          router.refresh();
        }
      } catch {
        // Ignore malformed frames.
      }
    };

    source.onerror = () => {
      // Token may have rotated or the stream dropped — refresh the page so
      // the server re-renders with a fresh session/access token.
      source.close();
      router.refresh();
    };

    return () => {
      source.close();
    };
  }, [isActive, accessToken, prescriptionId, router]);

  if (status === "completed") {
    return (
      <div className="text-sm text-emerald-700 flex items-center gap-2">
        <CheckCircle2 className="size-4" />
        Digitization completed
      </div>
    );
  }
  if (status === "failed") {
    return (
      <div className="text-destructive flex items-center gap-2 text-sm">
        <AlertCircle className="size-4" />
        Processing failed — you can retry below
      </div>
    );
  }
  if (!isActive) return null;

  return (
    <div className="space-y-2">
      <div className="text-muted-foreground flex items-center gap-2 text-sm">
        <Loader2 className="size-4 animate-spin" />
        {message}
      </div>
      <div className="bg-muted h-2 w-full overflow-hidden rounded-full">
        <div
          className="bg-primary h-full rounded-full transition-all duration-500"
          style={{ width: `${Math.max(progress, 5)}%` }}
        />
      </div>
    </div>
  );
}
