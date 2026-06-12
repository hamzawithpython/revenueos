import { useEffect, useState, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { useTenant } from "../TenantContext"
import { listClaims, getClaim } from "../api"

export default function Denials() {
  const { tenantId } = useTenant()
  const navigate = useNavigate()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    if (!tenantId) return
    setLoading(true)
    // Pull denied + appeal-drafted claims, then fetch detail for denial info.
    Promise.all(["DENIED", "APPEAL_DRAFTED"].map((s) => listClaims(tenantId, s)))
      .then((lists) => {
        const claims = lists.flat()
        return Promise.all(claims.map((c) => getClaim(tenantId, c.id)))
      })
      .then((details) => {
        setRows(details.filter((d) => d.denial))
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [tenantId])

  useEffect(() => { load() }, [load])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Denials & Appeals</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Every denial, the reason, and how the system handled it.
        </p>
      </div>

      {loading ? (
        <div className="text-slate-400 text-sm">Loading?</div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-lg border border-slate-200 p-8 text-center text-sm text-slate-500">
          No denials yet. Process claims with defects to see denial handling.
        </div>
      ) : (
        <div className="space-y-3">
          {rows.map((c) => (
            <div key={c.id} className="bg-white rounded-lg border border-slate-200 p-5">
              <div className="flex items-start justify-between">
                <div>
                  <button onClick={() => navigate(`/claims/${c.id}`)}
                    className="text-sm font-medium text-ink hover:text-accent">{c.patient_name}</button>
                  <div className="text-xs text-slate-500 mt-0.5">{c.payer_name}</div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs tabular font-medium text-bad">{c.denial.carc_code}</span>
                  <span className="text-xs tabular px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                    {c.denial.appeal_status}
                  </span>
                </div>
              </div>
              <div className="text-sm text-slate-600 mt-2">{c.denial.reason}</div>
              {c.denial.appeal_letter && (
                <details className="mt-3">
                  <summary className="text-xs text-accent cursor-pointer hover:underline">
                    View appeal letter
                  </summary>
                  <div className="mt-2 bg-slate-50 rounded p-3 text-xs text-slate-700 whitespace-pre-wrap">
                    {c.denial.appeal_letter}
                  </div>
                </details>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
