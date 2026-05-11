import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";

type Customer = {
  id: number;
  name: string;
  phone?: string;
  email?: string;
  address?: string;
};

export default function Customers() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [form, setForm] = useState({ name: "", phone: "", email: "", address: "" });

  const { data, isLoading } = useQuery({
    queryKey: ["customers", q],
    queryFn: async () => (await api.get<Customer[]>("/customers", { params: q ? { q } : {} })).data,
  });

  const create = useMutation({
    mutationFn: async () => (await api.post<Customer>("/customers", form)).data,
    onSuccess: () => {
      setForm({ name: "", phone: "", email: "", address: "" });
      qc.invalidateQueries({ queryKey: ["customers"] });
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">Kunder</h1>

      <div className="card">
        <h2 className="font-semibold text-slate-700 mb-3">Ny kunde</h2>
        <form onSubmit={onSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <input className="input" placeholder="Navn *" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input className="input" placeholder="Telefon" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          <input className="input" placeholder="E-post" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <input className="input" placeholder="Adresse" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
          <div className="md:col-span-2">
            <button className="btn-primary" disabled={create.isPending}>Lagre kunde</button>
          </div>
        </form>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-slate-700">Kundeliste</h2>
          <input className="input max-w-xs" placeholder="Søk navn/telefon/e-post" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {isLoading ? (
          <div>Laster…</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500 border-b">
              <tr>
                <th className="py-2">Navn</th>
                <th>Telefon</th>
                <th>E-post</th>
                <th>Adresse</th>
              </tr>
            </thead>
            <tbody>
              {data?.map((c) => (
                <tr key={c.id} className="border-b last:border-0 hover:bg-slate-50">
                  <td className="py-2 font-medium">
                    <Link to={`/kunder/${c.id}`} className="text-gold-600 hover:underline">{c.name}</Link>
                  </td>
                  <td>{c.phone}</td>
                  <td>{c.email}</td>
                  <td>{c.address}</td>
                </tr>
              ))}
              {data?.length === 0 && (
                <tr><td colSpan={4} className="py-4 text-center text-slate-500">Ingen kunder.</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
