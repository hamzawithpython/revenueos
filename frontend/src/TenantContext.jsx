import { createContext, useContext, useEffect, useState } from "react"
import { listTenants } from "./api"

const TenantContext = createContext(null)

const ROLES = ["Admin", "Manager", "Biller", "Practice"]

export function TenantProvider({ children }) {
  const [tenants, setTenants] = useState([])
  const [tenantId, setTenantId] = useState(null)
  const [role, setRole] = useState("Admin")

  useEffect(() => {
    listTenants().then((t) => {
      setTenants(t)
      if (t.length) setTenantId(t[0].id)
    }).catch(() => {})
  }, [])

  const current = tenants.find((t) => t.id === tenantId) || null

  return (
    <TenantContext.Provider
      value={{ tenants, tenantId, setTenantId, role, setRole, roles: ROLES, current }}>
      {children}
    </TenantContext.Provider>
  )
}

export const useTenant = () => useContext(TenantContext)
