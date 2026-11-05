import {
  DashboardPreview,
  Icon,
  SectionHeading,
  SiteFooter,
  SiteHeader,
  SolutionCard,
} from "@/components/landing";
import Link from "next/link";

const solutions = [
  {
    icon: "connectivity" as const,
    title: "Connectivity",
    description: "Reliable fibre, wireless and multi-site connectivity for every kind of business.",
    details: "Internet · Leased line · SD-WAN",
  },
  {
    icon: "communication" as const,
    title: "Business communication",
    description: "Keep your customers close with professional calling, messaging and WhatsApp tools.",
    details: "Cloud telephony · SMS · WhatsApp",
  },
  {
    icon: "cloud" as const,
    title: "Cloud & productivity",
    description: "Give your people the secure tools they need to do their best work from anywhere.",
    details: "Email · Backup · Billing",
  },
  {
    icon: "security" as const,
    title: "Security & IoT",
    description: "Protect your operations and keep a closer eye on every site, asset and device.",
    details: "Firewall · CCTV · IoT tracking",
  },
];

const journeySteps = [
  ["01", "Tell us about your business", "Share a few essential details about your business, locations and goals."],
  ["02", "Discover suitable solutions", "See a focused mix of digital services that fit how your business works."],
  ["03", "Get transparent quotations", "Understand your choices, costs and terms before you make a decision."],
  ["04", "Complete digital onboarding", "Move from selection to activation with guided, paper-light onboarding."],
] as const;

const benefits = [
  ["spark", "Personalised recommendations", "A relevant starting point built around your business profile."],
  ["document", "Transparent pricing", "Clear product options, quote ranges and setup charges—up front."],
  ["lock", "Simplified documentation", "Know what you need before you begin, with fewer surprises along the way."],
  ["check", "Guided onboarding", "Move confidently through every step with a journey designed for progress."],
] as const;

