"use client";

import {
  type ChangeEvent,
  type FormEvent,
  useCallback,
  useEffect,
  useState,
} from "react";

import { SiteFooter, SiteHeader } from "@/components/landing";
import { getCurrentApplicantId, saveCurrentApplicantId } from "@/lib/applicant-session";
import {
  type KycAssessment,
  type KycDocumentState,
  type KycDocumentType,
  type KycRole,
  type KycSessionIdentity,
  KYC_SESSION_KEY,
  udyamOneApi,
} from "@/lib/api";

function getErrorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "The KYC action could not be completed. Please try again.";
}

function DocumentCard({
  document,
  role,
  consentAccepted,
  busy,
  onView,
  onUpload,
  onReview,
  onProcess,
  onSaveCorrections,
}: {
  document: KycDocumentState;
  role: KycRole;
  consentAccepted: boolean;
  busy: boolean;
  onView: (documentType: KycDocumentType) => void;
  onUpload: (documentType: KycDocumentType, file: File) => void;
  onReview: (documentType: KycDocumentType, validation: "VALID" | "INVALID") => void;
  onProcess: (documentType: KycDocumentType) => void;
  onSaveCorrections: (
    documentType: KycDocumentType,
    fields: Record<string, string | null>,
  ) => void;
}) {
  const inputId = `document-${document.document_type}`;
  const extraction = document.extraction;
  const submitCorrections = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    onSaveCorrections(
      document.document_type,
      Object.fromEntries(
        (extraction?.fields ?? []).map((field) => [
          field.name,
          String(formData.get(field.name) ?? "").trim() || null,
        ]),
      ),
    );
  };

  return (
    <article className="rounded-xl border border-[#dfe5eb] bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-[#10223e]">{document.display_name}</h2>
          <p className="mt-1 text-sm text-[#526279]">
            Document: <span className="font-medium">{document.presence.replaceAll("_", " ").toLowerCase()}</span>
          </p>
        </div>
        {document.presence === "NOT_PROVIDED" ? (
          <span className="rounded-full bg-[#fff4e4] px-3 py-1 text-xs font-semibold text-[#765719]">
            Not provided
          </span>
        ) : (
          <span className="rounded-full bg-[#eaf5ed] px-3 py-1 text-xs font-semibold text-[#28613a]">
            Provided
          </span>
        )}
      </div>

      <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-[#68768a]">Document review</dt>
          <dd className="font-medium text-[#31445e]">{document.validation.replaceAll("_", " ")}</dd>
        </div>
        <div>
          <dt className="text-[#526279]">Registry verification</dt>
          <dd className="font-medium text-[#31445e]">{document.registry_verification.replaceAll("_", " ")}</dd>
        </div>
        <div>
          <dt className="text-[#526279]">Upload status</dt>
          <dd className="font-medium text-[#31445e]">{document.upload_status.replaceAll("_", " ")}</dd>
        </div>
        <div>
          <dt className="text-[#526279]">Processing</dt>
          <dd className="font-medium text-[#31445e]" aria-live="polite">
            {document.processing_status.replaceAll("_", " ").toLowerCase()}
          </dd>
        </div>
      </dl>

      {document.presence === "PROVIDED" ? (
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            className="inline-flex min-h-10 items-center rounded-lg border border-[#bdc7d3] px-3 text-sm font-semibold text-[#31445e] hover:bg-[#f7f9fb] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e]"
            onClick={() => onView(document.document_type)}
            type="button"
          >
            View document
          </button>
          {role === "CUSTOMER" && consentAccepted ? <button
            className="min-h-10 rounded-lg border border-[#bdc7d3] px-3 text-sm font-semibold text-[#31445e] hover:bg-[#f7f9fb] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e] disabled:opacity-60"
            disabled={busy}
            onClick={() => onProcess(document.document_type)}
            type="button"
          >
            {document.extraction ? "Run local OCR again" : "Run local OCR"}
          </button> : null}
        </div>
      ) : null}

      {extraction ? (
        <section className="mt-5 border-t border-[#e3e8ee] pt-4" aria-label={`${document.display_name} extraction`}>
          <h3 className="text-sm font-semibold text-[#10223e]">Extracted information</h3>
          {extraction.error_code ? (
            <p className="mt-2 text-sm text-[#8b2825]" role="status">
              Processing could not complete ({extraction.error_code.replaceAll("_", " ").toLowerCase()}).
            </p>
          ) : null}
          {extraction.classification_matches_category === false ? (
            <p className="mt-2 text-sm text-[#765719]" role="status">
              The detected document type differs from this category. Please review it manually.
            </p>
          ) : null}
          {!extraction.confidence_available && extraction.processing_status === "SUCCEEDED" ? (
            <p className="mt-2 text-sm text-[#526279]">
              Confidence scores are not provided by the local OCR engine; check extracted values against the document.
            </p>
          ) : null}
          {extraction.mismatch_warnings.map((warning) => (
            <p className="mt-2 text-sm text-[#765719]" key={warning} role="status">{warning}</p>
          ))}
          {extraction.fields.length && role === "CUSTOMER" && consentAccepted ? (
            <form
              className="mt-3"
              key={JSON.stringify(extraction)}
              onSubmit={submitCorrections}
            >
              <div className="grid gap-3 sm:grid-cols-2">
                {extraction.fields.map((field) => {
                  const invalid = field.status === "INVALID_FORMAT";
                  const missing = field.status === "MISSING";
                  return (
                    <div key={field.name}>
                      <label
                        className="block text-xs font-medium text-[#31445e]"
                        htmlFor={`${inputId}-field-${field.name}`}
                      >
                        {field.label}{extraction.required_fields.includes(field.name) ? " (required)" : ""}
                      </label>
                      <input
                        aria-describedby={`${inputId}-field-${field.name}-status`}
                        aria-invalid={invalid || missing}
                        className="mt-1 min-h-10 w-full rounded-md border border-[#bdc7d3] bg-white px-3 text-sm text-[#10223e] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e]"
                        defaultValue={field.value ?? ""}
                        id={`${inputId}-field-${field.name}`}
                        name={field.name}
                        required={extraction.required_fields.includes(field.name)}
                      />
                      <p
                        className={`mt-1 text-xs ${invalid || missing ? "text-[#8b2825]" : "text-[#526279]"}`}
                        id={`${inputId}-field-${field.name}-status`}
                      >
                        {field.status.replaceAll("_", " ").toLowerCase()}
                        {field.flags.length ? ` · ${field.flags.join(" ")}` : ""}
                      </p>
                    </div>
                  );
                })}
              </div>
              <button
                className="mt-3 min-h-10 rounded-lg border border-[#bdc7d3] px-3 text-sm font-semibold text-[#31445e] hover:bg-[#f7f9fb] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e] disabled:opacity-60"
                disabled={busy}
                type="submit"
              >
                Save corrections
              </button>
            </form>
          ) : null}
          {extraction.fields.length && role === "REVIEWER" ? (
            <dl className="mt-3 grid gap-2 sm:grid-cols-2">
              {extraction.fields.map((field) => (
                <div key={field.name}>
                  <dt className="text-xs font-medium text-[#526279]">{field.label}</dt>
                  <dd className="break-words text-sm text-[#10223e]">
                    {field.value || "Not extracted"} · {field.status.replaceAll("_", " ").toLowerCase()}
                  </dd>
                </div>
              ))}
            </dl>
          ) : null}
        </section>
      ) : null}

      {role === "CUSTOMER" && consentAccepted ? <div className="mt-4 flex flex-wrap items-center gap-3">
        <label
          className="inline-flex min-h-10 cursor-pointer items-center justify-center rounded-lg border border-[#bdc7d3] px-3 text-sm font-semibold text-[#31445e] hover:bg-[#f7f9fb] focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-[#10223e]"
          htmlFor={inputId}
        >
          {document.presence === "PROVIDED" ? "Replace document" : "Choose document"}
        </label>
        <input
          accept="image/png,image/jpeg,application/pdf"
          className="sr-only"
          disabled={busy}
          id={inputId}
          onChange={(event: ChangeEvent<HTMLInputElement>) => {
            const file = event.target.files?.[0];
            if (file) onUpload(document.document_type, file);
            event.target.value = "";
          }}
          type="file"
        />
      </div>
      : null}

      {role === "REVIEWER" && document.presence === "PROVIDED" ? (
        <div className="mt-4 flex flex-wrap items-center gap-3" aria-label="Reviewer document decision">
          <button
            aria-pressed={document.validation === "VALID"}
            className={`min-h-10 rounded-lg px-3 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e] disabled:opacity-60 ${
              document.validation === "VALID"
                ? "bg-[#24613a] text-white"
                : "border border-[#bdc7d3] text-[#31445e] hover:bg-[#f7f9fb]"
            }`}
            disabled={busy}
            onClick={() => onReview(document.document_type, "VALID")}
            type="button"
          >
            Mark reviewed: valid{document.validation === "VALID" ? " (selected)" : ""}
          </button>
          <button
            aria-pressed={document.validation === "INVALID"}
            className={`min-h-10 rounded-lg px-3 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e] disabled:opacity-60 ${
              document.validation === "INVALID"
                ? "border-2 border-[#8b2825] bg-[#fff1ef] text-[#8b2825]"
                : "border border-[#bdc7d3] text-[#31445e] hover:bg-[#f7f9fb]"
            }`}
            disabled={busy}
            onClick={() => onReview(document.document_type, "INVALID")}
            type="button"
          >
            Mark reviewed: invalid{document.validation === "INVALID" ? " (selected)" : ""}
          </button>
        </div>
      ) : null}
    </article>
  );
}

