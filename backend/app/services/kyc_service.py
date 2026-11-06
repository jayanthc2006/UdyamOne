"""Local KYC document storage, OCR, extraction, and approval-gate logic."""

import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
import uuid
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Literal, Mapping

import pypdfium2 as pdfium
from PIL import Image, ImageEnhance, ImageFilter, UnidentifiedImageError

from app.models.kyc import (
    KycAssessment,
    KycConsentState,
    KycDocumentPresence,
    KycDocumentState,
    KycDocumentType,
    KycDocumentValidation,
    KycExtractedField,
    KycExtraction,
    KycFieldStatus,
    KycProcessingStatus,
    KycRecencyStatus,
)
from app.models.verification import RegistryVerificationStatus
from app.services import applicant_service, registry_verification_service

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_KYC_ROOT = PROJECT_ROOT / "data" / "sample_kyc"
UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "runtime_uploads"
OCR_SCRIPT = Path(__file__).with_name("local_ocr.ps1")
APPLICANT_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 30_000_000
MAX_PDF_PAGES = 10
OCR_TIMEOUT_SECONDS = 90
KYC_CONSENT_VERSION = "kyc-consent-v2"
KYC_REFERENCE_DATE = date(2026, 7, 15)
KYC_ADDRESS_PROOF_MAX_AGE_DAYS = 90
SUPPORTED_MIME_TYPES = {
    "image/png": (".png", b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": (".jpg", b"\xff\xd8\xff"),
    "application/pdf": (".pdf", b"%PDF-"),
}
WINDOWS_OCR_SCRIPT = OCR_SCRIPT
GSTIN_PATTERN = re.compile(
    r"(?<![A-Z0-9])[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z](?![A-Z0-9])",
    re.IGNORECASE,
)
UDYAM_PATTERN = re.compile(
    r"(?<![A-Z0-9])UDYAM[-\s]?[A-Z]{2}[-\s]?\d{2}[-\s]?\d{7}(?!\d)",
    re.IGNORECASE,
)
UDYAM_CANDIDATE_PATTERN = re.compile(
    r"(?<![A-Z0-9])UDYAM[\s./:|_-]*([A-Z]{2})[\s./:|_-]*"
    r"([A-Z0-9]{2})[\s./:|_-]*([A-Z0-9]{7})(?![A-Z0-9])",
    re.IGNORECASE,
)
_APPLICANT_LOCKS: dict[str, threading.RLock] = {}
_APPLICANT_LOCKS_LOCK = threading.Lock()


class KycConfigurationError(ValueError):
    """Raised when the server-side document policy is invalid."""


class KycStateError(RuntimeError):
    """Raised when local KYC workflow state cannot be read or saved."""


class KycConsentRequiredError(RuntimeError):
    """Raised when a consent-gated KYC action is attempted without consent."""


class KycUploadValidationError(ValueError):
    """Raised when the upload is empty, unsupported, or malformed."""


class KycOcrError(RuntimeError):
    """Raised when the local OCR subsystem is unavailable."""


def _lock_for(applicant_id: str) -> threading.RLock:
    with _APPLICANT_LOCKS_LOCK:
        return _APPLICANT_LOCKS.setdefault(applicant_id, threading.RLock())


def validate_applicant_id(applicant_id: str) -> str:
    if not APPLICANT_ID_PATTERN.fullmatch(applicant_id):
        raise ValueError("Applicant ID must contain only letters, numbers, '_' or '-'.")
    return applicant_id


def get_required_document_types() -> tuple[KycDocumentType, ...]:
    """Read the backend-owned document policy; an empty value means no required docs."""
    raw = os.getenv("UDYAMONE_KYC_REQUIRED_DOCUMENTS", "")
    required: list[KycDocumentType] = []
    for value in (part.strip() for part in raw.split(",")):
        if not value:
            continue
        try:
            document_type = KycDocumentType(value)
        except ValueError as error:
            allowed = ", ".join(item.value for item in KycDocumentType)
            raise KycConfigurationError(
                "UDYAMONE_KYC_REQUIRED_DOCUMENTS contains an unsupported document "
                f"type. Allowed values: {allowed}."
            ) from error
        if document_type not in required:
            required.append(document_type)
    return tuple(required)


def _sample_path(applicant_id: str, document_type: KycDocumentType) -> Path:
    return SAMPLE_KYC_ROOT / applicant_id / f"{applicant_id}_{document_type.value}.png"


def _applicant_upload_dir(applicant_id: str) -> Path:
    applicant_id = validate_applicant_id(applicant_id)
    root = UPLOAD_ROOT.resolve()
    applicant_dir = (root / applicant_id).resolve()
    if applicant_dir.parent != root or applicant_dir.name != applicant_id:
        raise KycStateError("The local KYC storage location is invalid.")
    return applicant_dir


def _manifest_path(applicant_id: str) -> Path:
    return _applicant_upload_dir(applicant_id) / "manifest.json"


def _read_manifest(applicant_id: str) -> dict[str, Any]:
    path = _manifest_path(applicant_id)
    if not path.exists():
        return {
            "version": 2,
            "documents": {},
            "profile": {},
            "consent_history": [],
            "requested_documents": [],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise KycStateError("Stored KYC review state could not be read.") from error
    if not isinstance(payload, dict):
        raise KycStateError("Stored KYC review state has an invalid format.")

    documents = payload.get("documents")
    if documents is None:
        # Migrate the simple validation-only manifest from the previous KYC pass.
        documents = {
            key: {"validation": value}
            for key, value in payload.items()
            if key in {item.value for item in KycDocumentType}
        }
    if not isinstance(documents, dict):
        raise KycStateError("Stored KYC review state has an invalid format.")
    for key, value in documents.items():
        try:
            KycDocumentType(key)
        except ValueError as error:
            raise KycStateError("Stored KYC review state has an invalid format.") from error
        if not isinstance(value, dict):
            raise KycStateError("Stored KYC review state has an invalid format.")
        stored_name = value.get("stored_name")
        if stored_name is not None and not re.fullmatch(
            r"[0-9a-f]{32}\.(?:png|jpg|pdf)", str(stored_name)
        ):
            raise KycStateError("Stored KYC review state has an invalid file reference.")
        try:
            KycDocumentValidation(value.get("validation", "NOT_REVIEWED"))
            KycProcessingStatus(value.get("processing_status", "NOT_STARTED"))
        except ValueError as error:
            raise KycStateError("Stored KYC review state has an invalid format.") from error
    profile = payload.get("profile", {})
    if not isinstance(profile, dict):
        raise KycStateError("Stored KYC profile has an invalid format.")
    consent_history = payload.get("consent_history", [])
    if not isinstance(consent_history, list):
        raise KycStateError("Stored KYC consent state has an invalid format.")
    try:
        for consent in consent_history:
            consent_state = KycConsentState.model_validate(consent)
            if consent_state.applicant_id != applicant_id:
                raise ValueError("Consent applicant does not match the manifest.")
    except (TypeError, ValueError) as error:
        raise KycStateError("Stored KYC consent state has an invalid format.") from error
    requested_documents = payload.get("requested_documents", [])
    if not isinstance(requested_documents, list):
        raise KycStateError("Stored additional-document requests have an invalid format.")
    try:
        requested_documents = list(dict.fromkeys(
            KycDocumentType(document_type).value for document_type in requested_documents
        ))
    except (TypeError, ValueError) as error:
        raise KycStateError(
            "Stored additional-document requests have an invalid format."
        ) from error
    return {
        "version": 2,
        "documents": documents,
        "profile": profile,
        "consent_history": consent_history,
        "requested_documents": requested_documents,
    }


def _current_consent(manifest: Mapping[str, Any]) -> KycConsentState | None:
    history = manifest.get("consent_history", [])
    if not history:
        return None
    try:
        return KycConsentState.model_validate(history[-1])
    except (TypeError, ValueError) as error:
        raise KycStateError("Stored KYC consent state has an invalid format.") from error


def require_current_consent(applicant_id: str) -> KycConsentState:
    validate_applicant_id(applicant_id)
    consent = _current_consent(_read_manifest(applicant_id))
    if (
        consent is None
        or not consent.consented
        or consent.consent_version != KYC_CONSENT_VERSION
    ):
        raise KycConsentRequiredError(
            "Current KYC consent is required before KYC document or synthetic registry processing."
        )
    return consent


def _registry_document_values(
    manifest: Mapping[str, Any],
) -> dict[str, str | None]:
    documents = manifest.get("documents", {})

    def value(document_type: KycDocumentType, field_name: str) -> str | None:
        metadata = documents.get(document_type.value, {})
        extraction_data = metadata.get("extraction") if isinstance(metadata, dict) else None
        if not isinstance(extraction_data, dict):
            return None
        try:
            extraction = KycExtraction.model_validate(extraction_data)
        except ValueError as error:
            raise KycStateError("Stored KYC extraction state has an invalid format.") from error
        return next(
            (field.value for field in extraction.fields if field.name == field_name),
            None,
        )

    return {
        "gstin": value(KycDocumentType.GST_CERTIFICATE, "gstin"),
        "gst_legal_name": value(KycDocumentType.GST_CERTIFICATE, "legal_name"),
        "gst_trade_name": value(KycDocumentType.GST_CERTIFICATE, "trade_name"),
        "gst_registered_address": value(
            KycDocumentType.GST_CERTIFICATE, "registered_address"
        ),
        "udyam_number": value(KycDocumentType.UDYAM_CERTIFICATE, "udyam_number"),
        "udyam_enterprise_name": value(
            KycDocumentType.UDYAM_CERTIFICATE, "enterprise_name"
        ),
    }


def get_registry_document_values(applicant_id: str) -> dict[str, str | None]:
    """Return only effective OCR/corrected fields needed by registry matching."""
    validate_applicant_id(applicant_id)
    return _registry_document_values(_read_manifest(applicant_id))


def record_consent(applicant_id: str, consented: bool) -> KycAssessment:
    validate_applicant_id(applicant_id)
    required = get_required_document_types()
    lock = _lock_for(applicant_id)
    with lock:
        manifest = _read_manifest(applicant_id)
        consent = KycConsentState(
            applicant_id=applicant_id,
            consented=consented,
            consent_version=KYC_CONSENT_VERSION,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        manifest["consent_history"].append(consent.model_dump(mode="json"))
        _write_manifest(applicant_id, manifest)
        return get_assessment(applicant_id, required)


def request_additional_documents(
    applicant_id: str,
    document_types: list[KycDocumentType],
) -> KycAssessment:
    validate_applicant_id(applicant_id)
    required = get_required_document_types()
    lock = _lock_for(applicant_id)
    with lock:
        manifest = _read_manifest(applicant_id)
        requested = list(manifest["requested_documents"])
        for document_type in document_types:
            if document_type.value not in requested:
                requested.append(document_type.value)
        manifest["requested_documents"] = requested
        _write_manifest(applicant_id, manifest)
        return get_assessment(applicant_id, required)


def _write_manifest(applicant_id: str, manifest: Mapping[str, Any]) -> None:
    path = _manifest_path(applicant_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(".json.tmp")
        temporary_path.write_text(
            json.dumps(dict(manifest), separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8",
        )
        temporary_path.replace(path)
    except OSError as error:
        raise KycStateError("KYC review state could not be saved.") from error


def _safe_stored_path(applicant_id: str, stored_name: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}\.(?:png|jpg|pdf)", stored_name):
        raise KycStateError("Stored KYC review state has an invalid file reference.")
    root = _applicant_upload_dir(applicant_id).resolve()
    path = (root / stored_name).resolve()
    if path.parent != root:
        raise KycStateError("Stored KYC review state has an invalid file reference.")
    return path


def _stored_document(
    applicant_id: str,
    document_type: KycDocumentType,
    manifest: Mapping[str, Any] | None = None,
) -> tuple[Path, dict[str, Any]] | None:
    current = manifest or _read_manifest(applicant_id)
    metadata = current["documents"].get(document_type.value)
    if isinstance(metadata, dict) and metadata.get("stored_name"):
        path = _safe_stored_path(applicant_id, str(metadata["stored_name"]))
        if path.is_file():
            return path, metadata
    sample_path = _sample_path(applicant_id, document_type)
    if sample_path.is_file():
        sample_metadata = {
            "validation": "NOT_REVIEWED",
            "source": "SAMPLE",
            "content_type": "image/png",
            "size_bytes": sample_path.stat().st_size,
            "processing_status": "NOT_STARTED",
        }
        if (
            isinstance(metadata, dict)
            and metadata.get("source") in {None, "SAMPLE"}
            and not metadata.get("stored_name")
        ):
            sample_metadata.update(metadata)
            sample_metadata["source"] = "SAMPLE"
            sample_metadata.pop("stored_name", None)
        return sample_path, sample_metadata
    return None


def _validate_upload(content: bytes, content_type: str) -> tuple[str, str]:
    if not content:
        raise KycUploadValidationError("The uploaded document is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise KycUploadValidationError("The uploaded document exceeds the 10 MB limit.")
    signature = SUPPORTED_MIME_TYPES.get(content_type)
    if signature is None:
        raise KycUploadValidationError("Upload a PNG, JPEG, or PDF document.")
    extension, expected_signature = signature
    if not content.startswith(expected_signature):
        raise KycUploadValidationError(
            "The file content does not match the selected document format."
        )
    if content_type in {"image/png", "image/jpeg"}:
        try:
            with Image.open(BytesIO(content)) as image:
                image_format = image.format
                width, height = image.size
                if width * height > MAX_IMAGE_PIXELS:
                    raise KycUploadValidationError(
                        "The uploaded image dimensions exceed the supported limit."
                    )
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as error:
            raise KycUploadValidationError(
                "The uploaded image is corrupted or unreadable."
            ) from error
        expected_format = "PNG" if content_type == "image/png" else "JPEG"
        if image_format != expected_format:
            raise KycUploadValidationError(
                "The file content does not match the selected document format."
            )
        return extension, content_type
    try:
        document = pdfium.PdfDocument(content)
        page_count = len(document)
        document.close()
    except Exception as error:
        raise KycUploadValidationError(
            "The uploaded PDF is corrupted, encrypted, or unreadable."
        ) from error
    if page_count < 1:
        raise KycUploadValidationError("The PDF contains no pages.")
    if page_count > MAX_PDF_PAGES:
        raise KycUploadValidationError(
            f"The PDF has more than the supported {MAX_PDF_PAGES} pages."
        )
    if b"%%EOF" not in content[-2048:]:
        raise KycUploadValidationError("The uploaded PDF is incomplete.")
    return extension, content_type


def _powershell_executable() -> str:
    return os.getenv("UDYAMONE_POWERSHELL", "powershell.exe")


def _run_windows_ocr(paths: list[Path]) -> list[dict[str, Any]]:
    if not paths:
        return []
    if os.name != "nt":
        raise KycOcrError(
            "Local OCR requires Windows 10 or later with an OCR language installed."
        )
    payload = json.dumps([str(path.resolve()) for path in paths])
    try:
        result = subprocess.run(
            [
                _powershell_executable(),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(WINDOWS_OCR_SCRIPT),
            ],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=OCR_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise KycOcrError("Local OCR exceeded its processing time limit.") from error
    except OSError as error:
        raise KycOcrError(
            "Windows PowerShell or the local OCR language engine is unavailable."
        ) from error
    if result.returncode != 0:
        raise KycOcrError("The local OCR engine could not process the document.")
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise KycOcrError("The local OCR engine returned an invalid result.") from error
    if not isinstance(response, dict) or not response.get("engine_available"):
        raise KycOcrError(
            "No Windows OCR language engine is available for the current user."
        )
    results = response.get("results")
    if not isinstance(results, list) or len(results) != len(paths):
        raise KycOcrError("The local OCR engine returned an incomplete result.")
    return results


def _normalise_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text.replace("\r", "\n"))


def _normalise_identifier(value: str) -> str:
    return re.sub(r"[\s-]", "", value).upper()


def _is_udyam_specimen(text: str) -> bool:
    normalised = re.sub(r"\s+", " ", text.upper())
    return (
        "SPECIMEN" in normalised
        and "UDYAM REGISTRATION CERTIFICATE" in normalised
        and "HACKATHON OCR TESTING" in normalised
    )


def _recognize_udyam_number_row(path: Path) -> str:
    try:
        with Image.open(path) as image:
            width, height = image.size
            row = image.crop(
                (
                    round(width * 0.40),
                    round(height * 0.125),
                    round(width * 0.92),
                    round(height * 0.18),
                )
            ).resize(
                (round(width * 0.52 * 3), round(height * 0.055 * 3)),
                Image.Resampling.LANCZOS,
            )
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise KycUploadValidationError(
            "The Udyam specimen registration-number region could not be read."
        ) from error

    with tempfile.TemporaryDirectory(prefix="udyam-number-ocr-") as directory:
        row_path = Path(directory) / "registration-row.png"
        row.save(row_path, format="PNG")
        result = _run_windows_ocr([row_path])[0]
    if result.get("status") == "FAILED":
        raise KycOcrError("The local OCR engine could not read the Udyam number row.")
    return str(result.get("text", ""))


def _gst_name_crop(image: Image.Image, row: str, angle: int, fallback: bool) -> Image.Image:
    rotated = image.rotate(
        angle,
        resample=Image.Resampling.BICUBIC,
        expand=False,
        fillcolor="white",
    )
    width, height = rotated.size
    bounds = {
        ("legal_name", False): (0.175, 0.215),
        ("trade_name", False): (0.215, 0.255),
        ("legal_name", True): (0.17, 0.235),
        ("trade_name", True): (0.215, 0.265),
    }
    top, bottom = bounds[(row, fallback)]
    crop = rotated.crop(
        (round(width * 0.40), round(height * top), round(width * 0.98), round(height * bottom))
    )
    crop = ImageEnhance.Contrast(crop).enhance(1.7)
    crop = crop.filter(ImageFilter.UnsharpMask(radius=2, percent=180, threshold=3))
    scale = 3 if fallback else 4
    return crop.resize(
        (crop.width * scale, crop.height * scale),
        Image.Resampling.LANCZOS,
    )


def _clean_gst_name_row(text: str) -> str | None:
    value = re.sub(r"\s+", " ", text).strip(" \t:;,.|")
    value = re.sub(
        r"(?i)^(?:legal\s+name\s+of\s+business|legal\s+name|trade\s+name)"
        r"\s*[:\-|]?\s*",
        "",
        value,
    )
    if "\ufffd" in value:
        return None
    tokens = value.split()
    if tokens and re.fullmatch(r"[A-Z0-9]{15}", tokens[0], re.IGNORECASE):
        value = " ".join(tokens[1:])
    words = re.findall(r"[A-Za-z][A-Za-z'.&()-]*", value)
    normalised_words = [word.casefold().strip("'.&()-") for word in words]
    if (
        len(words) < 2
        or any(not word for word in normalised_words)
        or len(normalised_words) != len(set(normalised_words))
        or any(
            word in {"gstin", "specimen", "certificate"}
            for word in normalised_words
        )
        or "principal place of business" in value.casefold()
    ):
        return None
    return value


def _recognize_gst_name_rows(path: Path) -> tuple[str | None, str | None]:
    try:
        with Image.open(path) as source:
            base_rows = {
                row: _gst_name_crop(source, row, 0, False)
                for row in ("legal_name", "trade_name")
            }
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise KycUploadValidationError(
            "The GST specimen name region could not be read."
        ) from error

    def recognize(rows: Mapping[str, Image.Image]) -> dict[str, str | None]:
        with tempfile.TemporaryDirectory(prefix="gst-name-ocr-") as directory:
            paths: list[Path] = []
            names: list[str] = []
            for name, image in rows.items():
                image_path = Path(directory) / f"{name}.png"
                image.save(image_path, format="PNG")
                paths.append(image_path)
                names.append(name)
            results = _run_windows_ocr(paths)
        if any(result.get("status") == "FAILED" for result in results):
            raise KycOcrError("The local OCR engine could not read the GST name rows.")
        return {
            name: _clean_gst_name_row(str(result.get("text", "")))
            for name, result in zip(names, results)
        }

    recognized = recognize(base_rows)
    missing_rows = [name for name, value in recognized.items() if value is None]
    if missing_rows:
        fallback_rows: dict[str, Image.Image] = {}
        try:
            with Image.open(path) as source:
                for name in missing_rows:
                    for angle in (5, 7, 10):
                        fallback_rows[f"{name}-{angle}"] = _gst_name_crop(
                            source, name, angle, True
                        )
        except (UnidentifiedImageError, OSError, ValueError) as error:
            raise KycUploadValidationError(
                "The GST specimen name region could not be read."
            ) from error
        candidates = recognize(fallback_rows)
        for name in missing_rows:
            values = [
                value
                for candidate_name, value in candidates.items()
                if candidate_name.startswith(f"{name}-") and value is not None
            ]
            if values:
                normalized = [value.casefold() for value in values]
                winner = max(normalized, key=normalized.count)
                if normalized.count(winner) > len(normalized) / 2:
                    recognized[name] = next(
                        value for value in values if value.casefold() == winner
                    )
    return recognized.get("legal_name"), recognized.get("trade_name")


_DOCUMENT_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
)


def _assess_address_proof_recency(
    document_date: str | None,
    reference_date: date = KYC_REFERENCE_DATE,
) -> KycRecencyStatus:
    if not document_date:
        return KycRecencyStatus.INCONCLUSIVE
    parsed_date = None
    for date_format in _DOCUMENT_DATE_FORMATS:
        try:
            parsed_date = datetime.strptime(document_date.strip(), date_format).date()
            break
        except ValueError:
            continue
    if parsed_date is None or parsed_date > reference_date:
        return KycRecencyStatus.INCONCLUSIVE
    age_days = (reference_date - parsed_date).days
    return (
        KycRecencyStatus.VALID
        if age_days <= KYC_ADDRESS_PROOF_MAX_AGE_DAYS
        else KycRecencyStatus.EXPIRED
    )


def _is_gst_specimen(text: str) -> bool:
    normalised = re.sub(r"\s+", " ", text.upper())
    return "GSTIN" in normalised and (
        "SPECIMEN" in normalised or "HACKATHON OCR TESTING" in normalised
    )


def _is_known_sample(path: Path, document_type: KycDocumentType) -> bool:
    resolved = path.resolve()
    return (
        resolved.parent.parent == SAMPLE_KYC_ROOT.resolve()
        and resolved.name == f"{resolved.parent.name}_{document_type.value}.png"
    )


def _recognize_gst_number_row(path: Path) -> str:
    try:
        with Image.open(path) as image:
            width, height = image.size
            row = image.crop((0, 0, width, round(height * 0.20))).resize(
                (width * 3, round(height * 0.20) * 3),
                Image.Resampling.LANCZOS,
            )
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise KycUploadValidationError(
            "The GST specimen registration-number region could not be read."
        ) from error

    with tempfile.TemporaryDirectory(prefix="gst-number-ocr-") as directory:
        row_path = Path(directory) / "registration-row.png"
        row.save(row_path, format="PNG")
        result = _run_windows_ocr([row_path])[0]
    if result.get("status") == "FAILED":
        raise KycOcrError("The local OCR engine could not read the GST number row.")
    return str(result.get("text", ""))


def _field(
    name: str,
    label: str,
    value: str | None,
    confidence: float | None = None,
    status: KycFieldStatus | None = None,
    flags: list[str] | None = None,
) -> KycExtractedField:
    return KycExtractedField(
        name=name,
        label=label,
        value=value.strip() if value else None,
        original_value=value.strip() if value else None,
        confidence=confidence,
        status=status or (
            KycFieldStatus.EXTRACTED if value else KycFieldStatus.MISSING
        ),
        flags=flags or [],
    )


def _label_value(
    text: str,
    labels: tuple[str, ...],
    stop_labels: tuple[str, ...] = (),
) -> str | None:
    normalised = re.sub(r"\s+", " ", text)
    label_pattern = "|".join(
        re.escape(label) for label in sorted(labels, key=len, reverse=True)
    )
    match = re.search(
        rf"(?i)(?<![A-Z0-9])(?:{label_pattern})(?![A-Z0-9])\s*(?:[:\-|]\s*)?",
        normalised,
    )
    if not match:
        return None
    value = normalised[match.end():]
    if stop_labels:
        stop_pattern = "|".join(
            re.escape(label) for label in sorted(stop_labels, key=len, reverse=True)
        )
        stop_match = re.search(
            rf"(?i)(?<![A-Z0-9])(?:{stop_pattern})(?![A-Z0-9])",
            value,
        )
        if stop_match:
            value = value[:stop_match.start()]
    value = value.strip(" :-|,;")
    return value or None


def _extract_address(
    text: str,
    labels: tuple[str, ...],
    stop_labels: tuple[str, ...] = (),
) -> str | None:
    value = _label_value(text, labels, stop_labels)
    return re.sub(r"\s+", " ", value).strip(" :-|\n") if value else None


def _validate_gstin(value: str | None) -> KycFieldStatus:
    if not value:
        return KycFieldStatus.MISSING
    return (
        KycFieldStatus.EXTRACTED
        if GSTIN_PATTERN.fullmatch(_normalise_identifier(value))
        else KycFieldStatus.INVALID_FORMAT
    )


def _validate_udyam(value: str | None) -> KycFieldStatus:
    if not value:
        return KycFieldStatus.MISSING
    return (
        KycFieldStatus.EXTRACTED
        if UDYAM_PATTERN.fullmatch(_normalise_identifier(value))
        else KycFieldStatus.INVALID_FORMAT
    )


def _extract_gstin_candidate(text: str, specimen_row: bool = False) -> str | None:
    if specimen_row:
        candidates = re.findall(
            r"(?i)(?<![A-Z0-9])[A-Z0-9]{15}(?![A-Z0-9])",
            text,
        )
        if (
            len(candidates) == 1
            and candidates[0][:2].isdigit()
            and any(character.isalpha() for character in candidates[0])
        ):
            return candidates[0].upper()
        return None
    valid_match = GSTIN_PATTERN.search(text)
    if valid_match:
        return valid_match.group().upper()
    labelled_value = _label_value(
        text,
        ("GSTIN/UIN", "GST Identification Number", "GSTIN"),
        (
            "Legal Name of Business",
            "Legal Name",
            "Name of Business",
            "Trade Name",
            "Principal Place of Business",
            "Registered Address",
        ),
    )
    if not labelled_value:
        return None
    candidate = _normalise_identifier(labelled_value)
    return candidate if len(candidate) <= 15 else None


def _parse_udyam_candidate(
    text: str,
    documented_specimen_format: bool,
) -> tuple[str | None, KycFieldStatus, list[str]]:
    matches = list(UDYAM_CANDIDATE_PATTERN.finditer(text))
    if len(matches) != 1:
        if matches:
            return (
                None,
                KycFieldStatus.LOW_CONFIDENCE,
                ["Multiple registration-number candidates need manual confirmation."],
            )
        return (
            None,
            KycFieldStatus.MISSING,
            ["Registration number not legible; manual confirmation is required."],
        )

    state, district, serial = (group.upper() for group in matches[0].groups())
    flags: list[str] = []
    status = KycFieldStatus.EXTRACTED
    if district in {"OO", "O0", "0O"} and documented_specimen_format:
        district = "00"
        status = KycFieldStatus.LOW_CONFIDENCE
        flags.append(
            "OCR confused the documented specimen district code 00; confirm the number against the document."
        )
    elif not district.isdigit():
        return (
            f"UDYAM{state}{district}{serial}",
            KycFieldStatus.LOW_CONFIDENCE,
            ["District-code characters are ambiguous; correct the number manually."],
        )

    number = f"UDYAM{state}{district}{serial}"
    if not serial.isdigit():
        return (
            number,
            KycFieldStatus.LOW_CONFIDENCE,
            ["Serial-number characters are ambiguous; correct the number manually."],
        )
    if _validate_udyam(number) is not KycFieldStatus.EXTRACTED:
        return (
            number,
            KycFieldStatus.INVALID_FORMAT,
            ["The extracted number does not match the documented format."],
        )
    return number, status, flags


def _classification(text: str) -> KycDocumentType | None:
    normalised = text.upper()
    scores = {
        KycDocumentType.GST_CERTIFICATE: sum(
            token in normalised for token in ("GSTIN", "GOODS AND SERVICES TAX", "GST REGISTRATION")
        ),
        KycDocumentType.UDYAM_CERTIFICATE: sum(
            token in normalised for token in ("UDYAM", "MSME REGISTRATION", "UDYAM REGISTRATION")
        ),
        KycDocumentType.SIGNATORY_ID: sum(
            token in normalised
            for token in (
                "AADHAAR",
                "PASSPORT",
                "DRIVING LICENCE",
                "VOTER ID",
                "AUTHORISED SIGNATORY",
                "AUTHORIZED SIGNATORY",
                "SIGNATORY ID",
            )
        ),
        KycDocumentType.ADDRESS_PROOF: sum(
            token in normalised for token in ("ELECTRICITY BILL", "UTILITY BILL", "ADDRESS PROOF", "BANK STATEMENT")
        ),
    }
    winner = max(scores, key=scores.get)
    return winner if scores[winner] else None


def _profile_mismatch_warnings(
    fields: list[KycExtractedField],
    profile: Mapping[str, Any],
) -> list[str]:
    warnings: list[str] = []
    expected_name = profile.get("business_name")
    actual_name = next(
        (
            field.value
            for field in fields
            if field.name in {"legal_name", "enterprise_name", "signatory_name", "holder_name"}
            and field.value
        ),
        None,
    )
    if expected_name and actual_name and _normalise_identifier(str(expected_name)) != _normalise_identifier(actual_name):
        warnings.append("Extracted name differs from the submitted business name.")
    expected_address = profile.get("business_address")
    actual_address = next(
        (
            field.value
            for field in fields
            if field.name in {"registered_address", "address"} and field.value
        ),
        None,
    )
    if expected_address and actual_address:
        expected_tokens = set(re.findall(r"[A-Z0-9]+", str(expected_address).upper()))
        actual_tokens = set(re.findall(r"[A-Z0-9]+", actual_address.upper()))
        if expected_tokens and len(expected_tokens & actual_tokens) / len(expected_tokens) < 0.5:
            warnings.append(
                "Extracted address may differ from the submitted business address."
            )
    return warnings


def _extract_fields(
    document_type: KycDocumentType,
    text: str,
    confidence: float | None,
    profile: Mapping[str, Any],
    udyam_number_text: str | None = None,
    documented_udyam_format: bool = False,
    gstin_value_text: str | None = None,
    gst_name_rows: tuple[str | None, str | None] | None = None,
) -> tuple[
    list[KycExtractedField],
    list[str],
    list[str],
    list[str],
    list[str],
    list[str],
]:
    text = _normalise_text(text)
    fields: list[KycExtractedField] = []
    if document_type is KycDocumentType.GST_CERTIFICATE:
        gstin = _extract_gstin_candidate(
            text if gstin_value_text is None else gstin_value_text,
            specimen_row=gstin_value_text is not None,
        )
        gstin_status = _validate_gstin(gstin)
        gstin_flags = (
            ["GSTIN format is unclear; verify the extracted characters manually."]
            if gstin_status is KycFieldStatus.INVALID_FORMAT
            else []
        )
        fields.extend(
            [
                _field(
                    "gstin",
                    "GSTIN",
                    gstin,
                    confidence,
                    gstin_status,
                    gstin_flags,
                ),
                _field(
                    "legal_name",
                    "Legal name",
                    (
                        gst_name_rows[0]
                        if gst_name_rows is not None
                        else _label_value(
                            text,
                            ("Legal Name of Business", "Legal Name", "Name of Business"),
                            ("Trade Name", "Principal Place of Business", "GSTIN/UIN", "GSTIN"),
                        )
                    ),
                    confidence,
                ),
                _field(
                    "trade_name",
                    "Trade name",
                    (
                        gst_name_rows[1]
                        if gst_name_rows is not None
                        else _label_value(
                            text,
                            ("Trade Name",),
                            ("Principal Place of Business", "GSTIN/UIN", "GSTIN"),
                        )
                    ),
                    confidence,
                ),
                _field(
                    "registered_address",
                    "Registered address",
                    _extract_address(
                        text,
                        ("Principal Place of Business", "Registered Address", "Address"),
                        ("GSTIN/UIN", "GSTIN", "Legal Name", "Trade Name"),
                    ),
                    confidence,
                ),
            ]
        )
    elif document_type is KycDocumentType.UDYAM_CERTIFICATE:
        udyam_source = text if udyam_number_text is None else udyam_number_text
        udyam, udyam_status, udyam_flags = _parse_udyam_candidate(
            udyam_source,
            documented_udyam_format,
        )
        if udyam_number_text is None and udyam_status is KycFieldStatus.MISSING:
            udyam = _label_value(
                text,
                ("Udyam Registration Number", "Udyam Registration No"),
                ("Name of Enterprise", "Enterprise Name", "Date of Registration"),
            )
            udyam_status = _validate_udyam(udyam)
            udyam_flags = (
                []
                if udyam
                else ["Registration number not legible; manual confirmation is required."]
            )
        fields.extend(
            [
                _field(
                    "udyam_number",
                    "Udyam registration number",
                    udyam,
                    confidence,
                    udyam_status,
                    udyam_flags,
                ),
                _field(
                    "enterprise_name",
                    "Enterprise name",
                    _label_value(
                        text,
                        ("Name of Enterprise", "Enterprise Name", "Name of the Enterprise"),
                        ("Udyam Registration", "Registration Date", "Enterprise Type"),
                    ),
                    confidence,
                ),
                _field(
                    "registration_date",
                    "Registration date",
                    _label_value(
                        text,
                        ("Date of Commencement", "Date of Registration", "Registration Date"),
                        ("Enterprise Type", "Name of Enterprise", "Udyam Registration"),
                    ),
                    confidence,
                ),
                _field(
                    "enterprise_type",
                    "Enterprise type",
                    _label_value(
                        text,
                        ("Enterprise Type", "Organisation Type", "Organization Type"),
                        ("Udyam Registration", "Date of Commencement"),
                    ),
                    confidence,
                ),
            ]
        )
    elif document_type is KycDocumentType.SIGNATORY_ID:
        fields.extend(
            [
                _field(
                    "signatory_name",
                    "Signatory name",
                    _label_value(
                        text,
                        (
                            "Authorised Signatory Name",
                            "Authorized Signatory Name",
                            "Name of Authorised Signatory",
                            "Name of Authorized Signatory",
                            "Name of Holder",
                            "Name of Person",
                            "Name",
                        ),
                        ("ID Number", "Document Number", "Date of Birth", "Signature"),
                    ),
                    confidence,
                ),
            ]
        )
    else:
        fields.extend(
            [
                _field(
                    "holder_name",
                    "Name or entity",
                    _label_value(
                        text,
                        (
                            "Name of Consumer",
                            "Consumer Name",
                            "Customer Name",
                            "Account Holder",
                            "Consumer",
                        ),
                        ("Address", "Bill Date", "Consumer Number", "Account Number"),
                    ),
                    confidence,
                ),
                _field(
                    "address",
                    "Address",
                    _extract_address(
                        text,
                        ("Service Address", "Billing Address", "Installation Address", "Address"),
                        ("Bill Date", "Consumer Number", "Account Number", "Customer Care"),
                    ),
                    confidence,
                ),
                _field(
                    "document_date",
                    "Document date",
                    _label_value(
                        text,
                        ("Bill Date", "Statement Date", "Date of Issue", "Document Date"),
                        ("Consumer Number", "Account Number", "Address"),
                    ),
                    confidence,
                ),
            ]
        )

    missing = [field.name for field in fields if field.status is KycFieldStatus.MISSING]
    invalid = [
        field.name for field in fields if field.status is KycFieldStatus.INVALID_FORMAT
    ]
    low_confidence = [
        field.name
        for field in fields
        if field.status is KycFieldStatus.LOW_CONFIDENCE
        or (field.confidence is not None and field.confidence < 0.6)
    ]
    mismatch_warnings = _profile_mismatch_warnings(fields, profile)
    if confidence is None:
        for field_index, item in enumerate(fields):
            flags = list(item.flags)
            flags.append("OCR engine does not provide confidence scores.")
            fields[field_index] = item.model_copy(
                update={"flags": flags}
            )
    required_names = {
        KycDocumentType.GST_CERTIFICATE: [
            "gstin",
            "legal_name",
            "registered_address",
        ],
        KycDocumentType.UDYAM_CERTIFICATE: [
            "udyam_number",
            "enterprise_name",
        ],
        KycDocumentType.SIGNATORY_ID: [
            "signatory_name",
        ],
        KycDocumentType.ADDRESS_PROOF: [
            "holder_name",
            "address",
            "document_date",
        ],
    }[document_type]
    return fields, required_names, missing, invalid, low_confidence, mismatch_warnings


def _address_proof_recency_message(status: KycRecencyStatus) -> str:
    if status is KycRecencyStatus.VALID:
        return "Document date is within 90 days of 15 July 2026."
    if status is KycRecencyStatus.EXPIRED:
        return "Document date is more than 90 days before 15 July 2026."
    return "Document date is missing, unparseable, or after 15 July 2026; confirm it manually."


def _registry_context(
    applicant_id: str,
    manifest: Mapping[str, Any],
) -> tuple[str | None, str | None, dict[str, str | None], bool]:
    profile = manifest.get("profile", {})
    business_name = (
        profile.get("business_name") if isinstance(profile, Mapping) else None
    )
    city = profile.get("business_address") if isinstance(profile, Mapping) else None
    self_reported_gstin = False
    if applicant_id.startswith("APPL-"):
        try:
            applicant = applicant_service.get_applicant(applicant_id)
        except applicant_service.ApplicantNotFoundError:
            pass
        else:
            business_name = applicant.profile.business_name
            city = applicant.profile.city
            self_reported_gstin = (
                applicant.profile.gstin_self_reported_status == "Verified"
            )
    values = _registry_document_values(manifest)
    if not business_name:
        business_name = (
            values.get("gst_legal_name")
            or values.get("gst_trade_name")
            or values.get("udyam_enterprise_name")
        )
    return business_name, city, values, self_reported_gstin


def get_registry_verification_context(
    applicant_id: str,
) -> tuple[str | None, str | None, dict[str, str | None], bool]:
    validate_applicant_id(applicant_id)
    return _registry_context(applicant_id, _read_manifest(applicant_id))


def _extract_pdf_text(path: Path) -> tuple[str, list[Image.Image], list[str]]:
    try:
        document = pdfium.PdfDocument(str(path))
    except Exception as error:
        raise KycUploadValidationError(
            "The uploaded PDF is corrupted, encrypted, or unreadable."
        ) from error
    pages = len(document)
    if pages < 1 or pages > MAX_PDF_PAGES:
        document.close()
        raise KycUploadValidationError(
            f"The PDF must contain between 1 and {MAX_PDF_PAGES} pages."
        )
    text_parts: list[str] = []
    rendered_pages: list[Image.Image] = []
    text_by_page: list[str] = []
    try:
        for page_index in range(pages):
            page = document[page_index]
            textpage = page.get_textpage()
            page_text = textpage.get_text_range()
            text_by_page.append(page_text)
            if len(page_text.strip()) < 20:
                page_width, page_height = page.get_size()
                if page_width * page_height * 4 > MAX_IMAGE_PIXELS:
                    raise KycUploadValidationError(
                        "The PDF page dimensions exceed the supported limit."
                    )
                rendered_pages.append(page.render(scale=2).to_pil().convert("RGB"))
            text_parts.append(page_text)
    except KycUploadValidationError:
        raise
    except Exception as error:
        raise KycUploadValidationError(
            "The PDF page data could not be read or rendered."
        ) from error
    finally:
        document.close()
    return "\n".join(text_parts), rendered_pages, text_by_page


def _process_document_path(
    document_type: KycDocumentType,
    path: Path,
    metadata: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> KycExtraction:
    confidence: float | None = None
    text = ""
    udyam_number_text: str | None = None
    gstin_value_text: str | None = None
    gst_name_rows: tuple[str | None, str | None] | None = None
    try:
        content_type = metadata.get("content_type")
        if content_type == "application/pdf":
            selectable_text, rendered_pages, text_by_page = _extract_pdf_text(path)
            if rendered_pages:
                with tempfile.TemporaryDirectory(
                    prefix="udyam-ocr-",
                    dir=str(UPLOAD_ROOT),
                ) as temporary_directory:
                    image_paths: list[Path] = []
                    render_index = 0
                    for page_text in text_by_page:
                        if len(page_text.strip()) < 20:
                            image_path = Path(temporary_directory) / f"page-{render_index}.png"
                            rendered_pages[render_index].save(image_path, format="PNG")
                            image_paths.append(image_path)
                            render_index += 1
                    results = _run_windows_ocr(image_paths)
                ocr_text = "\n".join(
                    str(item.get("text", ""))
                    for item in results
                    if item.get("status") == "SUCCEEDED"
                )
                if any(item.get("status") == "FAILED" for item in results):
                    return KycExtraction(
                        processing_status=KycProcessingStatus.FAILED,
                        error_code="OCR_FAILED",
                    )
                text = "\n".join(part for part in (selectable_text, ocr_text) if part.strip())
                confidence_values = [
                    item.get("confidence")
                    for item in results
                    if isinstance(item.get("confidence"), (int, float))
                ]
                confidence = (
                    sum(confidence_values) / len(confidence_values)
                    if confidence_values
                    else None
                )
                if not ocr_text.strip() and not selectable_text.strip():
                    return KycExtraction(
                        processing_status=KycProcessingStatus.UNREADABLE,
                        detected_document_type=None,
                        classification_matches_category=None,
                        error_code="NO_TEXT_DETECTED",
                    )
            else:
                text = selectable_text
        else:
            results = _run_windows_ocr([path])
            result = results[0]
            if result.get("status") == "FAILED":
                return KycExtraction(
                    processing_status=KycProcessingStatus.FAILED,
                    error_code="OCR_FAILED",
                )
            text = str(result.get("text", ""))
            confidence_value = result.get("confidence")
            confidence = (
                float(confidence_value)
                if isinstance(confidence_value, (int, float))
                else None
            )
            if not text.strip():
                return KycExtraction(
                    processing_status=KycProcessingStatus.UNREADABLE,
                    error_code="NO_TEXT_DETECTED",
                )
            if (
                document_type is KycDocumentType.UDYAM_CERTIFICATE
                and _is_udyam_specimen(text)
            ):
                udyam_number_text = _recognize_udyam_number_row(path)
            if (
                document_type is KycDocumentType.GST_CERTIFICATE
                and (
                    _is_gst_specimen(text)
                    or _is_known_sample(path, KycDocumentType.GST_CERTIFICATE)
                )
            ):
                gstin_value_text = _recognize_gst_number_row(path)
                gst_name_rows = _recognize_gst_name_rows(path)
    except KycUploadValidationError as error:
        return KycExtraction(
            processing_status=KycProcessingStatus.FAILED,
            error_code=(
                "CORRUPTED_PDF"
                if "PDF" in str(error)
                else "DOCUMENT_UNREADABLE"
            ),
        )
    except KycOcrError as error:
        return KycExtraction(
            processing_status=KycProcessingStatus.FAILED,
            error_code=(
                "OCR_ENGINE_UNAVAILABLE"
                if "available" in str(error).lower()
                else "OCR_FAILED"
            ),
        )
    if not text.strip():
        return KycExtraction(
            processing_status=KycProcessingStatus.UNREADABLE,
            error_code="NO_TEXT_DETECTED",
        )

    detected_type = _classification(text)
    fields, required_fields, missing, invalid, low_confidence, mismatches = _extract_fields(
        document_type,
        text,
        confidence,
        profile,
        udyam_number_text,
        _is_udyam_specimen(text),
        gstin_value_text,
        gst_name_rows,
    )
    address_proof_recency = None
    if document_type is KycDocumentType.ADDRESS_PROOF:
        document_date = next(
            (field.value for field in fields if field.name == "document_date"),
            None,
        )
        address_proof_recency = _assess_address_proof_recency(document_date)
        date_field = next(
            (field for field in fields if field.name == "document_date"),
            None,
        )
        if date_field is not None:
            updated_flags = [
                flag for flag in date_field.flags
                if not flag.startswith("Document date ")
            ]
            updated_flags.append(_address_proof_recency_message(address_proof_recency))
            if (
                address_proof_recency is KycRecencyStatus.INCONCLUSIVE
                and date_field.value
            ):
                fields = [
                    field.model_copy(
                        update={
                            "status": KycFieldStatus.INVALID_FORMAT,
                            "flags": updated_flags,
                        }
                    )
                    if field.name == "document_date"
                    else field
                    for field in fields
                ]
            else:
                fields = [
                    field.model_copy(update={"flags": updated_flags})
                    if field.name == "document_date"
                    else field
                    for field in fields
                ]
            missing = [field.name for field in fields if field.status is KycFieldStatus.MISSING]
            invalid = [field.name for field in fields if field.status is KycFieldStatus.INVALID_FORMAT]
            low_confidence = [
                field.name
                for field in fields
                if field.status is KycFieldStatus.LOW_CONFIDENCE
                or (field.confidence is not None and field.confidence < 0.6)
            ]
    return KycExtraction(
        processing_status=KycProcessingStatus.SUCCEEDED,
        detected_document_type=detected_type,
        classification_matches_category=(
            detected_type is document_type if detected_type is not None else None
        ),
        fields=fields,
        required_fields=required_fields,
        missing_fields=missing,
        invalid_fields=invalid,
        low_confidence_fields=low_confidence,
        mismatch_warnings=mismatches,
        confidence_available=confidence is not None,
        address_proof_recency=address_proof_recency,
        address_proof_reference_date=(
            KYC_REFERENCE_DATE.isoformat()
            if document_type is KycDocumentType.ADDRESS_PROOF
            else None
        ),
    )


def process_document(
    applicant_id: str,
    document_type: KycDocumentType,
) -> KycAssessment:
    validate_applicant_id(applicant_id)
    required = get_required_document_types()
    lock = _lock_for(applicant_id)
    with lock:
        require_current_consent(applicant_id)
        manifest = _read_manifest(applicant_id)
        stored = _stored_document(applicant_id, document_type, manifest)
        if stored is None:
            raise ValueError(f"{document_type.display_name} has not been provided.")
        path, metadata = stored
        metadata["processing_status"] = KycProcessingStatus.PROCESSING.value
        manifest["documents"][document_type.value] = metadata
        _write_manifest(applicant_id, manifest)

        extraction = _process_document_path(
            document_type,
            path,
            metadata,
            manifest.get("profile", {}),
        )
        metadata["processing_status"] = extraction.processing_status.value
        metadata["extraction"] = extraction.model_dump(mode="json")
        manifest["documents"][document_type.value] = metadata
        _write_manifest(applicant_id, manifest)
        return get_assessment(applicant_id, required)


def get_assessment(
    applicant_id: str,
    required_documents: tuple[KycDocumentType, ...] | None = None,
) -> KycAssessment:
    validate_applicant_id(applicant_id)
    required = (
        get_required_document_types()
        if required_documents is None
        else required_documents
    )
    manifest = _read_manifest(applicant_id)
    (
        applicant_name,
        applicant_city,
        registry_inputs,
        self_reported_gstin,
    ) = _registry_context(
        applicant_id, manifest
    )
    registry_results = registry_verification_service.get_persisted_verifications(
        applicant_id,
        applicant_name,
        applicant_city,
        registry_inputs,
    )
    registry_type_by_document: dict[
        KycDocumentType, Literal["GSTIN", "UDYAM"]
    ] = {
        KycDocumentType.GST_CERTIFICATE: "GSTIN",
        KycDocumentType.UDYAM_CERTIFICATE: "UDYAM",
    }
    documents: list[KycDocumentState] = []
    for document_type in KycDocumentType:
        registry_type = registry_type_by_document.get(document_type)
        registry_result = (
            registry_results[registry_type] if registry_type is not None else None
        )
        stored = _stored_document(applicant_id, document_type, manifest)
        metadata = stored[1] if stored else {}
        present = stored is not None
        validation = (
            KycDocumentValidation(metadata.get("validation", "NOT_REVIEWED"))
            if present
            else KycDocumentValidation.NOT_REVIEWED
        )
        extraction_data = metadata.get("extraction")
        try:
            extraction = (
                KycExtraction.model_validate(extraction_data)
                if isinstance(extraction_data, dict)
                else None
            )
            processing_status = KycProcessingStatus(
                metadata.get(
                    "processing_status",
                    extraction.processing_status.value if extraction else "NOT_STARTED",
                )
            )
        except ValueError as error:
            raise KycStateError("Stored KYC extraction state has an invalid format.") from error
        is_uploaded = metadata.get("source") != "SAMPLE" and bool(
            metadata.get("stored_name")
        )
        document_source = (
            "CUSTOMER_UPLOAD"
            if is_uploaded
            else "COMPETITION_SAMPLE"
            if present and metadata.get("source") == "SAMPLE"
            else "NOT_PROVIDED"
        )
        recency_status = (
            (
                extraction.address_proof_recency
                if extraction and extraction.address_proof_recency
                else _assess_address_proof_recency(
                    next(
                        (
                            field.value
                            for field in (extraction.fields if extraction else [])
                            if field.name == "document_date"
                        ),
                        None,
                    )
                )
            )
            if document_type is KycDocumentType.ADDRESS_PROOF and present
            else KycRecencyStatus.NOT_APPLICABLE
        )
        documents.append(
            KycDocumentState(
                document_type=document_type,
                display_name=document_type.display_name,
                presence=(
                    KycDocumentPresence.PROVIDED
                    if present
                    else KycDocumentPresence.NOT_PROVIDED
                ),
                validation=validation,
                registry_verification=(
                    registry_result.status
                    if registry_result is not None
                    else "NOT_CHECKED"
                ),
                document_source=document_source,
                recency_status=recency_status,
                upload_status="UPLOADED" if is_uploaded else "NOT_UPLOADED",
                processing_status=processing_status,
                original_filename=(
                    f"{document_type.value}{Path(str(metadata.get('stored_name', ''))).suffix}"
                    if is_uploaded
                    else None
                ),
                file_size_bytes=metadata.get("size_bytes"),
                content_type=metadata.get("content_type"),
                extraction=extraction,
            )
        )

    states_by_type = {document.document_type: document for document in documents}
    upload_requests = [
        document_type
        for document_type in required
        if states_by_type[document_type].presence
        is KycDocumentPresence.NOT_PROVIDED
    ]
    requested_documents = [
        KycDocumentType(document_type)
        for document_type in manifest["requested_documents"]
    ]
    required_registry_types: list[str] = []
    if applicant_id.startswith("APPL-"):
        if (
            KycDocumentType.GST_CERTIFICATE in required
            or KycDocumentType.GST_CERTIFICATE in requested_documents
            or states_by_type[KycDocumentType.GST_CERTIFICATE].presence
            is KycDocumentPresence.PROVIDED
            or self_reported_gstin
        ):
            required_registry_types.append("GSTIN")
        if (
            KycDocumentType.UDYAM_CERTIFICATE in required
            or KycDocumentType.UDYAM_CERTIFICATE in requested_documents
            or states_by_type[KycDocumentType.UDYAM_CERTIFICATE].presence
            is KycDocumentPresence.PROVIDED
        ):
            required_registry_types.append("UDYAM")
    outstanding_requests = [
        document_type
        for document_type in requested_documents
        if states_by_type[document_type].presence is KycDocumentPresence.NOT_PROVIDED
        or states_by_type[document_type].validation is not KycDocumentValidation.VALID
        or (
            states_by_type[document_type].extraction
            and (
                set(states_by_type[document_type].extraction.invalid_fields)
                | set(states_by_type[document_type].extraction.missing_fields)
                | set(states_by_type[document_type].extraction.low_confidence_fields)
            ).intersection(states_by_type[document_type].extraction.required_fields)
        )
        or (
            document_type is KycDocumentType.ADDRESS_PROOF
            and states_by_type[document_type].recency_status is not KycRecencyStatus.VALID
        )
    ]
    for document_type in outstanding_requests:
        if (
            states_by_type[document_type].presence is KycDocumentPresence.NOT_PROVIDED
            and document_type not in upload_requests
        ):
            upload_requests.append(document_type)
    next_steps = [
        f"Please upload the {document_type.display_name} to continue to final approval."
        for document_type in upload_requests
    ]
    for document_type in dict.fromkeys((*required, *outstanding_requests)):
        state = states_by_type[document_type]
        if (
            state.presence is KycDocumentPresence.PROVIDED
            and state.validation is not KycDocumentValidation.VALID
        ):
            if state.validation is KycDocumentValidation.INVALID:
                next_steps.append(
                    f"Please upload a replacement {state.display_name} before final approval."
                )
            else:
                next_steps.append(
                    f"Review the {state.display_name} before final approval."
                )
        if (
            document_type is KycDocumentType.ADDRESS_PROOF
            and state.presence is KycDocumentPresence.PROVIDED
            and state.recency_status is not KycRecencyStatus.VALID
        ):
            next_steps.append(
                "Confirm that the address-proof date is within 90 days of 15 July 2026."
            )
        if state.extraction:
            required_fields = set(state.extraction.required_fields)
            for name in state.extraction.invalid_fields:
                if name not in required_fields:
                    continue
                next_steps.append(
                    f"Correct the invalid {name.replace('_', ' ')} field in the {state.display_name}."
                )
            for name in state.extraction.missing_fields:
                if name not in required_fields:
                    continue
                next_steps.append(
                    f"Review the missing {name.replace('_', ' ')} field in the {state.display_name}."
                )
            for name in state.extraction.low_confidence_fields:
                if name not in required_fields:
                    continue
                next_steps.append(
                    f"Confirm the {name.replace('_', ' ')} field in the {state.display_name}."
                )
    for registry_type in required_registry_types:
        verification = registry_results[registry_type]
        if verification is None:
            document_type = (
                KycDocumentType.GST_CERTIFICATE
                if registry_type == "GSTIN"
                else KycDocumentType.UDYAM_CERTIFICATE
            )
            state = states_by_type[document_type]
            if (
                state.presence is KycDocumentPresence.PROVIDED
                and state.extraction is not None
            ):
                next_steps.append(
                    f"Run {registry_type} verification against the synthetic competition registry."
                )
            else:
                next_steps.append(
                    f"Upload and process the {state.display_name} before {registry_type} verification."
                )
        elif verification.status is not RegistryVerificationStatus.VERIFIED:
            if verification.status is RegistryVerificationStatus.UNAVAILABLE:
                next_steps.append(
                    f"{registry_type} verification is temporarily unavailable; retry the synthetic registry check."
                )
            elif verification.status is RegistryVerificationStatus.MISMATCH:
                next_steps.append(
                    f"Review the {registry_type} mismatch and correct the relevant applicant or document details."
                )
            else:
                next_steps.append(
                    f"{registry_type} verification is inconclusive; confirm the identifier and business details."
                )
    documents_ready = all(
        states_by_type[document_type].presence is KycDocumentPresence.PROVIDED
        and states_by_type[document_type].validation is KycDocumentValidation.VALID
        and not (
            states_by_type[document_type].extraction
            and (
                set(states_by_type[document_type].extraction.invalid_fields)
                | set(states_by_type[document_type].extraction.missing_fields)
                | set(states_by_type[document_type].extraction.low_confidence_fields)
            ).intersection(states_by_type[document_type].extraction.required_fields)
        )
        and (
            document_type is not KycDocumentType.ADDRESS_PROOF
            or states_by_type[document_type].recency_status is KycRecencyStatus.VALID
        )
        for document_type in dict.fromkeys((*required, *outstanding_requests))
    )
    registries_ready = all(
        registry_results[registry_type] is not None
        and registry_results[registry_type].status
        is RegistryVerificationStatus.VERIFIED
        for registry_type in required_registry_types
    )

    return KycAssessment(
        applicant_id=applicant_id,
        documents=documents,
        required_documents=list(required),
        requested_documents=outstanding_requests,
        upload_requests=upload_requests,
        next_steps=list(dict.fromkeys(next_steps)),
        ready_for_approval=documents_ready and registries_ready,
        consent=_current_consent(manifest),
        gstin_verification=registry_results["GSTIN"],
        udyam_verification=registry_results["UDYAM"],
        required_registry_verifications=required_registry_types,
    )


def save_document(
    applicant_id: str,
    document_type: KycDocumentType,
    content: bytes,
    content_type: str,
) -> KycAssessment:
    validate_applicant_id(applicant_id)
    required = get_required_document_types()
    extension, normalised_content_type = _validate_upload(content, content_type)
    lock = _lock_for(applicant_id)
    with lock:
        require_current_consent(applicant_id)
        manifest = _read_manifest(applicant_id)
        applicant_dir = _applicant_upload_dir(applicant_id)
        try:
            applicant_dir.mkdir(parents=True, exist_ok=True)
            stored_name = f"{uuid.uuid4().hex}{extension}"
            destination = applicant_dir / stored_name
            temporary_path = applicant_dir / f".{uuid.uuid4().hex}.tmp"
            with temporary_path.open("xb") as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            temporary_path.replace(destination)
        except OSError as error:
            raise KycStateError("The uploaded document could not be saved.") from error

        old_metadata = manifest["documents"].get(document_type.value, {})
        safe_source_name = f"{document_type.value}{extension}"
        new_metadata = {
            "source": "UPLOAD",
            "stored_name": stored_name,
            "original_filename": safe_source_name,
            "content_type": normalised_content_type,
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "upload_status": "UPLOADED",
            "processing_status": KycProcessingStatus.NOT_STARTED.value,
            "validation": KycDocumentValidation.NOT_REVIEWED.value,
            "extraction": None,
        }
        manifest["documents"][document_type.value] = new_metadata
        try:
            _write_manifest(applicant_id, manifest)
        except KycStateError:
            destination.unlink(missing_ok=True)
            raise

        previous = old_metadata.get("stored_name") if isinstance(old_metadata, dict) else None
        if previous and previous != stored_name:
            try:
                _safe_stored_path(applicant_id, str(previous)).unlink(missing_ok=True)
            except OSError:
                raise KycStateError(
                    "The replacement was saved, but the prior document could not be removed."
                )
        return get_assessment(applicant_id, required)


def get_document_file(
    applicant_id: str,
    document_type: KycDocumentType,
) -> tuple[Path, str]:
    validate_applicant_id(applicant_id)
    stored = _stored_document(applicant_id, document_type)
    if stored is None:
        raise FileNotFoundError("The requested document is not available.")
    path, metadata = stored
    return path, str(metadata.get("content_type", "application/octet-stream"))


def review_document(
    applicant_id: str,
    document_type: KycDocumentType,
    validation: KycDocumentValidation,
) -> KycAssessment:
    validate_applicant_id(applicant_id)
    required = get_required_document_types()
    if validation is KycDocumentValidation.NOT_REVIEWED:
        raise ValueError("A document review must be VALID or INVALID.")
    lock = _lock_for(applicant_id)
    with lock:
        require_current_consent(applicant_id)
        manifest = _read_manifest(applicant_id)
        stored = _stored_document(applicant_id, document_type, manifest)
        if stored is None:
            raise ValueError(f"{document_type.display_name} has not been provided.")
        metadata = stored[1]
        metadata["validation"] = validation.value
        manifest["documents"][document_type.value] = metadata
        _write_manifest(applicant_id, manifest)
        return get_assessment(applicant_id, required)


def correct_extracted_fields(
    applicant_id: str,
    document_type: KycDocumentType,
    fields: Mapping[str, str | None],
) -> KycAssessment:
    validate_applicant_id(applicant_id)
    required = get_required_document_types()
    lock = _lock_for(applicant_id)
    with lock:
        require_current_consent(applicant_id)
        manifest = _read_manifest(applicant_id)
        metadata = manifest["documents"].get(document_type.value)
        if not isinstance(metadata, dict) or not isinstance(metadata.get("extraction"), dict):
            raise ValueError("The document has no extraction results to correct.")
        extraction = KycExtraction.model_validate(metadata["extraction"])
        extracted = {field.name: field for field in extraction.fields}
        if any(name not in extracted for name in fields):
            raise ValueError("One or more field names cannot be corrected for this document.")
        for name, value in fields.items():
            original = extracted[name]
            normalised = value.strip() if isinstance(value, str) else None
            status = KycFieldStatus.MANUALLY_CORRECTED
            if not normalised:
                status = KycFieldStatus.MISSING
            elif name == "document_date":
                recency = _assess_address_proof_recency(normalised)
                status = (
                    KycFieldStatus.INVALID_FORMAT
                    if recency is KycRecencyStatus.INCONCLUSIVE
                    else KycFieldStatus.MANUALLY_CORRECTED
                )
            elif name == "gstin":
                status = (
                    KycFieldStatus.MANUALLY_CORRECTED
                    if _validate_gstin(normalised) is KycFieldStatus.EXTRACTED
                    else KycFieldStatus.INVALID_FORMAT
                )
            elif name == "udyam_number":
                status = (
                    KycFieldStatus.MANUALLY_CORRECTED
                    if _validate_udyam(normalised) is KycFieldStatus.EXTRACTED
                    else KycFieldStatus.INVALID_FORMAT
                )
            extracted[name] = original.model_copy(
                update={
                    "value": normalised,
                    "corrected_value": normalised,
                    "correction_applied": True,
                    "status": status,
                    "flags": ["Manually corrected"],
                }
            )
        corrected_fields = list(extracted.values())
        address_proof_recency = extraction.address_proof_recency
        if document_type is KycDocumentType.ADDRESS_PROOF:
            corrected_date = next(
                (field.value for field in corrected_fields if field.name == "document_date"),
                None,
            )
            address_proof_recency = _assess_address_proof_recency(corrected_date)
            date_field = next(
                (field for field in corrected_fields if field.name == "document_date"),
                None,
            )
            if date_field is not None:
                date_flags = [
                    flag for flag in date_field.flags
                    if not flag.startswith("Document date ")
                ]
                date_flags.append(
                    _address_proof_recency_message(address_proof_recency)
                )
                corrected_fields = [
                    field.model_copy(update={"flags": date_flags})
                    if field.name == "document_date"
                    else field
                    for field in corrected_fields
                ]
        invalid = [
            item.name for item in corrected_fields
            if item.status is KycFieldStatus.INVALID_FORMAT
        ]
        missing = [
            item.name for item in corrected_fields
            if item.status is KycFieldStatus.MISSING
        ]
        low = [
            item.name for item in corrected_fields
            if item.status is KycFieldStatus.LOW_CONFIDENCE
        ]
        metadata["extraction"] = extraction.model_copy(
            update={
                "fields": corrected_fields,
                "invalid_fields": invalid,
                "missing_fields": missing,
                "low_confidence_fields": low,
                "address_proof_recency": address_proof_recency,
                "address_proof_reference_date": (
                    KYC_REFERENCE_DATE.isoformat()
                    if document_type is KycDocumentType.ADDRESS_PROOF
                    else extraction.address_proof_reference_date
                ),
                "mismatch_warnings": _profile_mismatch_warnings(
                    corrected_fields,
                    manifest.get("profile", {}),
                ),
            }
        ).model_dump(mode="json")
        manifest["documents"][document_type.value] = metadata
        _write_manifest(applicant_id, manifest)
        return get_assessment(applicant_id, required)


def set_applicant_profile(
    applicant_id: str,
    business_name: str | None,
    business_address: str | None,
) -> KycAssessment:
    validate_applicant_id(applicant_id)
    required = get_required_document_types()
    lock = _lock_for(applicant_id)
    with lock:
        manifest = _read_manifest(applicant_id)
        manifest["profile"] = {
            "business_name": business_name.strip() if business_name else None,
            "business_address": business_address.strip() if business_address else None,
        }
        for document_metadata in manifest["documents"].values():
            if not isinstance(document_metadata, dict):
                continue
            extraction_data = document_metadata.get("extraction")
            if not isinstance(extraction_data, dict):
                continue
            extraction = KycExtraction.model_validate(extraction_data)
            document_metadata["extraction"] = extraction.model_copy(
                update={
                    "mismatch_warnings": _profile_mismatch_warnings(
                        extraction.fields,
                        manifest["profile"],
                    )
                }
            ).model_dump(mode="json")
        _write_manifest(applicant_id, manifest)
        return get_assessment(applicant_id, required)


def finalize_applicant(applicant_id: str) -> KycAssessment:
    assessment = get_assessment(applicant_id)
    if not assessment.ready_for_approval:
        instructions = " ".join(assessment.next_steps)
        raise ValueError(
            "Final approval is blocked until required documents are provided, "
            f"reviewed, and corrected. {instructions}".strip()
        )
    return assessment
