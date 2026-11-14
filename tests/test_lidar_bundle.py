"""Contract tests for the read-only FEMIC LiDAR bundle adapter."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

import pytest
from brushline.integrations.femic import FEMIC_VERSION_PIN
from brushline.integrations.lidar import (
    BUNDLE_LAYOUT_VERSION,
    PRODUCT_MANIFEST_SCHEMA_VERSION,
    LidarBundleError,
    bundle_reference,
    load_lidar_bundle,
    product_provenance,
    validate_lidar_bundle,
    write_bundle_reference,
)

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "notes" / "reference" / "femic-lidar-bundle.v1.json"


def _canonical_sha256(payload: object) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _bundle(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    root = tmp_path / "bundle"
    products = root / "products"
    products.mkdir(parents=True)
    payload = b'{"synthetic": true}\n'
    product_path = products / "dem.json"
    product_path.write_bytes(payload)
    selection = {
        "schema_version": "femic.lidar.selection.v1",
        "generated_utc": "2026-11-14T00:00:00+00:00",
        "source": {
            "source_id": "lidarbc",
            "licence_id": "OGL-BC",
            "native_crs": "EPSG:3005",
        },
        "aoi": {"bbox_epsg3005": [0.0, 0.0, 100.0, 100.0]},
        "products": ["dem"],
        "tiles": [{"tile_id": "tile-1", "layer_id": 1}],
    }
    provenance = root / "provenance" / "selection.json"
    provenance.parent.mkdir(parents=True)
    provenance.write_text(json.dumps(selection), encoding="utf-8")
    digest = _canonical_sha256(selection)
    manifest: dict[str, object] = {
        "schema_version": PRODUCT_MANIFEST_SCHEMA_VERSION,
        "layout_version": BUNDLE_LAYOUT_VERSION,
        "bundle_id": "lidarbc-0123456789abcdef",
        "bundle_name": "lidarbc-0123456789abcdef-2026.1",
        "bundle_version": "2026.1",
        "created_utc": "2026-11-14T00:00:00+00:00",
        "producer": {"tool": "femic", "version": FEMIC_VERSION_PIN},
        "source": {
            "source_id": "lidarbc",
            "licence_id": "OGL-BC",
            "native_crs": "EPSG:3005",
        },
        "selection": {
            "schema_version": "femic.lidar.selection.v1",
            "generated_utc": "2026-11-14T00:00:00+00:00",
            "sha256": digest,
            "aoi_bbox_epsg3005": [0.0, 0.0, 100.0, 100.0],
            "requested_products": ["dem"],
            "tile_ids": ["tile-1"],
            "source_layer_ids": [1],
            "tile_count": 1,
        },
        "processing": {"version": "p3.1", "lineage": [], "parameters": {}},
        "summary": {"product_count": 1, "total_bytes": len(payload)},
        "products": [
            {
                "product_id": "dem-1",
                "product": "dem",
                "relative_path": "products/dem.json",
                "media_type": "application/json",
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "crs": "EPSG:3005",
                "resolution_m": 1.0,
                "vertical_datum": "CGVD2013",
                "retrieved_utc": "2026-11-14T00:00:00+00:00",
                "source_tile_ids": ["tile-1"],
                "source_layer_ids": [1],
                "licence_id": "OGL-BC",
                "derived": False,
                "lineage": [],
            }
        ],
        "consumer_contract": {
            "manifest_path": "manifest.json",
            "selection_provenance_path": "provenance/selection.json",
            "products_dir": "products",
            "pin_rule": "pin the bundle",
            "native_resolution_rule": "do not reproject silently",
            "consumer_phases": {"ws4": "P43", "fhops": "P13"},
        },
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root, manifest


def _write(root: Path, manifest: dict[str, object]) -> None:
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _set_selection(
    root: Path,
    manifest: dict[str, object],
    selection: dict[str, object],
) -> None:
    (root / "provenance" / "selection.json").write_text(json.dumps(selection), encoding="utf-8")
    cast("dict[str, object]", manifest["selection"])["sha256"] = _canonical_sha256(selection)
    _write(root, manifest)


def _product(manifest: dict[str, object]) -> dict[str, object]:
    return cast("dict[str, object]", cast("list[object]", manifest["products"])[0])


def test_reference_matches_the_committed_contract() -> None:
    """The committed reference is the canonical bundle contract."""
    payload = json.loads(REFERENCE.read_text(encoding="utf-8"))
    assert payload == bundle_reference()
    assert payload["femic_version"] == FEMIC_VERSION_PIN
    assert payload["product_schema_version"] == PRODUCT_MANIFEST_SCHEMA_VERSION
    assert "chm" in cast("list[str]", payload["product_kinds"])


def test_valid_bundle_loads_and_yields_provenance(tmp_path: Path) -> None:
    """A valid bundle validates and yields a pinned product provenance record."""
    root, _manifest = _bundle(tmp_path)
    report = validate_lidar_bundle(root)
    assert report.is_valid
    assert report.manifest is not None
    assert report.counts["products"] == 1
    assert report.counts["total_bytes"] > 0
    loaded = load_lidar_bundle(root)
    assert loaded.bundle_id == "lidarbc-0123456789abcdef"
    provenance = product_provenance(loaded)
    assert len(provenance) == 1
    assert provenance[0].bundle_version == "2026.1"
    assert provenance[0].femic_version == FEMIC_VERSION_PIN
    assert provenance[0].sha256 == _product(_manifest)["sha256"]
    assert provenance[0].vertical_datum == "CGVD2013"
    assert provenance[0].derived is False


def test_missing_or_malformed_manifest_fails(tmp_path: Path) -> None:
    """A missing manifest, invalid JSON, or non-object payload fails."""
    missing = tmp_path / "missing"
    missing.mkdir()
    assert any(
        error.startswith("LIDAR-MANIFEST") for error in validate_lidar_bundle(missing).errors
    )
    invalid = tmp_path / "invalid"
    invalid.mkdir()
    (invalid / "manifest.json").write_text("{", encoding="utf-8")
    assert any(
        error.startswith("LIDAR-MANIFEST") for error in validate_lidar_bundle(invalid).errors
    )
    non_object = tmp_path / "non-object"
    non_object.mkdir()
    (non_object / "manifest.json").write_text("[]", encoding="utf-8")
    assert any(
        error.startswith("LIDAR-MANIFEST") for error in validate_lidar_bundle(non_object).errors
    )


def test_schema_layout_and_pin_are_exact(tmp_path: Path) -> None:
    """A different schema, layout, producer tool, or producer version fails."""
    root, manifest = _bundle(tmp_path)
    manifest["schema_version"] = "femic.lidar.product.v2"
    manifest["layout_version"] = "femic.lidar.bundle.v2"
    cast("dict[str, object]", manifest["producer"])["tool"] = "other"
    cast("dict[str, object]", manifest["producer"])["version"] = "9.9.9"
    _write(root, manifest)
    errors = validate_lidar_bundle(root).errors
    assert any(error.startswith("LIDAR-SCHEMA") for error in errors)
    assert any(error.startswith("LIDAR-LAYOUT") for error in errors)
    assert any(error.startswith("LIDAR-PIN") for error in errors)


def test_source_and_contract_errors(tmp_path: Path) -> None:
    """Source identity, licence, CRS, processing, and consumer keys are required."""
    root, manifest = _bundle(tmp_path)
    source = cast("dict[str, object]", manifest["source"])
    source["source_id"] = "other"
    source["licence_id"] = "unknown"
    source["native_crs"] = "EPSG:4326"
    cast("dict[str, object]", manifest["processing"]).pop("version")
    cast("dict[str, object]", manifest["consumer_contract"]).pop("pin_rule")
    _write(root, manifest)
    errors = validate_lidar_bundle(root).errors
    assert any(error.startswith("LIDAR-SOURCE") for error in errors)
    assert any(error.startswith("LIDAR-LICENCE") for error in errors)
    assert any(error.startswith("LIDAR-CRS") for error in errors)
    assert any(error.startswith("LIDAR-PROCESSING") for error in errors)
    assert any(error.startswith("LIDAR-CONTRACT") for error in errors)


def test_selection_digest_and_shape_errors(tmp_path: Path) -> None:
    """A bad digest, missing provenance, or malformed selection is rejected."""
    root, manifest = _bundle(tmp_path)
    cast("dict[str, object]", manifest["selection"])["sha256"] = "0" * 64
    _write(root, manifest)
    assert any(error.startswith("LIDAR-SELECTION") for error in validate_lidar_bundle(root).errors)

    root, manifest = _bundle(tmp_path / "second")
    (root / "provenance" / "selection.json").unlink()
    _write(root, manifest)
    assert any(error.startswith("LIDAR-SELECTION") for error in validate_lidar_bundle(root).errors)

    root, manifest = _bundle(tmp_path / "third")
    selection = json.loads((root / "provenance" / "selection.json").read_text())
    selection["aoi"]["bbox_epsg3005"] = [0, 0]
    (root / "provenance" / "selection.json").write_text(json.dumps(selection))
    cast("dict[str, object]", manifest["selection"])["sha256"] = _canonical_sha256(selection)
    _write(root, manifest)
    assert any(error.startswith("LIDAR-SELECTION") for error in validate_lidar_bundle(root).errors)


def test_product_paths_and_checksums_fail(tmp_path: Path) -> None:
    """A path escape, missing file, size mismatch, or checksum mismatch fails."""
    for index, (key, value, prefix) in enumerate(
        (
            ("relative_path", "../outside.json", "LIDAR-PATH"),
            ("relative_path", "products/missing.json", "LIDAR-PATH"),
            ("size_bytes", 999, "LIDAR-SIZE"),
            ("sha256", "0" * 64, "LIDAR-CHECKSUM"),
        )
    ):
        root, manifest = _bundle(tmp_path / f"case-{index}")
        product = _product(manifest)
        product[key] = value
        _write(root, manifest)
        assert any(error.startswith(prefix) for error in validate_lidar_bundle(root).errors), key


def test_product_path_symlink_escape_fails(tmp_path: Path) -> None:
    """A symlink that resolves outside the bundle is rejected."""
    root, manifest = _bundle(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text("outside\n", encoding="utf-8")
    link = root / "products" / "link.json"
    link.symlink_to(outside)
    product = _product(manifest)
    product["relative_path"] = "products/link.json"
    product["size_bytes"] = outside.stat().st_size
    product["sha256"] = hashlib.sha256(outside.read_bytes()).hexdigest()
    _write(root, manifest)
    assert any(error.startswith("LIDAR-PATH") for error in validate_lidar_bundle(root).errors)


def test_product_identity_and_kind_errors(tmp_path: Path) -> None:
    """Duplicate ids, duplicate paths, unknown kinds, and raster resolution fail."""
    root, manifest = _bundle(tmp_path)
    first = _product(manifest)
    second = dict(first)
    second["product_id"] = first["product_id"]
    second["relative_path"] = first["relative_path"]
    products = cast("list[object]", manifest["products"])
    products.append(second)
    size = first.get("size_bytes")
    assert isinstance(size, int)
    manifest["summary"] = {"product_count": 2, "total_bytes": 2 * size}
    _write(root, manifest)
    errors = validate_lidar_bundle(root).errors
    assert any("duplicate product_id" in error for error in errors)
    assert any("duplicate path" in error for error in errors)

    root, manifest = _bundle(tmp_path / "kind")
    product = _product(manifest)
    product["product"] = "unknown"
    _write(root, manifest)
    assert any(error.startswith("LIDAR-PRODUCT") for error in validate_lidar_bundle(root).errors)

    root, manifest = _bundle(tmp_path / "resolution")
    product = _product(manifest)
    product["resolution_m"] = None
    _write(root, manifest)
    assert any(error.startswith("LIDAR-RESOLUTION") for error in validate_lidar_bundle(root).errors)


def test_derived_product_lineage_and_requested_warning(tmp_path: Path) -> None:
    """A derived product is flagged consistently and warns without lineage."""
    root, manifest = _bundle(tmp_path)
    product = _product(manifest)
    product["product"] = "chm"
    product["derived"] = True
    product["lineage"] = []
    cast("dict[str, object]", manifest["selection"])["requested_products"] = ["dem", "chm"]
    _write(root, manifest)
    report = validate_lidar_bundle(root)
    assert report.is_valid
    assert any(warning.startswith("LIDAR-LINEAGE") for warning in report.warnings)
    assert any(warning.startswith("LIDAR-COVERAGE") for warning in report.warnings)


def test_product_source_licence_crs_and_tile_errors(tmp_path: Path) -> None:
    """A product's CRS, licence, tile, or layer must match the selection."""
    root, manifest = _bundle(tmp_path)
    product = _product(manifest)
    product["crs"] = "EPSG:4326"
    product["licence_id"] = "unknown"
    product["source_tile_ids"] = ["tile-2"]
    product["source_layer_ids"] = [2]
    _write(root, manifest)
    errors = validate_lidar_bundle(root).errors
    assert any(error.startswith("LIDAR-CRS") for error in errors)
    assert any(error.startswith("LIDAR-LICENCE") for error in errors)
    assert any(error.startswith("LIDAR-TILE") for error in errors)


