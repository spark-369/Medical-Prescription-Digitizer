"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { FileUp, Loader2, Upload } from "lucide-react";

import { uploadPrescriptionAction } from "@/actions/prescriptions";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { uploadSchema, type UploadInput } from "@/lib/validations";

export function UploadDialog() {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  const {
    control,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<UploadInput>({
    resolver: zodResolver(uploadSchema),
    defaultValues: { file: undefined as unknown as File },
  });

  const fileName = watch("file")?.name;

  const onSubmit = async (values: UploadInput) => {
    const formData = new FormData();
    formData.set("file", values.file);
    const result = await uploadPrescriptionAction(formData);
    if (!result.ok) {
      toast.error(result.error ?? "Upload failed");
      return;
    }
    toast.success("Prescription uploaded — processing started");
    reset();
    setOpen(false);
    if (result.id) {
      router.push(`/prescriptions/${result.id}`);
    }
    router.refresh();
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <Upload />
          Upload prescription
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Upload prescription</DialogTitle>
          <DialogDescription>
            PNG, JPEG or WebP — between 10 KB and 10 MB. The vision
            model extracts patient details and medications automatically.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="file">Prescription image</Label>
            <Controller
              control={control}
              name="file"
              render={({ field: { onChange, onBlur, name, ref } }) => (
                <Input
                  type="file"
                  name={name}
                  onBlur={onBlur}
                  ref={ref}
                  accept="image/png,image/jpeg,image/webp"
                  className="cursor-pointer"
                  onChange={(event) => {
                    // Store the actual File (not the FileList) in form state.
                    onChange(event.target.files?.[0] ?? undefined);
                  }}
                />
              )}
            />
            {fileName && (
              <p className="text-muted-foreground text-xs">Selected: {fileName}</p>
            )}
            {errors.file && (
              <p className="text-destructive text-xs">{errors.file.message}</p>
            )}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? (
                <Loader2 className="animate-spin" />
              ) : (
                <FileUp />
              )}
              Upload & digitize
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
