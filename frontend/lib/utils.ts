import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatRelativeTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const diffMs = Date.now() - date.getTime();
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} d ago`;
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/**
 * Human-friendly model label for the UI. Raw tags like
 * "hf.co/Qwen/Qwen3-VL-2B-Instruct-GGUF:Q4_K_M" never appear on screen.
 */
const FRIENDLY_MODEL_NAMES: Record<string, string> = {
  "hf.co/Qwen/Qwen3-VL-2B-Instruct-GGUF:Q4_K_M": "Qwen3-VL 2B Instruct",
  "qwen3-vl:2b": "Qwen3-VL 2B Instruct",
};

export function displayModelName(raw: string | null | undefined): string {
  if (!raw) return "—";
  const known = FRIENDLY_MODEL_NAMES[raw];
  if (known) return known;
  // Unknown tag: derive a readable label (strip registry prefix and
  // quantization suffix, e.g. "hf.co/org/model-GGUF:Q8_0" → "model").
  return (
    raw
      .replace(/^hf\.co\//i, "")
      .replace(/[-_:]?gguf$/i, "")
      .replace(/:[A-Za-z0-9_+-]+$/, "")
      .split("/")
      .pop() || raw
  );
}
