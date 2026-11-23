import { AssistantChat } from "@/components/assistant-chat";
import { apiFetch } from "@/lib/api/server";
import type { PrescriptionList } from "@/lib/api/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "AI Assistant — Prescription Digitizer" };

export default async function AssistantPage() {
  const list = await apiFetch<PrescriptionList>(
    "/prescriptions?page=1&page_size=100",
  );

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">AI assistant</h1>
        <p className="text-muted-foreground text-sm">
          Ask questions about medications and prescriptions — answers stream
          from your local model.
        </p>
      </div>
      <AssistantChat prescriptions={list.items} />
    </div>
  );
}
