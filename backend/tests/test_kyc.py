"""KYC document-presence, validation, and approval-gate tests."""

import hashlib
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import kyc_service
from app.security.kyc_auth import (
    create_session_token,
    hash_password,
    load_kyc_auth_configuration,
)

client = TestClient(app)
reviewer_client = TestClient(app)
_customer_password_hash = hash_password("SyntheticCustomerPassword1!")
_reviewer_password_hash = hash_password("SyntheticReviewerPassword1!")


@pytest.fixture(autouse=True)
def configure_kyc_test_sessions(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("UDYAMONE_KYC_AUTH_SECRET", "synthetic-test-signing-secret-not-for-use")
    monkeypatch.setenv(
        "UDYAMONE_KYC_AUTH_USERS",
        (
            '[{"username":"test-customer","role":"CUSTOMER",'
            f'"password_hash":"{_customer_password_hash}","applicant_ids":["K05","K01"]}},'
            '{"username":"test-reviewer","role":"REVIEWER",'
            f'"password_hash":"{_reviewer_password_hash}","applicant_ids":[]}}]'
        ),
    )
    monkeypatch.setattr(kyc_service, "UPLOAD_ROOT", tmp_path)
    configuration = load_kyc_auth_configuration()
    customer_token, _ = create_session_token(
        configuration.accounts["test-customer"], configuration.secret
    )
    reviewer_token, _ = create_session_token(
        configuration.accounts["test-reviewer"], configuration.secret
    )
    client.headers["Authorization"] = f"Bearer {customer_token}"
    reviewer_client.headers["Authorization"] = f"Bearer {reviewer_token}"
    for applicant_id in ("K05", "K01"):
        consent = client.post(
            f"/api/v1/kyc/{applicant_id}/consent", json={"consented": True}
        )
        assert consent.status_code == 200

GST_SAMPLE_TEXT = (
    "GOODS AND SERVICES TAX REGISTRATION\n"
    "GSTIN: 29ABCDE1234F1Z5\n"
    "Legal Name of Business: SAMPLE TRADERS\n"
    "Principal Place of Business: 12 SAMPLE ROAD BENGALURU"
)


def _image_bytes(image_format: str = "PNG", text: str | None = None) -> bytes:
    image = Image.new("RGB", (1100, 360), "white")
    if text:
        ImageDraw.Draw(image).text((20, 20), text, fill="black", spacing=8)
    buffer = BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def _pdf_bytes() -> bytes:
    image = Image.new("RGB", (850, 300), "white")
    ImageDraw.Draw(image).text((20, 20), "Scanned synthetic document", fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PDF")
    return buffer.getvalue()


def _document(payload: dict, document_type: str) -> dict:
    return next(
        document
        for document in payload["documents"]
        if document["document_type"] == document_type
    )


def test_k05_missing_udyam_is_explicit_and_does_not_block_optional_onboarding(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.delenv("UDYAMONE_KYC_REQUIRED_DOCUMENTS", raising=False)
    monkeypatch.setattr(kyc_service, "UPLOAD_ROOT", tmp_path)

    response = client.get("/api/v1/kyc/K05")

    assert response.status_code == 200
    payload = response.json()
    udyam = _document(payload, "udyam_certificate")
    assert udyam["presence"] == "NOT_PROVIDED"
    assert udyam["validation"] == "NOT_REVIEWED"
    assert udyam["registry_verification"] == "NOT_CHECKED"
    assert payload["required_documents"] == []
    assert payload["ready_for_approval"] is True
    assert payload["upload_requests"] == []

    finalization = reviewer_client.post("/api/v1/kyc/K05/finalize")
    assert finalization.status_code == 200
    assert finalization.json()["finalized"] is True


def test_required_missing_document_requests_upload_and_blocks_final_approval(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "UDYAMONE_KYC_REQUIRED_DOCUMENTS", "udyam_certificate"
    )

    response = client.get("/api/v1/kyc/K05")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready_for_approval"] is False
    assert payload["upload_requests"] == ["udyam_certificate"]
    assert "Udyam certificate" in payload["next_steps"][0]

    finalization = reviewer_client.post("/api/v1/kyc/K05/finalize")
    assert finalization.status_code == 409
    assert "Udyam certificate" in finalization.json()["detail"]


def test_required_upload_stays_separate_from_validation_and_registry_states(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv(
        "UDYAMONE_KYC_REQUIRED_DOCUMENTS", "udyam_certificate"
    )
    monkeypatch.setattr(kyc_service, "UPLOAD_ROOT", tmp_path)

    upload = client.put(
        "/api/v1/kyc/K05/documents/udyam_certificate",
        content=_image_bytes(),
        headers={"content-type": "image/png"},
    )

    assert upload.status_code == 200
    uploaded = upload.json()
    uploaded_udyam = _document(uploaded, "udyam_certificate")
    assert uploaded_udyam["presence"] == "PROVIDED"
    assert uploaded_udyam["validation"] == "NOT_REVIEWED"
    assert uploaded_udyam["registry_verification"] == "NOT_CHECKED"
    assert uploaded["ready_for_approval"] is False
    assert uploaded["upload_requests"] == []

    blocked = reviewer_client.post("/api/v1/kyc/K05/finalize")
    assert blocked.status_code == 409

    review = reviewer_client.post(
        "/api/v1/kyc/K05/documents/udyam_certificate/review",
        json={"validation": "VALID"},
    )
    assert review.status_code == 200
    reviewed = review.json()
    reviewed_udyam = _document(reviewed, "udyam_certificate")
    assert reviewed_udyam["presence"] == "PROVIDED"
    assert reviewed_udyam["validation"] == "VALID"
    assert reviewed_udyam["registry_verification"] == "NOT_CHECKED"
    assert reviewed["ready_for_approval"] is True

    finalization = reviewer_client.post("/api/v1/kyc/K05/finalize")
    assert finalization.status_code == 200
    assert finalization.json()["finalized"] is True
    stored_files = list((tmp_path / "K05").glob("*.png"))
    assert len(stored_files) == 1
    assert len(stored_files[0].stem) == 32


def test_required_invalid_document_prevents_final_approval(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("UDYAMONE_KYC_REQUIRED_DOCUMENTS", "udyam_certificate")
    monkeypatch.setattr(kyc_service, "UPLOAD_ROOT", tmp_path)
    client.put(
        "/api/v1/kyc/K05/documents/udyam_certificate",
        content=_image_bytes(),
        headers={"content-type": "image/png"},
    )

    review = reviewer_client.post(
        "/api/v1/kyc/K05/documents/udyam_certificate/review",
        json={"validation": "INVALID"},
    )

    assert review.status_code == 200
    assert _document(review.json(), "udyam_certificate")["validation"] == "INVALID"
    assert review.json()["ready_for_approval"] is False
    assert reviewer_client.post("/api/v1/kyc/K05/finalize").status_code == 409


def test_review_state_for_original_sample_documents_persists(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(kyc_service, "UPLOAD_ROOT", tmp_path)
    review = reviewer_client.post(
        "/api/v1/kyc/K05/documents/gst_certificate/review",
        json={"validation": "VALID"},
    )
    refreshed = client.get("/api/v1/kyc/K05")
    gst = _document(refreshed.json(), "gst_certificate")

    assert review.status_code == refreshed.status_code == 200
    assert gst["validation"] == "VALID"
    assert gst["upload_status"] == "NOT_UPLOADED"
    assert gst["registry_verification"] == "NOT_CHECKED"


def test_unknown_document_type_and_unsupported_upload_type_are_rejected(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(kyc_service, "UPLOAD_ROOT", tmp_path)

    unknown = client.put(
        "/api/v1/kyc/K05/documents/unknown",
        content=b"document",
        headers={"content-type": "image/png"},
    )
    unsupported = client.put(
        "/api/v1/kyc/K05/documents/udyam_certificate",
        content=b"document",
        headers={"content-type": "text/plain"},
    )

    assert unknown.status_code == 422
    assert unsupported.status_code == 415


def test_upload_rejects_mismatched_and_corrupted_file_signatures(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(kyc_service, "UPLOAD_ROOT", tmp_path)
    checksum_corrupted = bytearray(_image_bytes())
    chunk_offset = 8
    while chunk_offset < len(checksum_corrupted):
        chunk_size = int.from_bytes(
            checksum_corrupted[chunk_offset : chunk_offset + 4], "big"
        )
        chunk_type = checksum_corrupted[chunk_offset + 4 : chunk_offset + 8]
        if chunk_type == b"IDAT":
            checksum_offset = chunk_offset + 8 + chunk_size
            checksum_corrupted[checksum_offset] ^= 1
            break
        chunk_offset += chunk_size + 12
    invalid = client.put(
        "/api/v1/kyc/K05/documents/gst_certificate",
        content=b"not a png",
        headers={"content-type": "image/png"},
    )
    corrupted = client.put(
        "/api/v1/kyc/K05/documents/gst_certificate",
        content=b"\x89PNG\r\n\x1a\ncorrupted",
        headers={"content-type": "image/png"},
    )
    checksum_invalid = client.put(
        "/api/v1/kyc/K05/documents/gst_certificate",
        content=bytes(checksum_corrupted),
        headers={"content-type": "image/png"},
    )

    assert invalid.status_code == 422
    assert corrupted.status_code == 422
    assert checksum_invalid.status_code == 422
    assert not list(tmp_path.rglob("*.png"))


def test_upload_enforces_size_limit_and_supports_jpeg_and_pdf(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(kyc_service, "UPLOAD_ROOT", tmp_path)
    too_large = client.put(
        "/api/v1/kyc/K05/documents/gst_certificate",
        content=b"x" * (kyc_service.MAX_UPLOAD_BYTES + 1),
        headers={"content-type": "image/png"},
    )
    jpeg = client.put(
        "/api/v1/kyc/K05/documents/gst_certificate",
        content=_image_bytes("JPEG"),
        headers={"content-type": "image/jpeg"},
    )
    pdf = client.put(
        "/api/v1/kyc/K05/documents/address_proof",
        content=_pdf_bytes(),
        headers={"content-type": "application/pdf"},
    )

    assert too_large.status_code == 413
    assert jpeg.status_code == 200
    assert _document(jpeg.json(), "gst_certificate")["content_type"] == "image/jpeg"
    assert pdf.status_code == 200
    assert _document(pdf.json(), "address_proof")["content_type"] == "application/pdf"


def test_reupload_uses_unique_names_and_retrieval_never_exposes_storage_path(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(kyc_service, "UPLOAD_ROOT", tmp_path)
    first = client.put(
        "/api/v1/kyc/K05/documents/signatory_id",
        content=_image_bytes(),
        headers={"content-type": "image/png"},
    )
    first_path = next((tmp_path / "K05").glob("*.png"))
    second = client.put(
        "/api/v1/kyc/K05/documents/signatory_id",
        content=_image_bytes("JPEG"),
        headers={
            "content-type": "image/jpeg",
            "content-disposition": 'attachment; filename="../../unsafe.png"',
        },
    )
    second_path = next((tmp_path / "K05").glob("*.jpg"))
    retrieval = client.get(
        "/api/v1/kyc/K05/documents/signatory_id/file"
    )

    assert first.status_code == second.status_code == retrieval.status_code == 200
    assert first_path.name != second_path.name
    assert not first_path.exists()
    assert retrieval.content.startswith(b"\xff\xd8\xff")
    assert "runtime_uploads" not in retrieval.headers.get("content-disposition", "")
    assert "nosniff" in retrieval.headers["x-content-type-options"]


def test_local_ocr_extracts_fields_and_supports_review_corrections_and_finalization(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("UDYAMONE_KYC_REQUIRED_DOCUMENTS", "gst_certificate")
    monkeypatch.setattr(kyc_service, "UPLOAD_ROOT", tmp_path)
    monkeypatch.setattr(
        kyc_service,
        "_run_windows_ocr",
        lambda paths: [
            {
                "status": "SUCCEEDED",
                "text": GST_SAMPLE_TEXT,
                "confidence": None,
            }
            for _ in paths
        ],
    )
    upload = client.put(
        "/api/v1/kyc/K05/documents/gst_certificate",
        content=_image_bytes(),
        headers={"content-type": "image/png"},
    )
    processed = client.post(
        "/api/v1/kyc/K05/documents/gst_certificate/process"
    )

    assert upload.status_code == 200
    assert processed.status_code == 200
    gst = _document(processed.json(), "gst_certificate")
    assert gst["processing_status"] == "SUCCEEDED"
    assert gst["registry_verification"] == "NOT_CHECKED"
    assert gst["extraction"]["confidence_available"] is False
    values = {field["name"]: field["value"] for field in gst["extraction"]["fields"]}
    assert values["gstin"] == "29ABCDE1234F1Z5"
    assert values["legal_name"] == "SAMPLE TRADERS"
    assert gst["extraction"]["missing_fields"] == ["trade_name"]
    assert "trade_name" not in gst["extraction"]["required_fields"]
    assert processed.json()["ready_for_approval"] is False

    corrected = client.patch(
        "/api/v1/kyc/K05/documents/gst_certificate/corrections",
        json={"fields": {"legal_name": "Corrected Sample Name"}},
    )
    assert corrected.status_code == 200
    corrected_gst = _document(corrected.json(), "gst_certificate")
    corrected_legal_name = next(
        field for field in corrected_gst["extraction"]["fields"]
        if field["name"] == "legal_name"
    )
    assert corrected_legal_name["status"] == "MANUALLY_CORRECTED"

    reviewed = reviewer_client.post(
        "/api/v1/kyc/K05/documents/gst_certificate/review",
        json={"validation": "VALID"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["ready_for_approval"] is True
    assert reviewer_client.post("/api/v1/kyc/K05/finalize").status_code == 200


def test_authentic_sample_upload_preserves_source_and_uses_local_processing(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.delenv("UDYAMONE_KYC_REQUIRED_DOCUMENTS", raising=False)
    monkeypatch.setattr(kyc_service, "UPLOAD_ROOT", tmp_path)
    sample_path = (
        kyc_service.SAMPLE_KYC_ROOT
        / "K01"
        / "K01_gst_certificate.png"
    )
    sample_bytes = sample_path.read_bytes()
    original_digest = hashlib.sha256(sample_bytes).digest()
    monkeypatch.setattr(
        kyc_service,
        "_run_windows_ocr",
        lambda paths: [
            {"status": "SUCCEEDED", "text": GST_SAMPLE_TEXT, "confidence": None}
            for _ in paths
        ],
    )

    upload = client.put(
        "/api/v1/kyc/K01/documents/gst_certificate",
        content=sample_bytes,
        headers={"content-type": "image/png"},
    )
    processed = client.post(
        "/api/v1/kyc/K01/documents/gst_certificate/process"
    )
    retrieval = client.get(
        "/api/v1/kyc/K01/documents/gst_certificate/file"
    )
    gst = _document(processed.json(), "gst_certificate")

    assert upload.status_code == processed.status_code == retrieval.status_code == 200
    assert hashlib.sha256(retrieval.content).digest() == original_digest
    assert hashlib.sha256(sample_path.read_bytes()).digest() == original_digest
    assert gst["processing_status"] == "SUCCEEDED"
    assert gst["registry_verification"] == "NOT_CHECKED"


def test_ocr_failures_and_invalid_extracted_identifiers_are_reported(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("UDYAMONE_KYC_REQUIRED_DOCUMENTS", "gst_certificate")
    monkeypatch.setattr(kyc_service, "UPLOAD_ROOT", tmp_path)
    monkeypatch.setattr(
        kyc_service,
        "_run_windows_ocr",
        lambda paths: [
            {"status": "SUCCEEDED", "text": "GSTIN: BAD", "confidence": 0.2}
            for _ in paths
        ],
    )
    client.put(
        "/api/v1/kyc/K05/documents/gst_certificate",
        content=_image_bytes(),
        headers={"content-type": "image/png"},
    )
    processed = client.post(
        "/api/v1/kyc/K05/documents/gst_certificate/process"
    )
    gst = _document(processed.json(), "gst_certificate")
    gstin = next(
        field for field in gst["extraction"]["fields"] if field["name"] == "gstin"
    )
    assert gst["processing_status"] == "SUCCEEDED"
    assert gstin["status"] == "INVALID_FORMAT"
    assert "gstin" in gst["extraction"]["invalid_fields"]
    reviewed = reviewer_client.post(
        "/api/v1/kyc/K05/documents/gst_certificate/review",
        json={"validation": "VALID"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["ready_for_approval"] is False
    assert reviewer_client.post("/api/v1/kyc/K05/finalize").status_code == 409

    monkeypatch.setattr(
        kyc_service,
        "_run_windows_ocr",
        lambda paths: [
            {"status": "UNREADABLE", "text": "", "confidence": None}
            for _ in paths
        ],
    )
    unreadable = client.post(
        "/api/v1/kyc/K05/documents/gst_certificate/process"
    )
    assert _document(unreadable.json(), "gst_certificate")["processing_status"] == "UNREADABLE"

    monkeypatch.setattr(
        kyc_service,
        "_run_windows_ocr",
        lambda _: (_ for _ in ()).throw(
            kyc_service.KycOcrError("No Windows OCR language engine is available.")
        ),
    )
    failed = client.post(
        "/api/v1/kyc/K05/documents/gst_certificate/process"
    )
    failed_gst = _document(failed.json(), "gst_certificate")
    assert failed_gst["processing_status"] == "FAILED"
    assert failed_gst["extraction"]["error_code"] == "OCR_ENGINE_UNAVAILABLE"


def test_scanned_pdf_uses_local_ocr_and_profile_mismatches_are_flagged(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(kyc_service, "UPLOAD_ROOT", tmp_path)
    seen_paths: list[str] = []

    def fake_ocr(paths):
        seen_paths.extend(str(path) for path in paths)
        return [
            {"status": "SUCCEEDED", "text": GST_SAMPLE_TEXT, "confidence": None}
            for _ in paths
        ]

    monkeypatch.setattr(kyc_service, "_run_windows_ocr", fake_ocr)
    client.put(
        "/api/v1/kyc/K05/documents/gst_certificate",
        content=_pdf_bytes(),
        headers={"content-type": "application/pdf"},
    )
    processed = client.post(
        "/api/v1/kyc/K05/documents/gst_certificate/process"
    )
    assert processed.status_code == 200
    assert len(seen_paths) == 1
    assert Path(seen_paths[0]).suffix == ".png"

    profiled = client.put(
        "/api/v1/kyc/K05/profile",
        json={"business_name": "DIFFERENT BUSINESS", "business_address": None},
    )
    gst = _document(profiled.json(), "gst_certificate")
    assert any("business name" in warning for warning in gst["extraction"]["mismatch_warnings"])


def test_selectable_text_pdf_extraction_uses_local_pdf_parser() -> None:
    case_brief = (
        kyc_service.PROJECT_ROOT / "docs" / "case_pack" / "Airtel_SYNC_Case.pdf"
    )
    assert case_brief.is_file()
    text, rendered_pages, page_text = kyc_service._extract_pdf_text(case_brief)

    assert len(page_text) == 6
    assert sum(bool(page.strip()) for page in page_text) >= 1
    assert text.strip()
    assert len(rendered_pages) < len(page_text)


def test_extraction_recognizes_valid_gstin_and_udyam_formats() -> None:
    gst_fields, *_ = kyc_service._extract_fields(
        kyc_service.KycDocumentType.GST_CERTIFICATE,
        GST_SAMPLE_TEXT,
        None,
        {},
    )
    gstin = next(field for field in gst_fields if field.name == "gstin")
    assert gstin.value == "29ABCDE1234F1Z5"
    assert gstin.status.value == "EXTRACTED"

    udyam_fields, *_ = kyc_service._extract_fields(
        kyc_service.KycDocumentType.UDYAM_CERTIFICATE,
        "UDYAM-KR-03-1234567\nName of Enterprise: SAMPLE ENTERPRISE",
        None,
        {},
    )
    udyam = next(field for field in udyam_fields if field.name == "udyam_number")
    assert udyam.value == "UDYAMKR031234567"
    assert udyam.status.value == "EXTRACTED"


def test_gstin_extraction_stops_at_unpunctuated_next_label() -> None:
    text = (
        "GSTIN: 29ABCDE1234F1?5 Legal Name of Business SAMPLE TRADERS "
        "Principal Place of Business SAMPLE ROAD"
    )

    fields, _, _, invalid, _, _ = kyc_service._extract_fields(
        kyc_service.KycDocumentType.GST_CERTIFICATE,
        text,
        None,
        {},
    )

    gstin = next(field for field in fields if field.name == "gstin")
    assert gstin.status.value == "INVALID_FORMAT"
    assert gstin.value is not None
    assert len(gstin.value) == 15
    assert invalid == ["gstin"]


def test_udyam_specimen_uses_number_row_and_flags_documented_ocr_ambiguity() -> None:
    full_page_text = (
        "SPECIMEN UDYAM REGISTRATION CERTIFICATE HACKATHON OCR TESTING "
        "UDYAMZZ991234567 Name of Enterprise SAMPLE"
    )

    fields, _, _, _, low_confidence, _ = kyc_service._extract_fields(
        kyc_service.KycDocumentType.UDYAM_CERTIFICATE,
        full_page_text,
        0.9,
        {},
        "Udyam / KA / OO / 1234567",
        True,
    )

    number = next(field for field in fields if field.name == "udyam_number")
    assert number.value == "UDYAMKA001234567"
    assert number.status.value == "LOW_CONFIDENCE"
    assert low_confidence == ["udyam_number"]
    assert number.flags


def test_udyam_specimen_does_not_fall_back_to_unrelated_page_sequence() -> None:
    full_page_text = (
        "SPECIMEN UDYAM REGISTRATION CERTIFICATE HACKATHON OCR TESTING "
        "UDYAMZZ991234567 Name of Enterprise SAMPLE"
    )

    fields, _, missing, _, _, _ = kyc_service._extract_fields(
        kyc_service.KycDocumentType.UDYAM_CERTIFICATE,
        full_page_text,
        0.9,
        {},
        "",
        True,
    )

    number = next(field for field in fields if field.name == "udyam_number")
    assert number.value is None
    assert number.status.value == "MISSING"
    assert "udyam_number" in missing
    assert number.flags


def test_actual_udyam_sample_is_cropped_for_local_number_row_ocr(
    monkeypatch,
) -> None:
    sample_path = next(kyc_service.SAMPLE_KYC_ROOT.glob("K*/K*_udyam_certificate.png"))
    calls = 0

    def fake_ocr(paths: list[Path]) -> list[dict]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return [
                {
                    "status": "SUCCEEDED",
                    "text": (
                        "SPECIMEN UDYAM REGISTRATION CERTIFICATE "
                        "HACKATHON OCR TESTING Name of Enterprise SAMPLE"
                    ),
                    "confidence": 0.9,
                }
            ]
        return [
            {
                "status": "SUCCEEDED",
                "text": "UDYAM KA 00 1234567",
                "confidence": 0.9,
            }
        ]

    monkeypatch.setattr(kyc_service, "_run_windows_ocr", fake_ocr)
    extraction = kyc_service._process_document_path(
        kyc_service.KycDocumentType.UDYAM_CERTIFICATE,
        sample_path,
        {"content_type": "image/png"},
        {},
    )

    number = next(
        field for field in extraction.fields if field.name == "udyam_number"
    )
    assert calls == 2
    assert extraction.processing_status.value == "SUCCEEDED"
    assert number.status.value == "EXTRACTED"
    assert number.value is not None


def test_actual_gst_sample_is_cropped_for_local_number_row_ocr(
    monkeypatch,
) -> None:
    sample_path = next(kyc_service.SAMPLE_KYC_ROOT.glob("K*/K*_gst_certificate.png"))
    calls = 0

    def fake_ocr(paths: list[Path]) -> list[dict]:
        nonlocal calls
        calls += 1
        text = (
            "SPECIMEN GSTIN HACKATHON OCR TESTING"
            if calls == 1
            else "GSTIN: 29ABCDE1234F1Z5"
        )
        return [{"status": "SUCCEEDED", "text": text, "confidence": 0.9}]

    monkeypatch.setattr(kyc_service, "_run_windows_ocr", fake_ocr)
    extraction = kyc_service._process_document_path(
        kyc_service.KycDocumentType.GST_CERTIFICATE,
        sample_path,
        {"content_type": "image/png"},
        {},
    )

    gstin = next(field for field in extraction.fields if field.name == "gstin")
    assert calls == 2
    assert extraction.processing_status.value == "SUCCEEDED"
    assert gstin.status.value == "EXTRACTED"


def test_ambiguous_udyam_number_blocks_until_manual_correction(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("UDYAMONE_KYC_REQUIRED_DOCUMENTS", "udyam_certificate")
    monkeypatch.setattr(kyc_service, "UPLOAD_ROOT", tmp_path)
    sample_path = next(kyc_service.SAMPLE_KYC_ROOT.glob("K*/K*_udyam_certificate.png"))
    calls = 0

    def fake_ocr(paths: list[Path]) -> list[dict]:
        nonlocal calls
        calls += 1
        text = (
            "SPECIMEN UDYAM REGISTRATION CERTIFICATE HACKATHON OCR TESTING "
            "Name of Enterprise SAMPLE ENTERPRISE"
            if calls == 1
            else "UDYAM KA OO 1234567"
        )
        return [{"status": "SUCCEEDED", "text": text, "confidence": 0.9}]

    monkeypatch.setattr(kyc_service, "_run_windows_ocr", fake_ocr)
    upload = client.put(
        "/api/v1/kyc/K05/documents/udyam_certificate",
        content=sample_path.read_bytes(),
        headers={"content-type": "image/png"},
    )
    assert upload.status_code == 200

    processed = client.post(
        "/api/v1/kyc/K05/documents/udyam_certificate/process"
    )
    udyam = _document(processed.json(), "udyam_certificate")
    number = next(
        field
        for field in udyam["extraction"]["fields"]
        if field["name"] == "udyam_number"
    )
    assert number["status"] == "LOW_CONFIDENCE"
    assert "udyam_number" in udyam["extraction"]["low_confidence_fields"]
    assert processed.json()["ready_for_approval"] is False

    reviewed = reviewer_client.post(
        "/api/v1/kyc/K05/documents/udyam_certificate/review",
        json={"validation": "VALID"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["ready_for_approval"] is False
    assert any("Confirm the udyam number" in step for step in reviewed.json()["next_steps"])

    corrected = client.patch(
        "/api/v1/kyc/K05/documents/udyam_certificate/corrections",
        json={"fields": {"udyam_number": "UDYAMKA001234567"}},
    )
    assert corrected.status_code == 200
    corrected_document = _document(corrected.json(), "udyam_certificate")
    assert corrected.json()["ready_for_approval"] is True
    assert corrected_document["registry_verification"] == "NOT_CHECKED"
    assert reviewer_client.post("/api/v1/kyc/K05/finalize").status_code == 200


def test_signatory_extraction_collects_only_the_name() -> None:
    fields, required_fields, *_ = kyc_service._extract_fields(
        kyc_service.KycDocumentType.SIGNATORY_ID,
        "SIGNATORY ID Name of Holder: SAMPLE PERSON ID Number: 123456789",
        None,
        {},
    )

    assert [field.name for field in fields] == ["signatory_name"]
    assert required_fields == ["signatory_name"]


def test_document_retrieval_rejects_missing_and_unsafe_applicants(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(kyc_service, "UPLOAD_ROOT", tmp_path)
    missing = client.get(
        "/api/v1/kyc/K05/documents/udyam_certificate/file"
    )
    unsafe = client.get(
        "/api/v1/kyc/../other/documents/udyam_certificate/file"
    )
    assert missing.status_code == 404
    assert unsafe.status_code in {404, 422}


def test_kyc_upload_endpoint_allows_cors_preflight() -> None:
    response = client.options(
        "/api/v1/kyc/K05/documents/udyam_certificate",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "PUT" in response.headers["access-control-allow-methods"]
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
    correction_preflight = client.options(
        "/api/v1/kyc/K05/documents/gst_certificate/corrections",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )
    assert correction_preflight.status_code == 200
    assert "PATCH" in correction_preflight.headers["access-control-allow-methods"]
