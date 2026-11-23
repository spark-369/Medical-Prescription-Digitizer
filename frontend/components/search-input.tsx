"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Search, X } from "lucide-react";

import { Input } from "@/components/ui/input";

export function SearchInput({ placeholder = "Search…" }: { placeholder?: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const current = searchParams.get("search") ?? "";
  const [value, setValue] = useState(current);

  const apply = (term: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("page");
    if (term.trim()) {
      params.set("search", term.trim());
    } else {
      params.delete("search");
    }
    const query = params.toString();
    router.replace(query ? `/prescriptions?${query}` : "/prescriptions");
  };

  return (
    <div className="relative w-full sm:w-72">
      <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
      <Input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") apply(value);
        }}
        onBlur={() => {
          if (value.trim() !== current) apply(value);
        }}
        placeholder={placeholder}
        className="pr-8 pl-9"
        aria-label="Search prescriptions"
      />
      {value && (
        <button
          type="button"
          onClick={() => {
            setValue("");
            apply("");
          }}
          className="text-muted-foreground hover:text-foreground absolute top-1/2 right-2 -translate-y-1/2"
          aria-label="Clear search"
        >
          <X className="size-4" />
        </button>
      )}
    </div>
  );
}
