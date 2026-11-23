import NextAuth from "next-auth";
import { authConfig } from "@/auth.config";

/**
 * Next.js 16 proxy (the renamed `middleware.ts`). Route protection runs on
 * the edge-safe Auth.js config — no database or Node-only APIs involved.
 */
const { auth } = NextAuth(authConfig);

const PROTECTED_PREFIXES = ["/dashboard", "/prescriptions", "/users"];
const AUTH_PAGES = ["/login", "/register"];

export default auth((req) => {
  const { nextUrl } = req;
  const session = req.auth;
  const isLoggedIn = !!session && !session.error;
  const isProtected = PROTECTED_PREFIXES.some((prefix) =>
    nextUrl.pathname.startsWith(prefix),
  );
  const isAuthPage = AUTH_PAGES.includes(nextUrl.pathname);

  if (isAuthPage && isLoggedIn) {
    return Response.redirect(new URL("/dashboard", nextUrl));
  }
  if (isProtected && !isLoggedIn) {
    const loginUrl = new URL("/login", nextUrl);
    loginUrl.searchParams.set("callbackUrl", nextUrl.pathname + nextUrl.search);
    return Response.redirect(loginUrl);
  }
  // Authenticated request to any other page — allow through.
});

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
