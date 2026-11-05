/** Browser-local pointer to the durable backend applicant profile. */

const APPLICANT_ID_STORAGE_KEY = "udyamone.applicant-id";

export function getCurrentApplicantId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(APPLICANT_ID_STORAGE_KEY);
}

export function saveCurrentApplicantId(applicantId: string): void {
  window.localStorage.setItem(APPLICANT_ID_STORAGE_KEY, applicantId);
}

export function clearCurrentApplicantId(): void {
  window.localStorage.removeItem(APPLICANT_ID_STORAGE_KEY);
}
