import { auth } from "@/auth";
import { API_URL_INTERNAL, API_V1 } from "@/lib/api/config";

/**
 * Proxy for the AI assistant: the browser POSTs here, we attach the
 * session's access token server-side and relay the structured JSON reply.
 */
export async function POST(request: Request) {
  const session = await auth();
  if (!session?.accessToken) {
    return new Response(null, { status: 401 });
  }
  const body = await request.json();

  const upstream = await fetch(
    `${API_URL_INTERNAL}${API_V1}/assistant/chat`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      cache: "no-store",
    },
  );

  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
