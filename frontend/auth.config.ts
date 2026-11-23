import type { NextAuthConfig } from "next-auth";
import { refreshAccessToken } from "@/lib/auth/refresh";

/**
 * Edge-safe Auth.js configuration shared by the full instance (auth.ts)
 * and the Next.js proxy (proxy.ts). Contains no Node-only code.
 */
export const authConfig = {
  trustHost: true,
  pages: { signIn: "/login" },
  session: { strategy: "jwt", maxAge: 7 * 24 * 60 * 60 },
  providers: [], // providers are registered in auth.ts
  callbacks: {
    async jwt({ token, user }) {
      // Initial sign-in: persist token metadata in the encrypted JWT.
      if (user) {
        token.id = user.id;
        token.role = user.role;
        token.accessToken = user.accessToken;
        token.refreshToken = user.refreshToken;
        token.accessTokenExpires = user.accessTokenExpires;
        token.error = undefined;
        return token;
      }
      // Proactive refresh one minute before expiry.
      const expiresAt = (token.accessTokenExpires as number | undefined) ?? 0;
      if (Date.now() < expiresAt - 60_000) {
        return token;
      }
      return refreshAccessToken(token);
    },
    async session({ session, token }) {
      if (token) {
        session.user.id = (token.id as string | undefined) ?? "";
        session.user.role = (token.role as string | undefined) ?? "staff";
        session.accessToken = token.accessToken as string | undefined;
        session.accessTokenExpires = token.accessTokenExpires as
          | number
          | undefined;
        session.error = token.error as "RefreshTokenError" | undefined;
      }
      return session;
    },
  },
} satisfies NextAuthConfig;