export default function KycPage() {
  const [applicantId, setApplicantId] = useState<string | null>(null);
  const [identityReady, setIdentityReady] = useState(false);
  const [principal, setPrincipal] = useState<KycSessionIdentity | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [reviewerApplicantId, setReviewerApplicantId] = useState("");
  const [assessment, setAssessment] = useState<KycAssessment | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [businessName, setBusinessName] = useState("");
  const [businessAddress, setBusinessAddress] = useState("");
  const [consentConfirmed, setConsentConfirmed] = useState(false);
  const [requestedDocumentTypes, setRequestedDocumentTypes] = useState<KycDocumentType[]>([]);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState("");

  const consentAccepted = assessment?.consent?.consented === true
    && assessment.consent.consent_version === "kyc-consent-v1";

  const loadAssessment = useCallback(async () => {
    if (!applicantId || !principal) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setAssessment(await udyamOneApi.getKycAssessment(applicantId));
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [applicantId, principal]);

  useEffect(() => {
    const requestedApplicantId = new URLSearchParams(window.location.search).get("applicant");
    const savedApplicantId = requestedApplicantId || getCurrentApplicantId();
    if (requestedApplicantId && requestedApplicantId !== "K05") {
      saveCurrentApplicantId(requestedApplicantId);
    }
    const timer = window.setTimeout(() => {
      setApplicantId(savedApplicantId);
      setIdentityReady(true);
      setLoading(Boolean(savedApplicantId));
    }, 0);
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
    udyamOneApi.getKycSession(token)
      .then((session) => {
        if (active) setPrincipal(session);
      })
      .catch((sessionError: unknown) => {
        window.sessionStorage.removeItem(KYC_SESSION_KEY);
        if (active) setError(getErrorMessage(sessionError));
      })
      .finally(() => {
        if (active) setAuthReady(true);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!identityReady || !applicantId || !principal) return;
    let active = true;
    udyamOneApi.getKycAssessment(applicantId)
      .then((result) => {
        if (active) setAssessment(result);
      })
      .catch((loadError: unknown) => {
        if (active) setError(getErrorMessage(loadError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [applicantId, identityReady, principal]);

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  const performAction = async (action: () => Promise<KycAssessment | { message: string }>) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await action();
      if ("documents" in result) {
        setAssessment(result);
      } else {
        setNotice(result.message);
        await loadAssessment();
      }
    } catch (actionError) {
      setError(getErrorMessage(actionError));
      await loadAssessment();
    } finally {
      setBusy(false);
    }
  };

  const upload = (documentType: KycDocumentType, file: File) => {
    if (!applicantId) return;
    void performAction(() => udyamOneApi.uploadKycDocument(applicantId, documentType, file));
  };

  const review = (
    documentType: KycDocumentType,
    validation: "VALID" | "INVALID",
  ) => {
    if (!applicantId) return;
    void performAction(() =>
      udyamOneApi.reviewKycDocument(applicantId, documentType, validation),
    );
  };

  const process = (documentType: KycDocumentType) => {
    if (!applicantId) return;
    void performAction(() => udyamOneApi.processKycDocument(applicantId, documentType));
  };

  const saveCorrections = (
    documentType: KycDocumentType,
    fields: Record<string, string | null>,
  ) => {
    if (!applicantId) return;
    void performAction(() =>
      udyamOneApi.correctKycDocumentFields(applicantId, documentType, fields),
    );
  };

  const saveProfile = () => {
    if (!applicantId) return;
    void performAction(() =>
      udyamOneApi.setKycProfile(applicantId, {
        business_name: businessName.trim() || null,
        business_address: businessAddress.trim() || null,
      }),
    );
  };

  const finalize = () => {
    if (!applicantId) return;
    void performAction(() => udyamOneApi.finalizeKyc(applicantId));
  };

  const signIn = async (event: FormEvent<HTMLFormElement>) => {
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
      setNotice(`Signed in as ${session.role.toLowerCase()}.`);
    } catch (loginError) {
      setError(getErrorMessage(loginError));
    } finally {
      setBusy(false);
    }
  };

  const signOut = () => {
    window.sessionStorage.removeItem(KYC_SESSION_KEY);
    setPrincipal(null);
    setAssessment(null);
    setNotice("You have signed out.");
  };

  const selectApplicant = (nextApplicantId: string) => {
    const normalized = nextApplicantId.trim();
    if (!normalized) return;
    setApplicantId(normalized);
    setAssessment(null);
    setLoading(true);
    setError(null);
    setNotice(null);
    setReviewerApplicantId(normalized);
    if (normalized !== "K05") saveCurrentApplicantId(normalized);
    const url = new URL(window.location.href);
    url.searchParams.set("applicant", normalized);
    window.history.replaceState(null, "", url);
  };

  const acceptConsent = () => {
    if (!applicantId || !consentConfirmed) return;
    void performAction(() => udyamOneApi.setKycConsent(applicantId, true));
  };

  const declineConsent = () => {
    if (!applicantId) return;
    void performAction(() => udyamOneApi.setKycConsent(applicantId, false));
  };

  const viewDocument = async (documentType: KycDocumentType) => {
    if (!applicantId) return;
    setBusy(true);
    setError(null);
    try {
      const blob = await udyamOneApi.getKycDocument(applicantId, documentType);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrl(URL.createObjectURL(blob));
      setPreviewTitle(`${documentType.replaceAll("_", " ")} for ${applicantId}`);
    } catch (viewError) {
      setError(getErrorMessage(viewError));
    } finally {
      setBusy(false);
    }
  };

  const requestAdditionalDocuments = () => {
    if (!applicantId || requestedDocumentTypes.length === 0) return;
    void performAction(() =>
      udyamOneApi.requestKycAdditionalDocuments(applicantId, requestedDocumentTypes),
    );
    setRequestedDocumentTypes([]);
  };

  return (
    <main className="min-h-screen bg-[#fcfcfb] text-[#10223e]">
      <SiteHeader />
      <section
        aria-busy={busy}
        className="mx-auto max-w-5xl px-5 py-10 sm:px-8 lg:py-16"
      >
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#c93835]">
          Smart KYC · Prototype
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-[-0.045em] sm:text-4xl">
          {applicantId ? "Your applicant-specific document checklist" : "Start with your business profile"}
        </h1>
        <p className="mt-4 max-w-3xl text-sm leading-6 text-[#526279]">
          Applicant documents are stored and reviewed separately for each applicant. Missing documents are not treated as invalid.
        </p>

        <div className="mt-6 rounded-xl border border-[#dce4ec] bg-[#f4f7fa] p-4 text-sm leading-6 text-[#31445e]">
          <p>
            This competition prototype uses backend-configured accounts and signed sessions; it is not production authentication.
          </p>
          <p className="mt-1">
            Uploaded documents and KYC workflow data are stored by this prototype backend. Local OCR extracts document fields, and configured reviewers may inspect documents, request more documents and record a manual review. Registry verification is not performed.
          </p>
        </div>

        {!authReady ? <p className="mt-8 text-sm text-[#526279]" role="status">Checking your sign-in…</p> : null}
        {authReady && !principal ? (
          <form
            className="mt-6 grid max-w-xl gap-4 rounded-xl border border-[#dce4ec] bg-white p-5"
            onSubmit={signIn}
          >
            <h2 className="text-lg font-semibold">Sign in to Smart KYC</h2>
            <p className="text-sm leading-6 text-[#526279]">
              Prototype accounts are created and assigned by the backend operator. There is no customer/reviewer role selector.
            </p>
            <div>
              <label className="text-sm font-medium" htmlFor="kyc-username">Username</label>
              <input
                autoComplete="username"
                className="mt-1 min-h-10 w-full rounded-md border border-[#bdc7d3] px-3 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e]"
                id="kyc-username"
                onChange={(event) => setUsername(event.target.value)}
                required
                value={username}
              />
            </div>
            <div>
              <label className="text-sm font-medium" htmlFor="kyc-password">Password</label>
              <input
                autoComplete="current-password"
                className="mt-1 min-h-10 w-full rounded-md border border-[#bdc7d3] px-3 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e]"
                id="kyc-password"
                onChange={(event) => setPassword(event.target.value)}
                required
                type="password"
                value={password}
              />
            </div>
            <button
              className="min-h-11 rounded-lg bg-[#10223e] px-5 text-sm font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#c93835] disabled:opacity-60"
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
              className="min-h-10 rounded-lg border border-[#bdc7d3] px-3 text-sm font-semibold text-[#31445e] hover:bg-[#f7f9fb] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e]"
              onClick={signOut}
              type="button"
            >
              Sign out
            </button>
          </div>
        ) : null}

        {principal?.role === "REVIEWER" ? (
          <section className="mt-6 rounded-xl border border-[#dce4ec] bg-white p-5" aria-labelledby="reviewer-applicant-heading">
            <h2 className="text-base font-semibold" id="reviewer-applicant-heading">Reviewer applicant lookup</h2>
            <p className="mt-1 text-sm text-[#526279]">Enter an applicant ID assigned to the reviewer account.</p>
            <div className="mt-3 flex flex-wrap gap-3">
              <label className="sr-only" htmlFor="reviewer-applicant-id">Applicant ID</label>
              <input
                className="min-h-10 rounded-md border border-[#bdc7d3] px-3 text-sm"
                id="reviewer-applicant-id"
                onChange={(event) => setReviewerApplicantId(event.target.value)}
                value={reviewerApplicantId}
              />
              <button
                className="min-h-10 rounded-lg bg-[#10223e] px-4 text-sm font-semibold text-white"
                onClick={() => selectApplicant(reviewerApplicantId)}
                type="button"
              >
                Open applicant
              </button>
              <button
                className="min-h-10 rounded-lg border border-[#bdc7d3] px-4 text-sm font-semibold text-[#31445e]"
                onClick={() => selectApplicant("K05")}
                type="button"
              >
                Open competition sample K05
              </button>
            </div>
          </section>
        ) : null}

        {principal?.role === "CUSTOMER" && applicantId && consentAccepted ? (
          <section className="mt-6 rounded-xl border border-[#dce4ec] bg-white p-5" aria-labelledby="profile-reference-heading">
          <h2 className="text-base font-semibold" id="profile-reference-heading">Optional business profile comparison</h2>
          <p className="mt-1 text-sm leading-6 text-[#526279]">
            Enter supplied business details to flag possible OCR mismatches. A mismatch is not a registry verification.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div>
              <label className="text-sm font-medium" htmlFor="business-name">Business name</label>
              <input
                className="mt-1 min-h-10 w-full rounded-md border border-[#bdc7d3] px-3 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e]"
                id="business-name"
                onChange={(event) => setBusinessName(event.target.value)}
                value={businessName}
              />
            </div>
            <div>
              <label className="text-sm font-medium" htmlFor="business-address">Business address</label>
              <input
                className="mt-1 min-h-10 w-full rounded-md border border-[#bdc7d3] px-3 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e]"
                id="business-address"
                onChange={(event) => setBusinessAddress(event.target.value)}
                value={businessAddress}
              />
            </div>
          </div>
          <button
            className="mt-3 min-h-10 rounded-lg border border-[#bdc7d3] px-3 text-sm font-semibold text-[#31445e] hover:bg-[#f7f9fb] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e] disabled:opacity-60"
            disabled={busy}
            onClick={saveProfile}
            type="button"
          >
            Compare against extracted values
          </button>
          </section>
        ) : null}

        {!identityReady ? <p className="mt-8 text-sm text-[#526279]" role="status">Loading your applicant profile…</p> : null}
        {principal?.role === "CUSTOMER" && identityReady && !applicantId ? <a className="mt-8 inline-flex min-h-11 items-center rounded-lg bg-[#10223e] px-5 text-sm font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#c93835]" href="/get-started">Create a business profile</a> : null}

        {principal && applicantId && loading ? (
          <p className="mt-8 text-sm text-[#526279]" role="status">Loading document checklist…</p>
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
        {busy ? (
          <p className="mt-4 text-sm text-[#526279]" role="status">Saving KYC changes…</p>
        ) : null}

        {assessment && applicantId && principal ? (
          <>
            {principal.role === "CUSTOMER" ? (
              <section className="mt-8 rounded-xl border border-[#dce4ec] bg-white p-5" aria-labelledby="kyc-consent-heading">
                <h2 className="text-base font-semibold" id="kyc-consent-heading">Document-processing consent</h2>
                <p className="mt-2 text-sm leading-6 text-[#526279]">
                  Before uploading, consent to the prototype backend storing the documents and associated KYC workflow data for this applicant, using local OCR to extract information, and allowing configured reviewers to inspect the documents and record manual review outcomes or request additional documents. This is not registry verification or official approval.
                </p>
                {assessment.consent ? (
                  <p className="mt-2 text-sm" role="status">
                    Latest decision: {assessment.consent.consented ? "consented" : "declined"} · {assessment.consent.timestamp}
                  </p>
                ) : (
                  <p className="mt-2 text-sm text-[#765719]">No consent decision is recorded.</p>
                )}
                {!consentAccepted ? (
                  <>
                    <label className="mt-3 flex items-start gap-2 text-sm leading-6">
                      <input
                        checked={consentConfirmed}
                        className="mt-1"
                        onChange={(event) => setConsentConfirmed(event.target.checked)}
                        type="checkbox"
                      />
                      <span>I understand and consent to the document storage, local OCR and reviewer processing described above.</span>
                    </label>
                    <div className="mt-3 flex flex-wrap gap-3">
                      <button
                        className="min-h-10 rounded-lg bg-[#10223e] px-4 text-sm font-semibold text-white disabled:opacity-60"
                        disabled={!consentConfirmed || busy}
                        onClick={acceptConsent}
                        type="button"
                      >
                        Record consent and continue
                      </button>
                      <button
                        className="min-h-10 rounded-lg border border-[#bdc7d3] px-4 text-sm font-semibold text-[#31445e] disabled:opacity-60"
                        disabled={busy}
                        onClick={declineConsent}
                        type="button"
                      >
                        Decline
                      </button>
                    </div>
                  </>
                ) : null}
                {!consentAccepted ? (
                  <p className="mt-2 text-sm text-[#765719]">Uploads, OCR processing and corrections are disabled until current consent is recorded.</p>
                ) : null}
              </section>
            ) : null}

            <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold">Applicant documents</h2>
              <p className="text-sm text-[#526279]">
                Required by current policy: {assessment.required_documents.length
                  ? assessment.required_documents.map((type) =>
                    assessment.documents.find((document) => document.document_type === type)?.display_name
                    ?? type,
                  ).join(", ")
                  : "None"}
              </p>
            </div>

            {assessment.next_steps.length ? (
              <ul className="mt-4 grid gap-2 rounded-xl border border-[#efd4a1] bg-[#fff8e8] p-4 text-sm text-[#765719]">
                {assessment.next_steps.map((step) => <li key={step}>{step}</li>)}
              </ul>
            ) : null}

            {principal.role === "CUSTOMER" && !consentAccepted ? (
              <p className="mt-4 rounded-lg border border-[#efd4a1] bg-[#fff8e8] p-4 text-sm text-[#765719]">
                Document cards remain visible, but uploads and field changes are disabled until you record current consent.
              </p>
            ) : null}
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              {assessment.documents.map((document) => (
                <DocumentCard
                  busy={busy}
                  consentAccepted={consentAccepted}
                  document={document}
                  key={document.document_type}
                  onProcess={process}
                  onReview={review}
                  onSaveCorrections={saveCorrections}
                  onUpload={upload}
                  onView={viewDocument}
                  role={principal.role}
                />
              ))}
            </div>

            {principal.role === "REVIEWER" ? (
              <>
                <section className="mt-6 rounded-xl border border-[#e3e8ee] bg-white p-5" aria-labelledby="additional-documents-heading">
                  <h2 className="text-base font-semibold" id="additional-documents-heading">Request additional documents</h2>
                  <p className="mt-1 text-sm text-[#526279]">Requested documents become part of this applicant’s outstanding readiness checks.</p>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    {assessment.documents.map((document) => (
                      <label className="flex items-center gap-2 text-sm" key={document.document_type}>
                        <input
                          checked={requestedDocumentTypes.includes(document.document_type)}
                          onChange={(event) => setRequestedDocumentTypes((current) =>
                            event.target.checked
                              ? [...current, document.document_type]
                              : current.filter((item) => item !== document.document_type),
                          )}
                          type="checkbox"
                        />
                        {document.display_name}
                      </label>
                    ))}
                  </div>
                  {assessment.requested_documents.length ? (
                    <p className="mt-3 text-sm text-[#765719]">
                      Outstanding requests: {assessment.requested_documents.map((type) =>
                        assessment.documents.find((document) => document.document_type === type)?.display_name ?? type,
                      ).join(", ")}
                    </p>
                  ) : null}
                  <button
                    className="mt-3 min-h-10 rounded-lg border border-[#bdc7d3] px-4 text-sm font-semibold text-[#31445e] disabled:opacity-60"
                    disabled={!requestedDocumentTypes.length || busy}
                    onClick={requestAdditionalDocuments}
                    type="button"
                  >
                    Save document request
                  </button>
                </section>
                <div className="mt-6 flex flex-col gap-3 rounded-xl border border-[#e3e8ee] bg-white p-5 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm leading-6 text-[#526279]">
                    {assessment.ready_for_approval
                      ? "Current required-document and reviewer-request checks are satisfied. Optional documents may remain missing."
                      : "Readiness remains blocked until required documents and outstanding reviewer requests are provided, reviewed as valid and corrected where necessary."}
                  </p>
                  <button
                    className="min-h-11 shrink-0 rounded-lg bg-[#c93835] px-5 text-sm font-semibold text-white hover:bg-[#b12d2b] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e] disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={!assessment.ready_for_approval || busy}
                    onClick={finalize}
                    type="button"
                  >
                    Record readiness assessment
                  </button>
                </div>
              </>
            ) : null}
          </>
        ) : null}
      </section>
      {previewUrl ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true" aria-label={previewTitle}>
          <div className="flex h-[90vh] w-full max-w-5xl flex-col rounded-xl bg-white p-3">
            <div className="flex items-center justify-between gap-3 pb-3">
              <h2 className="text-sm font-semibold capitalize">{previewTitle}</h2>
              <button
                className="min-h-10 rounded-lg border border-[#bdc7d3] px-3 text-sm font-semibold"
                onClick={() => setPreviewUrl(null)}
                type="button"
              >
                Close document
              </button>
            </div>
            <iframe className="min-h-0 flex-1 rounded border" src={previewUrl} title={previewTitle} />
          </div>
        </div>
      ) : null}
      <SiteFooter />
    </main>
  );
}
