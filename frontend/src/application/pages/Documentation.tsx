import { marked } from "marked";
import { useState } from "react";
import { ErrorNote, PageHeader, Panel } from "../../components/ui";
import { usePoll } from "../../hooks/useChannel";
import { api } from "../../services/api";

export default function Documentation() {
  const list = usePoll(() => api.get("/api/docs"), 0);
  const [sel, setSel] = useState("ASTRA_OVERVIEW.md");
  const doc = usePoll(() => api.get(`/api/docs/${sel}`), 0, [sel]);
  return (
    <div>
      <PageHeader eyebrow="Equations, units, assumptions, limitations" title="Documentation" />
      <ErrorNote error={list.error || doc.error} />
      <div className="grid lg:grid-cols-[260px_1fr] gap-5">
        <Panel eyebrow="docs/" title="Documents">
          <div className="space-y-0.5 max-h-[70vh] overflow-auto scroll-thin">{(list.data || []).map((d: string) => (
            <button key={d} onClick={() => setSel(d)} className={`w-full text-left text-[12.5px] px-2.5 py-1.5 rounded-[10px] ${sel === d ? "bg-sage" : "hover:bg-sage-soft"}`}>{d.replace(".md", "").replace(/_/g, " ")}</button>))}</div>
        </Panel>
        <Panel><article className="markdown max-w-[860px]" dangerouslySetInnerHTML={{ __html: doc.data?.content ? (marked.parse(doc.data.content) as string) : "" }} /></Panel>
      </div>
    </div>
  );
}
