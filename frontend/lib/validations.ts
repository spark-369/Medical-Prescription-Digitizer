import { z } from "zod";

export const MIN_UPLOAD_KB = 10;
export const MAX_UPLOAD_MB = 10;

export const loginSchema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

export const registerSchema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  full_name: z.string().min(1, "Full name is required").max(255),
});

export const uploadSchema = z.object({
  file: z
    .instanceof(File, { message: "Choose a prescription image" })
    .refine(
      (file) => file.size >= MIN_UPLOAD_KB * 1024,
      `File is too small — minimum ${MIN_UPLOAD_KB} KB`,
    )
    .refine(
      (file) => file.size < MAX_UPLOAD_MB * 1024 * 1024,
      `File must be smaller than ${MAX_UPLOAD_MB} MB`,
    )
    .refine(
      (file) => ["image/png", "image/jpeg", "image/webp"].includes(file.type),
      "Only PNG, JPEG or WebP images are supported",
    ),
});

export type LoginInput = z.infer<typeof loginSchema>;
export type RegisterInput = z.infer<typeof registerSchema>;
export type UploadInput = z.infer<typeof uploadSchema>;
