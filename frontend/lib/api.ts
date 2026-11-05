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

async function postJson<TResponse>(
  path: string,
  payload: unknown,
): Promise<TResponse> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
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

export const udyamOneApi = {
  getRecommendations: (request: RecommendationRequest) =>
    postJson<RecommendationResponse>("/api/v1/recommendations", request),
  advisorChat: (request: AdvisorChatRequest) =>
    postJson<AdvisorChatResponse>("/api/v1/advisor/chat", request),
  previewQuote: (request: QuoteRequest) =>
    postJson<QuoteResponse>("/api/v1/quotes/preview", request),
};
