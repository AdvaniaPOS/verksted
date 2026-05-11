import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, parseUTC } from "../api";
import { useAuth } from "../auth";

export default function Admin() {
  const { user } = useAuth();
  if (user?.role !== "admin") {
    return <div className="card">Kun administrator har tilgang til denne siden.</div>;
  }
  return (
    <div className="space-y-8 max-w-4xl">
      <h1 className="text-2xl font-bold text-slate-800">Administrasjon</h1>
      <SusoftSection />
      <PrinterSection />
    </div>
  );
}

// ---------------- Susoft ----------------
function SusoftSection() {
  const qc = useQueryClient();
  const { data: cfg } = useQuery({
    queryKey: ["admin", "susoft"],
    queryFn: async () => (await api.get("/admin/susoft")).data,
  });

  const [form, setForm] = useState({
    base_url: "https://api.susoft.com:4443",
    shop_url_key: "",
    login: "",
    password: "",
    auto_create_order: true,
    is_active: true,
  });
  useEffect(() => {
    if (cfg) {
      setForm((f) => ({
        ...f,
        base_url: cfg.base_url ?? f.base_url,
        shop_url_key: cfg.shop_url_key ?? "",
        login: cfg.login ?? "",
        auto_create_order: cfg.auto_create_order ?? true,
        is_active: cfg.is_active ?? true,
        password: "",
      }));
    }
  }, [cfg]);

  const save = useMutation({
    mutationFn: async () => {
      const payload: any = { ...form };
      if (!payload.password) delete payload.password;
      return (await api.put("/admin/susoft", payload)).data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "susoft"] }),
  });

  const test = useMutation({
    mutationFn: async () => (await api.post("/admin/susoft/test")).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "susoft"] }),
  });

  return (
    <section className="card space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-700">Susoft-integrasjon</h2>
        <span className={`text-xs px-2 py-1 rounded-full ${cfg?.has_password ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>
          {cfg?.has_password ? "Konfigurert" : "Ikke konfigurert"}
        </span>
      </div>
      <p className="text-sm text-slate-500">
        Når dette er aktivert blir alle nye verkstedjobber automatisk pushet til Susoft som «park-ordre»,
        og kunder synkroniseres mot kunderegisteret. Innstillingene er kun synlige for denne kunden (tenant).
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="label">Base-URL</label>
          <input className="input" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} />
        </div>
        <div>
          <label className="label">Shop URL-nøkkel <span className="text-slate-400">(X-Shop-Url-Key)</span></label>
          <input className="input" value={form.shop_url_key} onChange={(e) => setForm({ ...form, shop_url_key: e.target.value })} placeholder="f.eks. jonb" />
        </div>
        <div>
          <label className="label">Innloggings-e-post</label>
          <input className="input" value={form.login} onChange={(e) => setForm({ ...form, login: e.target.value })} placeholder="navn@firma.no" />
        </div>
        <div>
          <label className="label">Passord {cfg?.has_password && <span className="text-xs text-slate-400">(la stå tomt for å beholde eksisterende)</span>}</label>
          <input className="input" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} autoComplete="new-password" />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
          Aktiv
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.auto_create_order} onChange={(e) => setForm({ ...form, auto_create_order: e.target.checked })} />
          Opprett park-ordre automatisk i Susoft ved nye jobber
        </label>
      </div>

      <div className="flex gap-3">
        <button className="btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>
          {save.isPending ? "Lagrer…" : "Lagre"}
        </button>
        <button className="btn-secondary" onClick={() => test.mutate()} disabled={test.isPending || !cfg?.has_password}>
          {test.isPending ? "Tester…" : "Test tilkobling"}
        </button>
      </div>

      {test.data && (
        <div className={`text-sm rounded-md p-3 border ${test.data.ok ? "bg-emerald-50 border-emerald-200 text-emerald-800" : "bg-rose-50 border-rose-200 text-rose-800"}`}>
          {test.data.ok ? `✔ ${test.data.message}${test.data.shop_name ? " — " + test.data.shop_name : ""}` : `✖ ${test.data.message}`}
        </div>
      )}
      {cfg?.last_test_at && !test.data && (
        <div className="text-xs text-slate-500">
          Sist testet: {parseUTC(cfg.last_test_at).toLocaleString("nb-NO")}{" "}
          {cfg.last_test_ok ? "— OK" : `— Feil: ${cfg.last_test_error ?? ""}`}
        </div>
      )}
    </section>
  );
}

// ---------------- Printer ----------------
function PrinterSection() {
  const qc = useQueryClient();
  const { data: cfg } = useQuery({
    queryKey: ["admin", "printer"],
    queryFn: async () => (await api.get("/admin/printer")).data,
  });

  const [form, setForm] = useState({
    paper_width_mm: 80,
    dots_per_line: 576,
    header_line1: "",
    header_line2: "",
    header_line3: "",
    footer_line: "Takk for at du valgte oss!",
    print_qr_on_receipt: true,
    cut_paper: true,
    receipt_url_template: "",
    printer_host: "",
    printer_port: 9100,
    printer_timeout_s: 5,
  });
  useEffect(() => {
    if (cfg) setForm((f) => ({ ...f, ...cfg }));
  }, [cfg]);

  const save = useMutation({
    mutationFn: async () => (await api.put("/admin/printer", form)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "printer"] }),
  });

  const test = useMutation({
    mutationFn: async () => (await api.post("/admin/printer/test")).data,
  });

  return (
    <section className="card space-y-4">
      <h2 className="text-lg font-semibold text-slate-700">Skriver / kvittering</h2>
      <p className="text-sm text-slate-500">
        Innstillinger for innleveringskvittering og verkstedslapp som skrives på Epson ESC/POS termoskriver
        (TM-T20, TM-T88 m.fl.). Endringer trer i kraft umiddelbart.
      </p>

      <div className="rounded-md border border-slate-200 p-3 bg-slate-50/50">
        <div className="font-medium text-slate-700 text-sm mb-2">Nettverksskriver (Epson Ethernet/Wi-Fi)</div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="md:col-span-2">
            <label className="label">IP-adresse / hostname</label>
            <input className="input" value={form.printer_host ?? ""}
              onChange={(e) => setForm({ ...form, printer_host: e.target.value })}
              placeholder="f.eks. 192.168.1.50" />
          </div>
          <div>
            <label className="label">Port</label>
            <input className="input" type="number" value={form.printer_port ?? 9100}
              onChange={(e) => setForm({ ...form, printer_port: Number(e.target.value) })} />
          </div>
          <div>
            <label className="label">Tidsavbrudd (sek)</label>
            <input className="input" type="number" value={form.printer_timeout_s ?? 5}
              onChange={(e) => setForm({ ...form, printer_timeout_s: Number(e.target.value) })} />
          </div>
          <div className="md:col-span-2 flex items-end">
            <button className="btn-secondary" onClick={() => test.mutate()} disabled={test.isPending || !form.printer_host}>
              {test.isPending ? "Sender…" : "Send testutskrift"}
            </button>
          </div>
        </div>
        {test.data && (
          <div className={`text-sm rounded-md p-2 mt-3 border ${test.data.ok ? "bg-emerald-50 border-emerald-200 text-emerald-800" : "bg-rose-50 border-rose-200 text-rose-800"}`}>
            {test.data.ok ? `✔ ${test.data.message} (${test.data.bytes_sent} B)` : `✖ ${test.data.message}`}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="label">Papirbredde (mm)</label>
          <select className="input" value={form.paper_width_mm}
            onChange={(e) => {
              const w = Number(e.target.value);
              setForm({ ...form, paper_width_mm: w, dots_per_line: w >= 80 ? 576 : 384 });
            }}>
            <option value={80}>80 mm (576 dots)</option>
            <option value={58}>58 mm (384 dots)</option>
          </select>
        </div>
        <div>
          <label className="label">Header linje 1 (butikknavn)</label>
          <input className="input" value={form.header_line1 ?? ""} onChange={(e) => setForm({ ...form, header_line1: e.target.value })} />
        </div>
        <div>
          <label className="label">Header linje 2 (adresse)</label>
          <input className="input" value={form.header_line2 ?? ""} onChange={(e) => setForm({ ...form, header_line2: e.target.value })} />
        </div>
        <div>
          <label className="label">Header linje 3 (tlf / org.nr)</label>
          <input className="input" value={form.header_line3 ?? ""} onChange={(e) => setForm({ ...form, header_line3: e.target.value })} />
        </div>
        <div className="md:col-span-2">
          <label className="label">Bunntekst</label>
          <input className="input" value={form.footer_line ?? ""} onChange={(e) => setForm({ ...form, footer_line: e.target.value })} />
        </div>
        <div className="md:col-span-2">
          <label className="label">QR-mål (valgfri URL-mal)</label>
          <input className="input" value={form.receipt_url_template ?? ""} onChange={(e) => setForm({ ...form, receipt_url_template: e.target.value })}
            placeholder="https://gvk.example.com/p/{token}" />
          <div className="text-xs text-slate-500 mt-1">
            Plassholdere: <code>{"{token}"}</code>, <code>{"{number}"}</code>, <code>{"{code}"}</code>, <code>{"{id}"}</code>.
            Hvis tom: QR inneholder kun ordrenr + hentekode.
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.print_qr_on_receipt} onChange={(e) => setForm({ ...form, print_qr_on_receipt: e.target.checked })} />
          Skriv QR på kvittering
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.cut_paper} onChange={(e) => setForm({ ...form, cut_paper: e.target.checked })} />
          Klipp papir automatisk
        </label>
      </div>

      <div>
        <button className="btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>
          {save.isPending ? "Lagrer…" : "Lagre"}
        </button>
      </div>
    </section>
  );
}
