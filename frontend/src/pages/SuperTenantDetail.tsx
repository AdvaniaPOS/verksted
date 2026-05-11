import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { api, fmtDateTime } from "../api";
import { useAuth } from "../auth";

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

type SusoftCfg = {
  base_url?: string;
  shop_url_key?: string;
  login?: string;
  has_password?: boolean;
  auto_create_order?: boolean;
  is_active?: boolean;
  last_test_at?: string | null;
  last_test_ok?: boolean | null;
  last_test_error?: string | null;
};

export default function SuperTenantDetail() {
  const { id } = useParams();
  const tid = Number(id);
  const qc = useQueryClient();
  const { beginImpersonation } = useAuth();

  const { data: tenant } = useQuery<TenantStat>({
    queryKey: ["super", "tenant", tid],
    queryFn: async () => (await api.get(`/super/tenants/${tid}`)).data,
  });
  const { data: users } = useQuery<any[]>({
    queryKey: ["super", "tenant", tid, "users"],
    queryFn: async () => (await api.get(`/super/tenants/${tid}/users`)).data,
  });
  const { data: susoft } = useQuery<SusoftCfg>({
    queryKey: ["super", "tenant", tid, "susoft"],
    queryFn: async () => (await api.get(`/super/tenants/${tid}/susoft`)).data,
  });

  const [edit, setEdit] = useState<Partial<TenantStat>>({});
  useEffect(() => {
    if (tenant) setEdit({
      name: tenant.name, plan: tenant.plan, is_active: tenant.is_active,
      module_workshop: tenant.module_workshop, module_shop: tenant.module_shop,
    });
  }, [tenant]);

  const save = useMutation({
    mutationFn: async () => (await api.patch(`/super/tenants/${tid}`, edit)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["super", "tenant", tid] }),
  });

  const [sf, setSf] = useState<any>({});
  useEffect(() => {
    if (susoft) setSf({
      base_url: susoft.base_url ?? "https://api.susoft.com:4443",
      shop_url_key: susoft.shop_url_key ?? "",
      login: susoft.login ?? "",
      password: "",
      auto_create_order: !!susoft.auto_create_order,
      is_active: !!susoft.is_active,
    });
  }, [susoft]);

  const saveSusoft = useMutation({
    mutationFn: async () => (await api.put(`/super/tenants/${tid}/susoft`, sf)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["super", "tenant", tid, "susoft"] }),
    onError: (e: any) => alert(e?.response?.data?.detail ?? e?.message),
  });

  const impersonate = useMutation({
    mutationFn: async () => (await api.post(`/super/tenants/${tid}/impersonate`)).data,
    onSuccess: (data: any) => beginImpersonation(data.access_token, data.user),
    onError: (e: any) => alert(e?.response?.data?.detail ?? e?.message),
  });

  const [newUser, setNewUser] = useState({ name: "", email: "", password: "", role: "seller" });
  const addUser = useMutation({
    mutationFn: async () => (await api.post(`/super/tenants/${tid}/users`, newUser)).data,
    onSuccess: () => {
      setNewUser({ name: "", email: "", password: "", role: "seller" });
      qc.invalidateQueries({ queryKey: ["super", "tenant", tid, "users"] });
    },
    onError: (e: any) => alert(e?.response?.data?.detail ?? e?.message),
  });

  if (!tenant) return <div>Laster…</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/super" className="text-xs text-slate-500 hover:underline">← Alle tenants</Link>
          <h1 className="text-2xl font-bold text-slate-800">{tenant.name}</h1>
          <div className="text-sm text-slate-500 font-mono">{tenant.slug} · opprettet {fmtDateTime(tenant.created_at)}</div>
        </div>
        <button className="btn-primary" onClick={() => impersonate.mutate()} disabled={impersonate.isPending}>
          🔓 Åpne som denne tenant
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Settings */}
        <div className="card space-y-3">
          <h2 className="font-semibold text-slate-700">Innstillinger</h2>
          <div>
            <label className="label">Navn</label>
            <input className="input" value={edit.name ?? ""} onChange={(e) => setEdit({ ...edit, name: e.target.value })} />
          </div>
          <div>
            <label className="label">Plan</label>
            <select className="input" value={edit.plan ?? "standard"} onChange={(e) => setEdit({ ...edit, plan: e.target.value })}>
              <option value="trial">Trial</option>
              <option value="standard">Standard</option>
              <option value="pro">Pro</option>
            </select>
          </div>
          <div className="flex flex-col gap-2">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={!!edit.is_active} onChange={(e) => setEdit({ ...edit, is_active: e.target.checked })} />
              <span>Tenant aktiv</span>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={!!edit.module_workshop} onChange={(e) => setEdit({ ...edit, module_workshop: e.target.checked })} />
              <span>🔧 Verksted-modul</span>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={!!edit.module_shop} onChange={(e) => setEdit({ ...edit, module_shop: e.target.checked })} />
              <span>🛍 Butikk-modul</span>
            </label>
          </div>
          <button className="btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>Lagre</button>
        </div>

        {/* Susoft */}
        <div className="card space-y-3">
          <h2 className="font-semibold text-slate-700">Susoft-tilkobling</h2>
          <div>
            <label className="label">Base URL</label>
            <input className="input" value={sf.base_url ?? ""} onChange={(e) => setSf({ ...sf, base_url: e.target.value })} />
          </div>
          <div>
            <label className="label">Shop URL key</label>
            <input className="input" value={sf.shop_url_key ?? ""} onChange={(e) => setSf({ ...sf, shop_url_key: e.target.value })} />
          </div>
          <div>
            <label className="label">Login</label>
            <input className="input" value={sf.login ?? ""} onChange={(e) => setSf({ ...sf, login: e.target.value })} />
          </div>
          <div>
            <label className="label">Passord {susoft?.has_password && <span className="text-xs text-emerald-600">(lagret)</span>}</label>
            <input className="input" type="password" value={sf.password ?? ""} onChange={(e) => setSf({ ...sf, password: e.target.value })} placeholder={susoft?.has_password ? "La stå tom for å beholde" : ""} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={!!sf.auto_create_order} onChange={(e) => setSf({ ...sf, auto_create_order: e.target.checked })} />
              Opprett ordre automatisk i Susoft
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={!!sf.is_active} onChange={(e) => setSf({ ...sf, is_active: e.target.checked })} />
              Aktivér Susoft-integrasjon
            </label>
          </div>
          {susoft?.last_test_at && (
            <div className="text-xs text-slate-500">
              Sist testet {fmtDateTime(susoft.last_test_at)} —{" "}
              {susoft.last_test_ok ? "✔ OK" : `✖ ${susoft.last_test_error ?? ""}`}
            </div>
          )}
          <button className="btn-primary" onClick={() => saveSusoft.mutate()} disabled={saveSusoft.isPending}>Lagre Susoft</button>
        </div>
      </div>

      {/* Users */}
      <div className="card">
        <h2 className="font-semibold text-slate-700 mb-3">Brukere ({users?.length ?? 0})</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="py-2 pr-3">Navn</th>
              <th className="py-2 pr-3">E-post</th>
              <th className="py-2 pr-3">Rolle</th>
              <th className="py-2 pr-3">Aktiv</th>
            </tr>
          </thead>
          <tbody>
            {users?.map((u) => (
              <tr key={u.id} className="border-t border-slate-100">
                <td className="py-2 pr-3 font-medium">{u.name}</td>
                <td className="py-2 pr-3">{u.email}</td>
                <td className="py-2 pr-3 text-xs">{u.role}</td>
                <td className="py-2 pr-3">{u.is_active ? "✓" : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-5 gap-2 items-end border-t border-slate-100 pt-3">
          <div className="md:col-span-1">
            <label className="label">Navn</label>
            <input className="input" value={newUser.name} onChange={(e) => setNewUser({ ...newUser, name: e.target.value })} />
          </div>
          <div className="md:col-span-1">
            <label className="label">E-post</label>
            <input className="input" type="email" value={newUser.email} onChange={(e) => setNewUser({ ...newUser, email: e.target.value })} />
          </div>
          <div className="md:col-span-1">
            <label className="label">Passord</label>
            <input className="input" type="text" value={newUser.password} onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} />
          </div>
          <div className="md:col-span-1">
            <label className="label">Rolle</label>
            <select className="input" value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}>
              <option value="seller">Selger</option>
              <option value="goldsmith">Gullsmed</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <button
            className="btn-primary"
            onClick={() => addUser.mutate()}
            disabled={addUser.isPending || !newUser.name || !newUser.email || !newUser.password}
          >
            + Legg til
          </button>
        </div>
      </div>
    </div>
  );
}
