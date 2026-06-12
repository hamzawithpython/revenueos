import { useEffect, useState } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { ArrowLeft } from "lucide-react"
import { useTenant } from "../TenantContext"
import { getClaim } from "../api"

function Section({ title, children }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-5">
      <div className="text-sm font-medium text-ink mb-3">{title}</div>
      {children}
    </div>
  )
}

function StatusBadge({ status }) {
  const tone = status === "PAID" ? "bg-good/10 text-good"
    : status === "DENIED" ? "bg-bad/10 text-bad"
    : status === "APPEAL_DRAFTED" ? "bg-warn/10 text-warn"
    : "bg-slate-100 text-slate-600"
  return <span className={`text-xs font-medium px-2 py-1 rounded tabular ${tone}`}>{status}</span>
}

export default function ClaimDetail() {
  const { id } = useParams()
  const { tenantId } = useTenant()
  const navigate = useNavigate()
  const [claim, setClaim] = useState(null)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (!tenantId) return
    setClaim(null); setErr(null)
    getClaim(tenantId, id).then(setClaim).catch((e) => setErr(e.message))
  }, [tenantId, id])

  if (err) return <div className="text-bad text-sm">Could not load claim: {err}</div>
  if (!claim) return <div className="text-slate-400 text-sm">Loading?</div>

  const money = (n) => `$${(n ?? 0).toFixed(2)}`

  return (
    <div className="space-y-5 max-w-4xl">
      <button onClick={() => navigate(-1)}
        className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-ink">
        <ArrowLeft size={15} /> Back
      </button>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">{claim.patient_name}</h1>
          <div className="text-sm text-slate-500 tabular mt-0.5">
            {claim.member_id} ? {claim.payer_name} ? DOS {claim.dos}
          </div>
        </div>
        <StatusBadge status={claim.status} />
      </div>

      <Section title="Clinical Note">
        <p className="text-sm text-slate-700">{claim.clinical_note}</p>
      </Section>

      <Section title="Codes">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-400 border-b border-slate-100">
              <th className="pb-2 font-medium">Type</th>
              <th className="pb-2 font-medium">Code</th>
              <th className="pb-2 font-medium">Modifier</th>
              <th className="pb-2 font-medium text-right">Charge</th>
            </tr>
          </thead>
          <tbody className="tabular">
            {claim.codes.map((c, i) => (
              <tr key={i} className="border-b border-slate-50">
                <td className="py-2 uppercase text-xs text-slate-500">{c.code_type}</td>
                <td className="py-2 font-medium">{c.code}</td>
                <td className="py-2 text-slate-500">{c.modifier || "?"}</td>
                <td className="py-2 text-right">{c.charge ? money(c.charge) : "?"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <div className="grid grid-cols-2 gap-5">
        <Section title="Eligibility (271)">
          {claim.eligibility ? (
            <div className="text-sm space-y-1 tabular">
              <div className="flex justify-between"><span className="text-slate-500">Active</span>
                <span className={claim.eligibility.active ? "text-good" : "text-bad"}>
                  {claim.eligibility.active ? "Yes" : "No"}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">Copay</span>
                <span>{money(claim.eligibility.copay)}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">Deductible</span>
                <span>{money(claim.eligibility.deductible)}</span></div>
            </div>
          ) : <div className="text-sm text-slate-400">Not yet checked.</div>}
        </Section>

        <Section title="Scrub Result">
          {claim.scrub ? (
            <div className="text-sm">
              <div className={`font-medium ${claim.scrub.clean ? "text-good" : "text-warn"}`}>
                {claim.scrub.clean ? "Clean" : `${claim.scrub.edits.length} edit(s)`}
              </div>
              {!claim.scrub.clean && (
                <ul className="mt-2 space-y-1 text-xs text-slate-600">
                  {claim.scrub.edits.map((e, i) => <li key={i}>? {e}</li>)}
                </ul>
              )}
            </div>
          ) : <div className="text-sm text-slate-400">Not yet scrubbed.</div>}
        </Section>
      </div>

      {claim.remittance && (
        <Section title="Remittance (835)">
          <div className="text-sm space-y-1 tabular">
            <div className="flex justify-between"><span className="text-slate-500">Allowed</span>
              <span>{money(claim.remittance.allowed_amount)}</span></div>
            <div className="flex justify-between"><span className="text-slate-500">Paid</span>
              <span className="text-good font-medium">{money(claim.remittance.paid_amount)}</span></div>
          </div>
        </Section>
      )}

      {claim.denial && (
        <Section title="Denial & Appeal">
          <div className="text-sm space-y-2">
            <div className="flex items-center gap-2">
              <span className="tabular font-medium text-bad">{claim.denial.carc_code}</span>
              <span className="text-slate-600">{claim.denial.reason}</span>
            </div>
            <div className="text-xs text-slate-500">
              Strategy: <span className="tabular">{claim.denial.appeal_status}</span>
            </div>
            {claim.denial.appeal_letter && (
              <div className="mt-2 bg-slate-50 rounded p-3 text-xs text-slate-700 whitespace-pre-wrap">
                {claim.denial.appeal_letter}
              </div>
            )}
          </div>
        </Section>
      )}

      <Section title="Audit Trail">
        <div className="space-y-2">
          {claim.audit.map((a, i) => (
            <div key={i} className="flex items-start gap-3 text-xs">
              <span className="tabular text-slate-400 w-40 shrink-0">{a.actor}</span>
              <span className="text-slate-600">{a.action}</span>
            </div>
          ))}
        </div>
      </Section>
    </div>
  )
}
