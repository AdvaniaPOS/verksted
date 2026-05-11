import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, parseUTC } from "../api";

export default function CustomerDetail() {
  const { id } = useParams();
  const { data: customer, isLoading } = useQuery({
    queryKey: ["customer", id],
    queryFn: async () => (await api.get(`/customers/${id}`)).data,
  });
  const { data: jobs } = useQuery({
    queryKey: ["customer", id, "jobs"],
    queryFn: async () => (await api.get(`/customers/${id}/jobs`)).data,
  });

  if (isLoading || !customer) return <div>Laster…</div>;

  return (
    <div className="space-y-6">
      <Link to="/kunder" className="text-sm text-slate-500 hover:text-slate-700">← Kunder</Link>
      <div className="card">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">{customer.name}</h1>
            <div className="text-sm text-slate-600 mt-1 space-x-4">
              {customer.phone && <span>📞 <a href={`tel:${customer.phone}`} className="hover:underline">{customer.phone}</a></span>}
              {customer.email && <span>✉ <a href={`mailto:${customer.email}`} className="hover:underline">{customer.email}</a></span>}
            </div>
            {customer.address && <div className="text-sm text-slate-500 mt-1">{customer.address}</div>}
          </div>
          <div className="grid grid-cols-3 gap-4 text-center">
            <Stat label="Jobber" value={customer.stats.job_count} />
            <Stat label="Åpne" value={customer.stats.open_count} highlight />
            <Stat label="Estimert sum" value={`${Math.round(customer.stats.total_estimated_price).toLocaleString("nb-NO")} kr`} />
          </div>
        </div>
        {customer.stats.last_visit && (
          <div className="text-xs text-slate-500 mt-3">
            Siste besøk: {parseUTC(customer.stats.last_visit).toLocaleString("nb-NO")}
          </div>
        )}
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-slate-700">Jobbhistorikk</h2>
          <Link to="/jobber/ny" className="btn-secondary text-sm">+ Ny jobb</Link>
        </div>
        {jobs?.length === 0 ? (
          <div className="text-sm text-slate-500 py-4">Ingen jobber registrert ennå.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500 border-b">
              <tr><th className="py-2">Nr.</th><th>Dato</th><th>Type</th><th>Status</th><th>Beskrivelse</th><th>Pris</th></tr>
            </thead>
            <tbody>
              {jobs?.map((j: any) => (
                <tr key={j.id} className="border-b last:border-0 hover:bg-slate-50">
                  <td className="py-2"><Link to={`/jobber/${j.id}`} className="font-medium text-gold-600">{j.job_number}</Link></td>
                  <td>{parseUTC(j.created_at).toLocaleDateString("nb-NO")}</td>
                  <td>{j.job_type}</td>
                  <td><span className="text-xs px-2 py-0.5 rounded-full bg-slate-100">{j.status}</span></td>
                  <td className="truncate max-w-xs">{j.description}</td>
                  <td>{j.estimated_price ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, highlight }: { label: string; value: any; highlight?: boolean }) {
  return (
    <div className={`px-4 py-2 rounded-lg ${highlight ? "bg-amber-50 text-amber-700" : "bg-slate-50 text-slate-700"}`}>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs">{label}</div>
    </div>
  );
}
