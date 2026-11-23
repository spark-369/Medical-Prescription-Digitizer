import type { JWT } from "next-auth/jwt";
import { API_URL_INTERNAL, API_V1 } from "@/lib/api/config";

/**
 * Exchange the refresh token for a fresh token pair (Auth.js refresh-token
 * rotation pattern). Runs in the `jwt` callback — edge safe (plain fetch).
 */
export async function refreshAccessToken(token: JWT): Promise<JWT> {
  const refreshToken = token.refreshToken as string | undefined;
  try {
    if (!refreshToken) {
      throw new Error("Missing refresh token");
    }
    const response = await fetch(`${API_URL_INTERNAL}${API_V1}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(`Refresh failed with status ${response.status}`);
    }
    const tokens = (await response.json()) as {
      access_token: string;
      refresh_token: string;
      expires_in: number;
    };
    return {
      ...token,
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      accessTokenExpires: Date.now() + tokens.expires_in * 1000,
      error: undefined,
    };
  } catch (error) {
    console.error("Error refreshing access token", error);
    return {
      ...token,
      accessToken: undefined,
      error: "RefreshTokenError",
    };
  }
}
