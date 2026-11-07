"use client";

import { useCallback, useEffect, useState } from "react";

import { SiteFooter, SiteHeader } from "@/components/landing";
import {
  type KycSessionIdentity,
  type OrderRecordData,
  type OrderStatus,
  type OrderSummaryData,
  KYC_SESSION_KEY,
  ORDER_STATUS_LABELS,
  udyamOneApi,
} from "@/lib/api";
import { OrderTimeline, SnapshotTable, StatusBadge } from "@/components/order-ui";

const STATUS_FILTERS: Array<{ value: string; label: string }> = [
  { value: "", label: "All statuses" },
  ...(Object.keys(ORDER_STATUS_LABELS) as OrderStatus[]).map((status) => ({
    value: status,
    label: ORDER_STATUS_LABELS[status],
  })),
];

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "The operations action could not be completed.";
}

export default function OperationsPage() {
  const [principal, setPrincipal] = useState<KycSessionIdentity | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [orders, setOrders] = useState<OrderSummaryData[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<OrderRecordData | null>(null);
  const [partnerUsername, setPartnerUsername] = useState("");
  const [assignReason, setAssignReason] = useState("");
  const [transitionStatus, setTransitionStatus] = useState("");
  const [transitionReason, setTransitionReason] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const signIn = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const session = await udyamOneApi.createKycSession(username.trim(), password);
      window.sessionStorage.setItem(KYC_SESSION_KEY, session.access_token);
      setPrincipal({
        username: session.username,
        role: session.role,
        expires_at: session.expires_at,
      });
      setPassword("");
    } catch (loginError) {
      setError(getErrorMessage(loginError));
    } finally {
      setBusy(false);
    }
  };

  const signOut = () => {
    window.sessionStorage.removeItem(KYC_SESSION_KEY);
    setPrincipal(null);
    setOrders([]);
    setSelected(null);
  };

  useEffect(() => {
    let active = true;
    const token = window.sessionStorage.getItem(KYC_SESSION_KEY);
    if (!token) {
      const timer = window.setTimeout(() => {
        if (active) setAuthReady(true);
      }, 0);
      return () => {
        active = false;
        window.clearTimeout(timer);
      };
    }
    udyamOneApi
      .getKycSession(token)
      .then((session) => {
        if (active) setPrincipal(session);
      })
      .catch(() => {
        window.sessionStorage.removeItem(KYC_SESSION_KEY);
      })
      .finally(() => {
        if (active) setAuthReady(true);
      });
    return () => {
      active = false;
    };
  }, []);

  const loadOrders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setOrders(await udyamOneApi.listOperationsOrders(statusFilter || undefined, search.trim() || undefined));
    } catch (loadError) {
      setError(getErrorMessage(loadError));
      setOrders([]);
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter]);

  useEffect(() => {
    if (principal?.role !== "OPERATIONS") return;
    const timer = window.setTimeout(() => void loadOrders(), 0);
    return () => window.clearTimeout(timer);
  }, [loadOrders, principal]);

  const openOrder = async (orderId: string) => {
    setBusy(true);
    setError(null);
    try {
      setSelected(await udyamOneApi.getOperationsOrder(orderId));
      setNotice(null);
    } catch (openError) {
      setError(getErrorMessage(openError));
    } finally {
      setBusy(false);
    }
  };

  const assign = async (orderId: string) => {
    if (!partnerUsername.trim()) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const order = await udyamOneApi.assignOrderPartner(
        orderId,
        partnerUsername.trim(),
        assignReason.trim() || undefined,
      );
      setNotice(`Partner ${partnerUsername.trim()} assigned to order ${order.order_id.slice(0, 8)}…`);
      setSelected(order);
      await loadOrders();
    } catch (assignError) {
      setError(getErrorMessage(assignError));
    } finally {
      setBusy(false);
    }
  };

  const transition = async (orderId: string) => {
    if (!transitionStatus) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const order = await udyamOneApi.transitionOperationsOrder(
        orderId,
        transitionStatus,
        transitionReason.trim() || undefined,
      );
      setNotice(`Order moved to ${ORDER_STATUS_LABELS[transitionStatus as OrderStatus]}.`);
      setSelected(order);
      setTransitionStatus("");
      setTransitionReason("");
      await loadOrders();
    } catch (transitionError) {
      setError(getErrorMessage(transitionError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#fcfcfb] text-[#10223e]">
      <SiteHeader />
      <section className="mx-auto max-w-5xl px-5 py-10 sm:px-8 lg:py-16">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#c93835]">
          Operations · Prototype
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-[-0.045em] sm:text-4xl">
          Order operations dashboard
        </h1>
        <p className="mt-4 max-w-3xl text-sm leading-6 text-[#526279]">
          Manage confirmed prototype order requests: assign fulfilment partners, monitor progress and
          perform permitted lifecycle transitions.
        </p>

        {!authReady ? <p className="mt-8 text-sm text-[#526279]" role="status">Checking your sign-in…</p> : null}
        {authReady && !principal ? (
          <form
            className="mt-6 grid max-w-xl gap-4 rounded-xl border border-[#dce4ec] bg-white p-5"
            onSubmit={signIn}
          >
            <h2 className="text-lg font-semibold">Sign in to operations</h2>
            <p className="text-sm text-[#526279]">Only OPERATIONS accounts can use this dashboard.</p>
            <div>
              <label className="text-sm font-medium" htmlFor="ops-username">Username</label>
              <input
                autoComplete="username"
                className="mt-1 min-h-10 w-full rounded-md border border-[#bdc7d3] px-3 text-sm"
                id="ops-username"
                onChange={(event) => setUsername(event.target.value)}
                required
                value={username}
              />
            </div>
            <div>
              <label className="text-sm font-medium" htmlFor="ops-password">Password</label>
              <input
                autoComplete="current-password"
                className="mt-1 min-h-10 w-full rounded-md border border-[#bdc7d3] px-3 text-sm"
                id="ops-password"
                onChange={(event) => setPassword(event.target.value)}
                required
                type="password"
                value={password}
              />
            </div>
            <button
              className="min-h-11 rounded-lg bg-[#10223e] px-5 text-sm font-semibold text-white"
              disabled={busy}
              type="submit"
            >
              Sign in
            </button>
          </form>
        ) : null}

        {principal ? (
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#dce4ec] bg-white p-4">
            <p className="text-sm text-[#31445e]">
              Signed in as <strong>{principal.username}</strong> · {principal.role.toLowerCase()}
            </p>
            <button
              className="min-h-10 rounded-lg border border-[#bdc7d3] px-3 text-sm font-semibold text-[#31445e]"
              onClick={signOut}
              type="button"
            >
              Sign out
            </button>
          </div>
        ) : null}

        {principal?.role === "OPERATIONS" ? (
          <>
            <div className="mt-6 flex flex-wrap items-end gap-3 rounded-xl border border-[#dce4ec] bg-white p-4">
              <div>
                <label className="block text-sm font-medium" htmlFor="ops-status-filter">Status filter</label>
                <select
                  className="mt-1 min-h-10 rounded-md border border-[#bdc7d3] bg-white px-3 text-sm"
                  id="ops-status-filter"
                  onChange={(event) => setStatusFilter(event.target.value)}
                  value={statusFilter}
                >
                  {STATUS_FILTERS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium" htmlFor="ops-search">Search</label>
                <input
                  className="mt-1 min-h-10 w-64 rounded-md border border-[#bdc7d3] px-3 text-sm"
                  id="ops-search"
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Order or applicant ID"
                  value={search}
                />
              </div>
              <button
                className="min-h-10 rounded-lg bg-[#10223e] px-4 text-sm font-semibold text-white"
                onClick={() => void loadOrders()}
                type="button"
              >
                Apply filters
              </button>
            </div>

            {loading ? <p className="mt-4 text-sm text-[#526279]" role="status">Loading orders…</p> : null}
            {error ? (
              <div className="mt-4 rounded-lg border border-[#e4b7b4] bg-[#fff1ef] p-4 text-sm text-[#8b2825]" role="alert">
                {error}
              </div>
            ) : null}
            {notice ? (
              <div className="mt-4 rounded-lg border border-[#b9d8c1] bg-[#eff8f1] p-4 text-sm text-[#245b35]" role="status">
                {notice}
              </div>
            ) : null}

            {orders.length === 0 && !loading ? (
              <p className="mt-4 rounded-lg border border-[#dfe5eb] bg-white p-4 text-sm text-[#526279]">
                No orders match the current filters.
              </p>
            ) : null}
            <div className="mt-4 grid gap-3">
              {orders.map((order) => (
                <article className="rounded-xl border border-[#dfe5eb] bg-white p-4" key={order.order_id}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h2 className="text-sm font-semibold">
                      {order.order_id.slice(0, 8)}… · applicant {order.applicant_id}
                    </h2>
                    <StatusBadge status={order.status} />
                  </div>
                  <p className="mt-1 text-sm text-[#526279]">
                    Placed {new Date(order.created_at).toLocaleString()} · Estimated monthly
                    ₹{order.total_monthly_min_inr}–₹{order.total_monthly_max_inr}
                    {order.partner_username ? ` · Partner: ${order.partner_username}` : " · Unassigned"}
                  </p>
                  <button
                    className="mt-2 min-h-10 rounded-lg border border-[#bdc7d3] px-3 text-sm font-semibold text-[#31445e]"
                    onClick={() => void openOrder(order.order_id)}
                    type="button"
                  >
                    Manage order
                  </button>
                </article>
              ))}
            </div>

            {selected ? (
              <section className="mt-8 rounded-xl border border-[#dce4ec] bg-white p-5" aria-labelledby="ops-detail-heading">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h2 className="text-lg font-semibold" id="ops-detail-heading">
                    Order {selected.order_id.slice(0, 8)}… · applicant {selected.applicant_id}
                  </h2>
                  <StatusBadge status={selected.status} />
                </div>

                <h3 className="mt-4 text-sm font-semibold">Partner assignment</h3>
                <div className="mt-2 flex flex-wrap items-end gap-3">
                  <div>
                    <label className="block text-sm font-medium" htmlFor="ops-partner">Partner username</label>
                    <input
                      className="mt-1 min-h-10 w-56 rounded-md border border-[#bdc7d3] px-3 text-sm"
                      id="ops-partner"
                      onChange={(event) => setPartnerUsername(event.target.value)}
                      value={partnerUsername}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium" htmlFor="ops-assign-reason">Reason (optional)</label>
                    <input
                      className="mt-1 min-h-10 w-64 rounded-md border border-[#bdc7d3] px-3 text-sm"
                      id="ops-assign-reason"
                      onChange={(event) => setAssignReason(event.target.value)}
                      value={assignReason}
                    />
                  </div>
                  <button
                    className="min-h-10 rounded-lg bg-[#10223e] px-4 text-sm font-semibold text-white disabled:opacity-60"
                    disabled={busy || !partnerUsername.trim() || ["CANCELLED", "ACTIVATED"].includes(selected.status)}
                    onClick={() => void assign(selected.order_id)}
                    type="button"
                  >
                    {selected.current_assignment ? "Reassign partner" : "Assign partner"}
                  </button>
                </div>

                <h3 className="mt-5 text-sm font-semibold">Lifecycle transition</h3>
                <p className="mt-1 text-xs text-[#526279]">
                  Permitted transitions for operations: assign partner (moves ORDER_PLACED to ASSIGNED), put order ON_HOLD, resume permitted status from ON_HOLD, advance to ACTIVATED once fulfilment is completed/pending, or cancel.
                </p>
                <div className="mt-2 flex flex-wrap items-end gap-3">
                  <div>
                    <label className="block text-sm font-medium" htmlFor="ops-transition">New status</label>
                    <select
                      className="mt-1 min-h-10 rounded-md border border-[#bdc7d3] bg-white px-3 text-sm"
                      id="ops-transition"
                      onChange={(event) => setTransitionStatus(event.target.value)}
                      value={transitionStatus}
                    >
                      <option value="">Select status…</option>
                      {STATUS_FILTERS.filter((option) => option.value).map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium" htmlFor="ops-transition-reason">Reason</label>
                    <input
                      className="mt-1 min-h-10 w-64 rounded-md border border-[#bdc7d3] px-3 text-sm"
                      id="ops-transition-reason"
                      onChange={(event) => setTransitionReason(event.target.value)}
                      value={transitionReason}
                    />
                  </div>
                  <button
                    className="min-h-10 rounded-lg bg-[#10223e] px-4 text-sm font-semibold text-white disabled:opacity-60"
                    disabled={busy || !transitionStatus}
                    onClick={() => void transition(selected.order_id)}
                    type="button"
                  >
                    Apply transition
                  </button>
                </div>

                <h3 className="mt-5 text-sm font-semibold">Current assignment</h3>
                <p className="mt-1 text-sm text-[#526279]">
                  {selected.current_assignment
                    ? `${selected.current_assignment.partner_username}, assigned by ${selected.current_assignment.assigned_by_username} at ${new Date(selected.current_assignment.assigned_at).toLocaleString()}`
                    : "No partner assigned yet."}
                </p>

                <h3 className="mt-5 text-sm font-semibold">Confirmed pricing snapshot (estimated)</h3>
                <SnapshotTable order={selected} />

                <h3 className="mt-5 text-sm font-semibold">Order history</h3>
                <OrderTimeline events={selected.events} />

                <button
                  className="mt-4 min-h-10 rounded-lg border border-[#bdc7d3] px-3 text-sm font-semibold text-[#31445e]"
                  onClick={() => setSelected(null)}
                  type="button"
                >
                  Close details
                </button>
              </section>
            ) : null}
          </>
        ) : null}
        {principal && principal.role !== "OPERATIONS" ? (
          <p className="mt-6 rounded-lg border border-[#efd4a1] bg-[#fff8e8] p-4 text-sm text-[#765719]">
            This dashboard requires the operations role.
          </p>
        ) : null}
      </section>
      <SiteFooter />
    </main>
  );
}
