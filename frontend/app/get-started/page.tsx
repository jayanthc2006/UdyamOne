"use client";

import { type FormEvent, useState } from "react";

import { Icon, SiteFooter, SiteHeader } from "@/components/landing";
import { RecommendationResults } from "@/components/recommendation-results";
import {
  type BusinessSegment,
  type PrimaryRequirement,
  type RecommendationRequest,
  type RecommendationResponse,
  udyamOneApi,
} from "@/lib/api";

const businessTypes = [
  "Micro retail",
  "Professional office",
  "Multi-site business",
  "Manufacturing",
] as const;

const requirements = [
  "Connectivity",
  "Business communication",
  "Cloud and productivity",
  "Security and IoT",
] as const;

type Requirement = (typeof requirements)[number];
type FormValues = {
  businessName: string;
  businessType: string;
  city: string;
  cityTier: string;
  employeeCount: string;
  siteCount: string;
  gstinStatus: string;
  requirements: Requirement[];
};
type FormErrors = Partial<Record<keyof FormValues, string>>;
type EditableField = Exclude<keyof FormValues, "requirements">;

const initialValues: FormValues = {
  businessName: "",
  businessType: "",
  city: "",
  cityTier: "",
  employeeCount: "",
  siteCount: "",
  gstinStatus: "",
  requirements: [],
};

const businessSegmentMap: Record<(typeof businessTypes)[number], BusinessSegment> = {
  "Micro retail": "micro",
  "Professional office": "prof",
  "Multi-site business": "multi",
  Manufacturing: "mfg",
};

const requirementMap: Record<Requirement, PrimaryRequirement> = {
  Connectivity: "connectivity",
  "Business communication": "business_communication",
  "Cloud and productivity": "cloud_productivity",
  "Security and IoT": "security_iot",
};

function validate(values: FormValues): FormErrors {
  const errors: FormErrors = {};
  const positiveInteger = /^[1-9]\d*$/;

  if (!values.businessName.trim()) errors.businessName = "Enter your business name.";
  if (!values.businessType) errors.businessType = "Choose the type of business you run.";
  if (!values.city.trim()) errors.city = "Enter the city where your business is based.";
  if (!values.cityTier) errors.cityTier = "Select your city tier.";
  if (!positiveInteger.test(values.employeeCount)) {
    errors.employeeCount = "Enter a whole number greater than zero.";
  }
  if (!positiveInteger.test(values.siteCount)) {
    errors.siteCount = "Enter a whole number greater than zero.";
  }
  if (!values.gstinStatus) errors.gstinStatus = "Tell us your GSTIN status.";
  if (!values.requirements.length) {
    errors.requirements = "Select at least one business requirement.";
  }

  return errors;
}

function toRecommendationRequest(values: FormValues): RecommendationRequest {
  return {
    business_profile: {
      city_tier: values.cityTier === "tier-1" ? 1 : 2,
      employee_count: Number(values.employeeCount),
      site_count: Number(values.siteCount),
      gstin_verified: values.gstinStatus === "Verified",
    },
    business_segment: businessSegmentMap[values.businessType as (typeof businessTypes)[number]],
    primary_requirements: values.requirements.map((requirement) => requirementMap[requirement]),
  };
}

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return <p className="mt-2 text-sm font-medium text-[#c93835]" id={id} role="alert">{message}</p>;
}

function FieldLabel({
  htmlFor,
  label,
  description,
}: {
  htmlFor: string;
  label: string;
  description?: string;
}) {
  return (
    <div className="mb-2">
      <label className="text-sm font-semibold text-[#263952]" htmlFor={htmlFor}>{label}</label>
      {description ? <p className="mt-1 text-xs leading-5 text-[#778396]">{description}</p> : null}
    </div>
  );
}

