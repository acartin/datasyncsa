"use client";

import Link from "next/link";
import { ArrowLeft, ExternalLink, Eye, FolderKanban, Pencil, Plus, Trash2 } from "lucide-react";
import * as React from "react";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { DataGrid, DataGridColumn } from "@/components/market-watch/data-grid";
import { ProductVisual } from "@/components/market-watch/product-visual";
import { Modal } from "@/components/ui/modal";
import { Tabs } from "@/components/ui/tabs";
import { CampaignWorkspacePayload } from "@/lib/types";
import { Feedback } from "@/lib/feedback";

function visibleColumns(records: Array<Record<string, unknown>>) {
  return Array.from(new Set(records.flatMap((record) => Object.keys(record)))).slice(0, 8);
}

function columnsFor(records: Array<Record<string, unknown>>): DataGridColumn<Record<string, unknown>>[] {
  return visibleColumns(records).map((column) => ({
    id: column,
    header: column
  }));
}

function text(value: unknown, fallback = "-") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function boolText(value: unknown) {
  return value ? "Yes" : "No";
}

function clientOptionLabel(client: Record<string, unknown>) {
  const market = text(client.market, "");
  return `${text(client.name)}${market ? ` (${market})` : ""}`;
}

function chainOptionLabel(chain: Record<string, unknown>) {
  const engine = text(chain.engine, "");
  return `${text(chain.chain_name)}${engine ? ` (${engine})` : ""}`;
}

function storeOptionLabel(store: Record<string, unknown>) {
  const locationCode = text(store.location_code, "");
  return `${text(store.chain_name)} - ${text(store.store)}${locationCode ? ` (${locationCode})` : ""}`;
}

function productOptionLabel(product: Record<string, unknown>) {
  const brand = text(product.brand, "");
  const gtin = text(product.gtin_norm, "");
  const name = text(product.product);
  return `${brand ? `${brand} - ` : ""}${name}${gtin ? ` (${gtin})` : ""}`;
}

function reportUserOptionLabel(user: Record<string, unknown>) {
  const displayName = text(user.display_name, "");
  const email = text(user.email, "");
  return `${displayName || text(user.username, "User")}${email ? ` (${email})` : ""}`;
}

function canManageCampaignReports(payload: CampaignWorkspacePayload) {
  return ["client-admin", "system-admin", "system-user"].includes(payload.context.role);
}

