"""Tests for catalogue CSV loading and validation."""

import csv
from pathlib import Path

import pytest

from app.services.catalogue_loader import (
    CatalogueFileNotFoundError,
    CatalogueValidationError,
    load_catalogue,
)

CATALOGUE_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "catalogue"
    / "product_catalogue.csv"
)


def _write_catalogue(
    tmp_path: Path, content: str, *, encoding: str = "utf-8"
) -> Path:
    path = tmp_path / "catalogue.csv"
    path.write_text(content, encoding=encoding, newline="")
    return path


def _catalogue_text() -> str:
    return CATALOGUE_PATH.read_text(encoding="utf-8")


def _catalogue_rows() -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(_catalogue_text().splitlines())
    assert reader.fieldnames is not None
    return reader.fieldnames, list(reader)


def _write_rows(
    tmp_path: Path, fieldnames: list[str], rows: list[dict[str, str]]
) -> Path:
    output = tmp_path / "catalogue.csv"
    with output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output


def test_loads_all_25_catalogue_products() -> None:
    products = load_catalogue()

    assert len(products) == 25
    assert [product.product_id for product in products] == [
        f"P{number:02d}" for number in range(1, 26)
    ]


def test_loads_default_catalogue_from_an_unrelated_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert CATALOGUE_PATH.is_file()
    monkeypatch.chdir(tmp_path)

    products = load_catalogue()

    assert len(products) == 25


def test_parses_product_field_types_and_lists() -> None:
    product = next(product for product in load_catalogue() if product.product_id == "P09")

    assert product.price_min_inr_per_month == 499
    assert product.available_city_tiers == [1, 2]
    assert product.target_segments == ["multi", "prof"]
    assert product.requires_one_of == ["P01", "P02", "P03", "P05", "P06"]


def test_parses_gstin_flags_and_empty_dependencies() -> None:
    products = {product.product_id: product for product in load_catalogue()}

    assert products["P01"].requires_gstin is False
    assert products["P03"].requires_gstin is True
    assert products["P01"].requires_one_of == []


def test_rejects_duplicate_product_ids(tmp_path: Path) -> None:
    lines = _catalogue_text().splitlines()
    duplicate_catalogue = "\n".join([lines[0], lines[1], lines[1]])

    with pytest.raises(CatalogueValidationError, match="Duplicate product_id 'P01'"):
        load_catalogue(_write_catalogue(tmp_path, duplicate_catalogue))


def test_rejects_missing_catalogue_file(tmp_path: Path) -> None:
    with pytest.raises(CatalogueFileNotFoundError, match="Catalogue file was not found"):
        load_catalogue(tmp_path / "does-not-exist.csv")


@pytest.mark.parametrize(
    ("field", "replacement", "error_message"),
    [
        ("price_min_inr_per_month", "not-a-number", "Invalid integer value"),
        ("price_max_inr_per_month", "100", "minimum price exceeds maximum price"),
        ("category", "", "Missing required field 'category'"),
    ],
)
def test_rejects_invalid_product_data(
    tmp_path: Path, field: str, replacement: str, error_message: str
) -> None:
    fieldnames, rows = _catalogue_rows()
    rows[0][field] = replacement

    with pytest.raises(CatalogueValidationError, match=error_message):
        load_catalogue(_write_rows(tmp_path, fieldnames, rows))


def test_rejects_unknown_dependency_reference(tmp_path: Path) -> None:
    fieldnames, rows = _catalogue_rows()
    rows[8]["requires_one_of"] = "P99"

    with pytest.raises(CatalogueValidationError, match="unknown dependency 'P99'"):
        load_catalogue(_write_rows(tmp_path, fieldnames, rows))


def test_loads_utf8_bom_catalogue(tmp_path: Path) -> None:
    products = load_catalogue(
        _write_catalogue(tmp_path, _catalogue_text(), encoding="utf-8-sig")
    )

    assert len(products) == 25


def test_rejects_missing_required_header(tmp_path: Path) -> None:
    fieldnames, rows = _catalogue_rows()
    fieldnames.remove("target_segments")
    for row in rows:
        row.pop("target_segments")

    with pytest.raises(CatalogueValidationError, match="missing required columns: target_segments"):
        load_catalogue(_write_rows(tmp_path, fieldnames, rows))


