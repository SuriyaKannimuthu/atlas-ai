import "server-only";

import type {
  Health,
  IncidentBundle,
  IncidentDetail,
  IncidentList,
  Me,
  Report,
  WorkflowEvent,
} from "@/lib/types";

// The API key lives only on the server. The browser talks to Next.js (Server Components,
// Server Actions, and the /api BFF route), never to the backend directly.
const BASE_URL = process.env.ATLAS_API_URL ?? "http://localhost:8000";
const API_KEY = process.env.ATLAS_API_KEY ?? "";

export class AtlasApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
        ...init?.headers,
      },
    });
  } catch {
    throw new AtlasApiError(503, `Atlas API is unreachable at ${BASE_URL}`);
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new AtlasApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export const atlas = {
  health: () => request<Health>("/health"),
  me: () => request<Me>("/api/v1/me"),
  listIncidents: (status?: string, limit = 200) =>
    request<IncidentList>(
      `/api/v1/incidents?limit=${limit}${status ? `&status=${encodeURIComponent(status)}` : ""}`,
    ),
  getIncident: (id: string) => request<IncidentDetail>(`/api/v1/incidents/${encodeURIComponent(id)}`),
  getEvents: (id: string, after = 0) =>
    request<{ items: WorkflowEvent[]; next_after: number }>(
      `/api/v1/incidents/${encodeURIComponent(id)}/events?after=${after}&limit=1000`,
    ),
  getReport: (id: string) =>
    request<{ incident_id: string; final: boolean; report: Report }>(
      `/api/v1/incidents/${encodeURIComponent(id)}/report`,
    ),
  createIncident: (body: Record<string, unknown>) =>
    request<IncidentDetail>("/api/v1/incidents", { method: "POST", body: JSON.stringify(body) }),
  decide: (id: string, decision: "approved" | "rejected", comment?: string) =>
    request<IncidentDetail>(`/api/v1/incidents/${encodeURIComponent(id)}/approvals`, {
      method: "POST",
      body: JSON.stringify({ decision, comment: comment || null }),
    }),
  cancel: (id: string) =>
    request<IncidentDetail>(`/api/v1/incidents/${encodeURIComponent(id)}/cancel`, {
      method: "POST",
    }),
};

export type Attempt<T> = { ok: true; data: T } | { ok: false; error: Error };

/** Resolve a request without throwing, so callers can branch before rendering. */
export async function attempt<T>(promise: Promise<T>): Promise<Attempt<T>> {
  try {
    return { ok: true, data: await promise };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error : new Error(String(error)) };
  }
}

export async function loadIncidentBundle(id: string): Promise<IncidentBundle> {
  const [incident, events] = await Promise.all([atlas.getIncident(id), atlas.getEvents(id)]);
  const report = incident.has_report ? await atlas.getReport(id) : null;
  return {
    incident,
    events: events.items,
    report: report ? { final: report.final, report: report.report } : null,
  };
}
