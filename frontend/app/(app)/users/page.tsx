import { ShieldAlert, ShieldCheck, UserRound } from "lucide-react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/api/server";
import type { User } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";

export const dynamic = "force-dynamic";

export const metadata = { title: "Users — Prescription Digitizer" };

export default async function UsersPage() {
  let users: User[];
  let forbidden = false;
  try {
    users = await apiFetch<User[]>("/users");
  } catch {
    users = [];
    forbidden = true;
  }

  if (forbidden) {
    return (
      <div className="flex flex-col items-center gap-3 py-24 text-center">
        <div className="bg-muted flex size-12 items-center justify-center rounded-full">
          <ShieldAlert className="text-muted-foreground size-6" />
        </div>
        <h1 className="text-xl font-semibold">Admins only</h1>
        <p className="text-muted-foreground text-sm">
          You need the administrator role to manage users.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
        <p className="text-muted-foreground text-sm">
          {users.length} registered account{users.length === 1 ? "" : "s"}
        </p>
      </div>

      <div className="rounded-xl border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>User</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="hidden md:table-cell">Created</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((user) => {
              const initials = user.full_name
                .split(" ")
                .map((part) => part[0])
                .filter(Boolean)
                .slice(0, 2)
                .join("")
                .toUpperCase();
              return (
                <TableRow key={user.id}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <div className="bg-muted flex size-9 shrink-0 items-center justify-center rounded-full">
                        <span className="text-xs font-semibold">
                          {initials || <UserRound className="size-4" />}
                        </span>
                      </div>
                      <span className="font-medium">{user.full_name}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {user.email}
                  </TableCell>
                  <TableCell>
                    {user.role === "admin" ? (
                      <Badge className="bg-primary/10 text-primary border-transparent">
                        <ShieldCheck className="mr-1 size-3" />
                        Admin
                      </Badge>
                    ) : (
                      <Badge variant="secondary" className="capitalize">
                        {user.role}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {user.is_active ? (
                      <Badge className="border-transparent bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-400">
                        Active
                      </Badge>
                    ) : (
                      <Badge
                        variant="secondary"
                        className="bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-400"
                      >
                        Disabled
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground hidden md:table-cell">
                    {formatDate(user.created_at)}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