function normalizeSearch(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function productSearchText(product: Record<string, unknown>) {
  return normalizeSearch([
    product.brand,
    product.product,
    product.gtin_norm,
    product.content_quantity,
    product.content_unit
  ]
    .map((value) => text(value, ""))
    .join(" "));
}

function productContentLabel(product: Record<string, unknown>) {
  const quantity = text(product.content_quantity, "");
  const unit = text(product.content_unit, "");
  return [quantity, unit].filter(Boolean).join(" ");
}

function productChainCoverage(product: Record<string, unknown>) {
  if (!Array.isArray(product.chain_coverage)) return [];
  return product.chain_coverage
    .filter((chain): chain is Record<string, unknown> => Boolean(chain) && typeof chain === "object" && !Array.isArray(chain))
    .map((chain) => ({
      id: text(chain.chain_id, text(chain.chain_key, "")),
      name: text(chain.chain_name, text(chain.chain_id, "Chain")),
      activeListings: text(chain.active_listings, "0")
    }))
    .filter((chain) => chain.id || chain.name);
}

function ProductRoleSelect({ defaultValue = "tracked" }: { defaultValue?: string }) {
  return (
    <select
      name="product_role"
      defaultValue={defaultValue}
      className="min-h-9 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
    >
      <option value="tracked">tracked</option>
      <option value="owned">owned</option>
      <option value="competitor">competitor</option>
      <option value="reference">reference</option>
    </select>
  );
}

function AccessActions({
  campaignId,
  record,
  canManage
}: {
  campaignId: string;
  record: Record<string, unknown>;
  canManage: boolean;
}) {
  const [editOpen, setEditOpen] = React.useState(false);
  const clientId = text(record.client_id);
  const client = text(record.client);

  if (!canManage) return null;

  return (
    <>
      <div className="flex justify-end gap-1">
        <Button type="button" variant="ghost" className="h-8 w-8 px-0" title="Edit access" onClick={() => setEditOpen(true)}>
          <Pencil className="h-4 w-4" />
        </Button>
        <form action={`/api/operations/campaigns/${encodeURIComponent(campaignId)}/access/${encodeURIComponent(clientId)}`} method="post">
          <input type="hidden" name="_method" value="patch" />
          <input type="hidden" name="is_active" value="false" />
          <Button type="submit" variant="ghost" className="h-8 w-8 px-0" title="Deactivate access">
            <Trash2 className="h-4 w-4" />
          </Button>
        </form>
      </div>

      <Modal
        open={editOpen}
        title={`Edit access for ${client}`}
        onClose={() => setEditOpen(false)}
      >
        <form action={`/api/operations/campaigns/${encodeURIComponent(campaignId)}/access/${encodeURIComponent(clientId)}`} method="post" className="space-y-5">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm font-medium">
              <span>Access role</span>
              <select
                name="access_role"
                defaultValue={text(record.access_role, "viewer")}
                className="min-h-9 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="viewer">viewer</option>
                <option value="admin">admin</option>
                <option value="owner">owner</option>
              </select>
            </label>
            <label className="space-y-1 text-sm font-medium">
              <span>Status</span>
              <select
                name="is_active"
                defaultValue={String(record.is_active !== false)}
                className="min-h-9 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="true">active</option>
                <option value="false">inactive</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm font-medium">
              <input type="hidden" name="is_default" value="false" />
              <input type="checkbox" name="is_default" defaultChecked={Boolean(record.is_default)} className="h-4 w-4 rounded border" />
              <span>Default campaign for this client</span>
            </label>
          </div>
          <div className="flex justify-end gap-2 border-t pt-4">
            <Button type="button" variant="outline" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button type="submit">Update</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}

function AccessSection({
  payload,
  records
}: {
  payload: CampaignWorkspacePayload;
  records: Array<Record<string, unknown>>;
}) {
  const [assignOpen, setAssignOpen] = React.useState(false);
  const campaignId = text(payload.campaign.id);
  const canManage = Boolean(payload.context.can_manage_access);
  const assignedClientIds = new Set(records.map((record) => text(record.client_id)));
  const availableClients = (payload.available_clients ?? []).filter(
    (client) => !assignedClientIds.has(text(client.id))
  );
  const clientOptions = availableClients.length ? availableClients : payload.available_clients ?? [];
  const columns: DataGridColumn<Record<string, unknown>>[] = [
    { id: "client", header: "Client" },
    { id: "market", header: "Market" },
    { id: "access_role", header: "Role" },
    { id: "is_default", header: "Default", cell: (record) => boolText(record.is_default) },
    { id: "is_active", header: "Active", cell: (record) => boolText(record.is_active) },
    { id: "valid_from", header: "Valid from" },
    { id: "valid_to", header: "Valid to" },
    {
      id: "actions",
      header: "",
      sortable: false,
      className: "w-28 text-right",
      cell: (record) => <AccessActions campaignId={campaignId} record={record} canManage={canManage} />
    }
  ];

  return (
    <div className="space-y-4">
      {canManage ? (
        <div className="flex justify-end">
          <Button type="button" onClick={() => setAssignOpen(true)}>
            <Plus className="h-4 w-4" />
            Assign client
          </Button>
        </div>
      ) : null}
      <DataGrid
        columns={columns}
        records={records}
        emptyTitle="No access records"
        emptyDescription="No clients are assigned to this campaign yet."
      />

      <Modal
        open={assignOpen}
        title="Assign client"
        description="Grant a client visibility into this campaign."
        onClose={() => setAssignOpen(false)}
      >
        <form action={`/api/operations/campaigns/${encodeURIComponent(campaignId)}/access`} method="post" className="space-y-5">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm font-medium">
              <span>Client</span>
              <select
                name="client_id"
                required
                className="min-h-9 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              >
                {clientOptions.map((client) => (
                  <option key={text(client.id)} value={text(client.id)}>
                    {clientOptionLabel(client)}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm font-medium">
              <span>Access role</span>
              <select
                name="access_role"
                defaultValue="viewer"
                className="min-h-9 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="viewer">viewer</option>
                <option value="admin">admin</option>
                <option value="owner">owner</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm font-medium">
              <input type="checkbox" name="is_default" className="h-4 w-4 rounded border" />
              <span>Default campaign for this client</span>
            </label>
          </div>
          <div className="flex justify-end gap-2 border-t pt-4">
            <Button type="button" variant="outline" onClick={() => setAssignOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!clientOptions.length}>Assign</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

function ReportRecipientActions({
  campaignId,
  record,
  canManage
}: {
  campaignId: string;
  record: Record<string, unknown>;
  canManage: boolean;
}) {
  const [editOpen, setEditOpen] = React.useState(false);
  const recipientId = text(record.id);
  const label = text(record.display_name, text(record.email, "recipient"));

  if (!canManage) return null;

  return (
    <>
      <div className="flex justify-end gap-1">
        <Button type="button" variant="ghost" className="h-8 w-8 px-0" title="Edit recipient" onClick={() => setEditOpen(true)}>
          <Pencil className="h-4 w-4" />
        </Button>
        <form action={`/api/operations/campaigns/${encodeURIComponent(campaignId)}/report-recipients/${encodeURIComponent(recipientId)}`} method="post">
          <input type="hidden" name="_method" value="patch" />
          <input type="hidden" name="is_active" value="false" />
          <Button type="submit" variant="ghost" className="h-8 w-8 px-0" title="Deactivate recipient">
            <Trash2 className="h-4 w-4" />
          </Button>
        </form>
      </div>

      <Modal open={editOpen} title={`Edit ${label}`} onClose={() => setEditOpen(false)}>
        <form action={`/api/operations/campaigns/${encodeURIComponent(campaignId)}/report-recipients/${encodeURIComponent(recipientId)}`} method="post" className="space-y-5">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm font-medium">
              <span>Name</span>
              <input
                name="display_name"
                defaultValue={text(record.display_name, "")}
                className="h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              />
            </label>
            <label className="space-y-1 text-sm font-medium">
              <span>Email</span>
              <input
                name="email"
                type="email"
                required
                defaultValue={text(record.email, "")}
                className="h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              />
            </label>
            <label className="space-y-1 text-sm font-medium">
              <span>Delivery type</span>
              <select
                name="recipient_type"
                defaultValue={text(record.recipient_type, "to")}
                className="min-h-9 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="to">To</option>
                <option value="cc">CC</option>
                <option value="bcc">BCC</option>
              </select>
            </label>
            <label className="space-y-1 text-sm font-medium">
              <span>Status</span>
              <select
                name="is_active"
                defaultValue={String(record.is_active !== false)}
                className="min-h-9 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="true">active</option>
                <option value="false">inactive</option>
              </select>
            </label>
          </div>
          <input type="hidden" name="report_kind" value={text(record.report_kind, "daily_price_radar")} />
          <div className="flex justify-end gap-2 border-t pt-4">
            <Button type="button" variant="outline" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button type="submit">Update</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}

function ReportRecipientsSection({
  payload,
  records
}: {
  payload: CampaignWorkspacePayload;
  records: Array<Record<string, unknown>>;
}) {
  const [createOpen, setCreateOpen] = React.useState(false);
  const campaignId = text(payload.campaign.id);
  const canManage = canManageCampaignReports(payload);
  const userOptions = payload.available_report_users ?? [];
  const columns: DataGridColumn<Record<string, unknown>>[] = [
    { id: "display_name", header: "Name" },
    { id: "email", header: "Email" },
    { id: "recipient_type", header: "Type" },
    { id: "report_kind", header: "Report" },
    { id: "is_active", header: "Active", cell: (record) => boolText(record.is_active) },
    { id: "updated_at", header: "Updated" },
    {
      id: "actions",
      header: "",
      sortable: false,
      className: "w-28 text-right",
      cell: (record) => <ReportRecipientActions campaignId={campaignId} record={record} canManage={canManage} />
    }
  ];

  return (
    <div className="space-y-4">
      {canManage ? (
        <div className="flex justify-end">
          <Button type="button" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" />
            Add recipient
          </Button>
        </div>
      ) : null}

      <DataGrid
        columns={columns}
        records={records}
        emptyTitle="No report recipients"
        emptyDescription="No recipients are configured for this campaign and tenant yet."
      />

      <Modal
        open={createOpen}
        title="Add report recipient"
        description="Configure who receives campaign report emails and PDF attachments."
        onClose={() => setCreateOpen(false)}
      >
        <form action={`/api/operations/campaigns/${encodeURIComponent(campaignId)}/report-recipients`} method="post" className="space-y-5">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm font-medium">
              <span>Portal user</span>
              <select
                name="user_id"
                defaultValue=""
                className="min-h-9 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">External email</option>
                {userOptions.map((user) => (
                  <option key={text(user.id)} value={text(user.id)}>
                    {reportUserOptionLabel(user)}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm font-medium">
              <span>Delivery type</span>
              <select
                name="recipient_type"
                defaultValue="to"
                className="min-h-9 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="to">To</option>
                <option value="cc">CC</option>
                <option value="bcc">BCC</option>
              </select>
            </label>
            <label className="space-y-1 text-sm font-medium">
              <span>Name</span>
              <input
                name="display_name"
                className="h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              />
            </label>
            <label className="space-y-1 text-sm font-medium">
              <span>Email</span>
              <input
                name="email"
                type="email"
                className="h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              />
            </label>
          </div>
          <input type="hidden" name="report_kind" value="daily_price_radar" />
          <input type="hidden" name="is_active" value="true" />
          <div className="flex justify-end gap-2 border-t pt-4">
            <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button type="submit">Add</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

function ReportPreviewSection({
  payload,
  records
}: {
  payload: CampaignWorkspacePayload;
  records: Array<Record<string, unknown>>;
}) {
  const preview = payload.report_preview;
  const campaignId = text(payload.campaign.id);
  const businessDate = text(preview?.business_date, "");
  const kpis = preview?.kpis ?? {};
  const canSend = canManageCampaignReports(payload);
  const highlights = preview?.highlights ?? [];
  const columns: DataGridColumn<Record<string, unknown>>[] = [
    { id: "headline", header: "Headline", className: "min-w-80" },
    { id: "chain", header: "Chain" },
    { id: "brand", header: "Brand" },
    { id: "product", header: "Product" },
    { id: "signal_type", header: "Type" },
    { id: "severity", header: "Severity" },
    { id: "impact_score", header: "Impact" },
    { id: "recommended_action", header: "Recommended action", className: "min-w-72" }
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 rounded-md border border-border-2 bg-card p-3 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="text-sm font-medium">Daily report preview</div>
          <div className="mt-1 text-sm text-muted-foreground">Review the campaign signal digest before email and PDF delivery.</div>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <form method="get" action={`/operations/campaigns/${encodeURIComponent(campaignId)}`} className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <input type="hidden" name="tab" value="report-preview" />
            <label className="space-y-1 text-sm font-medium">
              <span>Business date</span>
              <input
                name="business_date"
                type="date"
                defaultValue={businessDate}
                className="h-9 rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              />
            </label>
            <Button type="submit" variant="outline">
              Preview
            </Button>
          </form>
          <form action={`/api/operations/campaigns/${encodeURIComponent(campaignId)}/reports/daily/send`} method="post">
            <input type="hidden" name="business_date" value={businessDate} />
            <Button type="submit" disabled={!canSend}>
              Send email
            </Button>
          </form>
        </div>
      </div>

      <div className="grid gap-2 md:grid-cols-6">
        {[
          ["Total signals", kpis.total_signals],
          ["High severity", kpis.high_severity_signals],
          ["Price signals", kpis.price_signals],
          ["Promo signals", kpis.promo_signals],
          ["Availability", kpis.availability_signals],
          ["Chains", kpis.chains_with_signals]
        ].map(([label, value]) => (
          <div key={String(label)} className="rounded-md border border-border-2 px-3 py-2">
            <div className="text-lg font-medium">{Number(value ?? 0)}</div>
            <div className="text-xs text-muted-foreground">{label}</div>
          </div>
        ))}
      </div>

      <div className="space-y-3">
        <div className="text-sm font-semibold uppercase tracking-normal text-foreground">What needs attention today</div>
        {highlights.length ? (
          <div className="grid gap-3 lg:grid-cols-2">
            {highlights.map((highlight, index) => {
              const severity = text(highlight.severity, "").toLowerCase();
              const accent = severity === "critical" || severity === "high"
                ? "border-l-destructive bg-destructive/5"
                : severity === "medium"
                  ? "border-l-primary bg-accent"
                  : "border-l-secondary bg-accent";
              return (
                <div key={`${text(highlight.family_id, "highlight")}-${index}`} className={`rounded-md border border-border-2 border-l-4 p-3 ${accent}`}>
                  <div className="text-xs font-semibold uppercase tracking-normal text-muted-foreground">{text(highlight.family_label)}</div>
                  <div className="mt-1 font-medium leading-snug">{text(highlight.headline)}</div>
                  <div className="mt-1 text-sm leading-5 text-muted-foreground">
                    {text(highlight.summary, text(highlight.business_reading, "No summary available."))}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                    <span>{text(highlight.chain)}</span>
                    <span>{text(highlight.brand)}</span>
                    <span>{text(highlight.severity)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="rounded-md border border-border-2 p-3 text-sm text-muted-foreground">
            No priority highlights were selected for this campaign and business date.
          </div>
        )}
      </div>

      <DataGrid
        columns={columns}
        records={records}
        emptyTitle="No report signals"
        emptyDescription="No executive signals were found for this campaign, tenant and business date."
      />
    </div>
  );
}

function ChainActions({
  campaignId,
  record,
  canManage
}: {
  campaignId: string;
  record: Record<string, unknown>;
  canManage: boolean;
}) {
  const chainKey = text(record.id);

  if (!canManage) return null;

  return (
    <div className="flex justify-end gap-1">
      <form action={`/api/operations/campaigns/${encodeURIComponent(campaignId)}/chains/${encodeURIComponent(chainKey)}`} method="post">
        <Button type="submit" variant="ghost" className="h-8 w-8 px-0" title="Remove chain">
          <Trash2 className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}

function ChainsSection({
  payload,
  records
}: {
  payload: CampaignWorkspacePayload;
  records: Array<Record<string, unknown>>;
}) {
  const [assignOpen, setAssignOpen] = React.useState(false);
  const campaignId = text(payload.campaign.id);
  const canManage = Boolean(payload.context.can_manage_access);
  const assignedChainIds = new Set(records.map((record) => text(record.id)));
  const availableChains = (payload.available_chains ?? []).filter(
    (chain) => !assignedChainIds.has(text(chain.id)) && chain.is_active !== false
  );
  const chainOptions = availableChains.length ? availableChains : [];
  const columns: DataGridColumn<Record<string, unknown>>[] = [
    { id: "chain_name", header: "Chain" },
    { id: "chain_id", header: "ID" },
    { id: "engine", header: "Engine" },
    { id: "pricing_scope", header: "Pricing scope" },
    { id: "country_code", header: "Country" },
    { id: "stores", header: "Stores" },
    { id: "is_active", header: "Active", cell: (record) => boolText(record.is_active) },
    {
      id: "actions",
      header: "",
      sortable: false,
      className: "w-20 text-right",
      cell: (record) => <ChainActions campaignId={campaignId} record={record} canManage={canManage} />
    }
  ];

  return (
    <div className="space-y-4">
      {canManage ? (
        <div className="flex justify-end">
          <Button type="button" onClick={() => setAssignOpen(true)}>
            <Plus className="h-4 w-4" />
            Assign chain
          </Button>
        </div>
      ) : null}
      <DataGrid
        columns={columns}
        records={records}
        emptyTitle="No chains assigned"
        emptyDescription="Assign a chain to add its active stores to this campaign."
      />

      <Modal
        open={assignOpen}
        title="Assign chain"
        description="Add all active stores from a chain to this campaign."
        onClose={() => setAssignOpen(false)}
      >
        <form action={`/api/operations/campaigns/${encodeURIComponent(campaignId)}/chains`} method="post" className="space-y-5">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm font-medium">
              <span>Chain</span>
              <select
                name="chain_key"
                required
                className="min-h-9 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              >
                {chainOptions.map((chain) => (
                  <option key={text(chain.id)} value={text(chain.id)}>
                    {chainOptionLabel(chain)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="flex justify-end gap-2 border-t pt-4">
            <Button type="button" variant="outline" onClick={() => setAssignOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!chainOptions.length}>Assign</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

function StoreActions({
  campaignId,
  record,
  canManage
}: {
  campaignId: string;
  record: Record<string, unknown>;
  canManage: boolean;
}) {
  const locationKey = text(record.id);

  if (!canManage) return null;

  return (
    <div className="flex justify-end gap-1">
      <form action={`/api/operations/campaigns/${encodeURIComponent(campaignId)}/stores/${encodeURIComponent(locationKey)}`} method="post">
        <Button type="submit" variant="ghost" className="h-8 w-8 px-0" title="Remove store">
          <Trash2 className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}

function StoresSection({
  payload,
  records
}: {
  payload: CampaignWorkspacePayload;
  records: Array<Record<string, unknown>>;
}) {
  const [assignOpen, setAssignOpen] = React.useState(false);
  const campaignId = text(payload.campaign.id);
  const canManage = Boolean(payload.context.can_manage_access);
  const assignedStoreIds = new Set(records.map((record) => text(record.id)));
  const storeOptions = (payload.available_stores ?? []).filter(
    (store) => !assignedStoreIds.has(text(store.id))
  );
  const columns: DataGridColumn<Record<string, unknown>>[] = [
    { id: "chain_name", header: "Chain" },
    { id: "store", header: "Store" },
    { id: "location_code", header: "Code" },
    { id: "sales_channel", header: "Channel" },
    { id: "province", header: "Province" },
    { id: "canton", header: "Canton" },
    { id: "district", header: "District" },
    { id: "is_default", header: "Default", cell: (record) => boolText(record.is_default) },
    { id: "is_active", header: "Active", cell: (record) => boolText(record.is_active) },
    {
      id: "actions",
      header: "",
      sortable: false,
      className: "w-20 text-right",
      cell: (record) => <StoreActions campaignId={campaignId} record={record} canManage={canManage} />
    }
  ];

  return (
    <div className="space-y-4">
      {canManage ? (
        <div className="flex justify-end">
          <Button type="button" onClick={() => setAssignOpen(true)}>
            <Plus className="h-4 w-4" />
            Assign store
          </Button>
        </div>
      ) : null}
      <DataGrid
        columns={columns}
        records={records}
        emptyTitle="No stores assigned"
        emptyDescription="Assign a chain or add individual stores to this campaign."
      />

      <Modal
        open={assignOpen}
        title="Assign store"
        description="Add one store to this campaign."
        onClose={() => setAssignOpen(false)}
      >
        <form action={`/api/operations/campaigns/${encodeURIComponent(campaignId)}/stores`} method="post" className="space-y-5">
          <div className="grid gap-3">
            <label className="space-y-1 text-sm font-medium">
              <span>Store</span>
              <select
                name="location_key"
                required
                className="min-h-9 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              >
                {storeOptions.map((store) => (
                  <option key={text(store.id)} value={text(store.id)}>
                    {storeOptionLabel(store)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="flex justify-end gap-2 border-t pt-4">
            <Button type="button" variant="outline" onClick={() => setAssignOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!storeOptions.length}>Assign</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

function ProductDetailCard({
  product,
  badge,
  role
}: {
  product: Record<string, unknown>;
  badge: string;
  role: string;
}) {
  const productId = text(product.id);
  const imageUrl = text(product.image_url, "");
  const sourceUrl = text(product.product_url, "");
  const content = productContentLabel(product);
  const chainCoverage = productChainCoverage(product);
  const campaignObservations = product.campaign_observations == null ? null : Number(product.campaign_observations);
  const canOpenProduct = Boolean(productId && (campaignObservations === null ? chainCoverage.length : campaignObservations > 0));
  const canOpenSourceListing = Boolean(sourceUrl && chainCoverage.length);

  return (
    <div className="rounded-md border border-border-2 bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-medium uppercase tracking-normal text-muted-foreground">Catalog preview</div>
          <div className="mt-1 line-clamp-2 text-lg font-semibold leading-snug">{text(product.product)}</div>
        </div>
        <Badge>{badge}</Badge>
      </div>

      <div className="mt-4 flex justify-center rounded-md border bg-background p-2">
        <ProductVisual hasSku={Boolean(imageUrl || text(product.gtin_norm, ""))} images={imageUrl ? [imageUrl] : []} size="lg" />
      </div>

      <div className="mt-4 border-t pt-4">
        <div className="text-xs text-muted-foreground">Available in chains</div>
        <div className="mt-2 flex flex-wrap gap-2">
          {chainCoverage.length ? chainCoverage.map((chain) => (
            <span key={chain.id || chain.name} title={`${chain.activeListings} active listing${chain.activeListings === "1" ? "" : "s"}`}>
              <Badge>{chain.name}</Badge>
            </span>
          )) : (
            <span className="text-sm text-muted-foreground">No active chain coverage</span>
          )}
        </div>
      </div>

      <div className="mt-4 space-y-3 text-sm">
        <div>
          <div className="text-xs text-muted-foreground">Brand</div>
          <div className="font-medium">{text(product.brand, "No brand")}</div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <div className="text-xs text-muted-foreground">GTIN</div>
            <div className="break-all font-mono text-sm">{text(product.gtin_norm)}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Content</div>
            <div>{content || "-"}</div>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <div className="text-xs text-muted-foreground">Assignment role</div>
            <div className="font-medium">{role}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Catalog status</div>
            <div className="font-medium">{product.is_active ? "Active" : "Inactive"}</div>
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-2 border-t pt-4 sm:grid-cols-2">
        {canOpenProduct ? (
          <Button asChild variant="outline">
            <Link href={`/pricing/products/${encodeURIComponent(productId)}`} target="_blank" rel="noreferrer">
              <ExternalLink className="h-4 w-4" />
              Open product
            </Link>
          </Button>
        ) : (
          <Button type="button" variant="outline" disabled>
            <ExternalLink className="h-4 w-4" />
            Open product
          </Button>
        )}
        {canOpenSourceListing ? (
          <Button asChild variant="outline">
            <a href={sourceUrl} target="_blank" rel="noreferrer">
              <ExternalLink className="h-4 w-4" />
              Source listing
            </a>
          </Button>
        ) : (
          <Button type="button" variant="outline" disabled>
            <ExternalLink className="h-4 w-4" />
            Source listing
          </Button>
        )}
      </div>
    </div>
  );
}

function ProductActions({
  campaignId,
  record,
  canManage
}: {
  campaignId: string;
  record: Record<string, unknown>;
  canManage: boolean;
}) {
  const [viewOpen, setViewOpen] = React.useState(false);
  const [editOpen, setEditOpen] = React.useState(false);
  const productKey = text(record.id);
  const productName = text(record.product);

  return (
    <>
      <div className="flex justify-end gap-1">
        <Button type="button" variant="ghost" className="h-8 w-8 px-0" title="View product" onClick={() => setViewOpen(true)}>
          <Eye className="h-4 w-4" />
        </Button>
        {canManage ? (
          <Button type="button" variant="ghost" className="h-8 w-8 px-0" title="Edit product role" onClick={() => setEditOpen(true)}>
            <Pencil className="h-4 w-4" />
          </Button>
        ) : null}
        {canManage ? (
          <form action={`/api/operations/campaigns/${encodeURIComponent(campaignId)}/products/${encodeURIComponent(productKey)}`} method="post">
            <input type="hidden" name="_method" value="delete" />
            <Button type="submit" variant="ghost" className="h-8 w-8 px-0" title="Remove product">
              <Trash2 className="h-4 w-4" />
            </Button>
          </form>
        ) : null}
      </div>

      <Modal
        open={viewOpen}
        title="Product detail"
        description={productName}
        onClose={() => setViewOpen(false)}
        className="max-w-xl"
      >
        <ProductDetailCard product={record} badge="Assigned" role={text(record.product_role, "tracked")} />
      </Modal>

      <Modal
        open={editOpen}
        title={`Edit product role`}
        description={productName}
        onClose={() => setEditOpen(false)}
      >
        <form action={`/api/operations/campaigns/${encodeURIComponent(campaignId)}/products/${encodeURIComponent(productKey)}`} method="post" className="space-y-5">
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-sm font-medium">
              <span>Product role</span>
              <ProductRoleSelect defaultValue={text(record.product_role, "tracked")} />
            </label>
          </div>
          <div className="flex justify-end gap-2 border-t pt-4">
            <Button type="button" variant="outline" onClick={() => setEditOpen(false)}>
              Cancel
            </Button>
            <Button type="submit">Update</Button>
          </div>
        </form>
      </Modal>
    </>
  );
}

function ProductSelectionPreview({
  product,
  selected,
  role
}: {
  product: Record<string, unknown> | null;
  selected: boolean;
  role: string;
}) {
  if (!product) {
    return (
      <div className="flex min-h-[390px] items-center justify-center rounded-md border border-dashed bg-card p-6 text-center text-sm text-muted-foreground">
        No catalog products match the current search.
      </div>
    );
  }

  return <ProductDetailCard product={product} badge={selected ? "Selected" : "Preview"} role={role} />;
}

function ProductsSection({
  payload,
  records
}: {
  payload: CampaignWorkspacePayload;
  records: Array<Record<string, unknown>>;
}) {
  const [assignOpen, setAssignOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [productRole, setProductRole] = React.useState("tracked");
  const [previewProductId, setPreviewProductId] = React.useState<string | null>(null);
  const [selectedProductIds, setSelectedProductIds] = React.useState<string[]>([]);
  const campaignId = text(payload.campaign.id);
  const canManage = Boolean(payload.context.can_manage_access);
  const assignedProductIds = new Set(records.map((record) => text(record.id)));
  const availableProducts = (payload.available_products ?? []).filter(
    (product) => !assignedProductIds.has(text(product.id))
  );
  const normalizedQuery = normalizeSearch(query.trim());
  const productOptions = availableProducts
    .filter((product) => !normalizedQuery || productSearchText(product).includes(normalizedQuery))
    .slice(0, 80);
  const previewCandidateId = previewProductId ?? selectedProductIds.at(-1) ?? null;
  const previewProduct = (
    previewCandidateId
      ? availableProducts.find((product) => text(product.id) === previewCandidateId)
      : null
  ) ?? productOptions[0] ?? null;
  const columns: DataGridColumn<Record<string, unknown>>[] = [
    { id: "product_role", header: "Role" },
    { id: "brand", header: "Brand" },
    { id: "product", header: "Product" },
    { id: "gtin_norm", header: "GTIN" },
    { id: "content_quantity", header: "Qty" },
    { id: "content_unit", header: "Unit" },
    { id: "is_active", header: "Active", cell: (record) => boolText(record.is_active) },
    {
      id: "actions",
      header: "",
      sortable: false,
      className: "w-24 text-right",
      cell: (record) => <ProductActions campaignId={campaignId} record={record} canManage={canManage} />
    }
  ];

  return (
    <div className="space-y-4">
      {canManage ? (
        <div className="flex justify-end">
          <Button type="button" onClick={() => setAssignOpen(true)}>
            <Plus className="h-4 w-4" />
            Assign product
          </Button>
        </div>
      ) : null}
      <DataGrid
        columns={columns}
        records={records}
        emptyTitle="No products assigned"
        emptyDescription="Select canonical catalog products to define this campaign."
      />

      <Modal
        open={assignOpen}
        title="Assign product"
        description="Select products from the canonical catalog."
        onClose={() => {
          setAssignOpen(false);
          setSelectedProductIds([]);
          setPreviewProductId(null);
          setQuery("");
        }}
        className="max-w-6xl"
      >
        <form action={`/api/operations/campaigns/${encodeURIComponent(campaignId)}/products`} method="post" className="space-y-5">
          {selectedProductIds.map((productId) => (
            <input key={productId} type="hidden" name="product_keys" value={productId} />
          ))}
          <div className="grid gap-3">
            <label className="space-y-1 text-sm font-medium">
              <span>Search catalog</span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Brand, product or GTIN"
                className="h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
              />
            </label>
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
              <div className="space-y-3">
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <label className="w-full max-w-48 space-y-1 text-sm font-medium">
                    <span>Product role</span>
                    <select
                      name="product_role"
                      value={productRole}
                      onChange={(event) => setProductRole(event.target.value)}
                      className="min-h-9 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                    >
                      <option value="tracked">tracked</option>
                      <option value="owned">owned</option>
                      <option value="competitor">competitor</option>
                      <option value="reference">reference</option>
                    </select>
                  </label>
                  <div className="text-xs text-muted-foreground">
                    {selectedProductIds.length} selected. Showing {productOptions.length} of {availableProducts.length}.
                  </div>
                </div>
                <div className="max-h-[430px] overflow-auto rounded-md border bg-background">
                  {productOptions.length ? productOptions.map((product) => {
                    const productId = text(product.id);
                    const content = productContentLabel(product);
                    return (
                      <label
                        key={productId}
                        className="flex cursor-pointer items-start gap-3 border-b px-3 py-3 text-sm font-normal last:border-b-0 hover:bg-surface-2"
                        onMouseEnter={() => setPreviewProductId(productId)}
                        onFocus={() => setPreviewProductId(productId)}
                      >
                        <input
                          type="checkbox"
                          checked={selectedProductIds.includes(productId)}
                          onChange={(event) => {
                            setPreviewProductId(productId);
                            setSelectedProductIds((current) =>
                              event.target.checked
                                ? Array.from(new Set([...current, productId]))
                                : current.filter((item) => item !== productId)
                            );
                          }}
                          className="mt-0.5 h-4 w-4 rounded border"
                        />
                        <span className="grid min-w-0 flex-1 gap-1">
                          <span className="flex min-w-0 items-start justify-between gap-3">
                            <span className="min-w-0">
                              <span className="block truncate font-medium">{productOptionLabel(product)}</span>
                              <span className="block truncate text-xs text-muted-foreground">{text(product.brand, "No brand")}</span>
                            </span>
                          </span>
                          <span className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                            <span className="font-mono">{text(product.gtin_norm)}</span>
                            <span>{content || "-"}</span>
                          </span>
                        </span>
                      </label>
                    );
                  }) : (
                    <div className="px-3 py-10 text-center text-sm text-muted-foreground">
                      No catalog products match this search.
                    </div>
                  )}
                </div>
              </div>
              <ProductSelectionPreview
                product={previewProduct}
                selected={previewProduct ? selectedProductIds.includes(text(previewProduct.id)) : false}
                role={productRole}
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 border-t pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setAssignOpen(false);
                setSelectedProductIds([]);
                setPreviewProductId(null);
                setQuery("");
              }}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={!selectedProductIds.length}>Assign selected</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export function CampaignWorkspace({
  payload,
  feedback,
  initialTab
}: {
  payload: CampaignWorkspacePayload;
  feedback?: Feedback | null;
  initialTab?: string;
}) {
  const initialSectionId = React.useMemo(() => {
    const fallback = payload.sections[0]?.id ?? "overview";
    return payload.sections.some((section) => section.id === initialTab) ? String(initialTab) : fallback;
  }, [initialTab, payload.sections]);
  const [activeSectionId, setActiveSectionId] = React.useState(initialSectionId);
  const activeSection = payload.sections.find((section) => section.id === activeSectionId) ?? payload.sections[0];
  const campaign = payload.campaign;

  function selectSection(sectionId: string) {
    setActiveSectionId(sectionId);
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    url.searchParams.set("tab", sectionId);
    url.searchParams.delete("feedback");
    url.searchParams.delete("message");
    window.history.replaceState(null, "", url.toString());
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div className="min-w-0">
          <Button asChild variant="ghost" className="mb-3 px-0">
            <Link href="/operations/campaigns">
              <ArrowLeft className="h-4 w-4" />
              Campaigns
            </Link>
          </Button>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Badge>{text(campaign.status)}</Badge>
            <Badge>{text(campaign.access_role)}</Badge>
            <Badge>tenant {payload.context.client_id}</Badge>
          </div>
          <h1 className="truncate text-2xl font-light">{text(campaign.name)}</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            {text(campaign.description, "Campaign configuration workspace.")}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-5">
          {Object.entries(payload.summary).map(([key, value]) => (
            <div key={key} className="rounded-md border border-border-2 px-3 py-2">
              <div className="text-lg font-medium">{value}</div>
              <div className="text-xs capitalize text-muted-foreground">{key.replaceAll("_", " ")}</div>
            </div>
          ))}
        </div>
      </div>

      {feedback ? (
        <Alert variant={feedback.type} title={feedback.type === "error" ? "Could not save" : "Operation completed"}>
          {feedback.message}
        </Alert>
      ) : null}

      <div className="rounded-md border border-border-2 bg-card px-4 py-3">
        <Tabs
          items={payload.sections.map((section) => ({ id: section.id, label: section.label }))}
          value={activeSectionId}
          onValueChange={selectSection}
          className="max-w-full overflow-x-auto"
        />
      </div>

      {activeSection ? (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <FolderKanban className="h-4 w-4 text-muted-foreground" />
              <div className="font-medium">{activeSection.label}</div>
            </div>
            <div className="mt-1 text-sm text-muted-foreground">{activeSection.description}</div>
          </CardHeader>
          <CardContent>
            {activeSection.id === "access" ? (
              <AccessSection payload={payload} records={activeSection.records} />
            ) : activeSection.id === "report-recipients" ? (
              <ReportRecipientsSection payload={payload} records={activeSection.records} />
            ) : activeSection.id === "report-preview" ? (
              <ReportPreviewSection payload={payload} records={activeSection.records} />
            ) : activeSection.id === "chains" ? (
              <ChainsSection payload={payload} records={activeSection.records} />
            ) : activeSection.id === "stores" ? (
              <StoresSection payload={payload} records={activeSection.records} />
            ) : activeSection.id === "products" ? (
              <ProductsSection payload={payload} records={activeSection.records} />
            ) : (
              <DataGrid
                columns={columnsFor(activeSection.records)}
                records={activeSection.records}
                emptyTitle={`No ${activeSection.label.toLowerCase()} records`}
                emptyDescription="This folder is ready for the next CRUD step."
              />
            )}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
