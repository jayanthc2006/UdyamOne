"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { SiteFooter, SiteHeader } from "@/components/landing";
import { getCurrentApplicantId } from "@/lib/applicant-session";
import {
  type OrderRecordData,
  type OrderSummaryData,
  type KycSessionIdentity,
  KYC_SESSION_KEY,
  ORDER_STATUS_LABELS,
  udyamOneApi,
} from "@/lib/api";
import { OrderTimeline, ProgressSteps, SnapshotTable, StatusBadge } from "@/components/order-ui";

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "The order action could not be completed.";
}

export default function OrdersPage() {
  const [principal, setPrincipal] = useState<KycSessionIdentity | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [applicantId, setApplicantId] = useState<string | null>(null);
  const [orders, setOrders] = useState<OrderSummaryData[] | null>(null);
  const [selected, setSelected] = useState<OrderRecordData | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmChecked, setConfirmChecked] = useState(false);
  const [orderPlaced, setOrderPlaced] = useState(false);

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
    setOrders(null);
    setSelected(null);
  };

  useEffect(() => {
    const timer = window.setTimeout(() => setApplicantId(getCurrentApplicantId()), 0);
    return () => window.clearTimeout(timer);
  }, []);

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

  const loadOrders = useCallback(async (applicant: string) => {
    setLoading(true);
    setError(null);
    try {
      setOrders(await udyamOneApi.getApplicantOrders(applicant));
    } catch (loadError) {
      setError(getErrorMessage(loadError));
      setOrders([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (principal?.role !== "CUSTOMER" || !applicantId) return;
    const timer = window.setTimeout(() => void loadOrders(applicantId), 0);
    return () => window.clearTimeout(timer);
  }, [applicantId, loadOrders, principal]);

  const openOrder = async (orderId: string) => {
    setBusy(true);
    setError(null);
    try {
      setSelected(await udyamOneApi.getOrder(orderId));
    } catch (openError) {
      setError(getErrorMessage(openError));
    } finally {
      setBusy(false);
    }
  };

  const placeOrder = async () => {
    if (!applicantId) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const order = await udyamOneApi.placeOrder(applicantId, true);
      setNotice(`Order ${order.order_id} placed. Operations will assign a partner next.`);
      setConfirmChecked(false);
      setOrderPlaced(true);
      await loadOrders(applicantId);
      setSelected(order);
    } catch (placeError) {
      setError(getErrorMessage(placeError));
    } finally {
      setBusy(false);
    }
  };

  const cancelOrder = async (orderId: string) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await udyamOneApi.cancelOrder(orderId);
      setNotice("Order cancelled.");
      setSelected(null);
      if (applicantId) await loadOrders(applicantId);
    } catch (cancelError) {
      setError(getErrorMessage(cancelError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#fcfcfb] text-[#10223e]">
      <SiteHeader />
      <section className="mx-auto max-w-5xl px-5 py-10 sm:px-8 lg:py-16">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#c93835]">
          Orders · Prototype
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-[-0.045em] sm:text-4xl">
          Your order tracking
        </h1>
        <p className="mt-4 max-w-3xl text-sm leading-6 text-[#526279]">
          Orders are confirmed prototype order requests created from your latest estimated quote.
          Pricing is estimated only and is not a binding commercial offer.
        </p>

        {!authReady ? <p className="mt-8 text-sm text-[#526279]" role="status">Checking your sign-in…</p> : null}
        {authReady && !principal ? (
          <form
            className="mt-6 grid max-w-xl gap-4 rounded-xl border border-[#dce4ec] bg-white p-5"
            onSubmit={signIn}
          >
            <h2 className="text-lg font-semibold">Sign in to view your orders</h2>
            <div>
              <label className="text-sm font-medium" htmlFor="orders-username">Username</label>
              <input
                autoComplete="username"
                className="mt-1 min-h-10 w-full rounded-md border border-[#bdc7d3] px-3 text-sm"
                id="orders-username"
                onChange={(event) => setUsername(event.target.value)}
                required
                value={username}
              />
            </div>
            <div>
              <label className="text-sm font-medium" htmlFor="orders-password">Password</label>
              <input
                autoComplete="current-password"
                className="mt-1 min-h-10 w-full rounded-md border border-[#bdc7d3] px-3 text-sm"
                id="orders-password"
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

        {error ? (
          <div className="mt-6 rounded-lg border border-[#e4b7b4] bg-[#fff1ef] p-4 text-sm text-[#8b2825]" role="alert">
            {error}
          </div>
        ) : null}
        {notice ? (
          <div className="mt-6 rounded-lg border border-[#b9d8c1] bg-[#eff8f1] p-4 text-sm text-[#245b35]" role="status">
            {notice}
          </div>
        ) : null}

        {principal?.role === "CUSTOMER" ? (
          applicantId ? (
            <>
              <section className="mt-6 rounded-xl border border-[#dce4ec] bg-white p-5" aria-labelledby="place-order-heading">
                <h2 className="text-base font-semibold" id="place-order-heading">Place an order from your latest quote</h2>
                {orderPlaced ? (
                  <Link
                    className="mt-2 inline-flex min-h-10 items-center rounded-lg bg-[#10223e] px-4 text-sm font-semibold text-white"
                    href="/orders"
                  >
                    View My Orders
                  </Link>
                ) : null}
                <p className="mt-1 text-sm leading-6 text-[#526279]">
                  This converts your latest persisted quote into a prototype order request. The quote
                  pricing is estimated and is snapshotted immutably with the order.
                </p>
                <label className="mt-3 flex items-start gap-2 text-sm leading-6">
                  <input
                    checked={confirmChecked}
                    onChange={(event) => setConfirmChecked(event.target.checked)}
                    type="checkbox"
                  />
                  <span>
                    I confirm I want to place this prototype order request. I understand pricing is
                    estimated only and this is not a binding commercial offer or contract.
                  </span>
                </label>
                <button
                  className="mt-3 min-h-10 rounded-lg bg-[#10223e] px-4 text-sm font-semibold text-white disabled:opacity-60"
                  disabled={busy || !confirmChecked}
                  onClick={placeOrder}
                  type="button"
                >
                  Confirm and place order
                </button>
              </section>

              <h2 className="mt-8 text-lg font-semibold">Your orders</h2>
              {loading ? <p className="mt-3 text-sm text-[#526279]" role="status">Loading orders…</p> : null}
              {orders && orders.length === 0 && !loading ? (
                <p className="mt-3 rounded-lg border border-[#dfe5eb] bg-white p-4 text-sm text-[#526279]">
                  You have no orders yet. Generate a quote from your recommendations, then place an
                  order above.
                </p>
              ) : null}
              <div className="mt-3 grid gap-3">
                {(orders ?? []).map((order) => (
                  <article className="rounded-xl border border-[#dfe5eb] bg-white p-4" key={order.order_id}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h3 className="text-sm font-semibold">
                        Order {order.order_id.slice(0, 8)}… · {ORDER_STATUS_LABELS[order.status]}
                      </h3>
                      <StatusBadge status={order.status} />
                    </div>
                    <p className="mt-1 text-sm text-[#526279]">
                      Estimated monthly ₹{order.total_monthly_min_inr}–₹{order.total_monthly_max_inr} ·
                      setup ₹{order.total_one_time_setup_inr}
                      {order.partner_username ? ` · Partner: ${order.partner_username}` : ""}
                    </p>
                    <button
                      className="mt-2 min-h-10 rounded-lg border border-[#bdc7d3] px-3 text-sm font-semibold text-[#31445e]"
                      onClick={() => void openOrder(order.order_id)}
                      type="button"
                    >
                      View details and timeline
                    </button>
                  </article>
                ))}
              </div>
            </>
          ) : (
            <p className="mt-6 rounded-lg border border-[#dfe5eb] bg-white p-4 text-sm text-[#526279]">
              No applicant profile is open in this browser. Start or open a profile from the
              onboarding flow first.
            </p>
          )
        ) : null}
        {principal && principal.role !== "CUSTOMER" ? (
          <p className="mt-6 rounded-lg border border-[#efd4a1] bg-[#fff8e8] p-4 text-sm text-[#765719]">
            This page is for customer order tracking. Use the operations or partner workspaces for
            your role.
          </p>
        ) : null}

        {selected ? (
          <section className="mt-8 rounded-xl border border-[#dce4ec] bg-white p-5" aria-labelledby="order-detail-heading">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold" id="order-detail-heading">
                Order {selected.order_id.slice(0, 8)}…
              </h2>
              <StatusBadge status={selected.status} />
            </div>
            <p className="mt-2 text-sm text-[#526279]">Applicant {selected.applicant_id}</p>
            <h3 className="mt-4 text-sm font-semibold">What happens next</h3>
            <ProgressSteps status={selected.status} />
            <h3 className="mt-4 text-sm font-semibold">Confirmed pricing snapshot (estimated)</h3>
            <SnapshotTable order={selected} />
            <h3 className="mt-4 text-sm font-semibold">Order timeline</h3>
            <OrderTimeline events={selected.events} />
            {selected.current_assignment ? (
              <p className="mt-3 text-sm text-[#526279]">
                Fulfilment partner: {selected.current_assignment.partner_username} · assigned{" "}
                {new Date(selected.current_assignment.assigned_at).toLocaleString()}
              </p>
            ) : null}
            {["ORDER_PLACED", "ASSIGNED", "ON_HOLD"].includes(selected.status) ? (
              <button
                className="mt-4 min-h-10 rounded-lg border border-[#e4b7b4] bg-[#fff1ef] px-3 text-sm font-semibold text-[#8b2825] disabled:opacity-60"
                disabled={busy}
                onClick={() => void cancelOrder(selected.order_id)}
                type="button"
              >
                Cancel this order
              </button>
            ) : null}
            <button
              className="mt-4 block min-h-10 rounded-lg border border-[#bdc7d3] px-3 text-sm font-semibold text-[#31445e]"
              onClick={() => setSelected(null)}
              type="button"
            >
              Close details
            </button>
          </section>
        ) : null}
      </section>
      <SiteFooter />
    </main>
  );
}
