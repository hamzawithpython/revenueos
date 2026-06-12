import { NavLink, Routes, Route, Navigate } from "react-router-dom"
import {
  LayoutDashboard, GitBranch, ClipboardCheck, FileText, BarChart3, AlertTriangle,
} from "lucide-react"
import { TenantProvider, useTenant } from "./TenantContext"
import Dashboard from "./screens/Dashboard"

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/pipeline", label: "Claims Pipeline", icon: GitBranch },
  { to: "/review", label: "Review Queue", icon: ClipboardCheck },
  { to: "/denials", label: "Denials & Appeals", icon: AlertTriangle },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
]

function Switcher() {
  const { tenants, tenantId, setTenantId, role, setRole, roles } = useTenant()
  return (
    <div className="flex items-center gap-3">
      <select
        value={tenantId || ""}
        onChange={(e) => setTenantId(e.target.value)}
        className="bg-slate-850 text-slate-100 text-sm rounded-md border border-slate-700 px-3 py-1.5">
        {tenants.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
      </select>
      <select
        value={role}
        onChange={(e) => setRole(e.target.value)}
        className="bg-slate-850 text-slate-100 text-sm rounded-md border border-slate-700 px-3 py-1.5">
        {roles.map((r) => <option key={r} value={r}>{r}</option>)}
      </select>
    </div>
  )
}

function Shell({ children }) {
  return (
    <div className="min-h-screen flex">
      <aside className="w-60 bg-ink text-slate-300 flex flex-col">
        <div className="px-5 py-5 border-b border-slate-800">
          <div className="text-white font-semibold tracking-tight text-lg">RevenueOS</div>
          <div className="text-[11px] text-slate-500 mt-0.5 tabular">SYNTHETIC DATA ? DEMO</div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive ? "bg-slate-850 text-white" : "hover:bg-slate-850/50 hover:text-white"
                }`}>
              <Icon size={17} strokeWidth={2} />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex-1 flex flex-col">
        <header className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6">
          <div className="text-sm text-slate-500">Revenue Cycle Management</div>
          <Switcher />
        </header>
        <main className="flex-1 p-6 overflow-auto">{children}</main>
      </div>
    </div>
  )
}

function Placeholder({ name }) {
  return <div className="text-slate-400 text-sm">{name} ? built in the next batch.</div>
}

export default function App() {
  return (
    <TenantProvider>
      <Shell>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/pipeline" element={<Placeholder name="Claims Pipeline" />} />
          <Route path="/review" element={<Placeholder name="Review Queue" />} />
          <Route path="/denials" element={<Placeholder name="Denials & Appeals" />} />
          <Route path="/analytics" element={<Placeholder name="Analytics" />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Shell>
    </TenantProvider>
  )
}
