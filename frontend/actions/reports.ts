"use server";

import { revalidatePath } from "next/cache";
import { apiFetch } from "@/lib/api/server";

export interface GenerateReportActionResult {
  ok: boolean;
  id?: string;
  error?: string;
}

export async function generateReportAction(): Promise<GenerateReportActionResult> {
  try {
    const result = await apiFetch<{ id: string; status: string }>(
      "/reports/generate",
      { method: "POST" },
    );
    revalidatePath("/reports");
    return { ok: true, id: result.id };
  } catch (error) {
    return {
      ok: false,
      error:
        error instanceof Error ? error.message : "Could not start the report.",
    };
  }
}

export async function deleteReportAction(
  id: string,
): Promise<{ ok: boolean; error?: string }> {
  try {
    await apiFetch(`/reports/${id}`, { method: "DELETE" });
    revalidatePath("/reports");
    return { ok: true };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Delete failed.",
    };
  }
}
