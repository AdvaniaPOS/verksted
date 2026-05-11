import { useQuery, useMutation } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api, fmtDateTime } from "../api";
import { useAuth } from "../auth";

type DashRow = {
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
  last_login_at: string | null;
  susoft_configured: boolean;
  susoft_ok: boolean | null;
  susoft_error: string | null;
  susoft_checked_at: string | null;
  susoft_consecutive_failures: number;
  created_at: string;
};

function StatusPill({ ok, label, dim }: { ok: boolean | null; label: string; dim?: boolean }) {
  if (dim) return <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500">{label}</span>;
  const cls =
    ok === true ? "bg-emerald-100 text-emerald-700"
    : ok === false ? "bg-rose-100 text-rose-700"
    : "bg-slate-100 text-slate-500";
  const dot = ok === true ? "🟢" : ok === false ? "🔴" : "⚪";
  return <span className={`text-[11px] px-2 py-0.5 rounded-full ${cls}`}>{dot} {label}</span>;
}

export default function SuperDashboard() {
  const navigate = useNavigate();
  const { beginImpersonation } = useAuth();

  const { data, isLoading, refetch, isFetching } = useQuery<DashRow[]>({
    queryKey: ["super", "dashboard"],
    queryFn: async () => (await api.get("/super/dashboard")).data,
    refetchInterval: 30_000, // auto-refresh every 30s
  });

  const test = useMutation({
    mutationFn: async (tid: number) => (await api.post(`/super/tenants/${tid}/susoft/test`)).data,
    onSuccess: () => refetch(),
    onError: (e: any) => alert(e?.response?.data?.detail ?? e?.message),
  });

  const impersonate = useMutation({
    mutationFn: async (tid: number) => (await api.post(`/super/tenants/${tid}/impersonate`)).data,
    onSuccess: (d: any) => beginImpersonation(d.access_token, d.user),
    onError: (e: any) => alert(e?.response?.data?.detail ?? e?.message),
  });

  const totals = (data ?? []).reduce(
    (a, t) => ({
      tenants: a.tenants + 1,
      online: a.online + (t.is_active ? 1 : 0),
      susoftOk: a.susoftOk + (t.susoft_ok === true ? 1 : 0),
      susoftErr: a.susoftErr + (t.susoft_ok === false ? 1 : 0),
    }),
    { tenants: 0, online: 0, susoftOk: 0, susoftErr: 0 }
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">🛡 Super-admin · Plattform-status</h1>
          <p className="text-sm text-slate-500">
            Auto-oppdateres hvert 30 sek. Susoft re-prøves automatisk ved feil.
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => refetch()} disabled={isFetching}>
            {isFetching ? "Oppdaterer…" : "↻ Oppdater nå"}
          </button>
          <button className="btn-primary" onClick={() => navigate("/super/tenants")}>
            + Ny tenant
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card"><div className="text-xs text-slate-500">Tenants</div><div className="text-2xl font-bold">{totals.tenants}</div></div>
        <div className="card"><div className="text-xs text-slate-500">Aktive</div><div className="text-2xl font-bold text-emerald-700">{totals.online}</div></div>
        <div className="card"><div className="text-xs text-slate-500">Susoft OK</div><div className="text-2xl font-bold text-emerald-700">{totals.susoftOk}</div></div>
        <div className="card"><div className="text-xs text-slate-500">Susoft feil</div><div className="text-2xl font-bold text-rose-700">{totals.susoftErr}</div></div>
      </div>

      {isLoading ? (
        <div className="card text-slate-500">Laster…</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {data?.map((t) => (
            <div key={t.id} className="card flex flex-col gap-3">
              <div className="flex items-start justify-between">
                <div>
                  <Link to={`/super/tenants/${t.id}`} className="text-lg font-semibold text-slate-800 hover:underline">{t.name}</Link>
                  <div className="text-xs font-mono text-slate-500">{t.slug} · {t.plan}</div>
                </div>
                <StatusPill ok={t.is_active} label={t.is_active ? "online" : "deaktivert"} />
              </div>

              <div className="flex flex-wrap gap-2">
                {t.module_workshop && <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">verksted</span>}
                {t.module_shop && <span className="text-[11px] px-2 py-0.5 rounded-full bg-sky-50 text-sky-700 border border-sky-200">butikk</span>}
                {!t.susoft_configured && <StatusPill ok={null} label="susoft: ikke konfigurert" dim />}
                {t.susoft_configured && (
                  <StatusPill
                    ok={t.susoft_ok}
                    label={
                      t.susoft_ok === true ? "susoft: ok"
                      : t.susoft_ok === false ? `susoft: feil (${t.susoft_consecutive_failures}x)`
                      : "susoft: tester…"
                    }
                  />
                )}
              </div>

              {t.susoft_ok === false && t.susoft_error && (
                <div className="text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded p-2 break-all">
                  {t.susoft_error}
                </div>
              )}

              <div className="grid grid-cols-3 gap-2 text-center text-xs text-slate-600">
                <div><div className="font-bold text-slate-800 text-base">{t.user_count}</div>brukere</div>
                <div><div className="font-bold text-slate-800 text-base">{t.job_count}</div>jobber</div>
                <div><div className="font-bold text-slate-800 text-base">{t.customer_count}</div>kunder</div>
              </div>

              <div className="text-[11px] text-slate-500 border-t border-slate-100 pt-2 space-y-0.5">
                <div>Sist innlogging: {t.last_login_at ? fmtDateTime(t.last_login_at) : "—"}</div>
                <div>Susoft sjekket: {t.susoft_checked_at ? fmtDateTime(t.susoft_checked_at) : "—"}</div>
              </div>

              <div className="flex gap-2">
                {t.susoft_configured && (
                  <button
                    className="flex-1 text-xs py-1.5 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-700"
                    onClick={() => test.mutate(t.id)}
                    disabled={test.isPending}
                  >
                    🔄 Test Susoft nå
                  </button>
                )}
                <button
                  className="flex-1 text-xs py-1.5 rounded-md bg-gold-500 hover:bg-gold-600 text-white"
                  onClick={() => impersonate.mutate(t.id)}
                  disabled={impersonate.isPending || !t.is_active}
                  title={!t.is_active ? "Tenant er deaktivert" : "Logg inn som support"}
                >
                  🔓 Åpne som support
                </button>
              </div>
            </div>
          ))}
          {data?.length === 0 && (
            <div className="card text-slate-500 col-span-full">
              Ingen tenants ennå. <Link to="/super/tenants" className="text-gold-600 hover:underline">Opprett den første →</Link>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
