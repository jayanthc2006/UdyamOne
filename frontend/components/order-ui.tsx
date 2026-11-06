"use client";

import {
  type OrderEventData,
  type OrderRecordData,
  type OrderStatus,
  ORDER_STATUS_LABELS,
} from "@/lib/api";

export function statusBadgeClass(status: OrderStatus): string {
  switch (status) {
    case "ACTIVATED":
      return "rounded-full bg-[#eaf5ed] px-3 py-1 text-xs font-semibold text-[#28613a]";
    case "CANCELLED":
      return "rounded-full bg-[#fff1ef] px-3 py-1 text-xs font-semibold text-[#8b2825]";
    case "ON_HOLD":
      return "rounded-full bg-[#fff4e4] px-3 py-1 text-xs font-semibold text-[#765719]";
    default:
      return "rounded-full bg-[#e8eef6] px-3 py-1 text-xs font-semibold text-[#31445e]";
  }
}

export function StatusBadge({ status }: { status: OrderStatus }) {
  return <span className={statusBadgeClass(status)}>{ORDER_STATUS_LABELS[status]}</span>;
}

export function OrderTimeline({ events }: { events: OrderEventData[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-[#526279]">No events recorded yet.</p>;
  }
  return (
    <ol className="mt-3 grid gap-3">
      {events.map((event) => (
        <li
          className="rounded-lg border border-[#dfe5eb] bg-[#fcfcfb] p-3 text-sm"
          key={event.event_id}
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-semibold text-[#10223e]">
              {ORDER_STATUS_LABELS[event.to_status as OrderStatus] ?? event.to_status}
            </span>
            <span className="text-xs text-[#526279]">
              {new Date(event.created_at).toLocaleString()}
            </span>
          </div>
          <p className="mt-1 text-[#526279]">
            {event.from_status ? `${event.from_status.replaceAll("_", " ")} → ` : ""}
            {event.to_status.replaceAll("_", " ")} · by {event.actor_username} (
            {event.actor_role.toLowerCase()})
          </p>
          {event.reason ? (
            <p className="mt-1 text-[#765719]">Reason: {event.reason}</p>
          ) : null}
          {event.detail ? <p className="mt-1 text-[#526279]">{event.detail}</p> : null}
        </li>
      ))}
    </ol>
  );
}

export function SnapshotTable({ order }: { order: OrderRecordData }) {
  const snapshot = order.snapshot;
  return (
    <div className="overflow-x-auto">
      <table className="mt-3 w-full text-sm">
        <caption className="sr-only">Immutable pricing snapshot</caption>
        <thead>
          <tr className="border-b border-[#dfe5eb] text-left text-xs uppercase tracking-wide text-[#526279]">
            <th className="py-2 pr-3">Product</th>
            <th className="py-2 pr-3">Qty</th>
            <th className="py-2 pr-3">Monthly (est.)</th>
            <th className="py-2">Setup (est.)</th>
          </tr>
        </thead>
        <tbody>
          {snapshot.line_items.map((item) => (
            <tr className="border-b border-[#eef2f6]" key={item.product_id}>
              <td className="py-2 pr-3 text-[#10223e]">{item.product_name}</td>
              <td className="py-2 pr-3 text-[#31445e]">{item.quantity}</td>
              <td className="py-2 pr-3 text-[#31445e]">
                ₹{item.monthly_subtotal_min_inr}–₹{item.monthly_subtotal_max_inr}
              </td>
              <td className="py-2 text-[#31445e]">₹{item.one_time_setup_subtotal_inr}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="text-sm font-semibold text-[#10223e]">
            <td className="py-2 pr-3">Total (estimated)</td>
            <td className="py-2 pr-3" />
            <td className="py-2 pr-3">
              ₹{snapshot.total_monthly_min_inr}–₹{snapshot.total_monthly_max_inr}
            </td>
            <td className="py-2">₹{snapshot.total_one_time_setup_inr}</td>
          </tr>
        </tfoot>
      </table>
      <p className="mt-2 text-xs text-[#526279]">
        Snapshot version {snapshot.snapshot_version} · Quote reference {snapshot.quote_id} ·
        Pricing is an estimate only, not a binding commercial offer.
      </p>
    </div>
  );
}

export const ORDER_STATUS_ORDER: OrderStatus[] = [
  "ORDER_PLACED",
  "ASSIGNED",
  "FULFILMENT_IN_PROGRESS",
  "FULFILMENT_COMPLETED",
  "ACTIVATION_PENDING",
  "ACTIVATED",
];

export function ProgressSteps({ status }: { status: OrderStatus }) {
  if (status === "CANCELLED") {
    return <p className="text-sm text-[#8b2825]">This order has been cancelled.</p>;
  }
  const activeIndex =
    status === "ON_HOLD"
      ? -1
      : ORDER_STATUS_ORDER.indexOf(status);
  return (
    <ol className="mt-3 grid gap-1 text-sm">
      {ORDER_STATUS_ORDER.map((step, index) => {
        const reached = activeIndex >= 0 && index <= activeIndex;
        const current = activeIndex === index;
        return (
          <li
            className={`flex items-center gap-2 ${current ? "font-semibold text-[#10223e]" : reached ? "text-[#31445e]" : "text-[#8a97a8]"}`}
            key={step}
          >
            <span aria-hidden="true">{current ? "●" : reached ? "○" : "·"}</span>
            {ORDER_STATUS_LABELS[step]}
            {current ? " (current)" : ""}
          </li>
        );
      })}
      {status === "ON_HOLD" ? (
        <li className="text-[#765719]">
          ● On hold — operations will resume the order when the reason is resolved.
        </li>
      ) : null}
    </ol>
  );
}
