import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ChangeEvent, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, parseUTC } from "../api";
import { openPrint, downloadEscPos } from "../printing";
import CustomerPicker, { Customer } from "../CustomerPicker";
import CameraCapture from "../CameraCapture";

const STATUS_OPTIONS = [
  "registered", "in_transit", "awaiting", "in_progress",
  "waiting_parts", "done", "delivered", "cancelled",
];
const STATUS_LABEL: Record<string, string> = {
  registered: "Registrert", in_transit: "Under transport", awaiting: "Venter",
  in_progress: "Pågår", waiting_parts: "Venter deler", done: "Ferdig",
  delivered: "Hentet", cancelled: "Avbrutt",
};

const TEMPLATES = [
  { key: "received", label: "Mottatt" },
  { key: "ready", label: "Klar for henting" },
  { key: "delayed", label: "Forsinket" },
  { key: "quote", label: "Tilbud" },
];

const ASSET_BASE = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api").replace(/\/api$/, "");

export default function JobDetail() {
  const { id } = useParams();
  const qc = useQueryClient();

  const { data: job, isLoading } = useQuery({
    queryKey: ["job", id],
    queryFn: async () => (await api.get(`/jobs/${id}`)).data,
  });
  const { data: locations } = useQuery({
    queryKey: ["locations"],
    queryFn: async () => (await api.get("/locations")).data,
  });
  const { data: notifications } = useQuery({
    queryKey: ["job", id, "notifications"],
    queryFn: async () => (await api.get(`/jobs/${id}/notifications`)).data,
    enabled: !!id,
  });

  const [editing, setEditing] = useState(false);
  const [edit, setEdit] = useState<any>({});
  const [editCustomer, setEditCustomer] = useState<Customer | null>(null);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [notifyOpen, setNotifyOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (job && editing && Object.keys(edit).length === 0) {
      setEdit({
        description: job.description ?? "",
        job_type: job.job_type ?? "repair",
        metal_type: job.metal_type ?? "",
        gemstones: job.gemstones ?? "",
        estimated_weight_g: job.estimated_weight_g ?? "",
        estimated_price: job.estimated_price ?? "",
        condition_notes: job.condition_notes ?? "",
        estimated_completion: job.estimated_completion ? job.estimated_completion.slice(0, 10) : "",
        weight_in_g: job.weight_in_g ?? "",
        weight_out_g: job.weight_out_g ?? "",
        storage_location: job.storage_location ?? "",
        internal_notes: job.internal_notes ?? "",
      });
      setEditCustomer(job.customer ?? null);
    }
  }, [job, editing]);

  const update = useMutation({
    mutationFn: async (patch: any) => (await api.patch(`/jobs/${id}`, patch)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["job", id] }),
  });

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return (await api.post(`/jobs/${id}/images`, fd, { headers: { "Content-Type": "multipart/form-data" } })).data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["job", id] }),
  });

  const deleteImage = useMutation({
    mutationFn: async (imageId: number) => (await api.delete(`/jobs/${id}/images/${imageId}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["job", id] }),
  });

  const resyncSusoft = useMutation({
    mutationFn: async () => (await api.post(`/jobs/${id}/susoft/sync`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["job", id] }),
    onError: (e: any) => alert("Susoft sync feilet: " + (e?.response?.data?.detail ?? e?.message ?? e)),
  });
  const sendReceipt = useMutation({
    mutationFn: async () => (await api.post(`/jobs/${id}/print/receipt/send`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["job", id] }),
    onError: (e: any) => alert("Utskrift feilet: " + (e?.response?.data?.detail ?? e?.message ?? e)),
  });
  const sendTag = useMutation({
    mutationFn: async () => (await api.post(`/jobs/${id}/print/tag/send`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["job", id] }),
    onError: (e: any) => alert("Utskrift feilet: " + (e?.response?.data?.detail ?? e?.message ?? e)),
  });

  function saveEdit() {
    const patch: any = {};
    const fields = ["description", "job_type", "metal_type", "gemstones", "condition_notes", "storage_location", "internal_notes"];
    for (const f of fields) {
      if ((job?.[f] ?? "") !== edit[f]) patch[f] = edit[f] || null;
    }
    for (const f of ["estimated_weight_g", "estimated_price", "weight_in_g", "weight_out_g"]) {
      if (String(job?.[f] ?? "") !== String(edit[f] ?? "")) {
        patch[f] = edit[f] === "" || edit[f] == null ? null : Number(edit[f]);
      }
    }
    const oldDate = job?.estimated_completion ? job.estimated_completion.slice(0, 10) : "";
    if (oldDate !== edit.estimated_completion) {
      patch.estimated_completion = edit.estimated_completion ? new Date(edit.estimated_completion).toISOString() : null;
    }
    if ((editCustomer?.id ?? null) !== (job?.customer?.id ?? null)) {
      patch.customer_id = editCustomer?.id ?? null;
    }
    if (Object.keys(patch).length === 0) {
      setEditing(false); setEdit({}); return;
    }
    update.mutate(patch, { onSuccess: () => { setEditing(false); setEdit({}); qc.invalidateQueries({ queryKey: ["job", id] }); } });
  }

  if (isLoading || !job) return <div>Laster…</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">{job.job_number}</h1>
          <div className="text-slate-500">
            {job.customer ? (
              <Link to={`/kunder/${job.customer.id}`} className="hover:underline">{job.customer.name}</Link>
            ) : "Ingen kunde"}
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs text-slate-500">Hentekode</div>
          <div className="text-xl font-mono font-bold text-gold-600">{job.pickup_code}</div>
          {job.susoft_order_id && <div className="text-xs text-emerald-600 mt-1">Susoft #{job.susoft_order_id}</div>}
        </div>
      </div>

      {/* Action toolbar */}
      <div className="card flex flex-wrap gap-2 items-center">
        <button className="btn-primary" onClick={() => sendReceipt.mutate()} disabled={sendReceipt.isPending}>
          {sendReceipt.isPending ? "Sender…" : "🖨️ Kvittering"}
        </button>
        <button className="btn-primary" onClick={() => sendTag.mutate()} disabled={sendTag.isPending}>
          {sendTag.isPending ? "Sender…" : "🖨️ Lapp"}
        </button>
        <button className="btn-secondary text-sm" onClick={() => openPrint(`/jobs/${id}/print/receipt.html?auto=1`)}>🧾 PDF kvittering</button>
        <button className="btn-secondary text-sm" onClick={() => openPrint(`/jobs/${id}/print/tag.html?auto=1`)}>🏷️ PDF lapp</button>
        <button className="btn-secondary text-xs" title="Last ned ESC/POS"
          onClick={() => downloadEscPos(`/jobs/${id}/print/receipt.escpos`, `kvittering-${job.job_number}.bin`)}>.escpos kvittering</button>
        <button className="btn-secondary text-xs"
          onClick={() => downloadEscPos(`/jobs/${id}/print/tag.escpos`, `lapp-${job.job_number}.bin`)}>.escpos lapp</button>
        <span className="flex-1" />
        <button className="btn-primary" onClick={() => setNotifyOpen(true)} disabled={!job.customer}>✉️ Varsle kunde</button>
        <button className="btn-secondary text-sm" onClick={() => resyncSusoft.mutate()} disabled={resyncSusoft.isPending}>
          {resyncSusoft.isPending ? "Synker…" : (job.susoft_order_id ? "Synk Susoft" : "Push til Susoft")}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Details / Edit */}
        <div className="card lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-slate-700">Detaljer</h2>
            {!editing ? (
              <button className="btn-secondary text-sm" onClick={() => setEditing(true)}>✏️ Rediger</button>
            ) : (
              <div className="flex gap-2">
                <button className="btn-primary text-sm" onClick={saveEdit} disabled={update.isPending}>
                  {update.isPending ? "Lagrer…" : "Lagre"}
                </button>
                <button className="btn-secondary text-sm" onClick={() => { setEditing(false); setEdit({}); }}>Avbryt</button>
              </div>
            )}
          </div>
          {!editing ? (
            <>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><span className="text-slate-500">Type:</span> {job.job_type}</div>
                <div><span className="text-slate-500">Metall:</span> {job.metal_type ?? "—"}</div>
                <div><span className="text-slate-500">Edelstener:</span> {job.gemstones ?? "—"}</div>
                <div><span className="text-slate-500">Vekt (estimert):</span> {job.estimated_weight_g ?? "—"} g</div>
                <div><span className="text-slate-500">Vekt inn:</span> {job.weight_in_g ?? "—"} g</div>
                <div><span className="text-slate-500">Vekt ut:</span> {job.weight_out_g ?? "—"} g</div>
                <div><span className="text-slate-500">Pris:</span> {job.estimated_price ?? "—"} kr</div>
                <div><span className="text-slate-500">Forfall:</span> {job.estimated_completion ? new Date(job.estimated_completion).toLocaleDateString("nb-NO") : "—"}</div>
                <div className="col-span-2"><span className="text-slate-500">Lagerplass:</span> {job.storage_location ?? "—"}</div>
              </div>
              <div><div className="text-slate-500 text-sm">Beskrivelse</div><div>{job.description ?? "—"}</div></div>
              <div><div className="text-slate-500 text-sm">Tilstand</div><div>{job.condition_notes ?? "—"}</div></div>
              {job.internal_notes && (
                <div className="bg-amber-50 border border-amber-200 rounded p-2">
                  <div className="text-amber-700 text-xs font-semibold mb-1">🔒 Internt notat</div>
                  <div className="text-sm whitespace-pre-wrap">{job.internal_notes}</div>
                </div>
              )}
            </>
          ) : (
            <div className="space-y-3">
              <div>
                <label className="label">Kunde</label>
                <CustomerPicker value={editCustomer} onChange={setEditCustomer} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Type</label>
                  <select className="input" value={edit.job_type} onChange={(e) => setEdit({ ...edit, job_type: e.target.value })}>
                    <option value="repair">Reparasjon</option><option value="design">Design</option>
                    <option value="sale">Salg</option><option value="other">Annet</option>
                  </select>
                </div>
                <div>
                  <label className="label">Forfall</label>
                  <input className="input" type="date" value={edit.estimated_completion}
                    onChange={(e) => setEdit({ ...edit, estimated_completion: e.target.value })} />
                </div>
                <div><label className="label">Metalltype</label>
                  <input className="input" value={edit.metal_type} onChange={(e) => setEdit({ ...edit, metal_type: e.target.value })} /></div>
                <div><label className="label">Edelstener</label>
                  <input className="input" value={edit.gemstones} onChange={(e) => setEdit({ ...edit, gemstones: e.target.value })} /></div>
                <div><label className="label">Vekt (g)</label>
                  <input className="input" type="number" step="0.001" value={edit.estimated_weight_g}
                    onChange={(e) => setEdit({ ...edit, estimated_weight_g: e.target.value })} /></div>
                <div><label className="label">Pris (kr)</label>
                  <input className="input" type="number" step="0.01" value={edit.estimated_price}
                    onChange={(e) => setEdit({ ...edit, estimated_price: e.target.value })} /></div>
                <div><label className="label">Vekt inn (g)</label>
                  <input className="input" type="number" step="0.001" value={edit.weight_in_g}
                    onChange={(e) => setEdit({ ...edit, weight_in_g: e.target.value })} /></div>
                <div><label className="label">Vekt ut (g)</label>
                  <input className="input" type="number" step="0.001" value={edit.weight_out_g}
                    onChange={(e) => setEdit({ ...edit, weight_out_g: e.target.value })} /></div>
                <div className="col-span-2"><label className="label">Lagerplass (skap/hylle/boks)</label>
                  <input className="input" placeholder="f.eks. Skap A / Hylle 3 / Boks 12" value={edit.storage_location}
                    onChange={(e) => setEdit({ ...edit, storage_location: e.target.value })} /></div>
              </div>
              <div><label className="label">Beskrivelse</label>
                <textarea className="input" rows={3} value={edit.description}
                  onChange={(e) => setEdit({ ...edit, description: e.target.value })} /></div>
              <div><label className="label">Tilstand</label>
                <textarea className="input" rows={2} value={edit.condition_notes}
                  onChange={(e) => setEdit({ ...edit, condition_notes: e.target.value })} /></div>
              <div><label className="label">Internt notat (vises ikke for kunde)</label>
                <textarea className="input" rows={2} value={edit.internal_notes}
                  onChange={(e) => setEdit({ ...edit, internal_notes: e.target.value })} /></div>
            </div>
          )}
        </div>

        {/* Status / Location / Upload */}
        <div className="card space-y-3">
          <h2 className="font-semibold text-slate-700">Hurtighandlinger</h2>
          <div>
            <label className="label">Status</label>
            <select className="input" value={job.status}
              onChange={(e: ChangeEvent<HTMLSelectElement>) => update.mutate({ status: e.target.value })}>
              {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{STATUS_LABEL[s] ?? s}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Lokasjon</label>
            <select className="input" value={job.location?.id ?? ""}
              onChange={(e) => update.mutate({ location_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">— Ingen —</option>
              {locations?.map((l: any) => <option key={l.id} value={l.id}>{l.label}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Bilder</label>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={(e) => {
                const files = Array.from(e.target.files ?? []);
                files.forEach((f) => upload.mutate(f));
                if (fileInputRef.current) fileInputRef.current.value = "";
              }}
            />
            <div className="flex flex-wrap gap-2">
              <button className="btn-primary text-sm" onClick={() => setCameraOpen(true)}>📸 Kamera</button>
              <button className="btn-secondary text-sm" onClick={() => fileInputRef.current?.click()}>📁 Velg fil(er)</button>
            </div>
            {upload.isPending && <div className="text-xs text-slate-500 mt-1">Laster opp…</div>}
          </div>
        </div>
      </div>

      {/* Images */}
      {job.images?.length > 0 && (
        <div className="card">
          <h2 className="font-semibold text-slate-700 mb-3">Bilder ({job.images.length})</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
            {job.images.map((img: any) => (
              <div key={img.id} className="relative group">
                <a href={`${ASSET_BASE}/uploads/${img.file_path}`} target="_blank" rel="noreferrer">
                  <img src={`${ASSET_BASE}/uploads/${img.file_path}`}
                    className="rounded-md border border-slate-200 object-cover aspect-square w-full" alt={img.caption ?? ""} />
                </a>
                <button
                  className="absolute top-1 right-1 bg-rose-600 text-white rounded-full w-6 h-6 text-xs opacity-0 group-hover:opacity-100 transition"
                  title="Slett bilde"
                  onClick={() => { if (confirm("Slette dette bildet?")) deleteImage.mutate(img.id); }}>
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Notifications history */}
      {notifications && notifications.length > 0 && (
        <div className="card">
          <h2 className="font-semibold text-slate-700 mb-3">Sendte varsler</h2>
          <ul className="text-sm space-y-1">
            {notifications.map((n: any) => (
              <li key={n.id} className="border-b last:border-0 border-slate-100 py-2 flex gap-3">
                <span className="text-xs text-slate-400 w-36">
                  {n.sent_at ? parseUTC(n.sent_at).toLocaleString("nb-NO") : "—"}
                </span>
                <span className="font-medium uppercase text-xs w-12">{n.channel}</span>
                <span className="text-slate-600 w-40 truncate">{n.recipient}</span>
                <span className="flex-1 text-slate-700 truncate">{n.body}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  n.status === "sent" ? "bg-green-100 text-green-700" :
                  n.status === "failed" ? "bg-rose-100 text-rose-700" : "bg-slate-100 text-slate-600"
                }`}>{n.status}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Time / Parts / Comments */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <TimeTracker jobId={Number(id)} job={job} />
        <PartsSection jobId={Number(id)} parts={job.parts ?? []} />
        <CommentsSection jobId={Number(id)} comments={job.comments ?? []} />
      </div>

      {/* Audit log */}
      <div className="card">
        <h2 className="font-semibold text-slate-700 mb-3">Audit-logg</h2>
        <ul className="space-y-1 text-sm">
          {job.logs?.map((l: any) => (
            <li key={l.id} className="flex gap-3 border-b border-slate-100 py-1">
              <span className="text-slate-400 w-44">{parseUTC(l.created_at).toLocaleString("nb-NO")}</span>
              <span className="font-medium">{l.action}</span>
              <span className="text-slate-600">
                {l.from_value && `${l.from_value} → `}{l.to_value}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <CameraCapture
        open={cameraOpen}
        onClose={() => setCameraOpen(false)}
        onCapture={(file) => { upload.mutate(file); setCameraOpen(false); }}
      />
      {notifyOpen && (
        <NotifyModal jobId={Number(id)} customer={job.customer} onClose={() => setNotifyOpen(false)} />
      )}
    </div>
  );
}

function NotifyModal({ jobId, customer, onClose }: { jobId: number; customer: any; onClose: () => void }) {
  const qc = useQueryClient();
  const [channel, setChannel] = useState<"sms" | "email">(customer?.phone ? "sms" : "email");
  const [template, setTemplate] = useState("ready");
  const [recipient, setRecipient] = useState(customer?.phone ?? customer?.email ?? "");
  const [bodyOverride, setBodyOverride] = useState("");

  useEffect(() => {
    setRecipient(channel === "sms" ? (customer?.phone ?? "") : (customer?.email ?? ""));
  }, [channel, customer]);

  const send = useMutation({
    mutationFn: async () => (await api.post(`/jobs/${jobId}/notify`, {
      channel, template, recipient, body: bodyOverride || undefined,
    })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["job", String(jobId), "notifications"] });
      qc.invalidateQueries({ queryKey: ["job", String(jobId)] });
      onClose();
    },
    onError: (e: any) => alert("Kunne ikke sende: " + (e?.response?.data?.detail ?? e?.message ?? e)),
  });

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full">
        <div className="px-4 py-3 border-b flex items-center justify-between">
          <div className="font-semibold">Varsle kunde</div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700">✕</button>
        </div>
        <div className="p-4 space-y-3">
          <div className="flex gap-2">
            {(["sms", "email"] as const).map((c) => (
              <button key={c} onClick={() => setChannel(c)}
                className={`px-4 py-2 rounded-md text-sm font-medium ${channel === c ? "bg-gold-500 text-white" : "bg-slate-100 text-slate-700"}`}>
                {c === "sms" ? "📱 SMS" : "✉ E-post"}
              </button>
            ))}
          </div>
          <div>
            <label className="label">Mal</label>
            <select className="input" value={template} onChange={(e) => setTemplate(e.target.value)}>
              {TEMPLATES.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Mottaker</label>
            <input className="input" value={recipient} onChange={(e) => setRecipient(e.target.value)}
              placeholder={channel === "sms" ? "+47 XXX XX XXX" : "navn@eksempel.no"} />
          </div>
          <div>
            <label className="label">Egendefinert tekst (valgfri – overstyrer mal)</label>
            <textarea className="input" rows={3} value={bodyOverride} onChange={(e) => setBodyOverride(e.target.value)}
              placeholder="La stå tom for å bruke malen" />
          </div>
          <div className="text-xs text-slate-500 bg-amber-50 border border-amber-200 rounded p-2">
            ⚠ Ingen SMS/e-post-tjeneste er koblet til ennå. Varselet logges, men ikke faktisk sendt før integrasjon er på plass.
          </div>
        </div>
        <div className="px-4 py-3 border-t flex gap-2 justify-end">
          <button className="btn-secondary" onClick={onClose}>Avbryt</button>
          <button className="btn-primary" onClick={() => send.mutate()} disabled={send.isPending || !recipient}>
            {send.isPending ? "Sender…" : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}


// ----------------- Time tracker -----------------
function TimeTracker({ jobId, job }: { jobId: number; job: any }) {
  const qc = useQueryClient();
  const [tick, setTick] = useState(0);
  const [stopOpen, setStopOpen] = useState(false);
  const [stopNote, setStopNote] = useState("");
  const [stopOnReceipt, setStopOnReceipt] = useState(false);

  useEffect(() => {
    if (!job.open_time_entry_id || stopOpen) return;
    const t = setInterval(() => setTick((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, [job.open_time_entry_id, stopOpen]);

  const { data: entries } = useQuery({
    queryKey: ["job", jobId, "time"],
    queryFn: async () => (await api.get(`/jobs/${jobId}/time`)).data,
  });
  const start = useMutation({
    mutationFn: async () => (await api.post(`/jobs/${jobId}/time/start`, {})).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["job", String(jobId)] });
      qc.invalidateQueries({ queryKey: ["job", jobId, "time"] });
    },
  });
  const stop = useMutation({
    mutationFn: async (body: { note?: string; show_on_receipt?: boolean }) =>
      (await api.post(`/jobs/${jobId}/time/stop`, body)).data,
    onSuccess: () => {
      setStopOpen(false);
      setStopNote("");
      setStopOnReceipt(false);
      qc.invalidateQueries({ queryKey: ["job", String(jobId)] });
      qc.invalidateQueries({ queryKey: ["job", jobId, "time"] });
      qc.invalidateQueries({ queryKey: ["job", jobId, "comments"] });
    },
  });

  const open = entries?.find((e: any) => !e.stopped_at);
  const liveSec = open ? Math.floor((Date.now() - parseUTC(open.started_at).getTime()) / 1000) : 0;
  const total = job.total_minutes ?? 0;

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-slate-700">⏱ Tid</h2>
        <span className="text-xs text-slate-500">Total: <b>{fmtMinutes(total)}</b></span>
      </div>
      {open ? (
        <div className="bg-emerald-50 border border-emerald-200 rounded-md p-3">
          <div className="text-xs text-emerald-700 mb-1">{open.user_name ?? "Du"} arbeider nå</div>
          <div className="text-3xl font-mono font-bold text-emerald-700">{fmtClock(liveSec + tick * 0)}</div>
          <button className="btn-secondary mt-2 w-full" onClick={() => setStopOpen(true)} disabled={stop.isPending}>
            ⏸ Stopp
          </button>
        </div>
      ) : (
        <button className="btn-primary w-full" onClick={() => start.mutate()} disabled={start.isPending}>
          ▶ Start arbeid
        </button>
      )}
      {entries && entries.length > 0 && (
        <ul className="text-xs space-y-1 max-h-40 overflow-auto">
          {entries.slice(0, 10).map((e: any) => (
            <li key={e.id} className="flex justify-between border-b border-slate-100 py-1">
              <span className="text-slate-600">
                {e.user_name ?? "—"} · {parseUTC(e.started_at).toLocaleString("nb-NO", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
              </span>
              <span className={e.stopped_at ? "text-slate-700" : "text-emerald-700 font-medium"}>
                {e.stopped_at ? fmtMinutes(e.minutes) : "pågår"}
              </span>
            </li>
          ))}
        </ul>
      )}

      {stopOpen && createPortal(
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-slate-800">Stopp arbeid</h3>
              <button
                className="text-slate-400 hover:text-slate-700"
                onClick={() => setStopOpen(false)}
                disabled={stop.isPending}
              >✕</button>
            </div>
            <p className="text-xs text-slate-500">Hva har du gjort? Skriv en kort kommentar.</p>
            <textarea
              className="input text-sm w-full min-h-[100px]"
              placeholder="F.eks. polert ring, byttet lås, justert klokkelenke …"
              value={stopNote}
              onChange={(e) => setStopNote(e.target.value)}
              autoFocus
            />
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={stopOnReceipt}
                onChange={(e) => setStopOnReceipt(e.target.checked)}
              />
              <span>Vis kommentaren på kvitteringen til kunden</span>
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <button
                className="btn-secondary text-sm"
                onClick={() => setStopOpen(false)}
                disabled={stop.isPending}
              >
                Avbryt
              </button>
              <button
                className="btn-primary text-sm"
                onClick={() => stop.mutate({ note: stopNote.trim() || undefined, show_on_receipt: stopOnReceipt })}
                disabled={stop.isPending}
              >
                ⏸ Stopp arbeid
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}

function fmtMinutes(m: number) {
  if (!m) return "0 min";
  const h = Math.floor(m / 60); const r = m % 60;
  return h > 0 ? `${h}t ${r}m` : `${r} min`;
}
function fmtClock(s: number) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}


// ----------------- Comments -----------------
function CommentsSection({ jobId, comments: initial }: { jobId: number; comments: any[] }) {
  const qc = useQueryClient();
  const { data: comments } = useQuery({
    queryKey: ["job", jobId, "comments"],
    queryFn: async () => (await api.get(`/jobs/${jobId}/comments`)).data,
    initialData: initial,
  });
  const [body, setBody] = useState("");
  const [internal, setInternal] = useState(true);
  const add = useMutation({
    mutationFn: async () => (await api.post(`/jobs/${jobId}/comments`, { body, is_internal: internal })).data,
    onSuccess: () => {
      setBody("");
      qc.invalidateQueries({ queryKey: ["job", jobId, "comments"] });
      qc.invalidateQueries({ queryKey: ["job", String(jobId)] });
    },
  });
  const del = useMutation({
    mutationFn: async (cid: number) => (await api.delete(`/jobs/${jobId}/comments/${cid}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["job", jobId, "comments"] }),
  });

  return (
    <div className="card space-y-3">
      <h2 className="font-semibold text-slate-700">💬 Kommentarer ({comments?.length ?? 0})</h2>
      <div className="space-y-2 max-h-64 overflow-auto">
        {comments?.length === 0 && <div className="text-sm text-slate-400 italic">Ingen kommentarer ennå</div>}
        {comments?.map((c: any) => (
          <div key={c.id} className={`text-sm rounded-md p-2 ${c.is_internal ? "bg-amber-50 border border-amber-100" : "bg-sky-50 border border-sky-100"}`}>
            <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
              <span>
                <b className="text-slate-700">{c.user_name ?? "—"}</b>
                {" · "}{parseUTC(c.created_at).toLocaleString("nb-NO", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
                {c.is_internal ? " · 🔒 internt" : " · 📤 kunde"}
              </span>
              <button className="text-slate-400 hover:text-rose-600" onClick={() => { if (confirm("Slett?")) del.mutate(c.id); }}>✕</button>
            </div>
            <div className="whitespace-pre-wrap">{c.body}</div>
          </div>
        ))}
      </div>
      <div className="space-y-2 pt-2 border-t border-slate-100">
        <textarea className="input" rows={2} placeholder="Skriv kommentar…"
          value={body} onChange={(e) => setBody(e.target.value)} />
        <div className="flex items-center justify-between">
          <label className="text-xs flex items-center gap-1 text-slate-600">
            <input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} />
            Kun internt
          </label>
          <button className="btn-primary text-sm" onClick={() => add.mutate()} disabled={!body.trim() || add.isPending}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
}


// ----------------- Parts -----------------
const PART_STATUS_LABEL: Record<string, string> = {
  needed: "Trenger", ordered: "Bestilt", received: "Mottatt", installed: "Montert", cancelled: "Avbrutt",
};
const PART_STATUS_COLOR: Record<string, string> = {
  needed: "bg-amber-100 text-amber-700",
  ordered: "bg-sky-100 text-sky-700",
  received: "bg-emerald-100 text-emerald-700",
  installed: "bg-emerald-100 text-emerald-700",
  cancelled: "bg-slate-100 text-slate-600",
};

function PartsSection({ jobId, parts: initial }: { jobId: number; parts: any[] }) {
  const qc = useQueryClient();
  const { data: parts } = useQuery({
    queryKey: ["job", jobId, "parts"],
    queryFn: async () => (await api.get(`/jobs/${jobId}/parts`)).data,
    initialData: initial,
  });
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState<any>({ description: "", supplier: "", supplier_ref: "", quantity: 1, cost_price: "", sale_price: "" });

  const create = useMutation({
    mutationFn: async () => (await api.post(`/jobs/${jobId}/parts`, {
      ...form,
      cost_price: form.cost_price === "" ? null : Number(form.cost_price),
      sale_price: form.sale_price === "" ? null : Number(form.sale_price),
      quantity: Number(form.quantity),
    })).data,
    onSuccess: () => {
      setAdding(false);
      setForm({ description: "", supplier: "", supplier_ref: "", quantity: 1, cost_price: "", sale_price: "" });
      qc.invalidateQueries({ queryKey: ["job", jobId, "parts"] });
      qc.invalidateQueries({ queryKey: ["job", String(jobId)] });
    },
  });
  const patch = useMutation({
    mutationFn: async ({ id, body }: { id: number; body: any }) =>
      (await api.patch(`/jobs/${jobId}/parts/${id}`, body)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["job", jobId, "parts"] });
      qc.invalidateQueries({ queryKey: ["job", String(jobId)] });
    },
  });
  const del = useMutation({
    mutationFn: async (pid: number) => (await api.delete(`/jobs/${jobId}/parts/${pid}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["job", jobId, "parts"] }),
  });

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-slate-700">🛒 Deler ({parts?.length ?? 0})</h2>
        <button className="btn-secondary text-xs" onClick={() => setAdding((v) => !v)}>
          {adding ? "Avbryt" : "+ Ny"}
        </button>
      </div>
      {adding && (
        <div className="bg-slate-50 border border-slate-200 rounded-md p-3 space-y-2">
          <input className="input text-sm" placeholder="Beskrivelse (f.eks. Lås 14k gull 5mm)"
            value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <div className="grid grid-cols-2 gap-2">
            <input className="input text-sm" placeholder="Leverandør"
              value={form.supplier} onChange={(e) => setForm({ ...form, supplier: e.target.value })} />
            <input className="input text-sm" placeholder="Lev. ref / artikkelnr"
              value={form.supplier_ref} onChange={(e) => setForm({ ...form, supplier_ref: e.target.value })} />
            <input className="input text-sm" type="number" step="0.001" placeholder="Antall"
              value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
            <input className="input text-sm" type="number" step="0.01" placeholder="Innkjøpspris (intern)"
              value={form.cost_price} onChange={(e) => setForm({ ...form, cost_price: e.target.value })} />
            <input className="input text-sm" type="number" step="0.01" placeholder="Utpris (kunde)"
              value={form.sale_price} onChange={(e) => setForm({ ...form, sale_price: e.target.value })} />
          </div>
          <button className="btn-primary text-sm w-full"
            onClick={() => create.mutate()} disabled={!form.description.trim() || create.isPending}>
            Legg til
          </button>
        </div>
      )}
      <ul className="space-y-2 max-h-72 overflow-auto">
        {parts?.length === 0 && !adding && <li className="text-sm text-slate-400 italic">Ingen deler</li>}
        {parts?.map((p: any) => (
          <li key={p.id} className="border border-slate-200 rounded-md p-2 text-sm">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="font-medium truncate">{p.description}</div>
                <div className="text-xs text-slate-500">
                  {p.supplier ?? "—"}{p.supplier_ref ? ` · ${p.supplier_ref}` : ""}
                  {p.quantity ? ` · ${p.quantity} stk` : ""}
                  {p.cost_price ? ` · innkj. kr ${p.cost_price}` : ""}
                  {p.sale_price ? ` · utpris kr ${p.sale_price}` : ""}
                </div>
              </div>
              <button className="text-slate-400 hover:text-rose-600 text-xs"
                onClick={() => { if (confirm("Slett delen?")) del.mutate(p.id); }}>✕</button>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-1">
              <span className={`text-xs px-2 py-0.5 rounded-full ${PART_STATUS_COLOR[p.status] ?? "bg-slate-100"}`}>
                {PART_STATUS_LABEL[p.status] ?? p.status}
              </span>
              {Object.keys(PART_STATUS_LABEL).filter((s) => s !== p.status).map((s) => (
                <button key={s} className="text-xs px-2 py-0.5 rounded-full border border-slate-200 hover:bg-slate-50"
                  onClick={() => patch.mutate({ id: p.id, body: { status: s } })}>
                  → {PART_STATUS_LABEL[s]}
                </button>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
