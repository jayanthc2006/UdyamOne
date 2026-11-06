"""Backend-only matching against the supplied synthetic competition registries."""

import csv
import hashlib
import json
import re
import sqlite3
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Mapping

from app.models.verification import (
    RegistryVerificationResult,
    RegistryVerificationStatus,
)
from app.services import applicant_service

PROJECT_ROOT = Path(__file__).resolve().parents[3]
GSTIN_REGISTRY_PATH = PROJECT_ROOT / "data" / "mock_registries" / "mock_gstin_registry.csv"
UDYAM_REGISTRY_PATH = PROJECT_ROOT / "data" / "mock_registries" / "mock_udyam_registry.csv"

_GSTIN_PATTERN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_UDYAM_PATTERN = re.compile(r"^UDYAM[A-Z]{2}\d{2}\d{7}$")
_REGISTRY_COLUMNS = {
    "GSTIN": {
        "gstin",
        "legal_name",
        "trade_name",
        "principal_place_of_business",
        "state",
        "status",
    },
    "UDYAM": {"udyam_number", "enterprise_name", "city"},
}
_REGISTRY_FILES = {
    "GSTIN": GSTIN_REGISTRY_PATH.name,
    "UDYAM": UDYAM_REGISTRY_PATH.name,
}

RegistryType = Literal["GSTIN", "UDYAM"]


class RegistryUnavailableError(RuntimeError):
    """Raised when a registry cannot be read or its structure is invalid."""


class RegistryPersistenceError(RuntimeError):
    """Raised when verification metadata cannot be read or persisted."""


def normalize_identifier(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"[a-z0-9]+", normalized))


def _identifier_column(registry_type: RegistryType) -> str:
    return "gstin" if registry_type == "GSTIN" else "udyam_number"


def _registry_path(registry_type: RegistryType) -> Path:
    return GSTIN_REGISTRY_PATH if registry_type == "GSTIN" else UDYAM_REGISTRY_PATH


def _read_registry(registry_type: RegistryType) -> list[dict[str, str]]:
    path = _registry_path(registry_type)
    try:
        with path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file, strict=True)
            if (
                not reader.fieldnames
                or len(reader.fieldnames) != len(set(reader.fieldnames))
                or not _REGISTRY_COLUMNS[registry_type].issubset(set(reader.fieldnames))
            ):
                raise RegistryUnavailableError(
                    f"The synthetic {registry_type} registry has an invalid schema."
                )
            rows: list[dict[str, str]] = []
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise RegistryUnavailableError(
                        f"The synthetic {registry_type} registry contains a malformed row."
                    )
                normalized_row = {
                    key: value.strip()
                    for key, value in row.items()
                    if key is not None and value is not None
                }
                if not normalize_identifier(normalized_row.get(_identifier_column(registry_type))):
                    raise RegistryUnavailableError(
                        f"The synthetic {registry_type} registry contains a blank identifier."
                    )
                rows.append(normalized_row)
    except RegistryUnavailableError:
        raise
    except (OSError, UnicodeError, csv.Error) as error:
        raise RegistryUnavailableError(
            f"The synthetic {registry_type} registry could not be read."
        ) from error
    return rows


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _input_fingerprint(
    registry_type: RegistryType,
    business_name: str | None,
    city: str | None,
    document_values: Mapping[str, str | None],
) -> str:
    relevant_values = {
        "business_name": business_name,
        "city": city if registry_type == "UDYAM" else None,
        "identifier": document_values.get(
            "gstin" if registry_type == "GSTIN" else "udyam_number"
        ),
        "legal_name": document_values.get("gst_legal_name")
        if registry_type == "GSTIN"
        else document_values.get("udyam_enterprise_name"),
        "trade_name": document_values.get("gst_trade_name")
        if registry_type == "GSTIN"
        else None,
        "address": document_values.get("gst_registered_address")
        if registry_type == "GSTIN"
        else None,
    }
    encoded = json.dumps(relevant_values, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _result(
    registry_type: RegistryType,
    status: RegistryVerificationStatus,
    reason: str,
    compared_fields: list[str] | None = None,
    mismatched_fields: list[str] | None = None,
) -> RegistryVerificationResult:
    return RegistryVerificationResult(
        registry_type=registry_type,
        status=status,
        reason=reason,
        checked_at=_now(),
        registry_source=_REGISTRY_FILES[registry_type],
        compared_fields=compared_fields or [],
        mismatched_fields=mismatched_fields or [],
    )


def _deduplicate_matches(
    rows: list[dict[str, str]],
    identifier_column: str,
    identifier: str,
) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if normalize_identifier(row.get(identifier_column)) == identifier
    ]


