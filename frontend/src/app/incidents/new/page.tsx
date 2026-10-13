import type { Metadata } from "next";

import { IconBook, IconCommit, IconLogs, IconShield, IconSpark, IconTarget } from "@/components/icons";
import { NewIncidentForm } from "@/components/new-incident-form";
import { PageHeader } from "@/components/shell";
import { Panel } from "@/components/ui";

export const metadata: Metadata = { title: "New investigation" };

const STEPS = [
  { icon: <IconSpark size={16} />, title: "Triage", text: "Classifies the incident and resolves the service, deployment, and time window." },
  { icon: <IconLogs size={16} />, title: "Logs", text: "Quantifies error-rate change and clusters error signatures." },
  { icon: <IconCommit size={16} />, title: "Code & commits", text: "Inspects what shipped in the suspect deployment." },
  { icon: <IconBook size={16} />, title: "Knowledge", text: "Finds matching runbooks and prior postmortems." },
  { icon: <IconTarget size={16} />, title: "Root cause review", text: "Scores competing hypotheses; loops back if evidence is thin." },
  { icon: <IconShield size={16} />, title: "Approval gate", text: "Tickets and rollbacks wait for a human decision." },
];

export default function NewIncidentPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="New investigation" subtitle="Describe what you're seeing. Atlas gathers the evidence." />
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <Panel className="xl:col-span-2" title="Incident details">
          <NewIncidentForm />
        </Panel>
        <Panel title="How Atlas investigates">
          <ol className="space-y-4">
            {STEPS.map((step, index) => (
              <li key={step.title} className="flex gap-3">
                <span className="icon-badge flex size-8 shrink-0 items-center justify-center rounded-lg text-st-blue">
                  {step.icon}
                </span>
                <div>
                  <p className="text-sm font-medium text-ink">
                    {index + 1}. {step.title}
                  </p>
                  <p className="text-xs leading-relaxed text-ink-3">{step.text}</p>
                </div>
              </li>
            ))}
          </ol>
        </Panel>
      </div>
    </div>
  );
}
