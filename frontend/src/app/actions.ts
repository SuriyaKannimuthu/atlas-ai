"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { AtlasApiError, atlas } from "@/lib/atlas";

// Authorization is enforced by the backend for the API key's role; these actions only relay
// validated input and surface errors to the UI.

export type FormState = { error: string | null };

const DEPLOYMENT_ID = /^d-\d{1,8}$/;
const SERVICE = /^[a-z0-9-]{2,64}$/;
const SEVERITIES = new Set(["sev1", "sev2", "sev3", "sev4"]);

export async function createIncident(_prev: FormState, form: FormData): Promise<FormState> {
  const description = String(form.get("description") ?? "").trim();
  const service = String(form.get("service_name") ?? "").trim();
  const deployment = String(form.get("deployment_id") ?? "").trim();
  const severity = String(form.get("severity") ?? "").trim();

  if (description.length < 10) return { error: "Describe the incident in at least 10 characters." };
  if (description.length > 5000) return { error: "Description must be under 5,000 characters." };
  if (service && !SERVICE.test(service)) return { error: "Service names use lowercase letters, digits, and dashes." };
  if (deployment && !DEPLOYMENT_ID.test(deployment)) return { error: "Deployment IDs look like d-2041." };
  if (severity && !SEVERITIES.has(severity)) return { error: "Unknown severity." };

  let id: string;
  try {
    const incident = await atlas.createIncident({
      description,
      ...(service && { service_name: service }),
      ...(deployment && { deployment_id: deployment }),
      ...(severity && { severity }),
    });
    id = incident.id;
  } catch (error) {
    return { error: messageFor(error) };
  }
  redirect(`/incidents/${id}`);
}

export async function decideApproval(
  id: string,
  decision: "approved" | "rejected",
  comment: string,
): Promise<FormState> {
  try {
    await atlas.decide(id, decision, comment.slice(0, 2000));
  } catch (error) {
    return { error: messageFor(error) };
  }
  refresh();
  return { error: null };
}

export async function cancelIncident(id: string): Promise<FormState> {
  try {
    await atlas.cancel(id);
  } catch (error) {
    return { error: messageFor(error) };
  }
  refresh();
  return { error: null };
}

function messageFor(error: unknown): string {
  if (error instanceof AtlasApiError) {
    if (error.status === 401) return "The frontend's API key was rejected by the Atlas API.";
    if (error.status === 403) return `Not permitted: ${error.message}`;
    if (error.status === 429) return "Rate limit reached. Try again in a minute.";
    return error.message;
  }
  return "Unexpected error talking to the Atlas API.";
}
