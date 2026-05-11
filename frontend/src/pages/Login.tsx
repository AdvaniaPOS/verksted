import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("jon.sigurdarson@advania.no");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const u = await login(email, password);
      nav(u.role === "superadmin" ? "/super" : "/", { replace: true });
    } catch (e: any) {
      setErr(e.response?.data?.detail ?? "Innlogging feilet");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-100 to-gold-50">
      <form onSubmit={onSubmit} className="card w-full max-w-md space-y-4">
        <div className="text-center">
          <div className="text-3xl font-bold text-gold-600">GVK</div>
          <div className="text-sm text-slate-500">Gullsmed Verksted & Kundekontroll</div>
        </div>
        <div>
          <label className="label">E-post</label>
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div>
          <label className="label">Passord</label>
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        {err && <div className="text-red-600 text-sm">{err}</div>}
        <button className="btn-primary w-full" disabled={busy}>{busy ? "Logger inn…" : "Logg inn"}</button>
      </form>
    </div>
  );
}
