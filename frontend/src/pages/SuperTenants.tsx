import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useState } from "react";
import { api, fmtDateTime } from "../api";

type TenantStat = {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  plan: string;
  module_workshop: boolean;
  module_shop: boolean;
  user_count: number;
  job_count: number;
  customer_count: number;
  created_at: string;
};

export default function SuperTenants() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<TenantStat[]>({
    queryKey: ["super", "tenants"],
    queryFn: async () => (await api.get("/super/tenants")).data,
  });

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: "",
    slug: "",
    plan: "standard",
    module_workshop: true,
    module_shop: false,
    admin_email: "",
    admin_name: "",
    admin_password: "",
  });

  const create = useMutation({
    mutationFn: async () => (await api.post("/super/tenants", form)).data,
    onSuccess: () => {
      setOpen(false);
      setForm({
        name: "", slug: "", plan: "standard",
        module_workshop: true, module_shop: false,
        admin_email: "", admin_name: "", admin_password: "",
      });
      qc.invalidateQueries({ queryKey: ["super", "tenants"] });
    },
    onError: (e: any) => alert(e?.response?.data?.detail ?? e?.message),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">🛡 Super-admin · Tenants</h1>
        <button className="btn-primary" onClick={() => setOpen(true)}>+ Ny tenant</button>
      </div>

      <div className="card overflow-x-auto">
        {isLoading ? (
          <div className="text-slate-500 p-4">Laster…</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="py-2 pr-3">Navn</th>
                <th className="py-2 pr-3">Slug</th>
                <th className="py-2 pr-3">Plan</th>
                <th className="py-2 pr-3">Moduler</th>
                <th className="py-2 pr-3">Brukere</th>
                <th className="py-2 pr-3">Jobber</th>
                <th className="py-2 pr-3">Kunder</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2 pr-3">Opprettet</th>
                <th className="py-2 pr-3"></th>
              </tr>
            </thead>
            <tbody>
              {data?.map((t) => (
                <tr key={t.id} className="border-t border-slate-100">
                  <td className="py-2 pr-3 font-medium">{t.name}</td>
                  <td className="py-2 pr-3 font-mono text-xs text-slate-600">{t.slug}</td>
                  <td className="py-2 pr-3">{t.plan}</td>
                  <td className="py-2 pr-3 text-xs">
                    {t.module_workshop && <span className="inline-block px-2 py-0.5 mr-1 rounded-full bg-emerald-100 text-emerald-700">verksted</span>}
                    {t.module_shop && <span className="inline-block px-2 py-0.5 rounded-full bg-sky-100 text-sky-700">butikk</span>}
                  </td>
                  <td className="py-2 pr-3">{t.user_count}</td>
                  <td className="py-2 pr-3">{t.job_count}</td>
                  <td className="py-2 pr-3">{t.customer_count}</td>
                  <td className="py-2 pr-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${t.is_active ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`}>
                      {t.is_active ? "aktiv" : "deaktivert"}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-xs text-slate-500">{fmtDateTime(t.created_at)}</td>
                  <td className="py-2 pr-3">
                    <Link to={`/super/tenants/${t.id}`} className="text-gold-600 hover:underline text-sm">Åpne →</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {open && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={() => setOpen(false)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-5 space-y-3" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold">Ny tenant</h2>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Navn</label>
                <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Acme Gull" />
              </div>
              <div>
                <label className="label">Slug</label>
                <input className="input font-mono" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-") })} placeholder="acme-gull" />
              </div>
              <div>
                <label className="label">Plan</label>
                <select className="input" value={form.plan} onChange={(e) => setForm({ ...form, plan: e.target.value })}>
                  <option value="trial">Trial</option>
                  <option value="standard">Standard</option>
                  <option value="pro">Pro</option>
                </select>
              </div>
              <div className="flex items-end gap-3">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={form.module_workshop} onChange={(e) => setForm({ ...form, module_workshop: e.target.checked })} />
                  Verksted
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={form.module_shop} onChange={(e) => setForm({ ...form, module_shop: e.target.checked })} />
                  Butikk
                </label>
              </div>
            </div>
            <hr className="border-slate-200" />
            <div className="text-sm font-medium text-slate-700">Første admin-bruker</div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Navn</label>
                <input className="input" value={form.admin_name} onChange={(e) => setForm({ ...form, admin_name: e.target.value })} />
              </div>
              <div>
                <label className="label">E-post</label>
                <input className="input" type="email" value={form.admin_email} onChange={(e) => setForm({ ...form, admin_email: e.target.value })} />
              </div>
              <div className="col-span-2">
                <label className="label">Passord</label>
                <input className="input" type="text" value={form.admin_password} onChange={(e) => setForm({ ...form, admin_password: e.target.value })} placeholder="Send dette til kunden" />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button className="btn-secondary" onClick={() => setOpen(false)}>Avbryt</button>
              <button
                className="btn-primary"
                onClick={() => create.mutate()}
                disabled={create.isPending || !form.name || !form.slug || !form.admin_email || !form.admin_password || !form.admin_name}
              >
                Opprett
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
