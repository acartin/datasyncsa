"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowLeft, ExternalLink, Eye, PackageSearch } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Tabs } from "@/components/ui/tabs";
import { DataGrid, DataGridColumn } from "@/components/market-watch/data-grid";
import { ProductVisual } from "@/components/market-watch/product-visual";
import { ModulePayload, MonitoredProductWorkspacePayload } from "@/lib/types";

function text(value: unknown, fallback = "-") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function normalized(value: unknown) {
  return text(value, "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function numberValue(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function contentLabel(record: Record<string, unknown>) {
  const quantity = text(record.content_quantity, "");
  const unit = text(record.content_unit, "");
  return [quantity, unit].filter(Boolean).join(" ") || "-";
}

function ProductIdentifier({ value }: { value: unknown }) {
  const identifier = text(value, "");
  if (!identifier) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-[6px] border border-border-2 bg-surface-2 px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.08em] text-ink-secondary">
      GTIN
      <code className="select-all font-mono text-[11px] font-normal tracking-normal text-foreground">{identifier}</code>
    </span>
  );
}

function chainOptions(payload: ModulePayload) {
  const fromPayload = payload.filters?.chains;
  if (Array.isArray(fromPayload)) return fromPayload.map(String).filter(Boolean);
  return Array.from(
    new Set(
      payload.records.flatMap((record) =>
        text(record.chains, "")
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean)
      )
    )
  ).sort((left, right) => left.localeCompare(right));
}

function statusOptions(payload: ModulePayload) {
  const fromPayload = payload.filters?.statuses;
  if (Array.isArray(fromPayload)) return fromPayload.map(String).filter(Boolean);
  return Array.from(new Set(payload.records.map((record) => text(record.status, "")).filter(Boolean))).sort();
}

function matchesCoverage(record: Record<string, unknown>, coverage: string) {
  if (!coverage) return true;
  const activeListings = numberValue(record.active_listings);
  const campaigns = numberValue(record.campaigns);
  if (coverage === "with_active_listings") return activeListings > 0;
  if (coverage === "without_active_listings") return activeListings === 0;
  if (coverage === "used_in_campaigns") return campaigns > 0;
  if (coverage === "not_used_in_campaigns") return campaigns === 0;
  return true;
}

export function MonitoredProductsPage({ payload }: { payload: ModulePayload }) {
  const [query, setQuery] = React.useState("");
  const [status, setStatus] = React.useState("");
  const [chain, setChain] = React.useState("");
  const [coverage, setCoverage] = React.useState("");
  const queryTerm = normalized(query);
  const chains = chainOptions(payload);
  const statuses = statusOptions(payload);

  const records = React.useMemo(() => {
    return payload.records.filter((record) => {
      const queryMatches =
        !queryTerm ||
        ["product_key", "gtin_norm", "brand", "product", "content_unit", "chains"].some((key) =>
          normalized(record[key]).includes(queryTerm)
        );
      const statusMatches = !status || text(record.status) === status;
      const chainMatches = !chain || text(record.chains, "").split(",").map((item) => item.trim()).includes(chain);
      return queryMatches && statusMatches && chainMatches && matchesCoverage(record, coverage);
    });
  }, [chain, coverage, payload.records, queryTerm, status]);

  const columns: DataGridColumn<Record<string, unknown>>[] = [
    {
      id: "product",
      header: "Product",
      cell: (record) => (
        <div className="min-w-[280px]">
          <div className="font-medium">{text(record.product)}</div>
          <div className="mt-1 text-xs text-muted-foreground">{text(record.gtin_norm)}</div>
        </div>
      ),
      sortValue: (record) => text(record.product),
    },
    { id: "brand", header: "Brand" },
    { id: "content", header: "Content", cell: contentLabel, sortValue: contentLabel },
    {
      id: "status",
      header: "Status",
      cell: (record) => <Badge>{text(record.status)}</Badge>,
    },
    { id: "active_chains_seen", header: "Chains" },
    { id: "active_listings", header: "Listings" },
    { id: "campaigns", header: "Campaigns" },
    {
      id: "latest_observation_at",
      header: "Latest observation",
      cell: (record) => <span className="whitespace-nowrap">{text(record.latest_observation_at)}</span>,
    },
    {
      id: "actions",
      header: "",
      sortable: false,
      className: "w-16 text-right",
      cell: (record) => (
        <Button asChild variant="outline" className="h-8 w-8 px-0" aria-label="View monitored product">
          <Link href={`/operations/monitored-products/${encodeURIComponent(text(record.product_key ?? record.id))}`}>
            <Eye className="h-4 w-4" />
          </Link>
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <Badge>{payload.module.status}</Badge>
            <Badge>role: {payload.context.role}</Badge>
          </div>
          <h1 className="text-page-title font-light">{payload.module.title}</h1>
          <p className="mt-2 max-w-3xl text-page-subtitle text-muted-foreground">{payload.module.description}</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <PackageSearch className="h-4 w-4 text-muted-foreground" />
            <div className="text-card-title font-medium">Filters</div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-[minmax(260px,1fr)_180px_220px_220px]">
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search product, GTIN, brand or chain"
              aria-label="Search monitored products"
              className="h-control rounded-md border bg-background px-3 text-body-sm outline-none focus:ring-2 focus:ring-ring"
            />
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value)}
              aria-label="Filter by status"
              className="h-control rounded-md border bg-background px-3 text-body-sm outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">All statuses</option>
              {statuses.map((item) => (
                <option key={item} value={item}>{item}</option>
              ))}
            </select>
            <select
              value={chain}
              onChange={(event) => setChain(event.target.value)}
              aria-label="Filter by chain"
              className="h-control rounded-md border bg-background px-3 text-body-sm outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">All chains</option>
              {chains.map((item) => (
                <option key={item} value={item}>{item}</option>
              ))}
            </select>
            <select
              value={coverage}
              onChange={(event) => setCoverage(event.target.value)}
              aria-label="Filter by coverage"
              className="h-control rounded-md border bg-background px-3 text-body-sm outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">All coverage</option>
              <option value="with_active_listings">With active listings</option>
              <option value="without_active_listings">Without active listings</option>
              <option value="used_in_campaigns">Used in campaigns</option>
              <option value="not_used_in_campaigns">Not used in campaigns</option>
            </select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <div>
              <div className="text-card-title font-medium">Canonical products</div>
              <div className="mt-1 text-body-sm text-muted-foreground">{records.length} of {payload.records.length} products visible</div>
              </div>
            </div>
          </CardHeader>
        <CardContent>
          <DataGrid
            columns={columns}
            records={records}
            emptyTitle="No monitored products match the current filters"
            emptyDescription="Clear one or more filters and try again."
          />
        </CardContent>
      </Card>
    </div>
  );
}

