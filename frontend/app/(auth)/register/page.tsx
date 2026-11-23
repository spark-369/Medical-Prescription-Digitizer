import Link from "next/link";

import { RegisterForm } from "@/components/register-form";

export const dynamic = "force-dynamic";

export default function RegisterPage() {
  return (
    <div className="space-y-4">
      <RegisterForm />
      <p className="text-muted-foreground text-center text-sm">
        Already have an account?{" "}
        <Link href="/login" className="text-foreground font-medium underline underline-offset-4">
          Sign in
        </Link>
      </p>
    </div>
  );
}
