"use client";

import { useMemo, useState } from "react";

import { Icon } from "@/components/landing";
import { AdvisorChat } from "@/components/advisor-chat";
import {
  type ApiError,
  type QuoteResponse,
  type RecommendationBundle,
  type RecommendationRequest,
  type RecommendationResponse,
  udyamOneApi,
} from "@/lib/api";

const requirementLabels: Record<string, string> = {
  connectivity: "Connectivity",
  business_communication: "Business communication",
  cloud_productivity: "Cloud and productivity",
  security_iot: "Security and IoT",
};

const formatInr = (amount: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);

function BundleCard({
  bundle,
  selected,
  onSelect,
}: {
  bundle: RecommendationBundle;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <article
      className={`rounded-2xl border bg-white p-5 transition sm:p-6 ${
        selected
          ? "border-[#d9433f] shadow-[0_14px_36px_rgba(201,56,53,0.1)]"
          : "border-[#e3e8ee]"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#c93835]">
            {bundle.bundle_type === "budget" ? "Lower monthly cost" : bundle.bundle_type === "advanced" ? "Distinct catalogue option" : "Best overall fit"}
          </p>
          <h3 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-[#10223e]">
            {bundle.display_name}
          </h3>
        </div>
        {selected ? <span className="rounded-full bg-[#fdebea] px-2.5 py-1 text-xs font-semibold text-[#b53431]">Selected</span> : null}
      </div>
      <p className="mt-3 text-sm leading-6 text-[#68768a]">{bundle.explanation}</p>
      <div className="mt-5 rounded-xl bg-[#f7f8fa] p-4">
        <p className="text-xs font-medium text-[#768296]">Estimated monthly range</p>
        <p className="mt-1 text-lg font-semibold tracking-[-0.03em] text-[#10223e]">
          {formatInr(bundle.monthly_min_inr)} – {formatInr(bundle.monthly_max_inr)}
        </p>
        <p className="mt-1 text-xs text-[#748094]">One-time setup: {formatInr(bundle.one_time_setup_inr)}</p>
      </div>
      <div className="mt-5 grid gap-3">
        {bundle.products.map((product) => (
          <div className="border-b border-[#edf0f3] pb-3 last:border-0 last:pb-0" key={product.product_id}>
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm font-semibold text-[#20334e]">{product.product_name}</p>
              {product.is_required_prerequisite ? <span className="shrink-0 rounded-full bg-[#eef3f8] px-2 py-1 text-[10px] font-semibold text-[#51647d]">Required prerequisite</span> : null}
            </div>
            <p className="mt-1 text-xs leading-5 text-[#748094]">{product.description}</p>
            <p className="mt-2 text-xs text-[#526279]">
              Qty {product.quantity} · {product.unit} · {product.min_contract_months}-month minimum contract
            </p>
            <p className="mt-2 text-xs font-medium text-[#526279]">{product.recommendation_reason}</p>
          </div>
        ))}
      </div>
      {bundle.unsupported_requirements.length || bundle.limitations.length ? (
        <div className="mt-5 rounded-lg bg-[#fff8e6] p-3 text-xs leading-5 text-[#765719]">
          {bundle.unsupported_requirements.length ? <p>Not currently covered: {bundle.unsupported_requirements.map((item) => requirementLabels[item]).join(", ")}.</p> : null}
          {bundle.limitations.map((limitation) => <p key={limitation}>{limitation}</p>)}
        </div>
      ) : null}
      <button
        className={`mt-6 inline-flex min-h-11 w-full items-center justify-center rounded-lg text-sm font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#d9433f] ${
          selected ? "bg-[#10223e] text-white hover:bg-[#193253]" : "border border-[#d8dee7] text-[#31445e] hover:bg-[#f7f9fb]"
        }`}
        onClick={onSelect}
        type="button"
      >
        {selected ? "Bundle selected" : "Select this bundle"}
      </button>
    </article>
  );
}

export function RecommendationResults({
  recommendation,
  request,
  onEdit,
  onRetry,
  retrying,
  onAdvisorUpdate,
}: {
  recommendation: RecommendationResponse;
  request: RecommendationRequest;
  onEdit: () => void;
  onRetry: () => void;
  retrying: boolean;
  onAdvisorUpdate: (
    recommendation: RecommendationResponse,
    request: RecommendationRequest,
  ) => void;
}) {
  const recommendedId = useMemo(
    () => recommendation.bundles.find((bundle) => bundle.bundle_type === "recommended")?.bundle_id ?? recommendation.bundles[0]?.bundle_id,
    [recommendation.bundles],
  );
  const [selectedBundleId, setSelectedBundleId] = useState<string | undefined>(recommendedId);
  const [showComparison, setShowComparison] = useState(false);
  const [quantities, setQuantities] = useState<Record<string, number>>(() => {
    const bundle = recommendation.bundles.find((item) => item.bundle_id === recommendedId);
    return Object.fromEntries((bundle?.products ?? []).map((product) => [product.product_id, product.quantity]));
  });
  const [quote, setQuote] = useState<QuoteResponse | null>(null);
  const [quoteError, setQuoteError] = useState<string | null>(null);
  const [quoteLoading, setQuoteLoading] = useState(false);

  const selectedBundle = recommendation.bundles.find(
    (bundle) => bundle.bundle_id === selectedBundleId,
  ) ?? recommendation.bundles.find(
    (bundle) => bundle.bundle_id === recommendedId,
  );

  const selectBundle = (bundle: RecommendationBundle) => {
    setSelectedBundleId(bundle.bundle_id);
    setQuantities(Object.fromEntries(bundle.products.map((product) => [product.product_id, product.quantity])));
    setQuote(null);
    setQuoteError(null);
  };

  const handleAdvisorUpdate = (
    nextRecommendation: RecommendationResponse,
    nextRequest: RecommendationRequest,
  ) => {
    setSelectedBundleId(
      nextRecommendation.bundles.find((bundle) => bundle.bundle_type === "recommended")?.bundle_id
        ?? nextRecommendation.bundles[0]?.bundle_id,
    );
    setQuantities(Object.fromEntries(
      (nextRecommendation.bundles.find((bundle) => bundle.bundle_type === "recommended")
        ?? nextRecommendation.bundles[0])?.products.map((product) => [product.product_id, product.quantity]) ?? [],
    ));
    setQuote(null);
    setQuoteError(null);
    onAdvisorUpdate(nextRecommendation, nextRequest);
  };

  const changeQuantity = (productId: string, currentQuantity: number, change: number) => {
    setQuantities((current) => ({
      ...current,
      [productId]: Math.max(1, (current[productId] ?? currentQuantity) + change),
    }));
    setQuote(null);
    setQuoteError(null);
  };

  const requestQuote = async () => {
    if (!selectedBundle || quoteLoading) return;
    setQuoteLoading(true);
    setQuoteError(null);
    try {
      setQuote(
        await udyamOneApi.previewQuote({
          business_profile: request.business_profile,
          selected_products: selectedBundle.products.map((product) => ({
            product_id: product.product_id,
            quantity: quantities[product.product_id] ?? 1,
          })),
        }),
      );
    } catch (error) {
      setQuoteError((error as ApiError).message);
    } finally {
      setQuoteLoading(false);
    }
  };

  if (!recommendation.bundles.length) {
    return (
      <section className="mx-auto max-w-4xl px-5 py-16 sm:px-8 lg:py-24">
        <div className="rounded-2xl border border-[#e3e8ee] bg-white p-7 text-center shadow-[0_14px_36px_rgba(16,34,62,0.06)] sm:p-10">
          <div className="mx-auto grid size-12 place-items-center rounded-full bg-[#fff4e4] text-[#a96a10]"><Icon className="size-6" name="spark" /></div>
          <h1 className="mt-5 text-2xl font-semibold tracking-[-0.035em] text-[#10223e]">No complete bundle is available yet.</h1>
          <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-[#68768a]">The current catalogue cannot form a complete eligible option for this profile. You can adjust your business details and try again.</p>
          {recommendation.limitations.map((limitation) => <p className="mt-2 text-xs text-[#94661a]" key={limitation}>{limitation}</p>)}
          <div className="mt-8 text-left">
            <AdvisorChat onRecommendationUpdate={handleAdvisorUpdate} recommendation={recommendation} request={request} />
          </div>
          <div className="mt-7 flex flex-col justify-center gap-3 sm:flex-row">
            <button className="rounded-lg bg-[#10223e] px-5 py-3 text-sm font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#c93835]" onClick={onEdit} type="button">Edit business profile</button>
            <button className="rounded-lg border border-[#d8dee7] px-5 py-3 text-sm font-semibold text-[#34465f] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#c93835]" disabled={retrying} onClick={onRetry} type="button">{retrying ? "Trying again…" : "Retry"}</button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <main className="min-h-screen bg-[#fcfcfb] text-[#10223e]">
      <section className="border-b border-[#e7ebf0] bg-[#f5f1ee]">
        <div className="mx-auto max-w-7xl px-5 py-12 sm:px-8 lg:px-10">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#c93835]">Your solution options</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-[-0.05em] sm:text-4xl">Catalogue-backed choices for your business.</h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-[#657287]">Every option is based on the current product catalogue, your profile and the availability rules checked by UdyamOne.</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <button aria-pressed={!showComparison} className={`rounded-lg px-4 py-2 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#c93835] ${!showComparison ? "bg-[#10223e] text-white" : "border border-[#d8dee7] bg-white text-[#40536b]"}`} onClick={() => setShowComparison(false)} type="button">Bundle options</button>
            <button aria-pressed={showComparison} className={`rounded-lg px-4 py-2 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#c93835] ${showComparison ? "bg-[#10223e] text-white" : "border border-[#d8dee7] bg-white text-[#40536b]"}`} onClick={() => setShowComparison(true)} type="button">Compare bundles</button>
            <button className="rounded-lg px-4 py-2 text-sm font-semibold text-[#c93835] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#c93835]" onClick={onEdit} type="button">Edit business profile</button>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-10 sm:px-8 lg:px-10 lg:py-14">
        <AdvisorChat onRecommendationUpdate={handleAdvisorUpdate} recommendation={recommendation} request={request} />
        {recommendation.unsupported_requirements.length ? <div className="mb-7 rounded-xl border border-[#f1dfbc] bg-[#fff8e8] p-4 text-sm leading-6 text-[#705116]">Some requested needs are not covered by an eligible current catalogue product: {recommendation.unsupported_requirements.map((item) => requirementLabels[item]).join(", ")}.</div> : null}
        {recommendation.limitations.map((limitation) => <p className="mb-3 text-sm text-[#7a662d]" key={limitation}>{limitation}</p>)}

        {showComparison ? (
          <div className="overflow-x-auto rounded-2xl border border-[#e3e8ee] bg-white">
            <table className="min-w-[720px] w-full text-left text-sm">
              <thead className="bg-[#f7f8fa] text-xs uppercase tracking-[0.1em] text-[#7b8797]"><tr><th className="px-5 py-4">Bundle</th><th className="px-5 py-4">Products</th><th className="px-5 py-4">Monthly</th><th className="px-5 py-4">One-time</th><th className="px-5 py-4">Action</th></tr></thead>
              <tbody>{recommendation.bundles.map((bundle) => <tr className="border-t border-[#edf0f3]" key={bundle.bundle_id}><td className="px-5 py-5 font-semibold text-[#243852]">{bundle.display_name}</td><td className="px-5 py-5 text-[#647287]">{bundle.products.map((product) => product.product_name).join(", ")}</td><td className="px-5 py-5 font-medium text-[#243852]">{formatInr(bundle.monthly_min_inr)} – {formatInr(bundle.monthly_max_inr)}</td><td className="px-5 py-5 text-[#647287]">{formatInr(bundle.one_time_setup_inr)}</td><td className="px-5 py-5"><button className="font-semibold text-[#c93835] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#c93835]" onClick={() => { selectBundle(bundle); setShowComparison(false); }} type="button">Select</button></td></tr>)}</tbody>
            </table>
          </div>
        ) : <div className="grid gap-5 lg:grid-cols-3">{recommendation.bundles.map((bundle) => <BundleCard bundle={bundle} key={bundle.bundle_id} onSelect={() => selectBundle(bundle)} selected={bundle.bundle_id === selectedBundleId} />)}</div>}

        {selectedBundle ? <section className="mt-10 grid gap-7 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="rounded-2xl border border-[#e3e8ee] bg-white p-5 sm:p-7">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#c93835]">Selected bundle</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-[-0.04em]">{selectedBundle.display_name}</h2>
            <p className="mt-2 text-sm leading-6 text-[#68768a]">Adjust quantity if needed. UdyamOne will ask the backend for an updated quote before showing final totals.</p>
            <div className="mt-6 grid gap-4">{selectedBundle.products.map((product) => { const quantity = quantities[product.product_id] ?? product.quantity; return <div className="rounded-xl border border-[#e7ebf0] p-4" key={product.product_id}><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center"><div><div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold text-[#233650]">{product.product_name}</h3>{product.is_required_prerequisite ? <span className="rounded-full bg-[#eef3f8] px-2 py-1 text-[10px] font-semibold text-[#53657e]">Required</span> : null}</div><p className="mt-1 text-xs text-[#748094]">{product.unit} · {product.min_contract_months}-month minimum contract</p></div><div className="flex items-center gap-3"><button aria-label={`Reduce ${product.product_name} quantity`} className="grid size-8 place-items-center rounded-md border border-[#dce2e9] text-lg text-[#40536b]" onClick={() => changeQuantity(product.product_id, quantity, -1)} type="button">−</button><span className="min-w-5 text-center text-sm font-semibold">{quantity}</span><button aria-label={`Increase ${product.product_name} quantity`} className="grid size-8 place-items-center rounded-md border border-[#dce2e9] text-lg text-[#40536b]" onClick={() => changeQuantity(product.product_id, quantity, 1)} type="button">+</button></div></div></div>; })}</div>
          </div>
          <div className="rounded-2xl bg-[#10223e] p-5 text-white sm:p-7">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#f19d99]">Live quote preview</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-[-0.04em]">Confirm your current quantities.</h2>
            <p className="mt-3 text-sm leading-6 text-[#c5ceda]">Quote totals are calculated by the UdyamOne backend after it rechecks product eligibility and prerequisites.</p>
            <button className="mt-7 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#d9433f] px-5 text-sm font-semibold text-white transition hover:bg-[#ef514c] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white disabled:cursor-not-allowed disabled:opacity-60" disabled={quoteLoading} onClick={() => void requestQuote()} type="button">{quoteLoading ? "Getting your quote…" : "Get accurate quote"}<Icon className="size-4" name="arrow" /></button>
            {quoteError ? <div className="mt-5 rounded-lg bg-white/10 p-4 text-sm leading-6 text-[#ffd5d2]">{quoteError}<button className="ml-2 font-semibold text-white underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white" onClick={() => void requestQuote()} type="button">Retry</button></div> : null}
            {quote ? <div className="mt-6 rounded-xl bg-white p-5 text-[#10223e]"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#c93835]">Authoritative backend quote</p><p className="mt-3 text-sm text-[#68768a]">Monthly range</p><p className="text-xl font-semibold">{formatInr(quote.total_monthly_min_inr)} – {formatInr(quote.total_monthly_max_inr)}</p><p className="mt-3 text-sm text-[#68768a]">One-time setup</p><p className="text-lg font-semibold">{formatInr(quote.total_one_time_setup_inr)}</p><div className="mt-5 grid gap-2 border-t border-[#e9edf1] pt-4">{quote.line_items.map((line) => <p className="text-xs text-[#647287]" key={line.product_id}>{line.product_name} · Qty {line.quantity} · {line.min_contract_months}-month minimum</p>)}</div><p className="mt-5 text-xs leading-5 text-[#8a6a2b]">Prototype pricing only. Final availability, taxes and commercial terms are confirmed during onboarding.</p></div> : null}
          </div>
        </section> : null}
      </section>
    </main>
  );
}
