import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { SidebarShell } from "@/components/sidebar-shell";

export const dynamic = "force-dynamic";

export default async function AppLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const session = await auth();
  if (!session?.user?.id || session.error) {
    redirect("/login");
  }

  return (
    <SidebarShell
      name={session.user.name ?? session.user.email ?? "User"}
      email={session.user.email ?? ""}
      role={session.user.role}
    >
      {children}
    </SidebarShell>
  );
}
