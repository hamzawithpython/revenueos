import { useEffect, useState, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { useTenant } from "../TenantContext"
import { listClaims, processClaim } from "../api"

const COLUMNS = [
  { key: "DRAFT", label: "Draft" },
  { key: "CODED", label: "Coded" },
  { key: "SCRUBBED", label: "Scrubbed" },
  { key: "PAID", label: "Paid", tone: "good" },
  { key: "DENIED", label: "Denied", tone: "bad" },
  { key: "APPEAL_DRAFTED", label: "Appeal / Recovered", tone: "warn" },
]

function Card({ claim, onProcess, processing, onOpen }) {
  return (
    <div className="bg-white rounded-md border border-slate-200 p-3 shadow-sm hover:shadow transition-shadow">
      <div className="flex items-start justify-between">
        <button onClick={() => onOpen(claim.id)}
          className="text-sm font-medium text-ink hover:text-accent text-left">
          {claim.patient_name}
        </button>
        <span className="text-xs tabular text-slate-400">
          ${claim.total_charge.toFixed(0)}
        </span>
      </div>
      <div className="text-xs text-slate-500 mt-1">{claim.payer_name}</div>
      <div className="text-[10px] tabular text-slate-400 mt-1">{claim.id.slice(0, 8)}</div>
      {claim.status === "DRAFT" && (
        <button onClick={() => onProcess(claim.id)} disabled={processing}
          className="mt-2 w-full text-xs bg-accent text-white rounded px-2 py-1 hover:bg-accent/90 disabled:opacity-50">
          {processing ? "Processing?" : "Run pipeline"}
        </button>
      )}
    </div>
  )
}

export default function Pipeline() {
  const { tenantId } = useTenant()
  const navigate = useNavigate()
  const [claims, setClaims] = useState([])
  const [loading, setLoading] = useState(true)
  const [processingId, setProcessingId] = useState(null)

  const load = useCallback(() => {
    if (!tenantId) return
    setLoading(true)
    listClaims(tenantId).then((c) => { setClaims(c); setLoading(false) })
      .catch(() => setLoading(false))
  }, [tenantId])

  useEffect(() => { load() }, [load])

  const handleProcess = async (id) => {
    setProcessingId(id)
    try {
      await processClaim(tenantId, id)
      load()  // refresh the board so the card moves columns
    } finally {
      setProcessingId(null)
    }
  }

  const byStatus = (status) => claims.filter((c) => c.status === status)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">Claims Pipeline</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Each claim moves left to right through its lifecycle. Run a draft to push it through.
          </p>
        </div>
        <button onClick={load}
          className="text-sm border border-slate-300 rounded-md px-3 py-1.5 hover:bg-white">
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="text-slate-400 text-sm">Loading?</div>
      ) : (
        <div className="grid grid-cols-6 gap-3">
          {COLUMNS.map((col) => {
            const items = byStatus(col.key)
            const dot = col.tone === "good" ? "bg-good" : col.tone === "bad" ? "bg-bad"
              : col.tone === "warn" ? "bg-warn" : "bg-slate-400"
            return (
              <div key={col.key} className="bg-slate-100 rounded-lg p-2 min-h-[200px]">
                <div className="flex items-center gap-2 px-1 py-2">
                  <span className={`w-2 h-2 rounded-full ${dot}`} />
                  <span className="text-xs font-medium text-slate-600">{col.label}</span>
                  <span className="text-xs tabular text-slate-400 ml-auto">{items.length}</span>
                </div>
                <div className="space-y-2">
                  {items.slice(0, 50).map((claim) => (
                    <Card key={claim.id} claim={claim} onProcess={handleProcess}
                      processing={processingId === claim.id} onOpen={(id) => navigate(`/claims/${id}`)} />
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
