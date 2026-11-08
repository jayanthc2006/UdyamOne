"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  type KycSessionIdentity,
  KYC_SESSION_KEY,
  udyamOneApi,
} from "@/lib/api";

type IconName =
  | "arrow"
  | "check"
  | "cloud"
  | "communication"
  | "connectivity"
  | "document"
  | "lock"
  | "security"
  | "spark";

type IconProps = {
  name: IconName;
  className?: string;
};

const iconPaths: Record<IconName, ReactNode> = {
  arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
  check: <path d="m5 12 4 4L19 6" />,
  cloud: <path d="M7.5 18h9.75a4.75 4.75 0 0 0 .75-9.44A6.5 6.5 0 0 0 5.6 9.6 4.2 4.2 0 0 0 7.5 18Z" />,
  communication: (
    <>
      <path d="M20 11.5a7.5 7.5 0 0 1-8 7.48 8.7 8.7 0 0 1-3.2-.64L4 20l1.58-4.13A7.34 7.34 0 0 1 4 11.5a7.5 7.5 0 0 1 8-7.48A7.5 7.5 0 0 1 20 11.5Z" />
      <path d="M8.5 11.5h7M8.5 8.5h4.5" />
    </>
  ),
  connectivity: (
    <>
      <path d="M4 10.5a11.5 11.5 0 0 1 16 0M7 13.5a7 7 0 0 1 10 0M10 16.5a2.8 2.8 0 0 1 4 0" />
      <path d="M12 20h.01" />
    </>
  ),
  document: (
    <>
      <path d="M7 3h7l4 4v14H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
      <path d="M14 3v5h5M9 13h6M9 17h6" />
    </>
  ),
  lock: (
    <>
      <rect x="5" y="10" width="14" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3" />
    </>
  ),
  security: (
    <>
      <path d="M12 3 4.5 6v5.3c0 4.6 3.1 7.7 7.5 9.7 4.4-2 7.5-5.1 7.5-9.7V6L12 3Z" />
      <path d="m9 12 2 2 4-4" />
    </>
  ),
  spark: <path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3Z" />,
};

export function Icon({ name, className = "" }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
    >
      {iconPaths[name]}
    </svg>
  );
}

export function Wordmark({
  inverted = false,
  href = "/",
}: {
  inverted?: boolean;
  href?: string;
}) {
  return (
    <Link
      aria-label="UdyamOne home"
      className={`inline-flex items-center gap-2.5 font-semibold tracking-[-0.04em] ${
        inverted ? "text-white" : "text-[#10223e]"
      }`}
      href={href}
    >
      <span className="grid size-8 place-items-center rounded-[10px] bg-[#d9433f] text-sm font-bold text-white shadow-sm">
        U
      </span>
      <span className="text-[1.28rem]">UdyamOne</span>
    </Link>
  );
}

