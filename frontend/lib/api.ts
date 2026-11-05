export type BusinessProfile = {
  city_tier: number;
  employee_count: number;
  site_count: number;
  gstin_verified: boolean;
};

export type PrimaryRequirement =
  | "connectivity"
  | "business_communication"
  | "cloud_productivity"
  | "security_iot";
export type BusinessSegment = "micro" | "prof" | "multi" | "mfg";

export type RecommendationRequest = {
  business_profile: BusinessProfile;
  business_segment: BusinessSegment;
  primary_requirements: PrimaryRequirement[];
};

export type RecommendedProduct = {
  product_id: string;
  category: string;
  product_name: string;
  description: string;
  unit: string;
  quantity: number;
  recommendation_reason: string;
  is_required_prerequisite: boolean;
  required_for_product_ids: string[];
  monthly_min_inr: number;
  monthly_max_inr: number;
  one_time_setup_inr: number;
  min_contract_months: number;
};

export type RecommendationBundle = {
  bundle_id: string;
  bundle_type: "budget" | "recommended" | "advanced";
  display_name: string;
  explanation: string;
  products: RecommendedProduct[];
  supported_requirements: PrimaryRequirement[];
  unsupported_requirements: PrimaryRequirement[];
  limitations: string[];
  monthly_min_inr: number;
  monthly_max_inr: number;
  one_time_setup_inr: number;
};

export type RecommendationResponse = {
  bundles: RecommendationBundle[];
  unsupported_requirements: PrimaryRequirement[];
  limitations: string[];
};

export type AdvisorLanguage = "en" | "hi" | "te" | "ta" | "kn";
export type AdvisorMessage = {
  role: "user" | "assistant";
  content: string;
};
export type AdvisorChatRequest = RecommendationRequest & {
  messages: AdvisorMessage[];
  language: AdvisorLanguage;
};
export type AdvisorChatResponse = {
  reply: string;
  language: AdvisorLanguage;
  extracted_requirements: PrimaryRequirement[];
  needs_clarification: boolean;
  recommendations_refreshed: boolean;
  recommendations: RecommendationResponse | null;
  privacy_notice: string;
  prototype_notice: string;
};

export type QuoteRequest = {
  business_profile: BusinessProfile;
  selected_products: Array<{ product_id: string; quantity: number }>;
};

export type QuoteLineItem = {
  product_id: string;
  category: string;
  product_name: string;
  description: string;
  unit: string;
  quantity: number;
  monthly_unit_price_min_inr: number;
  monthly_unit_price_max_inr: number;
  monthly_subtotal_min_inr: number;
  monthly_subtotal_max_inr: number;
  one_time_setup_fee_per_unit_inr: number;
  one_time_setup_subtotal_inr: number;
  min_contract_months: number;
};

export type QuoteResponse = {
  line_items: QuoteLineItem[];
  total_monthly_min_inr: number;
  total_monthly_max_inr: number;
  total_one_time_setup_inr: number;
};

export type KycDocumentType =
  | "gst_certificate"
  | "udyam_certificate"
  | "signatory_id"
  | "address_proof";
export type KycProcessingStatus =
  | "NOT_STARTED"
  | "PROCESSING"
  | "SUCCEEDED"
  | "UNREADABLE"
  | "FAILED";
export type KycFieldStatus =
  | "EXTRACTED"
  | "MISSING"
  | "INVALID_FORMAT"
  | "LOW_CONFIDENCE"
  | "MANUALLY_CORRECTED";
