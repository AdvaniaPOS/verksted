import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export type Customer = {
  id: number;
  name: string;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
};

type Props = {
  value: Customer | null;
  onChange: (c: Customer | null) => void;
  required?: boolean;
};

/** Searchable customer picker with inline create. Optimized for tablet input. */
export default function CustomerPicker({ value, onChange, required }: Props) {
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState({ name: "", phone: "", email: "", address: "" });
  const wrapRef = useRef<HTMLDivElement>(null);

  // Debounced
  const [debouncedQuery, setDebouncedQuery] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query.trim()), 200);
    return () => clearTimeout(t);
  }, [query]);

  const { data: results = [] } = useQuery<Customer[]>({
    queryKey: ["customers", "search", debouncedQuery],
    queryFn: async () => (await api.get("/customers", { params: debouncedQuery ? { q: debouncedQuery } : {} })).data,
    enabled: open,
  });

  const create = useMutation({
    mutationFn: async () => (await api.post<Customer>("/customers", draft)).data,
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["customers"] });
      onChange(c);
      setCreating(false);
      setOpen(false);
      setDraft({ name: "", phone: "", email: "", address: "" });
    },
  });

  // close on outside click
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  if (value && !open) {
    return (
      <div className="flex items-center justify-between gap-3 border border-slate-300 rounded-md px-3 py-2 bg-white">
        <div className="min-w-0">
          <div className="font-medium text-slate-800 truncate">{value.name}</div>
          <div className="text-xs text-slate-500 truncate">
            {[value.phone, value.email].filter(Boolean).join(" • ")}
          </div>
        </div>
        <div className="flex gap-2">
          <button type="button" className="text-sm text-slate-500 hover:text-slate-700"
            onClick={() => { setOpen(true); setQuery(""); }}>
            Bytt
          </button>
          {!required && (
            <button type="button" className="text-sm text-rose-500 hover:text-rose-700"
              onClick={() => onChange(null)}>
              Fjern
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div ref={wrapRef} className="relative">
      <input
        className="input"
        placeholder="Søk navn, telefon eller e-post…"
        value={query}
        onFocus={() => setOpen(true)}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
        autoComplete="off"
      />
      {open && (
        <div className="absolute z-30 mt-1 left-0 right-0 bg-white border border-slate-200 rounded-md shadow-lg max-h-80 overflow-auto">
          {results.length > 0 && (
            <ul className="divide-y divide-slate-100">
              {results.map((c) => (
                <li key={c.id}>
                  <button type="button" onClick={() => { onChange(c); setOpen(false); }}
                    className="w-full text-left px-3 py-2 hover:bg-slate-50">
                    <div className="font-medium">{c.name}</div>
                    <div className="text-xs text-slate-500">
                      {[c.phone, c.email].filter(Boolean).join(" • ") || "—"}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {results.length === 0 && debouncedQuery && (
            <div className="px-3 py-2 text-sm text-slate-500">Ingen treff på «{debouncedQuery}»</div>
          )}
          {!creating ? (
            <button type="button"
              className="w-full text-left px-3 py-2 border-t border-slate-100 text-gold-600 font-medium hover:bg-gold-50"
              onClick={() => {
                setCreating(true);
                // pre-fill the most likely field based on the query
                const v = query.trim();
                const looksPhone = /^[+\d][\d\s]{4,}$/.test(v);
                const looksEmail = v.includes("@");
                setDraft({
                  name: looksPhone || looksEmail ? "" : v,
                  phone: looksPhone ? v : "",
                  email: looksEmail ? v : "",
                  address: "",
                });
              }}>
              + Opprett ny kunde{query ? ` «${query}»` : ""}
            </button>
          ) : (
            <div className="border-t border-slate-100 p-3 space-y-2 bg-slate-50">
              <input className="input" placeholder="Navn *" required value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
              <input className="input" placeholder="Telefon" value={draft.phone} onChange={(e) => setDraft({ ...draft, phone: e.target.value })} />
              <input className="input" placeholder="E-post" type="email" value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} />
              <input className="input" placeholder="Adresse" value={draft.address} onChange={(e) => setDraft({ ...draft, address: e.target.value })} />
              <div className="flex gap-2">
                <button type="button" className="btn-primary text-sm"
                  disabled={!draft.name || create.isPending}
                  onClick={() => create.mutate()}>
                  {create.isPending ? "Lagrer…" : "Lagre kunde"}
                </button>
                <button type="button" className="btn-secondary text-sm"
                  onClick={() => setCreating(false)}>Avbryt</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
