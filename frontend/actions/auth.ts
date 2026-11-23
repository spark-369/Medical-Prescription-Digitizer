"use server";

import { signOut } from "@/auth";
import { registerSchema, type RegisterInput } from "@/lib/validations";
import { apiFetch } from "@/lib/api/server";
import { revalidatePath } from "next/cache";

export interface RegisterActionResult {
  error?: string;
}

export async function registerUser(
  input: RegisterInput,
): Promise<RegisterActionResult> {
  // Zod runs again on the server — never trust the client alone.
  const parsed = registerSchema.safeParse(input);
  if (!parsed.success) {
    return { error: parsed.error.issues[0]?.message ?? "Invalid input" };
  }
  try {
    await apiFetch("/auth/register", {
      method: "POST",
      body: JSON.stringify(parsed.data),
    });
    return {};
  } catch (error) {
    return {
      error:
        error instanceof Error ? error.message : "Registration failed. Try again.",
    };
  }
}

export async function logoutAction(): Promise<void> {
  // Revoke tokens server-side (JWT blacklist in Redis), then end the session.
  try {
    await apiFetch("/auth/logout", { method: "POST" });
  } catch {
    // Best effort — always end the NextAuth session.
  }
  revalidatePath("/", "layout");
  await signOut({ redirectTo: "/login" });
}