export default function GetStartedPage() {
  const [values, setValues] = useState<FormValues>(initialValues);
  const [errors, setErrors] = useState<FormErrors>({});
  const [touched, setTouched] = useState<Partial<Record<keyof FormValues, boolean>>>({});
  const [recommendation, setRecommendation] = useState<RecommendationResponse | null>(null);
  const [recommendationRequest, setRecommendationRequest] = useState<RecommendationRequest | null>(null);
  const [recommendationError, setRecommendationError] = useState<string | null>(null);
  const [recommendationLoading, setRecommendationLoading] = useState(false);

  const updateField = (field: EditableField, value: string) => {
    const nextValues = { ...values, [field]: value };
    setValues(nextValues);
    if (touched[field]) setErrors(validate(nextValues));
  };

  const markTouched = (field: keyof FormValues) => {
    setTouched((current) => ({ ...current, [field]: true }));
    setErrors(validate(values));
  };

  const toggleRequirement = (requirement: Requirement) => {
    const nextRequirements = values.requirements.includes(requirement)
      ? values.requirements.filter((item) => item !== requirement)
      : [...values.requirements, requirement];
    const nextValues = { ...values, requirements: nextRequirements };
    setValues(nextValues);
    if (touched.requirements) setErrors(validate(nextValues));
  };

  const requestRecommendations = async (request: RecommendationRequest) => {
    if (recommendationLoading) return;
    setRecommendationLoading(true);
    setRecommendationError(null);
    try {
      setRecommendation(await udyamOneApi.getRecommendations(request));
      setRecommendationRequest(request);
    } catch (error) {
      setRecommendationError(
        error instanceof Error ? error.message : "We could not create recommendations right now.",
      );
    } finally {
      setRecommendationLoading(false);
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const validationErrors = validate(values);
    setErrors(validationErrors);
    setTouched({
      businessName: true,
      businessType: true,
      city: true,
      cityTier: true,
      employeeCount: true,
      siteCount: true,
      gstinStatus: true,
      requirements: true,
    });

    if (Object.keys(validationErrors).length || recommendationLoading) return;
    void requestRecommendations(toRecommendationRequest(values));
  };

  if (recommendation) {
    return (
      <>
        <SiteHeader />
        <RecommendationResults
          onAdvisorUpdate={(nextRecommendation, nextRequest) => {
            setRecommendation(nextRecommendation);
            setRecommendationRequest(nextRequest);
          }}
          onEdit={() => {
            setRecommendation(null);
            setRecommendationRequest(null);
          }}
          onRetry={() => void requestRecommendations(recommendationRequest ?? toRecommendationRequest(values))}
          recommendation={recommendation}
          request={recommendationRequest ?? toRecommendationRequest(values)}
          retrying={recommendationLoading}
        />
        <SiteFooter />
      </>
    );
  }

  const inputClass = (field: keyof FormValues) =>
    `w-full rounded-lg border bg-white px-3.5 py-3 text-sm text-[#1f324c] outline-none transition placeholder:text-[#a2aab6] focus:border-[#c93835] focus:ring-4 focus:ring-[#fdebea] ${
      errors[field] && touched[field] ? "border-[#d9433f]" : "border-[#d9e0e8]"
    }`;
  const errorId = (field: keyof FormValues) => `${field}-error`;
  const isInvalid = (field: keyof FormValues) => Boolean(errors[field] && touched[field]);

  return (
    <main className="min-h-screen bg-[#fcfcfb] text-[#10223e]">
      <SiteHeader />
      <section className="border-b border-[#e9edf1] bg-[#f5f1ee]">
        <div className="mx-auto max-w-7xl px-5 py-12 sm:px-8 lg:px-10 lg:py-16">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#c93835]">Get started</p>
          <h1 className="mt-4 max-w-2xl text-3xl font-semibold tracking-[-0.05em] text-[#10223e] sm:text-4xl lg:text-5xl">Tell us a little about your business.</h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-[#647287]">We&apos;ll use these details to shape a relevant digital journey. It takes just a few minutes.</p>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-8 px-5 py-10 sm:px-8 lg:grid-cols-[minmax(0,1fr)_320px] lg:gap-14 lg:px-10 lg:py-16">
        <form className="rounded-2xl border border-[#e4e9ee] bg-white p-5 shadow-[0_12px_34px_rgba(16,34,62,0.05)] sm:p-8" noValidate onSubmit={handleSubmit}>
          <div className="flex items-start justify-between gap-4 border-b border-[#edf0f3] pb-6">
            <div>
              <h2 className="text-xl font-semibold tracking-[-0.03em] text-[#10223e]">Business profile</h2>
              <p className="mt-1 text-sm leading-6 text-[#6d798b]">All fields are required unless noted.</p>
            </div>
            <span className="rounded-full bg-[#fdebea] px-3 py-1.5 text-xs font-semibold text-[#b53431]">Step 1 of 1</span>
          </div>

          {recommendationError ? <div aria-live="polite" className="mt-6 rounded-xl border border-[#f1d3d1] bg-[#fff5f4] p-4 text-sm leading-6 text-[#a22f2c]">{recommendationError}<button className="ml-2 font-semibold underline" disabled={recommendationLoading} onClick={() => void requestRecommendations(toRecommendationRequest(values))} type="button">Retry</button></div> : null}

          <div className="mt-7 grid gap-6 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <FieldLabel htmlFor="businessName" label="Business name" description="Use the name customers and partners know you by." />
              <input aria-describedby={isInvalid("businessName") ? errorId("businessName") : undefined} aria-invalid={isInvalid("businessName")} className={inputClass("businessName")} id="businessName" onBlur={() => markTouched("businessName")} onChange={(event) => updateField("businessName", event.target.value)} placeholder="e.g. Sharma Trading Co." type="text" value={values.businessName} />
              <FieldError id={errorId("businessName")} message={touched.businessName ? errors.businessName : undefined} />
            </div>

            <div>
              <FieldLabel htmlFor="businessType" label="Business type" />
              <select aria-describedby={isInvalid("businessType") ? errorId("businessType") : undefined} aria-invalid={isInvalid("businessType")} className={inputClass("businessType")} id="businessType" onBlur={() => markTouched("businessType")} onChange={(event) => updateField("businessType", event.target.value)} value={values.businessType}>
                <option value="">Select your business type</option>
                {businessTypes.map((type) => <option key={type} value={type}>{type}</option>)}
              </select>
              <FieldError id={errorId("businessType")} message={touched.businessType ? errors.businessType : undefined} />
            </div>

            <div>
              <FieldLabel htmlFor="city" label="City" />
              <input aria-describedby={isInvalid("city") ? errorId("city") : undefined} aria-invalid={isInvalid("city")} className={inputClass("city")} id="city" onBlur={() => markTouched("city")} onChange={(event) => updateField("city", event.target.value)} placeholder="e.g. Pune" type="text" value={values.city} />
              <FieldError id={errorId("city")} message={touched.city ? errors.city : undefined} />
            </div>

            <div>
              <FieldLabel htmlFor="cityTier" label="City tier" description="This helps us check local service availability." />
              <select aria-describedby={isInvalid("cityTier") ? errorId("cityTier") : undefined} aria-invalid={isInvalid("cityTier")} className={inputClass("cityTier")} id="cityTier" onBlur={() => markTouched("cityTier")} onChange={(event) => updateField("cityTier", event.target.value)} value={values.cityTier}>
                <option value="">Select city tier</option>
                <option value="tier-1">Tier 1</option>
                <option value="tier-2">Tier 2</option>
              </select>
              <FieldError id={errorId("cityTier")} message={touched.cityTier ? errors.cityTier : undefined} />
            </div>

            <div>
              <FieldLabel htmlFor="employeeCount" label="Employee count" />
              <input aria-describedby={isInvalid("employeeCount") ? errorId("employeeCount") : undefined} aria-invalid={isInvalid("employeeCount")} className={inputClass("employeeCount")} id="employeeCount" inputMode="numeric" min="1" onBlur={() => markTouched("employeeCount")} onChange={(event) => updateField("employeeCount", event.target.value)} placeholder="e.g. 12" step="1" type="number" value={values.employeeCount} />
              <FieldError id={errorId("employeeCount")} message={touched.employeeCount ? errors.employeeCount : undefined} />
            </div>

            <div>
              <FieldLabel htmlFor="siteCount" label="Number of business sites" />
              <input aria-describedby={isInvalid("siteCount") ? errorId("siteCount") : undefined} aria-invalid={isInvalid("siteCount")} className={inputClass("siteCount")} id="siteCount" inputMode="numeric" min="1" onBlur={() => markTouched("siteCount")} onChange={(event) => updateField("siteCount", event.target.value)} placeholder="e.g. 1" step="1" type="number" value={values.siteCount} />
              <FieldError id={errorId("siteCount")} message={touched.siteCount ? errors.siteCount : undefined} />
            </div>

            <div className="sm:col-span-2">
              <FieldLabel htmlFor="gstinStatus" label="GSTIN status" description="Only your self-reported Verified selection is sent as verified in this prototype; UdyamOne does not verify GSTIN here." />
              <select aria-describedby={isInvalid("gstinStatus") ? errorId("gstinStatus") : undefined} aria-invalid={isInvalid("gstinStatus")} className={inputClass("gstinStatus")} id="gstinStatus" onBlur={() => markTouched("gstinStatus")} onChange={(event) => updateField("gstinStatus", event.target.value)} value={values.gstinStatus}>
                <option value="">Select GSTIN status</option>
                <option value="Verified">Verified</option>
                <option value="Not verified">Not verified</option>
                <option value="Not registered">Not registered</option>
              </select>
              <FieldError id={errorId("gstinStatus")} message={touched.gstinStatus ? errors.gstinStatus : undefined} />
            </div>

            <fieldset aria-describedby={isInvalid("requirements") ? errorId("requirements") : undefined} className="sm:col-span-2" onBlur={() => markTouched("requirements")}>
              <legend className="text-sm font-semibold text-[#263952]">Primary business requirements</legend>
              <p className="mt-1 text-xs leading-5 text-[#778396]">Select every area you would like to improve. You can choose more than one.</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {requirements.map((requirement) => {
                  const checked = values.requirements.includes(requirement);
                  return (
                    <label className={`flex cursor-pointer items-center gap-3 rounded-xl border p-4 transition ${checked ? "border-[#d9433f] bg-[#fff7f6]" : "border-[#dfe5eb] bg-white hover:border-[#bdc7d3]"}`} key={requirement}>
                      <input checked={checked} className="size-4 accent-[#d9433f]" onChange={() => toggleRequirement(requirement)} type="checkbox" />
                      <span className="text-sm font-semibold text-[#33455f]">{requirement}</span>
                    </label>
                  );
                })}
              </div>
              <FieldError id={errorId("requirements")} message={touched.requirements ? errors.requirements : undefined} />
            </fieldset>
          </div>

          <div className="mt-8 flex flex-col gap-3 border-t border-[#edf0f3] pt-6 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs leading-5 text-[#7b8797]">Your details are used only to request this prototype recommendation preview. Nothing is persisted by this frontend.</p>
            <button className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-[#d9433f] px-5 text-sm font-semibold text-white shadow-[0_8px_18px_rgba(201,56,53,0.18)] transition hover:bg-[#c33532] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e] disabled:cursor-not-allowed disabled:opacity-60" disabled={recommendationLoading} type="submit">
              {recommendationLoading ? "Finding solutions…" : "See my solutions"} <Icon className="size-4" name="arrow" />
            </button>
          </div>
        </form>

        <aside className="h-fit rounded-2xl border border-[#e4e9ee] bg-[#10223e] p-6 text-white lg:sticky lg:top-6">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#f19995]">What happens next</p>
          <h2 className="mt-3 text-xl font-semibold tracking-[-0.03em]">A more relevant starting point.</h2>
          <p className="mt-3 text-sm leading-6 text-[#c0cad8]">Your profile will help tailor the solution journey to the scale and needs of your business.</p>
          <ul className="mt-7 grid gap-5">
            {["Find services that fit your business", "See clear quote ranges and requirements", "Move through onboarding with confidence"].map((item) => (
              <li className="flex gap-3 text-sm leading-6 text-[#e4e9f0]" key={item}>
                <span className="mt-1 grid size-5 shrink-0 place-items-center rounded-full bg-white/10 text-[#f4a49f]"><Icon className="size-3" name="check" /></span>
                {item}
              </li>
            ))}
          </ul>
        </aside>
      </section>
      <SiteFooter />
    </main>
  );
}
