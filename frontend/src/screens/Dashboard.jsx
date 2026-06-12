import { useEffect, useState } from "react"
import { useTenant } from "../TenantContext"
import { getAnalytics } from "../api"

function Kpi({ label, value, sub, tone }) {
  const toneColor = tone === "good" ? "text-good" : tone === "bad" ? "text-bad" : "text-ink"
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-5">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`text-3xl font-semibold mt-2 tabular ${toneColor}`}>{value}</div>
      {sub && <div className="text-xs text-slate-400 mt-1 tabular">{sub}</div>}
    </div>
  )
}

const STATUS_ORDER = ["DRAFT", "ELIGIBILITY_CHECKED", "CODED", "SCRUBBED",
  "SUBMITTED", "PAID", "DENIED", "APPEAL_DRAFTED"]

export default function Dashboard() {
  const { tenantId } = useTenant()
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (!tenantId) return
    setData(null); setErr(null)
    getAnalytics(tenantId).then(setData).catch((e) => setErr(e.message))
  }, [tenantId])

  if (err) return <div className="text-bad text-sm">Could not load analytics: {err}</div>
  if (!data) return <div className="text-slate-400 text-sm">Loading?</div>

  const pct = (n) => `${Math.round(n * 100)}%`
  const money = (n) => `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Dashboard</h1>
        <p className="text-sm text-slate-500 mt-0.5">Revenue cycle at a glance</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <Kpi label="Total Claims" value={data.total_claims} />
        <Kpi label="Clean Claim Rate" value={pct(data.clean_claim_rate)}
          tone={data.clean_claim_rate >= 0.8 ? "good" : "bad"} />
        <Kpi label="Denial Rate" value={pct(data.denial_rate)}
          tone={data.denial_rate <= 0.1 ? "good" : "bad"} />
        <Kpi label="Collected" value={money(data.total_paid)}
          sub={`of ${money(data.total_billed)} billed`} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <div className="text-sm font-medium text-ink mb-4">Claims by Status</div>
          <div className="space-y-2">
            {STATUS_ORDER.filter((s) => data.by_status[s]).map((s) => {
              const count = data.by_status[s]
              const width = Math.round((count / data.total_claims) * 100)
              return (
                <div key={s} className="flex items-center gap-3">
                  <div className="w-40 text-xs text-slate-600 tabular">{s}</div>
                  <div className="flex-1 bg-slate-100 rounded h-5 overflow-hidden">
                    <div className="h-full bg-accent/80 rounded" style={{ width: `${width}%` }} />
                  </div>
                  <div className="w-8 text-right text-xs tabular text-slate-700">{count}</div>
                </div>
              )
            })}
          </div>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <div className="text-sm font-medium text-ink mb-4">Denial Reasons</div>
          {Object.keys(data.denial_reasons).length === 0 ? (
            <div className="text-sm text-slate-400">No denials recorded.</div>
          ) : (
            <div className="space-y-2">
              {Object.entries(data.denial_reasons).map(([carc, n]) => (
                <div key={carc} className="flex items-center justify-between text-sm">
                  <span className="tabular text-slate-700">{carc}</span>
                  <span className="tabular text-slate-500">{n}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
