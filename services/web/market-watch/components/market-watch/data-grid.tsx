"use client";

import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";

export type DataGridColumn<TRecord> = {
  id: string;
  header: string;
  cell?: (record: TRecord) => React.ReactNode;
  sortValue?: (record: TRecord) => unknown;
  sortable?: boolean;
  className?: string;
  headerClassName?: string;
};

function renderValue(value: unknown): string {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (value === null || value === undefined) return "-";
  return String(value);
}

function isNumericValue(value: unknown) {
  return typeof value === "number";
}

function compareValues(left: unknown, right: unknown) {
  if (left === right) return 0;
  if (left === null || left === undefined) return 1;
  if (right === null || right === undefined) return -1;
  if (typeof left === "number" && typeof right === "number") return left - right;

  const leftDate = typeof left === "string" ? Date.parse(left) : NaN;
  const rightDate = typeof right === "string" ? Date.parse(right) : NaN;
  if (!Number.isNaN(leftDate) && !Number.isNaN(rightDate)) return leftDate - rightDate;

  return String(left).localeCompare(String(right), "en", { numeric: true, sensitivity: "base" });
}

export function DataGrid<TRecord extends Record<string, unknown>>({
  columns,
  records,
  emptyTitle = "No records",
  emptyDescription,
  className
}: {
  columns: DataGridColumn<TRecord>[];
  records: TRecord[];
  emptyTitle?: string;
  emptyDescription?: string;
  className?: string;
}) {
  const [sort, setSort] = useState<{ id: string; direction: "asc" | "desc" } | null>(null);

  const sortedRecords = useMemo(() => {
    if (!sort) return records;
    const column = columns.find((item) => item.id === sort.id);
    if (!column) return records;
    return [...records].sort((left, right) => {
      const leftValue = column.sortValue ? column.sortValue(left) : left[column.id];
      const rightValue = column.sortValue ? column.sortValue(right) : right[column.id];
      const result = compareValues(leftValue, rightValue);
      return sort.direction === "asc" ? result : -result;
    });
  }, [columns, records, sort]);

  if (!records.length) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }

  return (
    <div className={cn("overflow-auto", className)}>
      <table className="w-full border-collapse text-sm">
        <thead className="sticky top-0 z-10 bg-card">
          <tr className="border-b text-left text-[10px] font-normal uppercase tracking-[0.07em] text-ink-muted">
            {columns.map((column) => {
              const sortable = column.sortable !== false && column.header !== "";
              const active = sort?.id === column.id;
              const Icon = active ? (sort.direction === "asc" ? ArrowUp : ArrowDown) : ChevronsUpDown;

              return (
                <th key={column.id} className={cn("whitespace-nowrap px-3 py-2 font-normal", column.headerClassName, column.className)}>
                  {sortable ? (
                    <button
                      type="button"
                      className={cn(
                        "inline-flex items-center gap-1 text-left text-inherit hover:text-foreground",
                        column.headerClassName?.includes("text-right") && "justify-end"
                      )}
                      onClick={() =>
                        setSort((current) =>
                          current?.id === column.id
                            ? { id: column.id, direction: current.direction === "asc" ? "desc" : "asc" }
                            : { id: column.id, direction: "asc" }
                        )
                      }
                    >
                      <span>{column.header}</span>
                      <Icon className="h-3.5 w-3.5" />
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sortedRecords.map((record, index) => (
            <tr key={index} className="border-b last:border-0 hover:bg-surface-2">
              {columns.map((column) => (
                <td
                  key={column.id}
                  className={cn(
                    "px-3 py-2 align-middle",
                    isNumericValue(record[column.id]) && "text-right font-mono",
                    column.className
                  )}
                >
                  {column.cell ? column.cell(record) : renderValue(record[column.id])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
