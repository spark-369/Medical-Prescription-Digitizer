import Link from "next/link";

import { LoginForm } from "@/components/login-form";

export const dynamic = "force-dynamic";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ callbackUrl?: string }>;
}) {
  const { callbackUrl } = await searchParams;

  return (
    <div className="space-y-4">
      <LoginForm callbackUrl={callbackUrl} />
      <p className="text-muted-foreground text-center text-sm">
        No account yet?{" "}
        <Link href="/register" className="text-foreground font-medium underline underline-offset-4">
          Register
        </Link>
      </p>
    </div>
  );
}
