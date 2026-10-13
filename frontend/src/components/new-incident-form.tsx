"use client";

import { useActionState, useState } from "react";

import { type FormState, createIncident } from "@/app/actions";
import { IconAlert, IconArrowRight } from "@/components/icons";

// Prompts that match the mock integrations shipped with the backend.
const EXAMPLES = [
  {
    label: "Checkout errors after deploy",
    text: "Investigate why the latest deployment of checkout-api caused an increase in API errors. Analyze the logs, inspect recent commits, identify the likely root cause, and prepare a remediation plan.",
  },
  {
    label: "Payments 502s",
    text: "payments-service is returning 502s on charges since deployment d-3107 this morning.",
  },
  {
    label: "Slow logins",
    text: "Login latency spiked for auth-service around 2026-10-12 08:00 UTC; users report slow sign-in.",
  },
];

const initial: FormState = { error: null };

export function NewIncidentForm() {
  const [state, action, pending] = useActionState(createIncident, initial);
  const [description, setDescription] = useState("");

  return (
    <form action={action} className="space-y-5">
      <div>
        <div className="mb-2 flex flex-wrap gap-2">
          {EXAMPLES.map((example) => (
            <button
              key={example.label}
              type="button"
              onClick={() => setDescription(example.text)}
              className="rounded-lg border border-line px-3 py-1.5 text-xs text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
            >
              {example.label}
            </button>
          ))}
        </div>
        <label htmlFor="description" className="mb-1.5 block text-sm font-medium text-ink">
          What is happening?
        </label>
        <textarea
          id="description"
          name="description"
          required
          minLength={10}
          maxLength={5000}
          rows={6}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="e.g. checkout-api started returning HTTP 500s right after this afternoon's deployment…"
          className="field w-full resize-y rounded-xl px-4 py-3 text-sm text-ink placeholder:text-ink-3"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Field label="Service (optional)" name="service_name" placeholder="checkout-api" pattern="[a-z0-9-]{2,64}" />
        <Field label="Deployment (optional)" name="deployment_id" placeholder="d-2041" pattern="d-\d{1,8}" />
        <div>
          <label htmlFor="severity" className="mb-1.5 block text-sm font-medium text-ink">
            Severity (optional)
          </label>
          <select id="severity" name="severity" defaultValue="" className="field h-10 w-full rounded-xl px-3 text-sm text-ink">
            <option value="">Let triage decide</option>
            <option value="sev1">SEV1 - critical</option>
            <option value="sev2">SEV2 - major</option>
            <option value="sev3">SEV3 - minor</option>
            <option value="sev4">SEV4 - low</option>
          </select>
        </div>
      </div>

      {state.error && (
        <p role="alert" className="flex items-center gap-2 rounded-xl border border-st-red/30 bg-st-red/10 px-4 py-3 text-sm text-st-red">
          <IconAlert size={16} /> {state.error}
        </p>
      )}

      <div className="flex items-center justify-between gap-4 border-t border-line pt-5">
        <p className="text-xs text-ink-3">Hints are validated against the service catalog before use.</p>
        <button
          type="submit"
          disabled={pending}
          className="btn-primary flex h-10 items-center gap-2 rounded-xl px-5 text-sm font-medium text-white disabled:opacity-60"
        >
          {pending ? "Starting…" : "Start investigation"}
          {!pending && <IconArrowRight size={16} />}
        </button>
      </div>
    </form>
  );
}

function Field({ label, name, placeholder, pattern }: { label: string; name: string; placeholder: string; pattern: string }) {
  return (
    <div>
      <label htmlFor={name} className="mb-1.5 block text-sm font-medium text-ink">
        {label}
      </label>
      <input
        id={name}
        name={name}
        placeholder={placeholder}
        pattern={pattern}
        className="field h-10 w-full rounded-xl px-3 text-sm text-ink placeholder:text-ink-3"
      />
    </div>
  );
}
