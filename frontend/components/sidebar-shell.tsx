"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu } from "lucide-react";

import { SidebarNav } from "@/components/sidebar-nav";
import { UserNav } from "@/components/user-nav";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { ThemeToggle } from "@/components/theme-toggle";
import { Pill } from "lucide-react";

interface SidebarShellProps {
  name: string;
  email: string;
  role: string;
  children: React.ReactNode;
}

function BrandMark() {
  return (
    <Link href="/dashboard" className="flex items-center gap-2 px-3">
      <div className="bg-primary text-primary-foreground flex size-8 items-center justify-center rounded-lg">
        <Pill className="size-4" />
      </div>
      <div className="leading-tight">
        <p className="text-sm font-semibold tracking-tight">Prescription</p>
        <p className="text-muted-foreground -mt-0.5 text-xs">Digitizer</p>
      </div>
    </Link>
  );
}

export function SidebarShell({ name, email, role, children }: SidebarShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const isAdmin = role === "admin";

  const sidebarBody = (
    <>
      <div className="flex h-16 items-center border-b px-3">
        <BrandMark />
      </div>
      <div className="flex-1 overflow-y-auto py-4">
        <p className="text-muted-foreground mb-2 px-6 text-xs font-medium uppercase tracking-wider">
          Workspace
        </p>
        <SidebarNav isAdmin={isAdmin} />
      </div>
      <div className="flex items-center justify-between border-t p-3">
        <UserNav name={name} email={email} role={role} />
        <div className="flex items-center gap-1">
          <ThemeToggle />
        </div>
      </div>
    </>
  );

  return (
    <div className="bg-background min-h-screen">
      {/* Desktop sidebar */}
      <aside className="bg-background fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r lg:flex">
        {sidebarBody}
      </aside>

      {/* Mobile top bar + drawer */}
      <header className="bg-background/95 supports-[backdrop-filter]:bg-background/60 sticky top-0 z-40 flex h-14 items-center justify-between border-b px-4 backdrop-blur lg:hidden">
        <div className="flex items-center gap-2">
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Open menu">
                <Menu className="size-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-64 p-0">
              <SheetHeader className="border-b">
                <SheetTitle className="flex items-center gap-2 text-base">
                  <div className="bg-primary text-primary-foreground flex size-7 items-center justify-center rounded-lg">
                    <Pill className="size-4" />
                  </div>
                  Prescription Digitizer
                </SheetTitle>
              </SheetHeader>
              <div
                className="flex flex-1 flex-col"
                onClick={() => setMobileOpen(false)}
              >
                <SidebarNav isAdmin={isAdmin} />
              </div>
              <div className="flex items-center justify-between border-t p-3">
                <UserNav name={name} email={email} role={role} />
                <ThemeToggle />
              </div>
            </SheetContent>
          </Sheet>
          <BrandMark />
        </div>
        <UserNav name={name} email={email} role={role} />
      </header>

      {/* Content */}
      <div className="flex min-h-screen flex-col lg:pl-60">
        <main className="mx-auto w-full max-w-6xl flex-1 p-4 sm:p-6 lg:p-8">
          {children}
        </main>
        <footer className="text-muted-foreground border-t px-6 py-3 text-center text-xs">
          Medical Prescription Digitizer — AI-assisted, not a substitute for
          professional medical judgment.
        </footer>
      </div>
    </div>
  );
}
