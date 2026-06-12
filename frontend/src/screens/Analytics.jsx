import { useEffect, useState } from "react"
import { useTenant } from "../TenantContext"
import { getAnalytics } from "../api"

export default function Analytics() {
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

  const money = (n) => `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  const pct = (n) => `${Math.round(n * 100)}%`
  const collectionRate = data.total_billed ? data.total_paid / data.total_billed : 0
  const maxDenial = Math.max(1, ...Object.values(data.denial_reasons))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Analytics</h1>
        <p className="text-sm text-slate-500 mt-0.5">Performance across the revenue cycle</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <div className="text-xs uppercase tracking-wide text-slate-500">Clean Claim Rate</div>
          <div className="text-3xl font-semibold mt-2 tabular text-ink">{pct(data.clean_claim_rate)}</div>
        </div>
        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <div className="text-xs uppercase tracking-wide text-slate-500">Denial Rate</div>
          <div className="text-3xl font-semibold mt-2 tabular text-ink">{pct(data.denial_rate)}</div>
        </div>
        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <div className="text-xs uppercase tracking-wide text-slate-500">Collection Rate</div>
          <div className="text-3xl font-semibold mt-2 tabular text-ink">{pct(collectionRate)}</div>
          <div className="text-xs text-slate-400 mt-1 tabular">{money(data.total_paid)} / {money(data.total_billed)}</div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <div className="text-sm font-medium text-ink mb-4">Claims by Status</div>
          <div className="space-y-2">
            {Object.entries(data.by_status).sort((a, b) => b[1] - a[1]).map(([status, count]) => {
              const width = Math.round((count / data.total_claims) * 100)
              return (
                <div key={status} className="flex items-center gap-3">
                  <div className="w-40 text-xs text-slate-600 tabular">{status}</div>
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
          <div className="text-sm font-medium text-ink mb-4">Denial Reasons (CARC)</div>
          {Object.keys(data.denial_reasons).length === 0 ? (
            <div className="text-sm text-slate-400">No denials recorded.</div>
          ) : (
            <div className="space-y-2">
              {Object.entries(data.denial_reasons).sort((a, b) => b[1] - a[1]).map(([carc, n]) => (
                <div key={carc} className="flex items-center gap-3">
                  <div className="w-20 text-xs tabular text-slate-600">{carc}</div>
                  <div className="flex-1 bg-slate-100 rounded h-5 overflow-hidden">
                    <div className="h-full bg-bad/70 rounded" style={{ width: `${Math.round((n / maxDenial) * 100)}%` }} />
                  </div>
                  <div className="w-8 text-right text-xs tabular text-slate-700">{n}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
