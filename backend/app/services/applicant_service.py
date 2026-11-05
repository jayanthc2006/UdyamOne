"""Small durable SQLite store for prototype applicant journeys.

The existing catalogue, eligibility, recommendation, pricing, and KYC services
remain the source of domain behaviour. This store only associates their outputs
with a generated applicant identifier across server restarts.
"""

import re
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.models.applicant import ApplicantProfile, ApplicantRecord
from app.models.pricing import QuoteResponse
from app.models.recommendation import RecommendationResponse

APPLICANT_DATABASE_PATH = Path(__file__).resolve().parents[2] / "runtime_data" / "applicants.sqlite3"
_APPLICANT_ID_PATTERN = re.compile(r"APPL-[0-9a-f]{32}")
_DATABASE_LOCK = threading.RLock()


class ApplicantNotFoundError(ValueError):
    """Raised when a journey request names no saved applicant."""


def _connect() -> sqlite3.Connection:
    APPLICANT_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(APPLICANT_DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS applicants (
            applicant_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            profile_json TEXT NOT NULL,
            recommendations_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS quote_previews (
            quote_id TEXT PRIMARY KEY,
            applicant_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            quote_json TEXT NOT NULL,
            FOREIGN KEY (applicant_id) REFERENCES applicants(applicant_id)
        )
        """
    )
    return connection


def _new_applicant_id() -> str:
    return f"APPL-{uuid.uuid4().hex}"


def _validate_applicant_id(applicant_id: str) -> str:
    if not _APPLICANT_ID_PATTERN.fullmatch(applicant_id):
        raise ApplicantNotFoundError("Applicant was not found.")
    return applicant_id


def create_applicant(
    profile: ApplicantProfile,
    recommendations: RecommendationResponse,
) -> ApplicantRecord:
    """Persist a newly submitted profile and its initial recommendations."""
    created_at = datetime.now(UTC).isoformat()
    with _DATABASE_LOCK, _connect() as connection:
        # UUID4 collisions are exceptionally unlikely; the loop still makes the
        # uniqueness guarantee explicit at the persistence boundary.
        while True:
            applicant_id = _new_applicant_id()
            try:
                connection.execute(
                    """
                    INSERT INTO applicants (
                        applicant_id, created_at, profile_json, recommendations_json
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        applicant_id,
                        created_at,
                        profile.model_dump_json(),
                        recommendations.model_dump_json(),
                    ),
                )
                break
            except sqlite3.IntegrityError:
                continue
    return ApplicantRecord(
        applicant_id=applicant_id,
        created_at=created_at,
        profile=profile,
        recommendations=recommendations,
    )


def get_applicant(applicant_id: str) -> ApplicantRecord:
    """Return one saved applicant without falling back to any sample fixture."""
    applicant_id = _validate_applicant_id(applicant_id)
    with _DATABASE_LOCK, _connect() as connection:
        row = connection.execute(
            """
            SELECT applicant_id, created_at, profile_json, recommendations_json
            FROM applicants WHERE applicant_id = ?
            """,
            (applicant_id,),
        ).fetchone()
        quote_row = connection.execute(
            """
            SELECT quote_json FROM quote_previews
            WHERE applicant_id = ?
            ORDER BY created_at DESC, quote_id DESC
            LIMIT 1
            """,
            (applicant_id,),
        ).fetchone()
    if row is None:
        raise ApplicantNotFoundError("Applicant was not found.")
    return ApplicantRecord(
        applicant_id=row["applicant_id"],
        created_at=row["created_at"],
        profile=ApplicantProfile.model_validate_json(row["profile_json"]),
        recommendations=RecommendationResponse.model_validate_json(
            row["recommendations_json"]
        ),
        latest_quote=(
            QuoteResponse.model_validate_json(quote_row["quote_json"])
            if quote_row is not None
            else None
        ),
    )


def update_applicant(
    applicant_id: str,
    profile: ApplicantProfile,
    recommendations: RecommendationResponse,
) -> ApplicantRecord:
    """Update an existing journey without changing its stable applicant ID."""
    applicant_id = _validate_applicant_id(applicant_id)
    with _DATABASE_LOCK, _connect() as connection:
        cursor = connection.execute(
            """
            UPDATE applicants
            SET profile_json = ?, recommendations_json = ?
            WHERE applicant_id = ?
            """,
            (
                profile.model_dump_json(),
                recommendations.model_dump_json(),
                applicant_id,
            ),
        )
        if cursor.rowcount == 0:
            raise ApplicantNotFoundError("Applicant was not found.")
        connection.execute(
            "DELETE FROM quote_previews WHERE applicant_id = ?",
            (applicant_id,),
        )
    return get_applicant(applicant_id)


def save_quote_preview(applicant_id: str, quote: QuoteResponse) -> None:
    """Record an authoritative quote generated by the existing pricing service."""
    applicant_id = _validate_applicant_id(applicant_id)
    # Ensure this insert cannot create a record for an arbitrary KYC/sample ID.
    get_applicant(applicant_id)
    with _DATABASE_LOCK, _connect() as connection:
        connection.execute(
            """
            INSERT INTO quote_previews (quote_id, applicant_id, created_at, quote_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                applicant_id,
                datetime.now(UTC).isoformat(),
                quote.model_dump_json(),
            ),
        )


def quote_preview_count(applicant_id: str) -> int:
    """Return saved quote count; used by service-level regression tests."""
    applicant_id = _validate_applicant_id(applicant_id)
    with _DATABASE_LOCK, _connect() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM quote_previews WHERE applicant_id = ?",
            (applicant_id,),
        ).fetchone()
    return int(row["count"])
