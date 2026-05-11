import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useState } from "react";
import { api } from "../api";

const STATUSES = [
  { key: "all", label: "Alle" },
  { key: "needed", label: "Trenger" },
  { key: "ordered", label: "Bestilt" },
  { key: "received", label: "Mottatt" },
  { key: "installed", label: "Montert" },
];
const COLOR: Record<string, string> = {
  needed: "bg-amber-100 text-amber-700",
  ordered: "bg-sky-100 text-sky-700",
  received: "bg-emerald-100 text-emerald-700",
  installed: "bg-emerald-100 text-emerald-700",
  cancelled: "bg-slate-100 text-slate-600",
};
const NEXT_STATUS: Record<string, string> = {
  needed: "ordered",
  ordered: "received",
  received: "installed",
};
const NEXT_LABEL: Record<string, string> = {
  needed: "Marker bestilt",
  ordered: "Marker mottatt",
  received: "Marker montert",
};

export default function Bestillinger() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("needed");
  const [supplier, setSupplier] = useState("");
  const [q, setQ] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["parts", status, supplier, q],
    queryFn: async () => {
      const params: any = {};
      if (status && status !== "all") params.status = status;
      if (supplier) params.supplier = supplier;
      if (q) params.q = q;
      return (await api.get("/parts", { params })).data;
    },
  });

  const patch = useMutation({
    mutationFn: async ({ p, body }: { p: any; body: any }) =>
      (await api.patch(`/jobs/${p.job_id}/parts/${p.id}`, body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["parts"] }),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">🛒 Bestillinger</h1>
        <span className="text-sm text-slate-500">{data?.length ?? 0} treff</span>
      </div>

      <div className="card flex flex-wrap gap-2 items-end">
        <div className="flex flex-wrap gap-1">
          {STATUSES.map((s) => (
            <button
              key={s.key}
              onClick={() => setStatus(s.key)}
              className={`px-3 py-1.5 rounded-full text-sm font-medium ${
                status === s.key ? "bg-gold-500 text-white" : "bg-slate-100 text-slate-700"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
        <div className="flex-1" />
        <div>
          <label className="label">Leverandør</label>
          <input className="input w-44" value={supplier} onChange={(e) => setSupplier(e.target.value)} placeholder="Filter…" />
        </div>
        <div>
          <label className="label">Søk</label>
          <input className="input w-56" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Beskrivelse / ref / jobb / kunde" />
        </div>
      </div>

      <div className="card overflow-x-auto">
        {isLoading ? (
          <div className="text-slate-500 p-4">Laster…</div>
        ) : (data?.length ?? 0) === 0 ? (
          <div className="text-slate-500 p-4 italic">Ingen bestillinger matcher filtrene</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="py-2 pr-3">Jobb</th>
                <th className="py-2 pr-3">Kunde</th>
                <th className="py-2 pr-3">Beskrivelse</th>
                <th className="py-2 pr-3">Leverandør</th>
                <th className="py-2 pr-3">Ref</th>
                <th className="py-2 pr-3">Antall</th>
                <th className="py-2 pr-3">Innkjøp</th>
                <th className="py-2 pr-3">Utpris</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2 pr-3">Handling</th>
              </tr>
            </thead>
            <tbody>
              {data?.map((p: any) => (
                <tr key={p.id} className="border-t border-slate-100">
                  <td className="py-2 pr-3">
                    <Link to={`/jobber/${p.job_id}`} className="text-gold-600 hover:underline font-medium">
                      {p.job_number ?? `#${p.job_id}`}
                    </Link>
                  </td>
                  <td className="py-2 pr-3 text-slate-600">{p.customer_name ?? "—"}</td>
                  <td className="py-2 pr-3">{p.description}</td>
                  <td className="py-2 pr-3">{p.supplier ?? "—"}</td>
                  <td className="py-2 pr-3 font-mono text-xs">{p.supplier_ref ?? "—"}</td>
                  <td className="py-2 pr-3">{p.quantity ?? "—"}</td>
                  <td className="py-2 pr-3">{p.cost_price ? `kr ${p.cost_price}` : "—"}</td>
                  <td className="py-2 pr-3">{p.sale_price ? `kr ${p.sale_price}` : "—"}</td>
                  <td className="py-2 pr-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${COLOR[p.status] ?? "bg-slate-100"}`}>
                      {p.status}
                    </span>
                  </td>
                  <td className="py-2 pr-3">
                    {NEXT_STATUS[p.status] && (
                      <button
                        className="text-xs px-2 py-1 rounded border border-slate-200 hover:bg-slate-50"
                        onClick={() => patch.mutate({ p, body: { status: NEXT_STATUS[p.status] } })}
                      >
                        {NEXT_LABEL[p.status]}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
