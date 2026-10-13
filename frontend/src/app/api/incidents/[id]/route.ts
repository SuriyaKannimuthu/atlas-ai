import type { NextRequest } from "next/server";

import { AtlasApiError, loadIncidentBundle } from "@/lib/atlas";

// Backend-for-frontend endpoint polled by the live incident view. Keeps the API key server-side.
export async function GET(_request: NextRequest, ctx: RouteContext<"/api/incidents/[id]">) {
  const { id } = await ctx.params;
  try {
    return Response.json(await loadIncidentBundle(id));
  } catch (error) {
    const status = error instanceof AtlasApiError ? error.status : 500;
    const message = error instanceof Error ? error.message : "unexpected error";
    return Response.json({ error: message }, { status });
  }
}
