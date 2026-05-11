import { FormEvent, useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import CustomerPicker, { Customer } from "../CustomerPicker";

export default function NewJob() {
  const nav = useNavigate();
  const { data: locations } = useQuery({
    queryKey: ["locations"],
    queryFn: async () => (await api.get("/locations")).data,
  });

  const [customer, setCustomer] = useState<Customer | null>(null);
  const [form, setForm] = useState({
    job_type: "repair",
    description: "",
    metal_type: "",
    gemstones: "",
    estimated_weight_g: "",
    condition_notes: "",
    estimated_price: "",
    estimated_completion: "",
    location_id: "",
  });

  const create = useMutation({
    mutationFn: async () => {
      if (!customer) throw new Error("Velg eller opprett kunde");
      const payload: any = {
        ...form,
        customer_id: customer.id,
        location_id: form.location_id ? Number(form.location_id) : null,
        estimated_weight_g: form.estimated_weight_g || null,
        estimated_price: form.estimated_price || null,
        estimated_completion: form.estimated_completion ? new Date(form.estimated_completion).toISOString() : null,
      };
      const r = await api.post("/jobs", payload);
      return r.data;
    },
    onSuccess: (j) => nav(`/jobber/${j.id}`),
    onError: (e: any) => alert(e?.response?.data?.detail ?? e?.message ?? "Feil"),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-2xl font-bold text-slate-800">Ny jobb</h1>
      <form onSubmit={onSubmit} className="card grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className="label">Kunde *</label>
          <CustomerPicker value={customer} onChange={setCustomer} required />
        </div>
        <div>
          <label className="label">Type</label>
          <select className="input" value={form.job_type} onChange={(e) => setForm({ ...form, job_type: e.target.value })}>
            <option value="repair">Reparasjon</option>
            <option value="design">Design</option>
            <option value="sale">Salg</option>
            <option value="other">Annet</option>
          </select>
        </div>
        <div>
          <label className="label">Forventet ferdig</label>
          <input className="input" type="date" value={form.estimated_completion}
            onChange={(e) => setForm({ ...form, estimated_completion: e.target.value })} />
        </div>
        <div className="md:col-span-2">
          <label className="label">Beskrivelse</label>
          <textarea className="input" rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </div>
        <div>
          <label className="label">Metalltype</label>
          <input className="input" value={form.metal_type} onChange={(e) => setForm({ ...form, metal_type: e.target.value })} placeholder="f.eks. 18k gult gull" />
        </div>
        <div>
          <label className="label">Edelstener</label>
          <input className="input" value={form.gemstones} onChange={(e) => setForm({ ...form, gemstones: e.target.value })} />
        </div>
        <div>
          <label className="label">Estimert vekt (g)</label>
          <input className="input" type="number" step="0.001" inputMode="decimal" value={form.estimated_weight_g} onChange={(e) => setForm({ ...form, estimated_weight_g: e.target.value })} />
        </div>
        <div>
          <label className="label">Estimert pris (kr)</label>
          <input className="input" type="number" step="0.01" inputMode="decimal" value={form.estimated_price} onChange={(e) => setForm({ ...form, estimated_price: e.target.value })} />
        </div>
        <div className="md:col-span-2">
          <label className="label">Tilstand / kondisjon (riper, skader)</label>
          <textarea className="input" rows={2} value={form.condition_notes} onChange={(e) => setForm({ ...form, condition_notes: e.target.value })} />
        </div>
        <div className="md:col-span-2">
          <label className="label">Lokasjon</label>
          <select className="input" value={form.location_id} onChange={(e) => setForm({ ...form, location_id: e.target.value })}>
            <option value="">— Ingen —</option>
            {locations?.map((l: any) => <option key={l.id} value={l.id}>{l.label}</option>)}
          </select>
        </div>
        <div className="md:col-span-2 flex gap-2">
          <button className="btn-primary" disabled={create.isPending || !customer}>
            {create.isPending ? "Oppretter…" : "Opprett jobb"}
          </button>
          {!customer && <span className="text-sm text-slate-500 self-center">Velg kunde for å fortsette</span>}
        </div>
      </form>
    </div>
  );
}