export function MonitoredProductWorkspace({
  payload,
  initialTab
}: {
  payload: MonitoredProductWorkspacePayload;
  initialTab?: string;
}) {
  const product = payload.product;
  const initialSectionId = React.useMemo(() => {
    const fallback = payload.sections[0]?.id ?? "overview";
    return payload.sections.some((section) => section.id === initialTab) ? String(initialTab) : fallback;
  }, [initialTab, payload.sections]);
  const [activeSectionId, setActiveSectionId] = React.useState(initialSectionId);
  const activeSection = payload.sections.find((section) => section.id === activeSectionId) ?? payload.sections[0];
  const images = [text(product.image_url, "")].filter(Boolean);

  function selectSection(sectionId: string) {
    setActiveSectionId(sectionId);
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    url.searchParams.set("tab", sectionId);
    window.history.replaceState(null, "", url.toString());
  }

  const columns = activeSection
    ? Array.from(new Set(activeSection.records.flatMap((record) => Object.keys(record))))
        .filter((column) => !["id", "image_url", "product_url", "detail_url"].includes(column))
        .slice(0, 9)
        .map((column) => ({ id: column, header: column }))
    : [];

  const gridColumns: DataGridColumn<Record<string, unknown>>[] = [
    ...columns,
    ...(activeSection?.records.some((record) => record.detail_url)
      ? [{
          id: "detail",
          header: "",
          sortable: false,
          className: "w-16 text-right",
          cell: (record: Record<string, unknown>) =>
            record.detail_url ? (
              <Button asChild variant="outline" className="h-8 w-8 px-0" aria-label="Open product intelligence">
                <Link href={text(record.detail_url)}>
                  <Eye className="h-4 w-4" />
                </Link>
              </Button>
            ) : null,
        } satisfies DataGridColumn<Record<string, unknown>>]
      : []),
    ...(activeSection?.records.some((record) => record.product_url)
      ? [{
          id: "source",
          header: "",
          sortable: false,
          className: "w-16 text-right",
          cell: (record: Record<string, unknown>) =>
            record.product_url ? (
              <Button asChild variant="outline" className="h-8 w-8 px-0" aria-label="Open source listing">
                <a href={text(record.product_url)} target="_blank" rel="noreferrer">
                  <ExternalLink className="h-4 w-4" />
                </a>
              </Button>
            ) : null,
        } satisfies DataGridColumn<Record<string, unknown>>]
      : []),
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-5 md:flex-row md:items-start">
        <div className="min-w-0">
          <Button asChild variant="ghost" className="mb-3 px-0">
            <Link href="/operations/monitored-products">
              <ArrowLeft className="h-4 w-4" />
              Monitored Products
            </Link>
          </Button>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Badge>{text(product.status)}</Badge>
          </div>
          <h1 className="truncate text-page-title font-light">{text(product.product)}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-page-subtitle text-muted-foreground">
            <span>{text(product.brand)}</span>
            <span className="text-border-2">/</span>
            <span>{contentLabel(product)}</span>
            <ProductIdentifier value={product.gtin_norm} />
          </div>
          <div className="mt-4">
            <Button asChild variant="outline">
              <Link href={`/pricing/products/${encodeURIComponent(text(product.product_key))}`}>
                <Eye className="h-4 w-4" />
                Product intelligence
              </Link>
            </Button>
          </div>
        </div>
        <div className="flex flex-col gap-4 md:flex-row md:items-start">
          <ProductVisual hasSku={Boolean(product.gtin_norm)} images={images} size="md" />
          <div className="grid grid-cols-2 gap-2 text-body-sm">
            {Object.entries(payload.summary).map(([key, value]) => (
              <div key={key} className="rounded-md border border-border-2 px-3 py-2">
                <div className="text-section-title font-medium">{value}</div>
                <div className="text-meta capitalize text-muted-foreground">{key.replaceAll("_", " ")}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

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
            <div className="text-card-title font-medium">{activeSection.label}</div>
            <div className="mt-1 text-body-sm text-muted-foreground">{activeSection.description}</div>
          </CardHeader>
          <CardContent>
            <DataGrid
              columns={gridColumns}
              records={activeSection.records}
              emptyTitle={`No ${activeSection.label.toLowerCase()} records`}
              emptyDescription="This product has no records for this section yet."
            />
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
