import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("gvk_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("gvk_token");
      if (location.pathname !== "/login") location.href = "/login";
    }
    return Promise.reject(err);
  }
);

/** Backend serializes naive UTC datetimes (no Z suffix). JS would otherwise
 * parse them as local time, giving 1–2 timer feil i Norge. Force-tag UTC
 * before constructing the Date. */
export function parseUTC(s: string | null | undefined): Date {
  if (!s) return new Date(NaN);
  return /Z|[+-]\d\d:?\d\d$/.test(s) ? new Date(s) : new Date(s + "Z");
}

/** Norsk dato/tid format som default. */
export function fmtDateTime(s: string | null | undefined, opts?: Intl.DateTimeFormatOptions): string {
  if (!s) return "—";
  const d = parseUTC(s);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString("nb-NO", opts);
}

export function fmtDate(s: string | null | undefined): string {
  if (!s) return "—";
  const d = parseUTC(s);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("nb-NO");
}