def _distinct_records(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_content: dict[str, dict[str, str]] = {}
    for row in rows:
        signature = json.dumps(row, sort_keys=True, separators=(",", ":"))
        by_content.setdefault(signature, row)
    return list(by_content.values())


def _address_matches(submitted: str, registered: str) -> bool:
    submitted_tokens = set(_normalize_text(submitted).split())
    registered_tokens = set(_normalize_text(registered).split())
    if not submitted_tokens or not registered_tokens:
        return False
    smaller = min(len(submitted_tokens), len(registered_tokens))
    return len(submitted_tokens & registered_tokens) / smaller >= 0.8


def _verify_gstin(
    identifier: str | None,
    business_name: str | None,
    document_values: Mapping[str, str | None],
) -> RegistryVerificationResult:
    normalized_identifier = normalize_identifier(identifier)
    if not normalized_identifier or not _GSTIN_PATTERN.fullmatch(normalized_identifier):
        return _result(
            "GSTIN",
            RegistryVerificationStatus.INCONCLUSIVE,
            "A valid GSTIN was not available in the processed GST certificate.",
        )

    rows = _read_registry("GSTIN")
    matches = _distinct_records(
        _deduplicate_matches(rows, "gstin", normalized_identifier)
    )
    if not matches:
        return _result(
            "GSTIN",
            RegistryVerificationStatus.INCONCLUSIVE,
            "No matching identifier was found in the synthetic GSTIN registry.",
        )
    if len(matches) != 1:
        return _result(
            "GSTIN",
            RegistryVerificationStatus.INCONCLUSIVE,
            "Multiple conflicting records use this identifier in the synthetic GSTIN registry.",
        )

    record = matches[0]
    registry_names = {
        name
        for name in (
            _normalize_text(record.get("legal_name")),
            _normalize_text(record.get("trade_name")),
        )
        if name
    }
    if not registry_names or not record.get("status"):
        return _result(
            "GSTIN",
            RegistryVerificationStatus.INCONCLUSIVE,
            "The matching registry record lacks required comparison information.",
        )
    supplied_names = [
        (field, _normalize_text(value))
        for field, value in (
            ("applicant_business_name", business_name),
            ("document_legal_name", document_values.get("gst_legal_name")),
            ("document_trade_name", document_values.get("gst_trade_name")),
        )
        if value and _normalize_text(value)
    ]
    if not supplied_names:
        return _result(
            "GSTIN",
            RegistryVerificationStatus.INCONCLUSIVE,
            "Business-name information is insufficient to compare the registry record.",
        )

    compared = [field for field, _ in supplied_names]
    mismatched = [
        field for field, name in supplied_names if name not in registry_names
    ]
    submitted_address = document_values.get("gst_registered_address")
    if submitted_address:
        compared.append("registered_address")
        if not _address_matches(
            submitted_address,
            record.get("principal_place_of_business", ""),
        ):
            mismatched.append("registered_address")
    if record.get("status", "").casefold() != "active":
        compared.append("registry_status")
        mismatched.append("registry_status")

    if mismatched:
        return _result(
            "GSTIN",
            RegistryVerificationStatus.MISMATCH,
            "The GSTIN record was found, but one or more business details do not match.",
            compared,
            mismatched,
        )
    return _result(
        "GSTIN",
        RegistryVerificationStatus.VERIFIED,
        "The unique GSTIN record and available business details match the synthetic registry.",
        compared,
    )


def _verify_udyam(
    identifier: str | None,
    business_name: str | None,
    city: str | None,
    document_values: Mapping[str, str | None],
) -> RegistryVerificationResult:
    normalized_identifier = normalize_identifier(identifier)
    if not normalized_identifier or not _UDYAM_PATTERN.fullmatch(normalized_identifier):
        return _result(
            "UDYAM",
            RegistryVerificationStatus.INCONCLUSIVE,
            "A valid Udyam number was not available in the processed Udyam certificate.",
        )

    rows = _read_registry("UDYAM")
    matches = _distinct_records(
        _deduplicate_matches(rows, "udyam_number", normalized_identifier)
    )
    if not matches:
        return _result(
            "UDYAM",
            RegistryVerificationStatus.INCONCLUSIVE,
            "No matching identifier was found in the synthetic Udyam registry.",
        )
    if len(matches) != 1:
        return _result(
            "UDYAM",
            RegistryVerificationStatus.INCONCLUSIVE,
            "Multiple conflicting records use this identifier in the synthetic Udyam registry.",
        )

    record = matches[0]
    registry_name = _normalize_text(record.get("enterprise_name"))
    registry_city = _normalize_text(record.get("city"))
    if not registry_name or not registry_city:
        return _result(
            "UDYAM",
            RegistryVerificationStatus.INCONCLUSIVE,
            "The matching registry record lacks required comparison information.",
        )
    supplied_names = [
        (field, _normalize_text(value))
        for field, value in (
            ("applicant_business_name", business_name),
            ("document_enterprise_name", document_values.get("udyam_enterprise_name")),
        )
        if value and _normalize_text(value)
    ]
    if not supplied_names or not city:
        return _result(
            "UDYAM",
            RegistryVerificationStatus.INCONCLUSIVE,
            "Business-name or city information is insufficient to compare the registry record.",
        )

    compared = [field for field, _ in supplied_names]
    mismatched = [
        field for field, name in supplied_names
        if name != registry_name
    ]
    compared.append("city")
    if _normalize_text(city) != registry_city:
        mismatched.append("city")

    if mismatched:
        return _result(
            "UDYAM",
            RegistryVerificationStatus.MISMATCH,
            "The Udyam record was found, but one or more business details do not match.",
            compared,
            mismatched,
        )
    return _result(
        "UDYAM",
        RegistryVerificationStatus.VERIFIED,
        "The unique Udyam record and available business details match the synthetic registry.",
        compared,
    )


def _connect() -> sqlite3.Connection:
    path = applicant_service.APPLICANT_DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS registry_verifications (
            applicant_id TEXT NOT NULL,
            registry_type TEXT NOT NULL,
            status TEXT NOT NULL,
            reason TEXT NOT NULL,
            checked_at TEXT NOT NULL,
            registry_source TEXT NOT NULL,
            compared_fields_json TEXT NOT NULL,
            mismatched_fields_json TEXT NOT NULL,
            input_fingerprint TEXT NOT NULL,
            PRIMARY KEY (applicant_id, registry_type)
        )
        """
    )
    return connection


def _persist(
    applicant_id: str,
    result: RegistryVerificationResult,
    fingerprint: str,
) -> None:
    try:
        with _connect() as connection:
            connection.execute(
                """
                INSERT INTO registry_verifications (
                    applicant_id, registry_type, status, reason, checked_at,
                    registry_source, compared_fields_json, mismatched_fields_json,
                    input_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(applicant_id, registry_type) DO UPDATE SET
                    status = excluded.status,
                    reason = excluded.reason,
                    checked_at = excluded.checked_at,
                    registry_source = excluded.registry_source,
                    compared_fields_json = excluded.compared_fields_json,
                    mismatched_fields_json = excluded.mismatched_fields_json,
                    input_fingerprint = excluded.input_fingerprint
                """,
                (
                    applicant_id,
                    result.registry_type,
                    result.status.value,
                    result.reason,
                    result.checked_at,
                    result.registry_source,
                    json.dumps(result.compared_fields),
                    json.dumps(result.mismatched_fields),
                    fingerprint,
                ),
            )
    except sqlite3.Error as error:
        raise RegistryPersistenceError(
            "Registry verification metadata could not be persisted."
        ) from error


def verify_applicant_registries(
    applicant_id: str,
    business_name: str | None,
    city: str | None,
    document_values: Mapping[str, str | None],
) -> dict[str, RegistryVerificationResult]:
    """Check both registries independently and persist only decision metadata."""
    validate_id = applicant_id.strip()
    if not validate_id or len(validate_id) > 64:
        raise ValueError("Applicant ID is invalid.")

    results: dict[str, RegistryVerificationResult] = {}
    for registry_type, verifier in (
        ("GSTIN", lambda: _verify_gstin(
            document_values.get("gstin"), business_name, document_values
        )),
        ("UDYAM", lambda: _verify_udyam(
            document_values.get("udyam_number"),
            business_name,
            city,
            document_values,
        )),
    ):
        try:
            result = verifier()
        except RegistryUnavailableError as error:
            result = _result(
                registry_type,
                RegistryVerificationStatus.UNAVAILABLE,
                str(error),
            )
        results[registry_type] = result
        _persist(
            applicant_id,
            result,
            _input_fingerprint(
                registry_type, business_name, city, document_values
            ),
        )
    return results


def get_persisted_verifications(
    applicant_id: str,
    business_name: str | None,
    city: str | None,
    document_values: Mapping[str, str | None],
) -> dict[str, RegistryVerificationResult | None]:
    """Return only results that still correspond to the current applicant inputs."""
    fingerprint_by_type = {
        registry_type: _input_fingerprint(
            registry_type, business_name, city, document_values
        )
        for registry_type in ("GSTIN", "UDYAM")
    }
    path = applicant_service.APPLICANT_DATABASE_PATH
    result_by_type: dict[str, RegistryVerificationResult | None] = {
        "GSTIN": None,
        "UDYAM": None,
    }
    if not path.is_file():
        return result_by_type
    try:
        with sqlite3.connect(path, timeout=10) as connection:
            connection.row_factory = sqlite3.Row
            table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' "
                "AND name = 'registry_verifications'"
            ).fetchone()
            if table is None:
                return result_by_type
            rows = connection.execute(
            """
            SELECT registry_type, status, reason, checked_at, registry_source,
                   compared_fields_json, mismatched_fields_json, input_fingerprint
            FROM registry_verifications WHERE applicant_id = ?
            """,
            (applicant_id,),
            ).fetchall()
    except sqlite3.Error as error:
        raise RegistryPersistenceError(
            "Persisted registry verification state could not be read."
        ) from error
    for row in rows:
        registry_type = row["registry_type"]
        if (
            registry_type not in result_by_type
            or row["input_fingerprint"] != fingerprint_by_type[registry_type]
        ):
            continue
        try:
            result_by_type[registry_type] = RegistryVerificationResult(
                registry_type=registry_type,
                status=RegistryVerificationStatus(row["status"]),
                reason=row["reason"],
                checked_at=row["checked_at"],
                registry_source=row["registry_source"],
                compared_fields=json.loads(row["compared_fields_json"]),
                mismatched_fields=json.loads(row["mismatched_fields_json"]),
            )
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise RegistryPersistenceError(
                "Persisted registry verification state has an invalid format."
            ) from error
    return result_by_type
