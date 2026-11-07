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

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "The fulfilment action could not be completed.";
}

export default function PartnerPage() {
  const [principal, setPrincipal] = useState<KycSessionIdentity | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [orders, setOrders] = useState<OrderSummaryData[]>([]);
  const [selected, setSelected] = useState<OrderRecordData | null>(null);
  const [transitionStatus, setTransitionStatus] = useState("");
  const [detail, setDetail] = useState("");
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
      setOrders(await udyamOneApi.listPartnerOrders());
    } catch (loadError) {
      setError(getErrorMessage(loadError));
      setOrders([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (principal?.role !== "PARTNER") return;
    const timer = window.setTimeout(() => void loadOrders(), 0);
    return () => window.clearTimeout(timer);
  }, [loadOrders, principal]);

  const openOrder = async (orderId: string) => {
    setBusy(true);
    setError(null);
    try {
      setSelected(await udyamOneApi.getPartnerOrder(orderId));
      setNotice(null);
    } catch (openError) {
      setError(getErrorMessage(openError));
    } finally {
      setBusy(false);
    }
  };

  const submitTransition = async (orderId: string) => {
    if (!transitionStatus) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const order = await udyamOneApi.transitionPartnerOrder(
        orderId,
        transitionStatus,
        undefined,
        detail.trim() || undefined,
      );
      setNotice(`Order moved to ${ORDER_STATUS_LABELS[transitionStatus as OrderStatus]}.`);
      setSelected(order);
      setTransitionStatus("");
      setDetail("");
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
          Partner fulfilment · Prototype
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-[-0.045em] sm:text-4xl">
          Assigned fulfilment work
        </h1>
        <p className="mt-4 max-w-3xl text-sm leading-6 text-[#526279]">
          Update fulfilment progress on orders currently assigned to you. This is a simulated
          prototype workflow — no real network activation or telecom provisioning is performed.
        </p>

        {!authReady ? <p className="mt-8 text-sm text-[#526279]" role="status">Checking your sign-in…</p> : null}
        {authReady && !principal ? (
          <form
            className="mt-6 grid max-w-xl gap-4 rounded-xl border border-[#dce4ec] bg-white p-5"
            onSubmit={signIn}
          >
            <h2 className="text-lg font-semibold">Sign in as a fulfilment partner</h2>
            <div>
              <label className="text-sm font-medium" htmlFor="partner-username">Username</label>
              <input
                autoComplete="username"
                className="mt-1 min-h-10 w-full rounded-md border border-[#bdc7d3] px-3 text-sm"
                id="partner-username"
                onChange={(event) => setUsername(event.target.value)}
                required
                value={username}
              />
            </div>
            <div>
              <label className="text-sm font-medium" htmlFor="partner-password">Password</label>
              <input
                autoComplete="current-password"
                className="mt-1 min-h-10 w-full rounded-md border border-[#bdc7d3] px-3 text-sm"
                id="partner-password"
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

        {principal?.role === "PARTNER" ? (
          <>
            {loading ? <p className="mt-6 text-sm text-[#526279]" role="status">Loading assigned orders…</p> : null}
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
                No orders are currently assigned to you.
              </p>
            ) : null}
            <div className="mt-4 grid gap-3">
              {orders.map((order) => (
                <article className="rounded-xl border border-[#dfe5eb] bg-white p-4" key={order.order_id}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h2 className="text-sm font-semibold">Order {order.order_id.slice(0, 8)}…</h2>
                    <StatusBadge status={order.status} />
                  </div>
                  <p className="mt-1 text-sm text-[#526279]">
                    Estimated monthly ₹{order.total_monthly_min_inr}–₹{order.total_monthly_max_inr} ·
                    updated {new Date(order.updated_at).toLocaleString()}
                  </p>
                  <button
                    className="mt-2 min-h-10 rounded-lg border border-[#bdc7d3] px-3 text-sm font-semibold text-[#31445e]"
                    onClick={() => void openOrder(order.order_id)}
                    type="button"
                  >
                    Open fulfilment
                  </button>
                </article>
              ))}
            </div>

            {selected ? (
              <section className="mt-8 rounded-xl border border-[#dce4ec] bg-white p-5" aria-labelledby="partner-detail-heading">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h2 className="text-lg font-semibold" id="partner-detail-heading">
                    Order {selected.order_id.slice(0, 8)}…
                  </h2>
                  <StatusBadge status={selected.status} />
                </div>
                <p className="mt-2 text-sm text-[#526279]">
                  {selected.current_assignment
                    ? `Assigned to you by ${selected.current_assignment.assigned_by_username}.`
                    : "No active assignment."}
                </p>

                <h3 className="mt-4 text-sm font-semibold">Fulfilment requirements</h3>
                <ul className="mt-2 list-disc pl-5 text-sm text-[#526279]">
                  <li>Confirm site details for the estimated scope in the pricing snapshot.</li>
                  <li>Advance status to <strong>Fulfilment in progress</strong>, record progress notes, and complete physical setup.</li>
                  <li>Advance status to <strong>Fulfilment completed</strong>, then hand off to <strong>Activation pending</strong>.</li>
                  <li><em>Operations-only action:</em> Final simulated activation is completed by Operations after handoff. Partners cannot activate directly.</li>
                </ul>

                <h3 className="mt-5 text-sm font-semibold">Update fulfilment progress</h3>
                <div className="mt-2 flex flex-wrap items-end gap-3">
                  <div>
                    <label className="block text-sm font-medium" htmlFor="partner-transition">Next status</label>
                    <select
                      className="mt-1 min-h-10 rounded-md border border-[#bdc7d3] bg-white px-3 text-sm"
                      id="partner-transition"
                      onChange={(event) => setTransitionStatus(event.target.value)}
                      value={transitionStatus}
                    >
                      <option value="">Select status…</option>
                      {(["FULFILMENT_IN_PROGRESS", "FULFILMENT_COMPLETED", "ACTIVATION_PENDING"] as OrderStatus[]).map(
                        (status) => (
                          <option key={status} value={status}>{ORDER_STATUS_LABELS[status]}</option>
                        ),
                      )}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium" htmlFor="partner-detail">Progress note (optional)</label>
                    <input
                      className="mt-1 min-h-10 w-72 rounded-md border border-[#bdc7d3] px-3 text-sm"
                      id="partner-detail"
                      onChange={(event) => setDetail(event.target.value)}
                      value={detail}
                    />
                  </div>
                  <button
                    className="min-h-10 rounded-lg bg-[#10223e] px-4 text-sm font-semibold text-white disabled:opacity-60"
                    disabled={busy || !transitionStatus}
                    onClick={() => void submitTransition(selected.order_id)}
                    type="button"
                  >
                    Record update
                  </button>
                </div>

                <h3 className="mt-5 text-sm font-semibold">Order pricing snapshot (estimated)</h3>
                <SnapshotTable order={selected} />

                <h3 className="mt-5 text-sm font-semibold">Fulfilment history</h3>
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
        {principal && principal.role !== "PARTNER" ? (
          <p className="mt-6 rounded-lg border border-[#efd4a1] bg-[#fff8e8] p-4 text-sm text-[#765719]">
            This workspace requires the fulfilment partner role.
          </p>
        ) : null}
      </section>
      <SiteFooter />
    </main>
  );
}
