import { auth } from "@/auth";
import { API_URL_INTERNAL, API_V1 } from "@/lib/api/config";

/**
 * Streams the original prescription image from FastAPI, authenticated with
 * the caller's NextAuth session — so the browser never needs the raw token
 * for <img src="/api/files/{id}">.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const session = await auth();
  if (!session?.accessToken) {
    return new Response(null, { status: 401 });
  }
  const upstream = await fetch(
    `${API_URL_INTERNAL}${API_V1}/prescriptions/${id}/file`,
    {
      headers: { Authorization: `Bearer ${session.accessToken}` },
      cache: "no-store",
    },
  );
  if (!upstream.ok || !upstream.body) {
    return new Response(null, { status: upstream.status });
  }
  return new Response(upstream.body, {
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/octet-stream",
      "Cache-Control": "private, max-age=60",
    },
  });
}
