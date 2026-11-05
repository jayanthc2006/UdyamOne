"use client";

import {
  type ChangeEvent,
  type FormEvent,
  useCallback,
  useEffect,
  useState,
} from "react";

import { SiteFooter, SiteHeader } from "@/components/landing";
import {
  type KycAssessment,
  type KycDocumentState,
  type KycDocumentType,
  udyamOneApi,
} from "@/lib/api";

const applicantId = "K05";

function getErrorMessage(error: unknown): string {
  return error instanceof Error
    ? error.message
    : "The KYC action could not be completed. Please try again.";
}

function DocumentCard({
  document,
  busy,
  onUpload,
  onReview,
  onProcess,
  onSaveCorrections,
}: {
  document: KycDocumentState;
  busy: boolean;
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
          <a
            className="inline-flex min-h-10 items-center rounded-lg border border-[#bdc7d3] px-3 text-sm font-semibold text-[#31445e] hover:bg-[#f7f9fb] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e]"
            href={udyamOneApi.getKycDocumentUrl("K05", document.document_type)}
            rel="noopener noreferrer"
            target="_blank"
          >
            View document
          </a>
          <button
            className="min-h-10 rounded-lg border border-[#bdc7d3] px-3 text-sm font-semibold text-[#31445e] hover:bg-[#f7f9fb] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e] disabled:opacity-60"
            disabled={busy}
            onClick={() => onProcess(document.document_type)}
            type="button"
          >
            {document.extraction ? "Run local OCR again" : "Run local OCR"}
          </button>
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
          {extraction.fields.length ? (
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
        </section>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-3">
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
        {document.presence === "PROVIDED" ? (
          <>
            <button
              className="min-h-10 rounded-lg bg-[#10223e] px-3 text-sm font-semibold text-white hover:bg-[#193253] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e] disabled:opacity-60"
              disabled={busy}
              onClick={() => onReview(document.document_type, "VALID")}
              type="button"
            >
              Mark reviewed: valid
            </button>
            <button
              className="min-h-10 rounded-lg border border-[#bdc7d3] px-3 text-sm font-semibold text-[#31445e] hover:bg-[#f7f9fb] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e] disabled:opacity-60"
              disabled={busy}
              onClick={() => onReview(document.document_type, "INVALID")}
              type="button"
            >
              Mark reviewed: invalid
            </button>
          </>
        ) : null}
      </div>
    </article>
  );
}

export default function KycPage() {
  const [assessment, setAssessment] = useState<KycAssessment | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [businessName, setBusinessName] = useState("");
  const [businessAddress, setBusinessAddress] = useState("");

  const loadAssessment = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setAssessment(await udyamOneApi.getKycAssessment(applicantId));
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
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
  }, []);

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
    void performAction(() => udyamOneApi.uploadKycDocument(applicantId, documentType, file));
  };

  const review = (
    documentType: KycDocumentType,
    validation: "VALID" | "INVALID",
  ) => {
    void performAction(() =>
      udyamOneApi.reviewKycDocument(applicantId, documentType, validation),
    );
  };

  const process = (documentType: KycDocumentType) => {
    void performAction(() => udyamOneApi.processKycDocument(applicantId, documentType));
  };

  const saveCorrections = (
    documentType: KycDocumentType,
    fields: Record<string, string | null>,
  ) => {
    void performAction(() =>
      udyamOneApi.correctKycDocumentFields(applicantId, documentType, fields),
    );
  };

  const saveProfile = () => {
    void performAction(() =>
      udyamOneApi.setKycProfile(applicantId, {
        business_name: businessName.trim() || null,
        business_address: businessAddress.trim() || null,
      }),
    );
  };

  const finalize = () => {
    void performAction(() => udyamOneApi.finalizeKyc(applicantId));
  };

  return (
    <main className="min-h-screen bg-[#fcfcfb] text-[#10223e]">
      <SiteHeader />
      <section
        aria-busy={busy}
        className="mx-auto max-w-5xl px-5 py-10 sm:px-8 lg:py-16"
      >
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#c93835]">
          Phase 3.1 · Sample KYC
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-[-0.045em] sm:text-4xl">
          Document checklist for applicant K05
        </h1>
        <p className="mt-4 max-w-3xl text-sm leading-6 text-[#526279]">
          K05 has a GST certificate, address proof and signatory ID. The supplied sample
          set does not include an Udyam certificate. Missing documents are shown as
          “Not provided”; they are not treated as invalid. Required documents are
          controlled by backend policy.
        </p>

        <div className="mt-6 rounded-xl border border-[#dce4ec] bg-[#f4f7fa] p-4 text-sm leading-6 text-[#31445e]">
          <p>
            Document presence, manual document review and registry verification are
            separate. Registry verification is not performed in Phase 3.1.
          </p>
          <p className="mt-1">
            The review buttons are prototype controls, not a secured reviewer workflow.
          </p>
        </div>

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

        {loading ? (
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

        {assessment ? (
          <>
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

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              {assessment.documents.map((document) => (
                <DocumentCard
                  busy={busy}
                  document={document}
                  key={document.document_type}
                  onReview={review}
                  onProcess={process}
                  onSaveCorrections={saveCorrections}
                  onUpload={upload}
                />
              ))}
            </div>

            <div className="mt-6 flex flex-col gap-3 rounded-xl border border-[#e3e8ee] bg-white p-5 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm leading-6 text-[#526279]">
                {assessment.ready_for_approval
                  ? "Current required-document checks are satisfied. Optional documents may remain missing."
                  : "Final approval is blocked until every required document is provided and manually reviewed as valid."}
              </p>
              <button
                className="min-h-11 shrink-0 rounded-lg bg-[#c93835] px-5 text-sm font-semibold text-white hover:bg-[#b12d2b] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#10223e] disabled:cursor-not-allowed disabled:opacity-50"
                disabled={!assessment.ready_for_approval || busy}
                onClick={finalize}
                type="button"
              >
                Finalize onboarding
              </button>
            </div>
          </>
        ) : null}
      </section>
      <SiteFooter />
    </main>
  );
}