def test_summary_and_time_errors(tmp_path: Path) -> None:
    """A summary mismatch and naive timestamps fail."""
    root, manifest = _bundle(tmp_path)
    cast("dict[str, object]", manifest["summary"])["product_count"] = 2
    manifest["created_utc"] = "2026-11-14T00:00:00"
    product = _product(manifest)
    product["retrieved_utc"] = "2026-11-14T00:00:00"
    _write(root, manifest)
    errors = validate_lidar_bundle(root).errors
    assert any(error.startswith("LIDAR-SUMMARY") for error in errors)
    assert any(error.startswith("LIDAR-TIME") for error in errors)


def test_load_raises_and_reference_writes(tmp_path: Path) -> None:
    """Loading an invalid bundle raises and the reference writer is deterministic."""
    root, manifest = _bundle(tmp_path)
    cast("dict[str, object]", manifest["producer"])["version"] = "other"
    _write(root, manifest)
    with pytest.raises(LidarBundleError, match="LIDAR-PIN"):
        load_lidar_bundle(root)
    target = write_bundle_reference(tmp_path / "reference.json")
    assert json.loads(target.read_text(encoding="utf-8")) == bundle_reference()


def test_report_to_dict_and_manifest_shape_error(tmp_path: Path) -> None:
    """A validation report serializes; a manifest missing a required key fails."""
    root, _manifest = _bundle(tmp_path)
    report = validate_lidar_bundle(root)
    assert report.to_dict()["is_valid"] is True
    root, manifest = _bundle(tmp_path / "shape")
    manifest.pop("bundle_name")
    _write(root, manifest)
    assert any(error.startswith("LIDAR-MANIFEST") for error in validate_lidar_bundle(root).errors)


