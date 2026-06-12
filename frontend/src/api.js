// Central API client. All calls go through the Vite proxy at /api and
// carry the current tenant id, mirroring the backend's X-Tenant-Id scoping.

const BASE = "/api"

export async function apiGet(path, tenantId) {
  const headers = {}
  if (tenantId) headers["X-Tenant-Id"] = tenantId
  const res = await fetch(`${BASE}${path}`, { headers })
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return res.json()
}

export async function apiPost(path, tenantId) {
  const headers = {}
  if (tenantId) headers["X-Tenant-Id"] = tenantId
  const res = await fetch(`${BASE}${path}`, { method: "POST", headers })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
  return res.json()
}

export const listTenants = () => apiGet("/tenants")
export const listClaims = (tenantId, status) =>
  apiGet(`/claims${status ? `?status=${status}&limit=500` : "?limit=500"}`, tenantId)
export const getClaim = (tenantId, id) => apiGet(`/claims/${id}`, tenantId)
export const processClaim = (tenantId, id) => apiPost(`/claims/${id}/process`, tenantId)
export const getAnalytics = (tenantId) => apiGet("/analytics", tenantId)
export const getScorecard = () => apiGet("/scorecard")

