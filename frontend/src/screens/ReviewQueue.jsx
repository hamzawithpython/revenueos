import { useEffect, useState, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { useTenant } from "../TenantContext"
import { listClaims } from "../api"

// The review worklist surfaces claims that ended in a state a biller
// should look at: denied, appeal drafted. (Recovered-after-denial claims
// end PAID but were flagged during processing; the Denials screen covers
// their history.)
const REVIEW_STATUSES = ["DENIED", "APPEAL_DRAFTED"]

export default function ReviewQueue() {
  const { tenantId } = useTenant()
  const navigate = useNavigate()
  const [claims, setClaims] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    if (!tenantId) return
    setLoading(true)
    Promise.all(REVIEW_STATUSES.map((s) => listClaims(tenantId, s)))
      .then((lists) => { setClaims(lists.flat()); setLoading(false) })
      .catch(() => setLoading(false))
  }, [tenantId])

  useEffect(() => { load() }, [load])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Review Queue</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Claims that need a human decision before they are closed.
        </p>
      </div>

      {loading ? (
        <div className="text-slate-400 text-sm">Loading?</div>
      ) : claims.length === 0 ? (
        <div className="bg-white rounded-lg border border-slate-200 p-8 text-center">
          <div className="text-sm text-slate-500">Nothing waiting for review. Process some claims in the Pipeline.</div>
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs text-slate-500">
              <tr className="text-left">
                <th className="px-4 py-2.5 font-medium">Patient</th>
                <th className="px-4 py-2.5 font-medium">Payer</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium text-right">Charge</th>
                <th className="px-4 py-2.5"></th>
              </tr>
            </thead>
            <tbody>
              {claims.map((c) => (
                <tr key={c.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-2.5 font-medium text-ink">{c.patient_name}</td>
                  <td className="px-4 py-2.5 text-slate-600">{c.payer_name}</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-xs tabular px-2 py-0.5 rounded ${
                      c.status === "DENIED" ? "bg-bad/10 text-bad" : "bg-warn/10 text-warn"}`}>
                      {c.status}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right tabular text-slate-700">${c.total_charge.toFixed(2)}</td>
                  <td className="px-4 py-2.5 text-right">
                    <button onClick={() => navigate(`/claims/${c.id}`)}
                      className="text-xs text-accent hover:underline">Review ?</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
