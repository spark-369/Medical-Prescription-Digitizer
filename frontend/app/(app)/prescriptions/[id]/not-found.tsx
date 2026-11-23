import Link from "next/link";
import { FileQuestion } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function PrescriptionNotFound() {
  return (
    <div className="flex flex-col items-center gap-4 py-24 text-center">
      <div className="bg-muted flex size-12 items-center justify-center rounded-full">
        <FileQuestion className="text-muted-foreground size-6" />
      </div>
      <div>
        <h1 className="text-xl font-semibold">Prescription not found</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          It may have been deleted, or you do not have access to it.
        </p>
      </div>
      <Button variant="outline" asChild>
        <Link href="/prescriptions">Back to prescriptions</Link>
      </Button>
    </div>
  );
}
