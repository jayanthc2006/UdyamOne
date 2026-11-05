# Phase 3.1 KYC document workflow

The prototype supports `gst_certificate`, `udyam_certificate`, `signatory_id`,
and `address_proof`. Supplied samples are read-only presence signals. In
particular, K05's absent Udyam certificate remains `NOT_PROVIDED`; no replacement
is generated and the omission is not treated as an intentional challenge.

## Separate workflow states

Each document reports independent presence, manual review, registry, upload, and
local processing states:

- Presence: `NOT_PROVIDED` or `PROVIDED`.
- Document review: `NOT_REVIEWED`, `VALID`, or `INVALID`.
- Registry verification: always `NOT_CHECKED` in Phase 3.1.
- Upload: `NOT_UPLOADED` or `UPLOADED`.
- Processing: `NOT_STARTED`, `PROCESSING`, `SUCCEEDED`, `UNREADABLE`, or
  `FAILED`.

`UDYAMONE_KYC_REQUIRED_DOCUMENTS` is a backend-owned comma-separated list of
approved required document types. Its default is empty. Optional missing
documents do not block finalization. A required document must be present and
manually marked `VALID`. If it has an extraction result, its required fields
must also be corrected when missing or invalid, and confirmed when flagged
low-confidence. Optional extracted fields do not block finalization.

## Upload, local processing, and review

The API accepts PNG, JPEG, and PDF uploads. It checks declared media type,
file signature, actual image/PDF readability, a 10 MB size limit, a 30-megapixel
image limit, and a 10-page PDF limit. It generates storage names and does not
retain a client-supplied filename. Re-uploads replace the previous stored
document for that applicant and category. Downloads are category-scoped and
return generated filenames; backend filesystem paths are not returned.

Uploads and manifests are stored under `backend/runtime_uploads/`, ignored by
Git. OCR and extraction run locally; document contents are never sent to Gemini,
OpenAI, or another external provider:

- Windows' built-in `Windows.Media.Ocr` handles PNG/JPEG and rendered scanned
  PDF pages.
- `pypdfium2` extracts selectable PDF text and renders scanned pages.
- Pillow checks and prepares image inputs.

For OCR, use Windows 10 or later and install a Windows OCR language supported
by the local document language. In Windows Settings, add the language under
**Time & language → Language & region**, then install its OCR/handwriting
optional capability under that language's options if it is not already
present. The Windows OCR engine must be available to the account running the
backend. The backend reports processing failure when it is unavailable; it
does not silently substitute a remote provider. This local setup was verified
on the development machine. Other Windows machines must verify their own OCR
language installation.

Windows OCR does not supply confidence scores through this integration.
Confidence is therefore reported as unavailable; the UI asks reviewers to
compare values with the document. Heuristic extraction reports missing/invalid
fields and possible submitted-profile mismatches. It is not a document
authenticity check, registry lookup, or official verification. Manual edits are
persisted separately from review and registry states.

The supplied GST and Udyam specimen layouts receive a separate local OCR pass
over the registration-number region because full-page OCR loses their table
relationships. This layout-specific pass is limited to the known sample files
or documents whose OCR identifies the specimen template. It does not repair
ambiguous GSTIN characters. The documented Udyam district code `00` may be
normalized only in the known specimen format, and the result remains
low-confidence until manually confirmed. Unreadable or ambiguous numbers stay
missing/invalid for manual correction; numbers are never inferred from other
fields. Signatory extraction is limited to the name; the case-pack does not
establish a need to extract ID subtype or number.

Useful local endpoints:

- `GET /api/v1/kyc/{applicant_id}` — assessment and document states.
- `PUT /api/v1/kyc/{applicant_id}/documents/{document_type}` — upload or replace.
- `GET /api/v1/kyc/{applicant_id}/documents/{document_type}/file` — download.
- `POST /api/v1/kyc/{applicant_id}/documents/{document_type}/process` — local OCR.
- `PATCH /api/v1/kyc/{applicant_id}/documents/{document_type}/corrections` —
  persist corrections.
- `POST /api/v1/kyc/{applicant_id}/documents/{document_type}/review` — prototype
  manual review.
- `POST /api/v1/kyc/{applicant_id}/finalize` — policy gate and assessment.

The K05 sample is available at `/kyc`. KYC data shown in this prototype is
synthetic competition data. Review and finalization endpoints are unauthenticated
and are not production-grade approval workflows. Production use requires
authentication, role-based access, encrypted object storage, malware scanning,
retention/deletion policies, durable audit records, and reviewer accountability.
