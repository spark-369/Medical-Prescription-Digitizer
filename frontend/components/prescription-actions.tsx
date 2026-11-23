"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Loader2, RefreshCw, Trash2 } from "lucide-react";

import {
  deletePrescriptionAction,
  reprocessPrescriptionAction,
} from "@/actions/prescriptions";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ConfirmDialog } from "@/components/confirm-dialog";

export function PrescriptionActions({
  id,
  canReprocess,
}: {
  id: string;
  canReprocess: boolean;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const onReprocess = () => {
    startTransition(async () => {
      const result = await reprocessPrescriptionAction(id);
      if (!result.ok) {
        toast.error(result.error ?? "Reprocess failed");
        return;
      }
      toast.info("Reprocessing started — watch the live status");
      router.refresh();
    });
  };

  const onDelete = () => {
    startTransition(async () => {
      const result = await deletePrescriptionAction(id);
      if (!result.ok) {
        toast.error(result.error ?? "Delete failed");
        return;
      }
      toast.success("Prescription deleted");
      router.push("/prescriptions");
    });
  };

  return (
    <div className="flex gap-2">
      {canReprocess && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              onClick={onReprocess}
              disabled={isPending}
            >
              {isPending ? (
                <Loader2 className="animate-spin" />
              ) : (
                <RefreshCw />
              )}
              Reprocess
            </Button>
          </TooltipTrigger>
          <TooltipContent>Run AI extraction again</TooltipContent>
        </Tooltip>
      )}

      <ConfirmDialog
        destructive
        trigger={
          <Button
            variant="outline"
            size="sm"
            className="text-destructive hover:text-destructive"
            disabled={isPending}
          >
            <Trash2 />
            Delete
          </Button>
        }
        title="Delete this prescription?"
        description="The uploaded image and all extracted data will be permanently removed. This action cannot be undone."
        confirmLabel="Delete permanently"
        onConfirm={onDelete}
      />
    </div>
  );
}