export function SiteHeader() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [principal, setPrincipal] = useState<KycSessionIdentity | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const pathname = usePathname();

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

  useEffect(() => {
    if (!authReady) return;
    const onStorage = (event: StorageEvent) => {
      if (event.key === KYC_SESSION_KEY || event.key === null) {
        const token = window.sessionStorage.getItem(KYC_SESSION_KEY);
        setPrincipal(null);
        if (token) {
          udyamOneApi
            .getKycSession(token)
            .then((session) => setPrincipal(session))
            .catch(() => window.sessionStorage.removeItem(KYC_SESSION_KEY));
        }
      }
    };
    window.addEventListener("storage", onStorage);
    // Re-check quickly so login/logout in the same tab updates the header
    // without a manual refresh. Only performs a network call when the stored
    // token presence differs from the rendered state.
    const pollTimer = window.setInterval(() => {
      const token = window.sessionStorage.getItem(KYC_SESSION_KEY);
      if (!token && principal) {
        setPrincipal(null);
      } else if (token && !principal) {
        udyamOneApi
          .getKycSession(token)
          .then((session) => setPrincipal(session))
          .catch(() => {
            window.sessionStorage.removeItem(KYC_SESSION_KEY);
            setPrincipal(null);
          });
      }
    }, 500);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.clearInterval(pollTimer);
    };
  }, [authReady, principal]);

  useEffect(() => {
    if (!isMobileMenuOpen) return;

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsMobileMenuOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [isMobileMenuOpen]);

  const closeMobileMenu = () => setIsMobileMenuOpen(false);

  // Public sign-in dropdown (logged-out visitors only): navigation entry
  // points to the existing per-workspace sign-in forms. Selecting an option is
  // navigation only — the actual role is determined by the backend session.
  const [isSignInOpen, setIsSignInOpen] = useState(false);
  const signInRef = useRef<HTMLDivElement | null>(null);
  const signInButtonRef = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    if (!isSignInOpen) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!signInRef.current?.contains(event.target as Node)) setIsSignInOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsSignInOpen(false);
        signInButtonRef.current?.focus();
      }
    };
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [isSignInOpen]);

  // Role-authorised workspace link, shown only to the matching role.
  const workspaceLink =
    principal?.role === "CUSTOMER" ? { href: "/orders", label: "My Orders" }
    : principal?.role === "OPERATIONS" ? { href: "/operations", label: "Operations Dashboard" }
    : principal?.role === "PARTNER" ? { href: "/partner", label: "Partner Workspace" }
    : principal?.role === "REVIEWER" ? { href: "/kyc", label: "KYC / Review" }
    : null;
  const isCurrentWorkspace = Boolean(workspaceLink && pathname?.startsWith(workspaceLink.href));
  const workspaceLinkClass = (extra: string) =>
    `${extra} ${isCurrentWorkspace
      ? "font-semibold text-[#c93835]"
      : "font-semibold text-[#10223e] hover:text-[#c93835]"}`;

  return (
    <header className="relative z-50 border-b border-[#e9edf1]/80 bg-[#fcfcfb]/95 backdrop-blur">
      <div className="relative mx-auto flex h-[74px] max-w-7xl items-center justify-between px-5 sm:px-8 lg:px-10">
        <Wordmark />
        <nav aria-label="Primary navigation" className="hidden items-center gap-7 lg:flex">
          <Link className="nav-link" href="/#solutions">Solutions</Link>
          <Link className="nav-link" href="/#how-it-works">How it works</Link>
          <Link className="nav-link" href="/#business-services">Business services</Link>
          {workspaceLink ? (
            <Link aria-current={isCurrentWorkspace ? "page" : undefined} className={workspaceLinkClass("nav-link")} href={workspaceLink.href}>{workspaceLink.label}</Link>
          ) : null}
        </nav>
        <div className="flex items-center gap-3 sm:gap-5">
          {authReady && !principal ? (
            <div ref={signInRef} className="relative">
              <button
                aria-controls="signin-dropdown"
                aria-expanded={isSignInOpen}
                aria-haspopup="menu"
                className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-lg border border-[#d8dee7] bg-white px-3.5 text-sm font-semibold text-[#31445e] transition hover:bg-[#f7f9fb] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#c93835]"
                id="signin-button"
                onClick={() => setIsSignInOpen((open) => !open)}
                ref={signInButtonRef}
                type="button"
              >
                Sign in
                <span aria-hidden="true" className={`text-[10px] transition-transform ${isSignInOpen ? "rotate-180" : ""}`}>▾</span>
              </button>
              {isSignInOpen ? (
                <div
                  aria-labelledby="signin-button"
                  className="absolute right-0 top-[calc(100%+8px)] z-50 w-64 overflow-hidden rounded-xl border border-[#dfe5eb] bg-white p-1.5 shadow-[0_16px_40px_rgba(16,34,62,0.14)]"
                  id="signin-dropdown"
                  role="menu"
                >
                  <p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#8b96a5]">Choose your workspace</p>
                  {[
                    { href: "/orders", label: "Customer Sign in", hint: "Onboarding, quotes & orders" },
                    { href: "/operations", label: "Operations Sign in", hint: "Assign partners & track fulfilment" },
                    { href: "/partner", label: "Partner Sign in", hint: "Assigned fulfilment work" },
                    { href: "/kyc", label: "Reviewer / KYC Sign in", hint: "Document review" },
                  ].map((item) => (
                    <Link
                      className="block rounded-lg px-3 py-2.5 text-sm font-semibold text-[#31445e] transition hover:bg-[#f7f9fb] focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[#c93835]"
                      href={item.href}
                      key={item.href}
                      onClick={() => setIsSignInOpen(false)}
                      role="menuitem"
                    >
                      {item.label}
                      <span className="mt-0.5 block text-xs font-normal text-[#7c8798]">{item.hint}</span>
                    </Link>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
          {principal ? (
            <Link
              className="hidden text-sm font-medium text-[#31445e] hover:text-[#c93835] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#c93835] sm:inline"
              href="/kyc"
            >
              Smart KYC
            </Link>
          ) : (
            <Link
              aria-label="Smart KYC prototype sign-in"
              className="hidden text-sm font-medium text-[#31445e] hover:text-[#c93835] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#c93835] sm:inline"
              href="/kyc"
            >
              Smart KYC
            </Link>
          )}
          <Link
            className="inline-flex items-center justify-center rounded-lg bg-[#c93835] px-4 py-2.5 text-sm font-semibold text-white shadow-[0_8px_18px_rgba(201,56,53,0.2)] transition hover:bg-[#b12d2b] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e] sm:px-5"
            href="/get-started"
          >
            Get started
          </Link>
          <button
            aria-controls="mobile-primary-navigation"
            aria-expanded={isMobileMenuOpen}
            aria-label={isMobileMenuOpen ? "Close navigation menu" : "Open navigation menu"}
            className="inline-flex size-10 items-center justify-center rounded-lg border border-[#d8dee7] text-[#31445e] transition hover:bg-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#c93835] lg:hidden"
            onClick={() => setIsMobileMenuOpen((isOpen) => !isOpen)}
            type="button"
          >
            <span aria-hidden="true" className="grid gap-1.5">
              <span className="h-0.5 w-4 rounded-full bg-current" />
              <span className="h-0.5 w-4 rounded-full bg-current" />
              <span className="h-0.5 w-4 rounded-full bg-current" />
            </span>
          </button>
        </div>
      </div>
      <nav
        aria-label="Mobile primary navigation"
        className={`${isMobileMenuOpen ? "border-t border-[#e9edf1] bg-[#fcfcfb]" : "hidden"} lg:hidden`}
        id="mobile-primary-navigation"
      >
        <div className="mx-auto grid max-w-7xl gap-1 px-5 py-4 sm:px-8">
          <Link className="nav-link rounded-lg px-3 py-3 hover:bg-white" href="/#solutions" onClick={closeMobileMenu}>Solutions</Link>
          <Link className="nav-link rounded-lg px-3 py-3 hover:bg-white" href="/#how-it-works" onClick={closeMobileMenu}>How it works</Link>
          <Link className="nav-link rounded-lg px-3 py-3 hover:bg-white" href="/#business-services" onClick={closeMobileMenu}>Business services</Link>
          {authReady && !principal ? (
            <>
              <p className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#8b96a5]">Sign in to a workspace</p>
              {[{ href: "/orders", label: "Customer Sign in" }, { href: "/operations", label: "Operations Sign in" }, { href: "/partner", label: "Partner Sign in" }, { href: "/kyc", label: "Reviewer / KYC Sign in" }].map((item) => (
                <Link className="nav-link rounded-lg px-3 py-2.5 hover:bg-white" href={item.href} key={item.href} onClick={closeMobileMenu}>{item.label}</Link>
              ))}
            </>
          ) : null}
          {workspaceLink ? (
            <Link aria-current={isCurrentWorkspace ? "page" : undefined} className={workspaceLinkClass("nav-link rounded-lg px-3 py-3 hover:bg-white")} href={workspaceLink.href} onClick={closeMobileMenu}>{workspaceLink.label}</Link>
          ) : null}
        </div>
      </nav>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-[#e9edf1] bg-white">
      <div className="mx-auto grid max-w-7xl gap-10 px-5 py-12 sm:px-8 md:grid-cols-[1.4fr_1fr_1fr] lg:px-10">
        <div>
          <Wordmark />
          <p className="mt-4 max-w-xs text-sm leading-6 text-[#68768a]">
            A simpler digital journey for India&apos;s ambitious small and medium businesses.
          </p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#8b96a5]">Explore</p>
          <div className="mt-4 grid gap-3 text-sm font-medium text-[#41536b]">
            <Link className="footer-link" href="/#solutions">Solutions</Link>
            <Link className="footer-link" href="/#how-it-works">How it works</Link>
            <Link className="footer-link" href="/#business-services">Business services</Link>
          </div>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#8b96a5]">Connect</p>
          <div className="mt-4 grid gap-3 text-sm font-medium text-[#41536b]">
            <a className="footer-link" href="mailto:hello@udyamone.in">hello@udyamone.in</a>
            <span className="cursor-default text-[#8b96a5]" title="Legal information is coming soon">Privacy &amp; terms (coming soon)</span>
          </div>
        </div>
      </div>
      <div className="border-t border-[#eef0f3] py-5 text-center text-xs text-[#8994a3]">
        © 2026 UdyamOne. All rights reserved.
      </div>
    </footer>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  centered = false,
}: {
  eyebrow: string;
  title: string;
  description: string;
  centered?: boolean;
}) {
  return (
    <div className={centered ? "mx-auto max-w-2xl text-center" : "max-w-2xl"}>
      <p className="mb-4 text-xs font-semibold uppercase tracking-[0.16em] text-[#c93835]">
        {eyebrow}
      </p>
      <h2 className="text-3xl font-semibold tracking-[-0.045em] text-[#10223e] sm:text-4xl lg:text-[2.7rem] lg:leading-[1.08]">
        {title}
      </h2>
      <p className="mt-5 text-base leading-7 text-[#637083] sm:text-[1.05rem]">
        {description}
      </p>
    </div>
  );
}

export function SolutionCard({
  icon,
  title,
  description,
  details,
}: {
  icon: IconName;
  title: string;
  description: string;
  details: string;
}) {
  return (
    <article className="group rounded-2xl border border-[#e5e9ef] bg-white p-6 transition duration-200 hover:-translate-y-1 hover:border-[#d8dde5] hover:shadow-[0_16px_40px_rgba(16,34,62,0.08)]">
      <div className="flex size-11 items-center justify-center rounded-xl bg-[#fdf0ef] text-[#cc3b38]">
        <Icon className="size-5" name={icon} />
      </div>
      <h3 className="mt-6 text-lg font-semibold tracking-[-0.025em] text-[#10223e]">
        {title}
      </h3>
      <p className="mt-2 text-sm leading-6 text-[#667386]">{description}</p>
      <p className="mt-5 border-t border-[#eef0f3] pt-4 text-xs font-medium text-[#45546a]">
        {details}
      </p>
    </article>
  );
}

export function DashboardPreview() {
  return (
    <div className="relative mx-auto w-full max-w-[560px] min-w-0">
      <div className="absolute -inset-5 -z-10 rounded-[2rem] bg-[#f4ece8] sm:-inset-7" />
      <div className="overflow-hidden rounded-[1.35rem] border border-[#dfe4eb] bg-white shadow-[0_28px_70px_rgba(18,37,65,0.15)]">
        <div className="flex items-center justify-between border-b border-[#eef0f3] px-4 py-3 sm:px-5">
          <div className="flex items-center gap-2">
            <span className="size-2 rounded-full bg-[#d9433f]" />
            <span className="size-2 rounded-full bg-[#f1b64c]" />
            <span className="size-2 rounded-full bg-[#83b88b]" />
          </div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.13em] text-[#9aa4b2]">
            UdyamOne workspace
          </p>
          <span className="size-4" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-[96px_minmax(0,1fr)] lg:grid-cols-[116px_minmax(0,1fr)]">
          <aside className="hidden border-r border-[#edf0f3] bg-[#fbfcfd] p-3 sm:block">
            <p className="px-2 pb-5 text-[10px] font-semibold uppercase tracking-[0.14em] text-[#9aa4b2]">
              Journey
            </p>
            {["Overview", "Profile", "Solutions", "Quote"].map((item, index) => (
              <div
                className={`mb-1 rounded-md px-2 py-2 text-[11px] font-medium ${
                  index === 2
                    ? "bg-[#fdebea] text-[#c93835]"
                    : "text-[#778396]"
                }`}
                key={item}
              >
                {item}
              </div>
            ))}
          </aside>
          <div className="min-w-0 bg-[#fff] p-3 sm:p-5 lg:p-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#c93835]">
                  Your business
                </p>
                <h3 className="mt-2 text-base font-semibold tracking-[-0.03em] text-[#142642] sm:text-lg">
                  Your digital foundation
                </h3>
              </div>
              <span className="inline-flex w-fit rounded-full bg-[#eaf5ed] px-2.5 py-1 text-[10px] font-semibold text-[#357044]">
                Profile complete
              </span>
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-[#e7ebf0] p-3.5">
                <div className="flex items-center justify-between gap-2">
                  <Icon className="size-4 shrink-0 text-[#c93835]" name="connectivity" />
                  <span className="text-[10px] font-semibold text-[#568f65]">Match</span>
                </div>
                <p className="mt-4 text-xs font-semibold text-[#1c2d47]">Business Fibre</p>
                <p className="mt-1 text-[11px] text-[#778396]">Fast, reliable connectivity</p>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[#edf0f3]">
                  <div className="h-full w-[88%] rounded-full bg-[#d9433f]" />
                </div>
              </div>
              <div className="rounded-xl border border-[#e7ebf0] p-3.5">
                <div className="flex items-center justify-between gap-2">
                  <Icon className="size-4 shrink-0 text-[#2d5e9e]" name="cloud" />
                  <span className="text-[10px] font-semibold text-[#568f65]">Match</span>
                </div>
                <p className="mt-4 text-xs font-semibold text-[#1c2d47]">Cloud Office</p>
                <p className="mt-1 text-[11px] text-[#778396]">Tools that grow with you</p>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[#edf0f3]">
                  <div className="h-full w-[76%] rounded-full bg-[#2d5e9e]" />
                </div>
              </div>
            </div>
            <div className="mt-4 flex items-center justify-between gap-3 rounded-xl bg-[#10223e] px-3 py-3 text-white sm:px-4">
              <div className="min-w-0">
                <p className="text-[10px] font-medium text-[#bdc6d3]">Your estimated plan</p>
                <p className="mt-1 text-sm font-semibold">Built around your needs</p>
              </div>
              <span className="shrink-0 rounded-lg bg-white/10 px-2.5 py-1.5 text-[10px] font-semibold">View quote</span>
            </div>
          </div>
        </div>
      </div>
      <div className="absolute -bottom-5 -left-3 hidden rounded-xl border border-[#e2e7ed] bg-white px-4 py-3 shadow-[0_12px_30px_rgba(16,34,62,0.12)] sm:-left-4 sm:block">
        <div className="flex items-center gap-2">
          <span className="grid size-7 place-items-center rounded-full bg-[#eaf5ed] text-[#398149]">
            <Icon className="size-3.5" name="check" />
          </span>
          <div>
            <p className="text-[10px] font-medium text-[#778396]">Clear next step</p>
            <p className="text-xs font-semibold text-[#1c2d47]">Quote ready to review</p>
          </div>
        </div>
      </div>
    </div>
  );
}