export default function Home() {
  return (
    <main className="overflow-hidden bg-[#fcfcfb] text-[#10223e]" id="top">
      <SiteHeader />

      <section className="relative">
        <div className="pointer-events-none absolute left-1/2 top-0 -z-0 h-64 w-[80%] -translate-x-1/2 rounded-b-[50%] bg-[#f7f3ef]" />
        <div className="relative z-10 mx-auto grid max-w-7xl gap-14 px-5 pb-20 pt-16 sm:px-8 sm:pt-24 lg:grid-cols-[1.02fr_0.98fr] lg:items-center lg:gap-16 lg:px-10 lg:pb-28 lg:pt-28">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#ecd9d6] bg-white px-3 py-1.5 text-xs font-semibold text-[#a93230] shadow-sm">
              <span className="size-1.5 rounded-full bg-[#d9433f]" />
              Built for India&apos;s growing businesses
            </div>
            <h1 className="mt-7 text-[2.8rem] font-semibold leading-[1.04] tracking-[-0.06em] text-[#10223e] sm:text-6xl lg:text-[4.25rem]">
              Everything Your Business Needs. <span className="text-[#c93835]">One Simple Journey.</span>
            </h1>
            <p className="mt-6 max-w-xl text-base leading-7 text-[#627086] sm:text-lg sm:leading-8">
              Discover the right digital services, build a stronger business foundation, compare clear quotations and move into onboarding—all in one guided experience.
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <Link className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-[#10223e] px-5 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-[#193253] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#d9433f]" href="/get-started">
                Get Started <Icon className="size-4" name="arrow" />
            </Link>
              <a className="inline-flex min-h-12 items-center justify-center rounded-lg border border-[#d8dee7] bg-white px-5 text-sm font-semibold text-[#243852] transition hover:border-[#b8c2cf] hover:bg-[#f8fafb]" href="#solutions">
                Explore Solutions
              </a>
            </div>
            <div className="mt-11 flex flex-wrap items-center gap-x-7 gap-y-3 text-sm text-[#68768a]">
              <span className="inline-flex items-center gap-2"><Icon className="size-4 text-[#c93835]" name="check" /> Built for MSMEs</span>
              <span className="inline-flex items-center gap-2"><Icon className="size-4 text-[#c93835]" name="check" /> Clear, guided decisions</span>
            </div>
          </div>
          <DashboardPreview />
        </div>
      </section>

      <section className="border-y border-[#edf0f2] bg-white py-6">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-5 text-center sm:flex-row sm:px-8 sm:text-left lg:px-10">
          <p className="text-sm font-medium text-[#627086]">A single journey for the digital essentials that help your business move forward.</p>
          <div className="flex items-center gap-4 text-xs font-semibold uppercase tracking-[0.14em] text-[#8b96a5]">
            <span>Discover</span><span className="size-1 rounded-full bg-[#d9433f]" /><span>Decide</span><span className="size-1 rounded-full bg-[#d9433f]" /><span>Onboard</span>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-20 sm:px-8 lg:px-10 lg:py-28" id="solutions">
        <SectionHeading eyebrow="Business solutions" title="The essential services behind better business." description="From getting connected to staying secure, UdyamOne brings together the services MSMEs need to work with more confidence." />
        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {solutions.map((solution) => <SolutionCard {...solution} key={solution.title} />)}
        </div>
      </section>

      <section className="bg-[#f5f7f9] py-20 lg:py-28" id="how-it-works">
        <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
          <SectionHeading centered eyebrow="How UdyamOne works" title="A clearer path from business need to business-ready." description="We simplify the decisions that usually slow businesses down—without taking away your control." />
          <div className="relative mt-14 grid gap-8 md:grid-cols-2 lg:grid-cols-4 lg:gap-5">
            <div className="absolute left-[12.5%] right-[12.5%] top-7 hidden border-t border-dashed border-[#cdd5df] lg:block" />
            {journeySteps.map(([number, title, description]) => (
              <article className="relative" key={number}>
                <span className="relative z-10 grid size-14 place-items-center rounded-full bg-[#10223e] text-sm font-semibold text-white shadow-[0_7px_15px_rgba(16,34,62,0.18)]">{number}</span>
                <h3 className="mt-6 text-lg font-semibold tracking-[-0.025em] text-[#10223e]">{title}</h3>
                <p className="mt-2 max-w-[17rem] text-sm leading-6 text-[#647287]">{description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-12 px-5 py-20 sm:px-8 lg:grid-cols-[0.88fr_1.12fr] lg:items-center lg:gap-20 lg:px-10 lg:py-28" id="business-services">
        <div>
          <SectionHeading eyebrow="Why UdyamOne" title="Designed to make the next right move feel obvious." description="The journey is intentionally practical: less searching, less uncertainty and a more confident way to build your digital business." />
          <a className="mt-8 inline-flex items-center gap-2 text-sm font-semibold text-[#c93835] transition hover:gap-3" href="#get-started">
            See how it works <Icon className="size-4" name="arrow" />
          </a>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {benefits.map(([icon, title, description]) => (
            <article className="rounded-2xl border border-[#e5e9ef] bg-white p-6" key={title}>
              <Icon className="size-5 text-[#c93835]" name={icon} />
              <h3 className="mt-5 text-base font-semibold tracking-[-0.025em] text-[#10223e]">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-[#667386]">{description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 pb-20 sm:px-8 lg:px-10 lg:pb-28" id="get-started">
        <div className="relative overflow-hidden rounded-[1.75rem] bg-[#10223e] px-6 py-14 text-center sm:px-12 lg:px-20 lg:py-20">
          <div className="absolute -right-16 -top-24 size-64 rounded-full border-[28px] border-white/[0.05]" />
          <div className="absolute -bottom-28 -left-14 size-64 rounded-full border-[28px] border-white/[0.04]" />
          <div className="relative mx-auto max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#f29a96]">Your next chapter starts here</p>
            <h2 className="mt-5 text-3xl font-semibold tracking-[-0.045em] text-white sm:text-4xl">Build the digital foundation your business deserves.</h2>
            <p className="mt-5 text-base leading-7 text-[#c3ccda]">Start with a few details. UdyamOne will help you find the services and path that make sense for your business.</p>
            <Link className="mt-8 inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-[#d9433f] px-6 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-[#ef514c] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white" href="/get-started">
              Begin your journey <Icon className="size-4" name="arrow" />
            </Link>
          </div>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
}
