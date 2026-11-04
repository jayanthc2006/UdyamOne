"""CSV-backed product catalogue loading and validation."""

import csv
import re
from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from app.models.product import Product

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOGUE_PATH = PROJECT_ROOT / "data" / "catalogue" / "product_catalogue.csv"

REQUIRED_COLUMNS = (
    "product_id",
    "category",
    "product_name",
    "description",
    "unit",
    "price_min_inr_per_month",
    "price_max_inr_per_month",
    "one_time_setup_inr",
    "min_contract_months",
    "available_city_tiers",
    "min_employees",
    "min_sites",
    "requires_gstin",
    "requires_one_of",
    "typical_install_days",
    "target_segments",
)

INTEGER_FIELDS = (
    "price_min_inr_per_month",
    "price_max_inr_per_month",
    "one_time_setup_inr",
    "min_contract_months",
    "min_employees",
    "min_sites",
    "typical_install_days",
)

PRODUCT_ID_PATTERN = re.compile(r"P\d{2}")
ALLOWED_CITY_TIERS = {1, 2}
ALLOWED_TARGET_SEGMENTS = {"micro", "prof", "multi", "mfg"}


class CatalogueError(ValueError):
    """Base error for catalogue-loading failures."""


class CatalogueFileNotFoundError(CatalogueError):
    """Raised when the source catalogue file does not exist."""


class CatalogueValidationError(CatalogueError):
    """Raised when a catalogue record or relationship is invalid."""


def resolve_catalogue_path(path: str | Path | None = None) -> Path:
    """Return a catalogue path, resolving relative paths from the project root."""
    candidate = DEFAULT_CATALOGUE_PATH if path is None else Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def _required_value(row: dict[str, str | None], field: str, row_number: int) -> str:
    value = row.get(field)
    if value is None or not value.strip():
        raise CatalogueValidationError(
            f"Missing required field '{field}' in catalogue row {row_number}."
        )
    return value.strip()


def _parse_integer(row: dict[str, str | None], field: str, row_number: int) -> int:
    value = _required_value(row, field, row_number)
    if not re.fullmatch(r"\d+", value):
        raise CatalogueValidationError(
            f"Invalid integer value for '{field}' in catalogue row {row_number}: {value!r}."
        )
    return int(value)


def _parse_delimited_values(
    value: str, delimiter: str, field: str, row_number: int
) -> list[str]:
    values = [item.strip() for item in value.split(delimiter)]
    if not all(values):
        raise CatalogueValidationError(
            f"Invalid empty value in '{field}' in catalogue row {row_number}."
        )
    return values


def _parse_product_id(value: str, row_number: int, field: str = "product_id") -> str:
    if not PRODUCT_ID_PATTERN.fullmatch(value):
        raise CatalogueValidationError(
            f"Invalid {field} in catalogue row {row_number}: expected 'P' followed "
            f"by exactly two digits, received {value!r}."
        )
    return value


def _parse_city_tiers(row: dict[str, str | None], row_number: int) -> list[int]:
    raw_value = _required_value(row, "available_city_tiers", row_number)
    tiers: list[int] = []
    for value in _parse_delimited_values(
        raw_value, ";", "available_city_tiers", row_number
    ):
        if not re.fullmatch(r"\d+", value):
            raise CatalogueValidationError(
                "Invalid city tier in catalogue row "
                f"{row_number}: {value!r} is not an integer."
            )
        tier = int(value)
        if tier not in ALLOWED_CITY_TIERS:
            raise CatalogueValidationError(
                "Invalid city tier in catalogue row "
                f"{row_number}: expected one of 1, 2, received {tier}."
            )
        if tier in tiers:
            raise CatalogueValidationError(
                f"Duplicate city tier {tier} in catalogue row {row_number}."
            )
        tiers.append(tier)
    return tiers


def _parse_gstin_flag(row: dict[str, str | None], row_number: int) -> bool:
    value = _required_value(row, "requires_gstin", row_number)
    if value not in {"Y", "N"}:
        raise CatalogueValidationError(
            "Invalid GSTIN flag in catalogue row "
            f"{row_number}: expected 'Y' or 'N', received {value!r}."
        )
    return value == "Y"


def _parse_dependencies(row: dict[str, str | None], row_number: int) -> list[str]:
    value = row.get("requires_one_of")
    if value is None or not value.strip():
        return []
    dependencies = _parse_delimited_values(
        value.strip(), "|", "requires_one_of", row_number
    )
    for dependency_id in dependencies:
        _parse_product_id(dependency_id, row_number, "dependency product ID")
    duplicate_dependencies = {
        dependency_id
        for dependency_id in dependencies
        if dependencies.count(dependency_id) > 1
    }
    if duplicate_dependencies:
        duplicate_dependency = sorted(duplicate_dependencies)[0]
        raise CatalogueValidationError(
            f"Duplicate dependency '{duplicate_dependency}' in catalogue row {row_number}."
        )
    return dependencies


