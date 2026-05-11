import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

const STATUS_LABELS: Record<string, string> = {
  registered: "Registrert",
  in_transit: "I transport",
  awaiting: "Venter",
  in_progress: "Under arbeid",
  waiting_parts: "Venter på deler",
  done: "Ferdig",
  delivered: "Utlevert",
  cancelled: "Kansellert",
};

type Summary = {
  total_jobs: number;
  total_customers: number;
  by_status: Record<string, number>;
};

export default function Dashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["summary"],
    queryFn: async () => (await api.get<Summary>("/dashboard/summary")).data,
  });

  if (isLoading) return <div>Laster…</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">Dashbord</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card">
          <div className="text-sm text-slate-500">Totalt jobber</div>
          <div className="text-3xl font-bold text-gold-600">{data?.total_jobs ?? 0}</div>
        </div>
        <div className="card">
          <div className="text-sm text-slate-500">Kunder</div>
          <div className="text-3xl font-bold text-gold-600">{data?.total_customers ?? 0}</div>
        </div>
        <div className="card">
          <div className="text-sm text-slate-500">Under arbeid</div>
          <div className="text-3xl font-bold text-gold-600">{data?.by_status.in_progress ?? 0}</div>
        </div>
        <div className="card">
          <div className="text-sm text-slate-500">Klar til henting</div>
          <div className="text-3xl font-bold text-gold-600">{data?.by_status.done ?? 0}</div>
        </div>
      </div>

      <div className="card">
        <h2 className="font-semibold text-slate-700 mb-3">Status-oversikt</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {Object.entries(data?.by_status ?? {}).map(([k, v]) => (
            <div key={k} className="border border-slate-200 rounded-md p-3">
              <div className="text-xs text-slate-500">{STATUS_LABELS[k] ?? k}</div>
              <div className="text-xl font-semibold">{v}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
