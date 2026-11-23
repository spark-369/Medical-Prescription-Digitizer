import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { z } from "zod";
import { authConfig } from "@/auth.config";
import { API_URL_INTERNAL, API_V1 } from "@/lib/api/config";

const loginSchema = z.object({
  email: z.email(),
  password: z.string().min(1),
});

interface LoginResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

interface MeResponse {
  id: string;
  email: string;
  full_name: string;
  role: string;
}

export const { handlers, auth, signIn, signOut, unstable_update } = NextAuth({
  ...authConfig,
  providers: [
    Credentials({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const parsed = loginSchema.safeParse(credentials);
        if (!parsed.success) {
          return null;
        }
        try {
          // 1. Authenticate against FastAPI (OAuth2 password form).
          const body = new URLSearchParams({
            username: parsed.data.email,
            password: parsed.data.password,
          });
          const loginResponse = await fetch(
            `${API_URL_INTERNAL}${API_V1}/auth/login`,
            {
              method: "POST",
              headers: { "Content-Type": "application/x-www-form-urlencoded" },
              body,
              cache: "no-store",
            },
          );
          if (!loginResponse.ok) {
            return null;
          }
          const tokens = (await loginResponse.json()) as LoginResponse;

          // 2. Fetch the user profile with the fresh access token.
          const meResponse = await fetch(
            `${API_URL_INTERNAL}${API_V1}/auth/me`,
            {
              headers: { Authorization: `Bearer ${tokens.access_token}` },
              cache: "no-store",
            },
          );
          if (!meResponse.ok) {
            return null;
          }
          const profile = (await meResponse.json()) as MeResponse;

          return {
            id: profile.id,
            email: profile.email,
            name: profile.full_name,
            role: profile.role,
            accessToken: tokens.access_token,
            refreshToken: tokens.refresh_token,
            accessTokenExpires: Date.now() + tokens.expires_in * 1000,
          };
        } catch (error) {
          console.error("Credential authorize failed", error);
          return null;
        }
      },
    }),
  ],
});
