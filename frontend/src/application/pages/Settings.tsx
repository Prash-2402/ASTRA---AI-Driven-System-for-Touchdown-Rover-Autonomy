import { useState } from "react";
import { Field, PageHeader, Panel } from "../../components/ui";
import { usePoll } from "../../hooks/useChannel";
import { api, apiBase, setApiBase } from "../../services/api";

export default function Settings() {
  const [base, setBase] = useState(apiBase());
  const status = usePoll(() => api.get("/api/platform/status"), 0);
  const profiles = usePoll(() => api.get("/api/profiles"), 0);
  const [name, setName] = useState("");
  return (
    <div>
      <PageHeader eyebrow="Local configuration" title="Settings" />
      <div className="grid lg:grid-cols-2 gap-5">
        <Panel eyebrow="Connection" title="Backend API">
          <Field label="API base URL"><input className="input num" value={base} onChange={(e) => setBase(e.target.value)} /></Field>
          <button className="btn btn-primary mt-3" onClick={() => { setApiBase(base); location.reload(); }}>Save & reload</button>
          <p className="text-[11px] text-muted mt-2">Stored in this browser only.</p>
        </Panel>
        <Panel eyebrow="Profiles" title="Local research profiles">
          <div className="flex gap-2"><input className="input" placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
            <button className="btn btn-sage" onClick={() => api.post("/api/profiles", { name }).then(() => { setName(""); profiles.refresh(); })}>Add</button></div>
          <ul className="mt-3 text-[13px] space-y-1">{(profiles.data || []).map((p: any) => <li key={p.id} className="chip">{p.name}</li>)}</ul>
        </Panel>
        <Panel eyebrow="Reproducibility" title="Software versions" className="lg:col-span-2">
          <pre className="num text-[11px] text-ink2">{JSON.stringify({ software: status.data?.software, database: status.data?.database }, null, 2)}</pre>
        </Panel>
      </div>
    </div>
  );
}