def test_source_identity_fields_are_required(tmp_path: Path) -> None:
    """A missing source identity, licence, or CRS fails."""
    root, manifest = _bundle(tmp_path)
    manifest["source"] = {}
    _write(root, manifest)
    errors = validate_lidar_bundle(root).errors
    assert any("source_id is missing" in error for error in errors)
    assert any(error.startswith("LIDAR-LICENCE") for error in errors)
    assert any(error.startswith("LIDAR-CRS") for error in errors)


def test_nonpositive_resolution_and_derived_flag(tmp_path: Path) -> None:
    """A non-positive resolution and an inconsistent derived flag fail."""
    root, manifest = _bundle(tmp_path)
    product = _product(manifest)
    product["resolution_m"] = 0
    product["derived"] = True
    _write(root, manifest)
    errors = validate_lidar_bundle(root).errors
    assert any(error.startswith("LIDAR-RESOLUTION") for error in errors)
    assert any(error.startswith("LIDAR-DERIVED") for error in errors)


def test_selection_sha_and_provenance_read_errors(tmp_path: Path) -> None:
    """An invalid selection digest, unreadable provenance, or non-object fails."""
    root, manifest = _bundle(tmp_path)
    cast("dict[str, object]", manifest["selection"])["sha256"] = "bad"
    _write(root, manifest)
    assert any(error.startswith("LIDAR-SELECTION") for error in validate_lidar_bundle(root).errors)
    root, manifest = _bundle(tmp_path / "invalid")
    (root / "provenance" / "selection.json").write_text("{", encoding="utf-8")
    assert any(error.startswith("LIDAR-SELECTION") for error in validate_lidar_bundle(root).errors)
    root, manifest = _bundle(tmp_path / "non-object")
    (root / "provenance" / "selection.json").write_text("[]", encoding="utf-8")
    assert any(error.startswith("LIDAR-SELECTION") for error in validate_lidar_bundle(root).errors)


