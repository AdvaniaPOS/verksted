import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth";

type NavItem = { to: string; label: string; icon: string; end?: boolean };

const navClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition ${
    isActive
      ? "bg-gold-500 text-white shadow-sm"
      : "text-slate-300 hover:bg-slate-800 hover:text-white"
  }`;

function Section({ title, items }: { title: string; items: NavItem[] }) {
  if (!items.length) return null;
  return (
    <div className="pt-4">
      <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
        {title}
      </div>
      <div className="space-y-1">
        {items.map((it) => (
          <NavLink key={it.to} to={it.to} end={it.end} className={navClass}>
            <span className="text-base w-5 text-center">{it.icon}</span>
            <span>{it.label}</span>
          </NavLink>
        ))}
      </div>
    </div>
  );
}

export default function Layout() {
  const { user, logout, isImpersonating, endImpersonation } = useAuth();
  const isSuper = user?.role === "superadmin";
  const t = user?.tenant;
  const showWorkshop = !!t?.module_workshop;
  const showShop = !!t?.module_shop;

  const workshop: NavItem[] = showWorkshop
    ? [
        { to: "/", label: "Dashbord", icon: "▦", end: true },
        { to: "/jobber", label: "Jobber", icon: "🔧" },
        { to: "/jobber/ny", label: "+ Ny jobb", icon: "✚" },
        { to: "/kunder", label: "Kunder", icon: "👥" },
        { to: "/bestillinger", label: "Bestillinger", icon: "🛒" },
        { to: "/lokasjoner", label: "Lokasjoner", icon: "📍" },
      ]
    : [];

  const shop: NavItem[] = showShop
    ? [
        { to: "/butikk", label: "Kasse", icon: "💳" },
        { to: "/butikk/varer", label: "Varer", icon: "📦" },
      ]
    : [];

  const settings: NavItem[] = [];
  if (user?.role === "admin" || user?.role === "superadmin") {
    settings.push({ to: "/admin", label: "Innstillinger", icon: "⚙" });
  }
  if (isSuper) {
    settings.push({ to: "/super", label: "Plattform-status", icon: "🛡" });
    settings.push({ to: "/super/tenants", label: "Tenants", icon: "🏢" });
  }

  return (
    <div className="min-h-screen flex bg-slate-100">
      <aside className="w-60 bg-slate-900 text-slate-100 flex flex-col fixed inset-y-0 left-0">
        <div className="p-4 border-b border-slate-800">
          <div className="text-lg font-bold text-gold-400">GVK</div>
          <div className="text-xs text-slate-400 truncate" title={t?.name}>{t?.name}</div>
          {isSuper && !isImpersonating && (
            <div className="text-[10px] uppercase tracking-wider text-rose-400 mt-1">Super-admin</div>
          )}
        </div>
        <nav className="px-3 pb-4 flex-1 overflow-auto">
          <Section title="Verksted" items={workshop} />
          <Section title="Butikk" items={shop} />
          <Section title="Innstillinger" items={settings} />
        </nav>
        <div className="p-3 border-t border-slate-800 text-sm">
          <div className="text-slate-100 font-medium truncate">{user?.name}</div>
          <div className="text-slate-400 text-xs mb-2 truncate">{user?.email}</div>
          <button
            onClick={logout}
            className="w-full text-sm py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-100"
          >
            Logg ut
          </button>
        </div>
      </aside>
      <main className="flex-1 ml-60 min-h-screen flex flex-col">
        {isImpersonating && (
          <div className="bg-amber-500 text-amber-950 text-sm font-medium px-4 py-2 flex items-center justify-between">
            <span>
              ⚠ Du er logget inn som <b>{user?.name}</b> ({user?.tenant.name}) på vegne av super-admin.
            </span>
            <button
              onClick={endImpersonation}
              className="px-3 py-1 rounded bg-amber-950 text-amber-100 hover:bg-amber-900 text-xs"
            >
              ← Tilbake til super-admin
            </button>
          </div>
        )}
        <div className="p-6 overflow-auto flex-1">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
