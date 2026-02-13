# Test Credentials & Role Guide
**Updated: January 2026**

This document lists the credentials for verifying Multi-Tenancy and Role-Based Access Control (RBAC).

## 🔑 Login Credentials
**Password for ALL users:** `holalola`

| Rol | Email | Cliente | Qué debería ver (Menú) |
|:---|:---|:---|:---|
| **Super Admin** | `acartina15@hotmail.com` | N/A (Global) | **TODO** (Global Settings, Tenants, Countries, Prompts) |
| **System User** | `system-user@datasyncsa.com` | DataSync | Server Status, Audit Logs (Vista Técnica) |
| **Client Admin** | `cocacola-admin@cocacola.com` | **Coca Cola** | Leads, Campañas, Configuración Cuenta, Prompts |
| **Client User** | `cocacola-user@cocacola.com` | **Coca Cola** | "Mis Leads", "Mis Tareas" (Vista Operativa) |
| **Client Admin** | `pepsi-admin@pepsi.com` | **Pepsi** | Igual a Coca Cola, pero **datos aislados** |
| **Client User** | `pepsi-user@pepsi.com` | **Pepsi** | Igual a Coca Cola, pero **datos aislados** |

---

## 🏗️ Structure Overview

### 1. Tenants (Clients)
- **Coca Cola**: Main manufacturing client.
- **Pepsi**: Competitor client. Data is strictly isolated.
- **DataSync Systems**: Technical/Internal tenant for system maintainers.

### 2. Roles
1. **admin**: The "God Mode". Can see and manage all tenants.
    - *Menu:* Dashboard, Clients, Prompts, Countries, System (Users, Roles).
2. **client-admin**: Manager of a specific tenant.
    - *Menu:* Dashboard, Leads (Team), Campaigns, Prompts (Self), Settings.
3. **client-user**: Operator/Salesperson.
    - *Menu:* Dashboard, My Leads, My Tasks.
4. **system-user**: IT Support.
    - *Menu:* Server Status, Logs.

## 🧪 Testing Instructions

1. **Verify Isolation**:
    - Login as `cocacola-admin`. Create a Prompt "Coke Promo".
    - Logout and login as `pepsi-admin`. Verify you **CANNOT** see "Coke Promo".

2. **Verify Portability**:
    - Login as `cocacola-user`. Any change you make should be visible to `cocacola-admin` but NOT `pepsi-admin`.

3. **Verify Security**:
    - As `client-user`, try to access `/settings` URL manually. It should default to home or 403 (if router protected).

## 🛠️ Data Reset
To reset this data to the initial state, verify the existence of `backend/setup_test_data.py` and run:

```bash
docker exec -it prd-web-aifirst-api-01 python setup_test_data.py
```
