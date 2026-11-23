import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";

interface PaginationProps {
  page: number;
  totalPages: number;
  buildHref: (page: number) => string;
}

export function Pagination({ page, totalPages, buildHref }: PaginationProps) {
  if (totalPages <= 1) return null;

  const pages: number[] = [];
  const start = Math.max(1, page - 2);
  const end = Math.min(totalPages, start + 4);
  for (let index = start; index <= end; index++) {
    pages.push(index);
  }

  const base =
    "inline-flex h-9 items-center rounded-md border px-3 text-sm transition-colors";

  return (
    <div className="flex items-center justify-between">
      <p className="text-muted-foreground text-sm">
        Page <span className="text-foreground font-medium">{page}</span> of{" "}
        <span className="text-foreground font-medium">{totalPages}</span>
      </p>
      <div className="flex items-center gap-1.5">
        {page > 1 && (
          <Link
            href={buildHref(page - 1)}
            className={cn(base, "hover:bg-accent gap-1")}
            aria-label="Previous page"
          >
            <ChevronLeft className="size-4" />
            Previous
          </Link>
        )}
        {pages.map((pageNumber) => (
          <Link
            key={pageNumber}
            href={buildHref(pageNumber)}
            aria-current={pageNumber === page ? "page" : undefined}
            className={cn(
              base,
              "w-9 justify-center px-0",
              pageNumber === page
                ? "bg-primary text-primary-foreground border-transparent"
                : "hover:bg-accent",
            )}
          >
            {pageNumber}
          </Link>
        ))}
        {page < totalPages && (
          <Link
            href={buildHref(page + 1)}
            className={cn(base, "hover:bg-accent gap-1")}
            aria-label="Next page"
          >
            Next
            <ChevronRight className="size-4" />
          </Link>
        )}
      </div>
    </div>
  );
}
