import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";

type Loc = { id: number; code: string; label: string; parent_id: number | null; qr_token?: string };

export default function Locations() {
  const qc = useQueryClient();
  const [form, setForm] = useState({ code: "", label: "", parent_id: "" });

  const { data, isLoading } = useQuery({
    queryKey: ["locations"],
    queryFn: async () => (await api.get<Loc[]>("/locations")).data,
  });

  const create = useMutation({
    mutationFn: async () => (await api.post<Loc>("/locations", {
      code: form.code,
      label: form.label,
      parent_id: form.parent_id ? Number(form.parent_id) : null,
    })).data,
    onSuccess: () => {
      setForm({ code: "", label: "", parent_id: "" });
      qc.invalidateQueries({ queryKey: ["locations"] });
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-2xl font-bold text-slate-800">Lokasjoner</h1>

      <div className="card">
        <h2 className="font-semibold text-slate-700 mb-3">Ny lokasjon (skap / hylle / boks)</h2>
        <form onSubmit={onSubmit} className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <input className="input" placeholder="Kode (A, 1, 12)" required value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
          <input className="input md:col-span-2" placeholder="Etikett (Skap A)" required value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} />
          <select className="input" value={form.parent_id} onChange={(e) => setForm({ ...form, parent_id: e.target.value })}>
            <option value="">— Topp-nivå —</option>
            {data?.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
          </select>
          <div className="md:col-span-4">
            <button className="btn-primary" disabled={create.isPending}>Legg til</button>
          </div>
        </form>
      </div>

      <div className="card">
        {isLoading ? <div>Laster…</div> : (
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500 border-b">
              <tr><th className="py-2">Etikett</th><th>Kode</th><th>Forelder</th><th>QR-token</th></tr>
            </thead>
            <tbody>
              {data?.map((l) => (
                <tr key={l.id} className="border-b last:border-0">
                  <td className="py-2 font-medium">{l.label}</td>
                  <td>{l.code}</td>
                  <td>{data.find((p) => p.id === l.parent_id)?.label ?? "—"}</td>
                  <td className="font-mono text-xs text-slate-500">{l.qr_token}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
