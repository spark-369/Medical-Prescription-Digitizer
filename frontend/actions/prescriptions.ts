"use server";

import { revalidatePath } from "next/cache";
import { apiFetch } from "@/lib/api/server";
import type { Prescription } from "@/lib/api/types";

export interface UploadActionResult {
  ok: boolean;
  id?: string;
  error?: string;
}

export async function uploadPrescriptionAction(
  formData: FormData,
): Promise<UploadActionResult> {
  try {
    const prescription = await apiFetch<Prescription>("/prescriptions", {
      method: "POST",
      body: formData,
    });
    revalidatePath("/prescriptions");
    revalidatePath("/dashboard");
    return { ok: true, id: prescription.id };
  } catch (error) {
    return {
      ok: false,
      error:
        error instanceof Error ? error.message : "Upload failed. Try again.",
    };
  }
}

export interface ReprocessActionResult {
  ok: boolean;
  error?: string;
}

export async function reprocessPrescriptionAction(
  id: string,
): Promise<ReprocessActionResult> {
  try {
    await apiFetch(`/prescriptions/${id}/reprocess`, { method: "POST" });
    revalidatePath(`/prescriptions/${id}`);
    revalidatePath("/prescriptions");
    return { ok: true };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Reprocess failed.",
    };
  }
}

export async function deletePrescriptionAction(
  id: string,
): Promise<{ ok: boolean; error?: string }> {
  try {
    await apiFetch(`/prescriptions/${id}`, { method: "DELETE" });
    revalidatePath("/prescriptions");
    revalidatePath("/dashboard");
    return { ok: true };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Delete failed.",
    };
  }
}

export interface GenerateInsightsActionResult {
  ok: boolean;
  status?: string;
  error?: string;
}

export async function generateInsightsAction(
  id: string,
): Promise<GenerateInsightsActionResult> {
  try {
    const result = await apiFetch<{ status: string }>(
      `/prescriptions/${id}/insights`,
      { method: "POST" },
    );
    revalidatePath(`/prescriptions/${id}`);
    return { ok: true, status: result.status };
  } catch (error) {
    return {
      ok: false,
      error:
        error instanceof Error ? error.message : "Could not start AI insights.",
    };
  }
}