def test_selection_schema_and_shape_errors(tmp_path: Path) -> None:
    """Selection schema, source, AOI, tiles, products, and tile fields are checked."""
    root, manifest = _bundle(tmp_path / "schema")
    selection = json.loads((root / "provenance" / "selection.json").read_text())
    selection["schema_version"] = "bad"
    _set_selection(root, manifest, selection)
    assert any(
        "schema version is not supported" in error for error in validate_lidar_bundle(root).errors
    )

    variants: list[tuple[str, dict[str, object], str]] = [
        (
            "source",
            {"schema_version": "femic.lidar.selection.v1", "aoi": {}, "tiles": [], "products": []},
            "source is missing",
        ),
        (
            "aoi",
            {
                "schema_version": "femic.lidar.selection.v1",
                "source": {},
                "tiles": [],
                "products": [],
            },
            "AOI is missing",
        ),
        (
            "tiles",
            {"schema_version": "femic.lidar.selection.v1", "source": {}, "aoi": {}, "products": []},
            "tiles are missing",
        ),
        (
            "products",
            {
                "schema_version": "femic.lidar.selection.v1",
                "source": {},
                "aoi": {},
                "tiles": [{"tile_id": "t", "layer_id": 1}],
            },
            "products are missing",
        ),
    ]
    for name, selection, message in variants:
        root, manifest = _bundle(tmp_path / name)
        _set_selection(root, manifest, selection)
        assert any(message in error for error in validate_lidar_bundle(root).errors), name

    root, manifest = _bundle(tmp_path / "tile-object")
    selection = json.loads((root / "provenance" / "selection.json").read_text())
    selection["tiles"] = [1]
    _set_selection(root, manifest, selection)
    assert any("not an object" in error for error in validate_lidar_bundle(root).errors)

    root, manifest = _bundle(tmp_path / "tile-fields")
    selection = json.loads((root / "provenance" / "selection.json").read_text())
    selection["tiles"] = [{}]
    _set_selection(root, manifest, selection)
    errors = validate_lidar_bundle(root).errors
    assert any("has no tile_id" in error for error in errors)
    assert any("has no layer_id" in error for error in errors)


