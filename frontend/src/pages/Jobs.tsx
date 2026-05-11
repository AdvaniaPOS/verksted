import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";

type Job = {
  id: number;
  job_number: string;
  status: string;
  job_type: string;
  description?: string;
  estimated_completion?: string | null;
  pickup_code?: string;
  created_at: string;
  customer?: { id: number; name: string } | null;
  location?: { id: number; label: string } | null;
};

const STATUS_BADGE: Record<string, string> = {
  registered: "bg-slate-200 text-slate-700",
  in_transit: "bg-blue-100 text-blue-700",
  awaiting: "bg-amber-100 text-amber-700",
  in_progress: "bg-yellow-200 text-yellow-800",
  waiting_parts: "bg-orange-100 text-orange-700",
  done: "bg-green-100 text-green-700",
  delivered: "bg-emerald-200 text-emerald-800",
  cancelled: "bg-red-100 text-red-700",
};

const STATUS_LABEL: Record<string, string> = {
  registered: "Registrert", in_transit: "Under transport", awaiting: "Venter",
  in_progress: "Pågår", waiting_parts: "Venter deler", done: "Ferdig",
  delivered: "Hentet", cancelled: "Avbrutt",
};

const STATUS_FILTERS: { key: string; label: string }[] = [
  { key: "open", label: "Åpne" },
  { key: "", label: "Alle" },
  { key: "registered", label: "Nye" },
  { key: "in_progress", label: "Pågår" },
  { key: "waiting_parts", label: "Venter deler" },
  { key: "done", label: "Ferdig" },
  { key: "delivered", label: "Hentet" },
];

export default function Jobs() {
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<string>("open");
  const [sort, setSort] = useState<"newest" | "oldest" | "due">("newest");

  const params: any = { sort };
  if (q.trim()) params.q = q.trim();
  if (filter === "open") params.open_only = true;
  else if (filter) params.status = filter;

  const { data, isLoading } = useQuery({
    queryKey: ["jobs", params],
    queryFn: async () => (await api.get<Job[]>("/jobs", { params })).data,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">Jobber</h1>
        <Link to="/jobber/ny" className="btn-primary">+ Ny jobb</Link>
      </div>

      <div className="card space-y-3">
        <div className="flex flex-wrap gap-2 items-center">
          <input className="input flex-1 min-w-[220px]" placeholder="Søk jobbnr, kunde, telefon, beskrivelse…"
            value={q} onChange={(e) => setQ(e.target.value)} />
          <select className="input w-auto" value={sort} onChange={(e) => setSort(e.target.value as any)}>
            <option value="newest">Nyeste først</option>
            <option value="oldest">Eldste først</option>
            <option value="due">Etter forfall</option>
          </select>
        </div>
        <div className="flex flex-wrap gap-1">
          {STATUS_FILTERS.map((f) => (
            <button key={f.key} onClick={() => setFilter(f.key)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition ${
                filter === f.key ? "bg-gold-500 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}>
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="card overflow-x-auto">
        {isLoading ? (
          <div>Laster…</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500 border-b">
              <tr>
                <th className="py-2">Nr.</th>
                <th>Kunde</th>
                <th>Type</th>
                <th>Status</th>
                <th>Lokasjon</th>
                <th>Forfall</th>
                <th>Beskrivelse</th>
              </tr>
            </thead>
            <tbody>
              {data?.map((j) => (
                <tr key={j.id} className="border-b last:border-0 hover:bg-slate-50">
                  <td className="py-2"><Link to={`/jobber/${j.id}`} className="font-medium text-gold-600">{j.job_number}</Link></td>
                  <td>
                    {j.customer ? (
                      <Link to={`/kunder/${j.customer.id}`} className="hover:underline">{j.customer.name}</Link>
                    ) : "—"}
                  </td>
                  <td>{j.job_type}</td>
                  <td>
                    <span className={`px-2 py-0.5 rounded-full text-xs ${STATUS_BADGE[j.status] ?? "bg-slate-100"}`}>
                      {STATUS_LABEL[j.status] ?? j.status}
                    </span>
                  </td>
                  <td>{j.location?.label ?? "—"}</td>
                  <td className="text-xs text-slate-500">
                    {j.estimated_completion ? new Date(j.estimated_completion).toLocaleDateString("nb-NO") : "—"}
                  </td>
                  <td className="truncate max-w-xs">{j.description}</td>
                </tr>
              ))}
              {data?.length === 0 && (
                <tr><td colSpan={7} className="py-4 text-center text-slate-500">Ingen jobber matcher filteret.</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