def _parse_target_segments(row: dict[str, str | None], row_number: int) -> list[str]:
    segments = _parse_delimited_values(
        _required_value(row, "target_segments", row_number),
        ";",
        "target_segments",
        row_number,
    )
    for segment in segments:
        if segment not in ALLOWED_TARGET_SEGMENTS:
            allowed_segments = ", ".join(sorted(ALLOWED_TARGET_SEGMENTS))
            raise CatalogueValidationError(
                "Invalid target segment in catalogue row "
                f"{row_number}: expected one of {allowed_segments}, received {segment!r}."
            )
    duplicate_segments = {
        segment for segment in segments if segments.count(segment) > 1
    }
    if duplicate_segments:
        duplicate_segment = sorted(duplicate_segments)[0]
        raise CatalogueValidationError(
            f"Duplicate target segment '{duplicate_segment}' in catalogue row {row_number}."
        )
    return segments


def _validate_headers(fieldnames: Iterable[str] | None) -> None:
    if fieldnames is None:
        raise CatalogueValidationError("Catalogue file is empty or has no header row.")

    actual_columns = tuple(fieldnames)
    duplicate_columns = sorted(
        {column for column in actual_columns if actual_columns.count(column) > 1}
    )
    if duplicate_columns:
        raise CatalogueValidationError(
            f"Catalogue header contains duplicate columns: {', '.join(duplicate_columns)}."
        )

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in actual_columns]
    if missing_columns:
        raise CatalogueValidationError(
            f"Catalogue header is missing required columns: {', '.join(missing_columns)}."
        )


def _parse_row(row: dict[str, str | None], row_number: int) -> Product:
    if None in row:
        raise CatalogueValidationError(
            f"Catalogue row {row_number} contains more values than the header defines."
        )

    product_data = {
        "product_id": _parse_product_id(
            _required_value(row, "product_id", row_number), row_number
        ),
        "category": _required_value(row, "category", row_number),
        "product_name": _required_value(row, "product_name", row_number),
        "description": _required_value(row, "description", row_number),
        "unit": _required_value(row, "unit", row_number),
        "available_city_tiers": _parse_city_tiers(row, row_number),
        "requires_gstin": _parse_gstin_flag(row, row_number),
        "requires_one_of": _parse_dependencies(row, row_number),
        "target_segments": _parse_target_segments(row, row_number),
    }
    product_data.update(
        {
            field: _parse_integer(row, field, row_number)
            for field in INTEGER_FIELDS
        }
    )

    if product_data["price_min_inr_per_month"] > product_data["price_max_inr_per_month"]:
        raise CatalogueValidationError(
            "Invalid monthly price range in catalogue row "
            f"{row_number}: minimum price exceeds maximum price."
        )

    try:
        return Product(**product_data)
    except ValidationError as error:
        raise CatalogueValidationError(
            f"Invalid product data in catalogue row {row_number}: {error}."
        ) from error


def _validate_dependencies(products: Iterable[Product]) -> None:
    product_list = list(products)
    known_ids = {product.product_id for product in product_list}
    for product in product_list:
        for dependency_id in product.requires_one_of:
            if dependency_id not in known_ids:
                raise CatalogueValidationError(
                    f"Product '{product.product_id}' references unknown dependency "
                    f"'{dependency_id}'."
                )


def load_catalogue(path: str | Path | None = None) -> list[Product]:
    """Load and validate products from the project catalogue CSV.

    Relative paths are resolved from the project root. The default source is
    ``data/catalogue/product_catalogue.csv``.
    """
    catalogue_path = resolve_catalogue_path(path)
    if not catalogue_path.is_file():
        raise CatalogueFileNotFoundError(
            f"Catalogue file was not found: {catalogue_path}."
        )

    products: list[Product] = []
    seen_product_ids: set[str] = set()
    try:
        with catalogue_path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source, strict=True)
            _validate_headers(reader.fieldnames)
            for row_number, row in enumerate(reader, start=2):
                product = _parse_row(row, row_number)
                if product.product_id in seen_product_ids:
                    raise CatalogueValidationError(
                        f"Duplicate product_id '{product.product_id}' in catalogue row "
                        f"{row_number}."
                    )
                seen_product_ids.add(product.product_id)
                products.append(product)
    except csv.Error as error:
        raise CatalogueValidationError(
            f"Unable to parse catalogue CSV '{catalogue_path}': {error}."
        ) from error

    _validate_dependencies(products)
    return products
