import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Customers from "./pages/Customers";
import CustomerDetail from "./pages/CustomerDetail";
import Jobs from "./pages/Jobs";
import JobDetail from "./pages/JobDetail";
import NewJob from "./pages/NewJob";
import Locations from "./pages/Locations";
import Bestillinger from "./pages/Bestillinger";
import Admin from "./pages/Admin";
import SuperDashboard from "./pages/SuperDashboard";
import SuperTenants from "./pages/SuperTenants";
import SuperTenantDetail from "./pages/SuperTenantDetail";
import Kasse from "./pages/Kasse";
import Varer from "./pages/Varer";

function Protected({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-8">Laster…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function RequireSuper({ children }: { children: JSX.Element }) {
  const { user } = useAuth();
  if (user?.role !== "superadmin") return <Navigate to="/" replace />;
  return children;
}

function RequireModule({ module: m, children }: { module: "workshop" | "shop"; children: JSX.Element }) {
  const { user } = useAuth();
  const ok = m === "workshop" ? user?.tenant?.module_workshop : user?.tenant?.module_shop;
  if (!ok) return (
    <div className="card text-center py-12">
      <div className="text-5xl mb-3">🔒</div>
      <div className="text-lg font-semibold">Modul ikke aktivert</div>
      <div className="text-sm text-slate-500">Kontakt super-admin for å aktivere {m === "workshop" ? "verksted" : "butikk"}-modulen.</div>
    </div>
  );
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="kunder" element={<Customers />} />
        <Route path="kunder/:id" element={<CustomerDetail />} />
        <Route path="jobber" element={<RequireModule module="workshop"><Jobs /></RequireModule>} />
        <Route path="jobber/ny" element={<RequireModule module="workshop"><NewJob /></RequireModule>} />
        <Route path="jobber/:id" element={<RequireModule module="workshop"><JobDetail /></RequireModule>} />
        <Route path="bestillinger" element={<RequireModule module="workshop"><Bestillinger /></RequireModule>} />
        <Route path="lokasjoner" element={<RequireModule module="workshop"><Locations /></RequireModule>} />
        <Route path="butikk" element={<RequireModule module="shop"><Kasse /></RequireModule>} />
        <Route path="butikk/varer" element={<RequireModule module="shop"><Varer /></RequireModule>} />
        <Route path="admin" element={<Admin />} />
        <Route path="super" element={<RequireSuper><SuperDashboard /></RequireSuper>} />
        <Route path="super/tenants" element={<RequireSuper><SuperTenants /></RequireSuper>} />
        <Route path="super/tenants/:id" element={<RequireSuper><SuperTenantDetail /></RequireSuper>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
