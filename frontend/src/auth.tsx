import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api } from "./api";

export type Tenant = {
  id: number;
  name: string;
  slug: string;
  is_active?: boolean;
  plan?: string;
  module_workshop?: boolean;
  module_shop?: boolean;
};

export type User = {
  id: number;
  email: string;
  name: string;
  role: "superadmin" | "admin" | "seller" | "goldsmith";
  tenant: Tenant;
};

type AuthCtx = {
  user: User | null;
  loading: boolean;
  isImpersonating: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
  beginImpersonation: (token: string, user: User) => void;
  endImpersonation: () => void;
  refresh: () => Promise<void>;
};

const Ctx = createContext<AuthCtx>(null!);

const TOK = "gvk_token";
const STASH = "gvk_token_super";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isImpersonating, setIsImpersonating] = useState(!!localStorage.getItem(STASH));

  async function refresh() {
    const token = localStorage.getItem(TOK);
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const r = await api.get<User>("/auth/me");
      setUser(r.data);
    } catch {
      localStorage.removeItem(TOK);
      localStorage.removeItem(STASH);
      setUser(null);
      setIsImpersonating(false);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function login(email: string, password: string) {
    const r = await api.post("/auth/login", { email, password });
    localStorage.setItem(TOK, r.data.access_token);
    localStorage.removeItem(STASH);
    setIsImpersonating(false);
    setUser(r.data.user);
    return r.data.user as User;
  }

  function logout() {
    localStorage.removeItem(TOK);
    localStorage.removeItem(STASH);
    setUser(null);
    setIsImpersonating(false);
    location.href = "/login";
  }

  function beginImpersonation(token: string, u: User) {
    const original = localStorage.getItem(TOK);
    if (original) localStorage.setItem(STASH, original);
    localStorage.setItem(TOK, token);
    setUser(u);
    setIsImpersonating(true);
    location.href = "/";
  }

  function endImpersonation() {
    const original = localStorage.getItem(STASH);
    if (!original) return;
    localStorage.setItem(TOK, original);
    localStorage.removeItem(STASH);
    setIsImpersonating(false);
    location.href = "/super";
  }

  return (
    <Ctx.Provider value={{ user, loading, isImpersonating, login, logout, beginImpersonation, endImpersonation, refresh }}>
      {children}
    </Ctx.Provider>
  );
}

export const useAuth = () => useContext(Ctx);