export type KycExtractedField = {
  name: string;
  label: string;
  value: string | null;
  confidence: number | null;
  status: KycFieldStatus;
  flags: string[];
};
export type KycExtraction = {
  processing_status: KycProcessingStatus;
  detected_document_type: KycDocumentType | null;
  classification_matches_category: boolean | null;
  fields: KycExtractedField[];
  required_fields: string[];
  missing_fields: string[];
  invalid_fields: string[];
  low_confidence_fields: string[];
  mismatch_warnings: string[];
  confidence_available: boolean;
  error_code: string | null;
};
export type KycDocumentState = {
  document_type: KycDocumentType;
  display_name: string;
  presence: "NOT_PROVIDED" | "PROVIDED";
  validation: "NOT_REVIEWED" | "VALID" | "INVALID";
  registry_verification: "NOT_CHECKED";
  upload_status: "NOT_UPLOADED" | "UPLOADED";
  processing_status: KycProcessingStatus;
  original_filename: string | null;
  file_size_bytes: number | null;
  content_type: string | null;
  extraction: KycExtraction | null;
};
export type KycAssessment = {
  applicant_id: string;
  documents: KycDocumentState[];
  required_documents: KycDocumentType[];
  upload_requests: KycDocumentType[];
  next_steps: string[];
  ready_for_approval: boolean;
};
export type KycFinalizationResponse = {
  finalized: true;
  message: string;
  assessment: KycAssessment | null;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");
const REQUEST_TIMEOUT_MS = 12_000;

function getErrorDetail(data: unknown): string {
  if (!data || typeof data !== "object" || !("detail" in data)) {
    return "The service could not process this request.";
  }

  const detail = data.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (!Array.isArray(detail)) return "The service could not process this request.";

  const messages = detail.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const message = "msg" in item && typeof item.msg === "string" ? item.msg : null;
    if (!message) return [];
    const rawLocation = "loc" in item ? item.loc : undefined;
    const location = Array.isArray(rawLocation)
      ? rawLocation.filter((part: unknown): part is string | number => typeof part === "string" || typeof part === "number")
          .filter((part) => part !== "body")
          .join(".")
      : "";
    return [location ? `${location}: ${message}` : message];
  });

  return messages.join(" ") || "The service could not process this request.";
}

async function requestJson<TResponse>(
  path: string,
  init: RequestInit,
  timeoutMs = REQUEST_TIMEOUT_MS,
): Promise<TResponse> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
    });
    const data: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      throw new ApiError(getErrorDetail(data), response.status);
    }
    return data as TResponse;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("The request took too long. Please try again.");
    }
    throw new ApiError(
      "We could not reach UdyamOne right now. Check that the local API is running and try again.",
    );
  } finally {
    window.clearTimeout(timeout);
  }
}

function postJson<TResponse>(path: string, payload?: unknown): Promise<TResponse> {
  return requestJson(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
  });
}

export const udyamOneApi = {
  getRecommendations: (request: RecommendationRequest) =>
    postJson<RecommendationResponse>("/api/v1/recommendations", request),
  advisorChat: (request: AdvisorChatRequest) =>
    postJson<AdvisorChatResponse>("/api/v1/advisor/chat", request),
  previewQuote: (request: QuoteRequest) =>
    postJson<QuoteResponse>("/api/v1/quotes/preview", request),
  getKycAssessment: (applicantId: string) =>
    requestJson<KycAssessment>(`/api/v1/kyc/${encodeURIComponent(applicantId)}`, {
      method: "GET",
    }),
  uploadKycDocument: (
    applicantId: string,
    documentType: KycDocumentType,
    file: File,
  ) =>
    requestJson<KycAssessment>(
      `/api/v1/kyc/${encodeURIComponent(applicantId)}/documents/${documentType}`,
      {
        method: "PUT",
        headers: { "Content-Type": file.type },
        body: file,
      },
    ),
  reviewKycDocument: (
    applicantId: string,
    documentType: KycDocumentType,
    validation: "VALID" | "INVALID",
  ) =>
    postJson<KycAssessment>(
      `/api/v1/kyc/${encodeURIComponent(applicantId)}/documents/${documentType}/review`,
      { validation },
    ),
  processKycDocument: (
    applicantId: string,
    documentType: KycDocumentType,
  ) =>
    requestJson<KycAssessment>(
      `/api/v1/kyc/${encodeURIComponent(applicantId)}/documents/${documentType}/process`,
      { method: "POST" },
      120_000,
    ),
  correctKycDocumentFields: (
    applicantId: string,
    documentType: KycDocumentType,
    fields: Record<string, string | null>,
  ) =>
    requestJson<KycAssessment>(
      `/api/v1/kyc/${encodeURIComponent(applicantId)}/documents/${documentType}/corrections`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fields }),
      },
    ),
  setKycProfile: (
    applicantId: string,
    profile: { business_name: string | null; business_address: string | null },
  ) =>
    requestJson<KycAssessment>(
      `/api/v1/kyc/${encodeURIComponent(applicantId)}/profile`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile),
      },
    ),
  getKycDocumentUrl: (
    applicantId: string,
    documentType: KycDocumentType,
  ) =>
    `${API_BASE_URL}/api/v1/kyc/${encodeURIComponent(applicantId)}/documents/${documentType}/file`,
  finalizeKyc: (applicantId: string) =>
    postJson<KycFinalizationResponse>(
      `/api/v1/kyc/${encodeURIComponent(applicantId)}/finalize`,
    ),
};