def test_rejects_duplicate_header(tmp_path: Path) -> None:
    lines = _catalogue_text().splitlines()
    header_with_duplicate = f"{lines[0]},product_id"
    duplicate_header_catalogue = "\n".join(
        [header_with_duplicate, *[f"{line},ignored" for line in lines[1:]]]
    )

    with pytest.raises(CatalogueValidationError, match="duplicate columns: product_id"):
        load_catalogue(_write_catalogue(tmp_path, duplicate_header_catalogue))


def test_rejects_malformed_csv_quoting(tmp_path: Path) -> None:
    malformed_catalogue = f'{_catalogue_text().splitlines()[0]}\n"P01'

    with pytest.raises(CatalogueValidationError, match="Unable to parse catalogue CSV"):
        load_catalogue(_write_catalogue(tmp_path, malformed_catalogue))


def test_rejects_row_with_more_values_than_header(tmp_path: Path) -> None:
    lines = _catalogue_text().splitlines()
    malformed_row_catalogue = "\n".join([lines[0], f"{lines[1]},unexpected"])

    with pytest.raises(CatalogueValidationError, match="more values than the header defines"):
        load_catalogue(_write_catalogue(tmp_path, malformed_row_catalogue))


@pytest.mark.parametrize("product_id", ["P1", "PRODUCT01"])
def test_rejects_invalid_product_id_format(tmp_path: Path, product_id: str) -> None:
    fieldnames, rows = _catalogue_rows()
    rows[0]["product_id"] = product_id

    with pytest.raises(CatalogueValidationError, match="expected 'P' followed by exactly two digits"):
        load_catalogue(_write_rows(tmp_path, fieldnames, rows))


@pytest.mark.parametrize(
    ("city_tiers", "error_message"),
    [("3", "expected one of 1, 2"), ("1;1", "Duplicate city tier 1")],
)
def test_rejects_invalid_or_duplicate_city_tiers(
    tmp_path: Path, city_tiers: str, error_message: str
) -> None:
    fieldnames, rows = _catalogue_rows()
    rows[0]["available_city_tiers"] = city_tiers

    with pytest.raises(CatalogueValidationError, match=error_message):
        load_catalogue(_write_rows(tmp_path, fieldnames, rows))


@pytest.mark.parametrize(
    ("segments", "error_message"),
    [
        ("enterprise", "Invalid target segment"),
        ("micro;micro", "Duplicate target segment 'micro'"),
    ],
)
def test_rejects_invalid_or_duplicate_target_segments(
    tmp_path: Path, segments: str, error_message: str
) -> None:
    fieldnames, rows = _catalogue_rows()
    rows[0]["target_segments"] = segments

    with pytest.raises(CatalogueValidationError, match=error_message):
        load_catalogue(_write_rows(tmp_path, fieldnames, rows))


def test_rejects_duplicate_dependencies(tmp_path: Path) -> None:
    fieldnames, rows = _catalogue_rows()
    rows[8]["requires_one_of"] = "P01|P01"

    with pytest.raises(CatalogueValidationError, match="Duplicate dependency 'P01'"):
        load_catalogue(_write_rows(tmp_path, fieldnames, rows))


def test_rejects_invalid_dependency_product_id(tmp_path: Path) -> None:
    fieldnames, rows = _catalogue_rows()
    rows[8]["requires_one_of"] = "P1"

    with pytest.raises(CatalogueValidationError, match="dependency product ID"):
        load_catalogue(_write_rows(tmp_path, fieldnames, rows))


@pytest.mark.parametrize("dependencies", ["P01||P02", "|P01", "P01|"])
def test_rejects_malformed_dependency_expressions(
    tmp_path: Path, dependencies: str
) -> None:
    fieldnames, rows = _catalogue_rows()
    rows[8]["requires_one_of"] = dependencies

    with pytest.raises(CatalogueValidationError, match="Invalid empty value in 'requires_one_of'"):
        load_catalogue(_write_rows(tmp_path, fieldnames, rows))


def test_supports_valid_forward_dependency_references(tmp_path: Path) -> None:
    fieldnames, rows = _catalogue_rows()
    rows[0]["requires_one_of"] = "P25"

    products = load_catalogue(_write_rows(tmp_path, fieldnames, rows))

    assert products[0].requires_one_of == ["P25"]