def test_selection_source_fields_are_required(tmp_path: Path) -> None:
    """Selection source_id, licence, and CRS are required."""
    root, manifest = _bundle(tmp_path)
    selection = json.loads((root / "provenance" / "selection.json").read_text())
    selection["source"] = {}
    _set_selection(root, manifest, selection)
    errors = validate_lidar_bundle(root).errors
    assert any("source_id is missing" in error for error in errors)
    root, manifest = _bundle(tmp_path / "licence")
    selection = json.loads((root / "provenance" / "selection.json").read_text())
    selection["source"] = {"source_id": "lidarbc"}
    _set_selection(root, manifest, selection)
    assert any("licence_id is missing" in error for error in validate_lidar_bundle(root).errors)
    root, manifest = _bundle(tmp_path / "crs")
    selection = json.loads((root / "provenance" / "selection.json").read_text())
    selection["source"] = {"source_id": "lidarbc", "licence_id": "OGL-BC"}
    _set_selection(root, manifest, selection)
    assert any("native_crs is missing" in error for error in validate_lidar_bundle(root).errors)


def test_invalid_timestamp_format_fails(tmp_path: Path) -> None:
    """A non-ISO timestamp fails with LIDAR-TIME."""
    root, manifest = _bundle(tmp_path)
    manifest["created_utc"] = "not-a-time"
    _write(root, manifest)
    assert any(error.startswith("LIDAR-TIME") for error in validate_lidar_bundle(root).errors)
