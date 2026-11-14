"""Read-only FEMIC LiDAR bundle adapter and provenance.

Brushline consumes the producer's packaged product bundle. It does not discover tiles, download
points, compile terrain, or write payloads. The adapter reads the manifest, pins the FEMIC producer
version and bundle identity, verifies the selection digest and every product checksum, checks the
native CRS, resolution, vertical datum, licence, and lineage, and returns source-preserving
provenance for later segment aggregation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from brushline.integrations.femic import FEMIC_VERSION_PIN

LIDAR_BUNDLE_REFERENCE_SCHEMA_VERSION: Literal["brushline.lidar-bundle-reference.v1"] = (
    "brushline.lidar-bundle-reference.v1"
)
PRODUCT_MANIFEST_SCHEMA_VERSION = "femic.lidar.product.v1"
BUNDLE_LAYOUT_VERSION = "femic.lidar.bundle.v1"
SELECTION_SCHEMA_VERSION = "femic.lidar.selection.v1"
MANIFEST_NAME = "manifest.json"
SELECTION_PROVENANCE_PATH = "provenance/selection.json"
PRODUCTS_DIR = "products"
PRODUCER_TOOL = "femic"
LIDARBC_SOURCE_ID = "lidarbc"
LIDARBC_LICENCE_ID = "OGL-BC"
LIDARBC_NATIVE_CRS = "EPSG:3005"
PRODUCT_KINDS: tuple[str, ...] = (
    "point_cloud",
    "dem",
    "dsm",
    "chm",
    "canopy",
    "individual_tree",
    "slope",
)
RASTER_PRODUCT_KINDS: frozenset[str] = frozenset({"dem", "dsm", "chm", "canopy", "slope"})
DERIVED_PRODUCT_KINDS: frozenset[str] = frozenset({"chm", "canopy", "slope"})
CONSUMER_CONTRACT_KEYS: tuple[str, ...] = (
    "manifest_path",
    "selection_provenance_path",
    "products_dir",
    "pin_rule",
    "native_resolution_rule",
    "consumer_phases",
)


class LidarBundleError(RuntimeError):
    """Raised when a FEMIC LiDAR bundle cannot be loaded or validated."""


class LidarProductRecord(BaseModel):
    """One packaged product in a FEMIC LiDAR bundle.

    Parameters
    ----------
    product_id : str
        Stable product identifier.
    product : str
        Product kind.
    relative_path : str
        Bundle-relative product path.
    media_type : str
        Media type.
    size_bytes : int
        Product size in bytes.
    sha256 : str
        Product SHA-256.
    crs : str
        Product CRS.
    resolution_m : float or None
        Raster resolution in metres, or ``None`` for a non-raster product.
    vertical_datum : str
        Vertical datum.
    retrieved_utc : str
        Source retrieval time.
    source_tile_ids : list of str
        Source tile ids.
    source_layer_ids : list of int
        Source layer ids.
    licence_id : str
        Source licence.
    derived : bool
        Whether the product is derived.
    lineage : list of str, optional
        Processing lineage notes.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    product_id: str = Field(min_length=1)
    product: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    crs: str = Field(min_length=1)
    resolution_m: float | None = None
    vertical_datum: str = Field(min_length=1)
    retrieved_utc: str = Field(min_length=1)
    source_tile_ids: list[str] = Field(min_length=1)
    source_layer_ids: list[int] = Field(default_factory=list)
    licence_id: str = Field(min_length=1)
    derived: bool = False
    lineage: list[str] = Field(default_factory=list)


class LidarBundleSummary(BaseModel):
    """The manifest summary counts.

    Parameters
    ----------
    product_count : int
        Number of products.
    total_bytes : int
        Total product bytes.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    product_count: int = Field(ge=0)
    total_bytes: int = Field(ge=0)


class LidarBundleManifest(BaseModel):
    """The consumer-facing FEMIC product bundle manifest.

    Parameters
    ----------
    schema_version : str
        Product manifest schema version.
    layout_version : str
        Bundle layout version.
    bundle_id : str
        Stable bundle id.
    bundle_name : str
        Human bundle name.
    bundle_version : str
        Bundle version.
    created_utc : str
        Creation time.
    producer : dict of str to object
        Producer tool and version.
    source : dict of str to object
        Source identity, licence, and native CRS.
    selection : dict of str to object
        Selection digest and tile summary.
    processing : dict of str to object
        Processing version, lineage, and parameters.
    summary : LidarBundleSummary
        Product counts and bytes.
    products : list of LidarProductRecord
        Packaged products.
    consumer_contract : dict of str to object
        Consumer rules.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    layout_version: str
    bundle_id: str = Field(min_length=1)
    bundle_name: str = Field(min_length=1)
    bundle_version: str = Field(min_length=1)
    created_utc: str = Field(min_length=1)
    producer: dict[str, object]
    source: dict[str, object]
    selection: dict[str, object]
    processing: dict[str, object]
    summary: LidarBundleSummary
    products: list[LidarProductRecord] = Field(min_length=1)
    consumer_contract: dict[str, object]


class LidarProductProvenance(BaseModel):
    """The provenance that travels with one product-derived attribute.

    Parameters
    ----------
    bundle_id : str
        Pinned bundle id.
    bundle_version : str
        Pinned bundle version.
    femic_version : str
        Producer FEMIC version.
    product_id : str
        Product id.
    product : str
        Product kind.
    sha256 : str
        Product checksum.
    crs : str
        Product CRS.
    resolution_m : float or None
        Product resolution.
    vertical_datum : str
        Product vertical datum.
    licence_id : str
        Product licence.
    retrieved_utc : str
        Source retrieval time.
    source_tile_ids : list of str
        Source tiles.
    source_layer_ids : list of int
        Source layers.
    derived : bool
        Whether the product is derived.
    lineage : list of str
        Lineage notes.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    bundle_id: str
    bundle_version: str
    femic_version: str
    product_id: str
    product: str
    sha256: str
    crs: str
    resolution_m: float | None
    vertical_datum: str
    licence_id: str
    retrieved_utc: str
    source_tile_ids: list[str]
    source_layer_ids: list[int]
    derived: bool
    lineage: list[str]


@dataclass(frozen=True)
class LidarBundleValidation:
    """The outcome of validating one FEMIC LiDAR bundle.

    Parameters
    ----------
    bundle_dir : Path
        Resolved bundle directory.
    manifest : LidarBundleManifest or None
        Parsed manifest when the JSON shape is valid.
    errors : tuple of str
        Named errors.
    warnings : tuple of str
        Non-fatal findings.
    counts : dict of str to int or float
        Product and byte counts.
    """

    bundle_dir: Path
    manifest: LidarBundleManifest | None
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    counts: dict[str, int | float]

    @property
    def is_valid(self) -> bool:
        """Return whether the bundle passed every check.

        Returns
        -------
        bool
            ``True`` when there are no errors.
        """
        return not self.errors

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-ready validation report.

        Returns
        -------
        dict of str to object
            Bundle path, validity, errors, warnings, and counts.
        """
        return {
            "bundle_dir": str(self.bundle_dir),
            "is_valid": self.is_valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "counts": dict(sorted(self.counts.items())),
        }


def validate_lidar_bundle(
    bundle_dir: Path,
    *,
    expected_femic_version: str = FEMIC_VERSION_PIN,
) -> LidarBundleValidation:
    """Validate a FEMIC product bundle without reading a payload.

    Parameters
    ----------
    bundle_dir : Path
        Bundle directory containing ``manifest.json``.
    expected_femic_version : str, optional
        Exact FEMIC producer version. Defaults to the pinned boundary.

    Returns
    -------
    LidarBundleValidation
        Manifest, errors, warnings, and counts.
    """
    root = Path(bundle_dir).expanduser().resolve()
    manifest_path = root / MANIFEST_NAME
    errors: list[str] = []
    warnings: list[str] = []
    manifest: LidarBundleManifest | None = None
    counts: dict[str, int | float] = {
        "products": 0,
        "total_bytes": 0,
    }
    if not manifest_path.is_file():
        errors.append(f"LIDAR-MANIFEST: no {MANIFEST_NAME} in {root}")
        return LidarBundleValidation(root, None, tuple(errors), tuple(warnings), counts)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"LIDAR-MANIFEST: cannot read {MANIFEST_NAME}: {exc}")
        return LidarBundleValidation(root, None, tuple(errors), tuple(warnings), counts)
    if not isinstance(payload, dict):
        errors.append("LIDAR-MANIFEST: manifest is not a JSON object")
        return LidarBundleValidation(root, None, tuple(errors), tuple(warnings), counts)
    try:
        manifest = LidarBundleManifest.model_validate(payload)
    except ValidationError as exc:
        errors.append(f"LIDAR-MANIFEST: {exc}")
        return LidarBundleValidation(root, None, tuple(errors), tuple(warnings), counts)
    counts["products"] = len(manifest.products)
    counts["total_bytes"] = sum(product.size_bytes for product in manifest.products)
    if manifest.schema_version != PRODUCT_MANIFEST_SCHEMA_VERSION:
        errors.append(
            f"LIDAR-SCHEMA: expected {PRODUCT_MANIFEST_SCHEMA_VERSION!r}, got "
            f"{manifest.schema_version!r}"
        )
    if manifest.layout_version != BUNDLE_LAYOUT_VERSION:
        errors.append(
            f"LIDAR-LAYOUT: expected {BUNDLE_LAYOUT_VERSION!r}, got {manifest.layout_version!r}"
        )
    _check_time(manifest.created_utc, "manifest created_utc", errors)
    producer = _mapping(manifest.producer)
    if producer.get("tool") != PRODUCER_TOOL:
        errors.append(f"LIDAR-PIN: producer tool is not {PRODUCER_TOOL!r}")
    if producer.get("version") != expected_femic_version:
        errors.append(
            f"LIDAR-PIN: producer version {producer.get('version')!r} is not "
            f"the pinned {expected_femic_version!r}"
        )
    source = _mapping(manifest.source)
    selection = _mapping(manifest.selection)
    processing = _mapping(manifest.processing)
    if not source.get("source_id"):
        errors.append("LIDAR-SOURCE: source_id is missing")
    if source.get("source_id") != LIDARBC_SOURCE_ID:
        errors.append(
            f"LIDAR-SOURCE: source_id {source.get('source_id')!r} is not {LIDARBC_SOURCE_ID!r}"
        )
    if source.get("licence_id") != LIDARBC_LICENCE_ID:
        errors.append(
            f"LIDAR-LICENCE: source licence {source.get('licence_id')!r} is not "
            f"{LIDARBC_LICENCE_ID!r}"
        )
    if source.get("native_crs") != LIDARBC_NATIVE_CRS:
        errors.append(
            f"LIDAR-CRS: native CRS {source.get('native_crs')!r} is not {LIDARBC_NATIVE_CRS!r}"
        )
    selection_facts = _selection_facts(root, selection, errors)
    if selection_facts is not None:
        if source.get("source_id") != selection_facts.source_id:
            errors.append("LIDAR-SOURCE: manifest source does not match selection provenance")
        if source.get("licence_id") != selection_facts.licence_id:
            errors.append("LIDAR-LICENCE: manifest licence does not match selection provenance")
        if source.get("native_crs") != selection_facts.native_crs:
            errors.append("LIDAR-CRS: manifest CRS does not match selection provenance")
    if not processing.get("version"):
        errors.append("LIDAR-PROCESSING: processing.version is missing")
    for key in CONSUMER_CONTRACT_KEYS:
        if key not in manifest.consumer_contract:
            errors.append(f"LIDAR-CONTRACT: consumer_contract is missing {key!r}")
    if manifest.summary.product_count != len(manifest.products):
        errors.append("LIDAR-SUMMARY: product_count does not match products")
    if manifest.summary.total_bytes != counts["total_bytes"]:
        errors.append("LIDAR-SUMMARY: total_bytes does not match products")
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    recorded_products: set[str] = set()
    for product in manifest.products:
        if product.product_id in seen_ids:
            errors.append(f"LIDAR-PRODUCT: duplicate product_id {product.product_id!r}")
        seen_ids.add(product.product_id)
        if product.relative_path in seen_paths:
            errors.append(f"LIDAR-PRODUCT: duplicate path {product.relative_path!r}")
        seen_paths.add(product.relative_path)
        recorded_products.add(product.product)
        if product.product not in PRODUCT_KINDS:
            errors.append(f"LIDAR-PRODUCT: unsupported product kind {product.product!r}")
        if product.product in RASTER_PRODUCT_KINDS and product.resolution_m is None:
            errors.append(
                f"LIDAR-RESOLUTION: raster {product.relative_path} is missing resolution_m"
            )
        if product.resolution_m is not None and product.resolution_m <= 0:
            errors.append(f"LIDAR-RESOLUTION: {product.relative_path} has non-positive resolution")
        if product.derived != (product.product in DERIVED_PRODUCT_KINDS):
            errors.append(
                f"LIDAR-DERIVED: {product.relative_path} has an inconsistent derived flag"
            )
        if product.product in DERIVED_PRODUCT_KINDS and not product.lineage:
            warnings.append(f"LIDAR-LINEAGE: derived {product.relative_path} has no lineage notes")
        _check_time(product.retrieved_utc, f"{product.product_id} retrieved_utc", errors)
        if selection_facts is not None:
            if product.crs != selection_facts.native_crs:
                errors.append(f"LIDAR-CRS: {product.relative_path} does not match native CRS")
            if product.licence_id != selection_facts.licence_id:
                errors.append(
                    f"LIDAR-LICENCE: {product.relative_path} does not match source licence"
                )
            unknown_tiles = set(product.source_tile_ids) - selection_facts.tile_ids
            if unknown_tiles:
                errors.append(
                    f"LIDAR-TILE: {product.relative_path} references unknown tiles: "
                    f"{', '.join(sorted(unknown_tiles))}"
                )
            unknown_layers = set(product.source_layer_ids) - selection_facts.layer_ids
            if unknown_layers:
                errors.append(
                    f"LIDAR-TILE: {product.relative_path} references unknown layers: "
                    f"{', '.join(str(layer) for layer in sorted(unknown_layers))}"
                )
        artifact = _bundle_member(root, product.relative_path)
        if artifact is None:
            errors.append(f"LIDAR-PATH: {product.relative_path!r} escapes the bundle")
        elif not artifact.is_file():
            errors.append(f"LIDAR-PATH: missing product {product.relative_path}")
        else:
            if artifact.stat().st_size != product.size_bytes:
                errors.append(f"LIDAR-SIZE: {product.relative_path} size does not match")
            if _sha256(artifact) != product.sha256:
                errors.append(f"LIDAR-CHECKSUM: {product.relative_path} checksum does not match")
    if selection_facts is not None:
        requested = set(selection_facts.products)
        missing = requested - recorded_products
        if missing:
            warnings.append(
                "LIDAR-COVERAGE: requested products absent: " + ", ".join(sorted(missing))
            )
    return LidarBundleValidation(
        root,
        manifest,
        tuple(errors),
        tuple(warnings),
        counts,
    )


def load_lidar_bundle(
    bundle_dir: Path,
    *,
    expected_femic_version: str = FEMIC_VERSION_PIN,
) -> LidarBundleManifest:
    """Load and validate a FEMIC LiDAR bundle.

    Parameters
    ----------
    bundle_dir : Path
        Bundle directory.
    expected_femic_version : str, optional
        Exact producer version.

    Returns
    -------
    LidarBundleManifest
        Validated manifest.

    Raises
    ------
    LidarBundleError
        When the bundle is invalid.
    """
    report = validate_lidar_bundle(
        bundle_dir,
        expected_femic_version=expected_femic_version,
    )
    if not report.is_valid or report.manifest is None:
        raise LidarBundleError("; ".join(report.errors))
    return report.manifest


def product_provenance(
    manifest: LidarBundleManifest,
) -> tuple[LidarProductProvenance, ...]:
    """Return source-preserving provenance for every product.

    Parameters
    ----------
    manifest : LidarBundleManifest
        Validated manifest.

    Returns
    -------
    tuple of LidarProductProvenance
        One provenance record per product.
    """
    femic_version = str(manifest.producer.get("version", ""))
    return tuple(
        LidarProductProvenance(
            bundle_id=manifest.bundle_id,
            bundle_version=manifest.bundle_version,
            femic_version=femic_version,
            product_id=product.product_id,
            product=product.product,
            sha256=product.sha256,
            crs=product.crs,
            resolution_m=product.resolution_m,
            vertical_datum=product.vertical_datum,
            licence_id=product.licence_id,
            retrieved_utc=product.retrieved_utc,
            source_tile_ids=list(product.source_tile_ids),
            source_layer_ids=list(product.source_layer_ids),
            derived=product.derived,
            lineage=list(product.lineage),
        )
        for product in manifest.products
    )


def bundle_reference() -> dict[str, object]:
    """Return the committed bundle contract reference.

    Returns
    -------
    dict of str to object
        Schema, pin, required keys, product kinds, and consumer rules.
    """
    return {
        "schema_version": LIDAR_BUNDLE_REFERENCE_SCHEMA_VERSION,
        "product_schema_version": PRODUCT_MANIFEST_SCHEMA_VERSION,
        "layout_version": BUNDLE_LAYOUT_VERSION,
        "selection_schema_version": SELECTION_SCHEMA_VERSION,
        "femic_version": FEMIC_VERSION_PIN,
        "producer_tool": PRODUCER_TOOL,
        "manifest_path": MANIFEST_NAME,
        "selection_provenance_path": SELECTION_PROVENANCE_PATH,
        "products_dir": PRODUCTS_DIR,
        "required_manifest_keys": [
            "schema_version",
            "layout_version",
            "bundle_id",
            "bundle_name",
            "bundle_version",
            "created_utc",
            "producer",
            "source",
            "selection",
            "processing",
            "summary",
            "products",
            "consumer_contract",
        ],
        "required_product_keys": [
            "product_id",
            "product",
            "relative_path",
            "media_type",
            "size_bytes",
            "sha256",
            "crs",
            "resolution_m",
            "vertical_datum",
            "retrieved_utc",
            "source_tile_ids",
            "source_layer_ids",
            "licence_id",
            "derived",
            "lineage",
        ],
        "product_kinds": list(PRODUCT_KINDS),
        "raster_product_kinds": sorted(RASTER_PRODUCT_KINDS),
        "derived_product_kinds": sorted(DERIVED_PRODUCT_KINDS),
        "pin_rule": (
            "Pin bundle_id and bundle_version, verify the producer version, and "
            "verify every product sha256 before use."
        ),
        "native_resolution_rule": (
            "Consume the recorded CRS, resolution, and vertical datum. Do not "
            "reproject or resample silently."
        ),
        "payload_rule": (
            "Brushline reads product bytes only after validation. The adapter "
            "does not download tiles, compile terrain, or write a payload."
        ),
        "model_card_rule": (
            "The product manifest does not carry a low-vegetation model card; "
            "P3.4 and P3.5 attach model cards and applicability to derived "
            "attributes."
        ),
    }


def write_bundle_reference(path: Path) -> Path:
    """Write the bundle contract reference as formatted JSON.

    Parameters
    ----------
    path : Path
        Destination JSON path.

    Returns
    -------
    Path
        The written path.
    """
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(bundle_reference(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


@dataclass(frozen=True)
class _SelectionFacts:
    source_id: str
    licence_id: str
    native_crs: str
    tile_ids: set[str]
    layer_ids: set[int]
    products: set[str]


def _selection_facts(
    root: Path,
    selection: dict[str, object],
    errors: list[str],
) -> _SelectionFacts | None:
    digest = selection.get("sha256")
    if not isinstance(digest, str) or not _is_sha256(digest):
        errors.append("LIDAR-SELECTION: selection.sha256 is missing or invalid")
        return None
    provenance_path = root / SELECTION_PROVENANCE_PATH
    if not provenance_path.is_file():
        errors.append(f"LIDAR-SELECTION: missing {SELECTION_PROVENANCE_PATH}")
        return None
    try:
        payload = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"LIDAR-SELECTION: cannot read selection provenance: {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append("LIDAR-SELECTION: selection provenance is not an object")
        return None
    if _canonical_sha256(payload) != digest:
        errors.append("LIDAR-SELECTION: selection digest does not match provenance")
    if payload.get("schema_version") != SELECTION_SCHEMA_VERSION:
        errors.append("LIDAR-SELECTION: selection schema version is not supported")
    source = payload.get("source")
    aoi = payload.get("aoi")
    raw_tiles = payload.get("tiles")
    raw_products = payload.get("products")
    if not isinstance(source, dict):
        errors.append("LIDAR-SELECTION: selection source is missing")
        return None
    if not isinstance(aoi, dict):
        errors.append("LIDAR-SELECTION: selection AOI is missing")
        return None
    if not isinstance(raw_tiles, list) or not raw_tiles:
        errors.append("LIDAR-SELECTION: selection tiles are missing")
        return None
    if not isinstance(raw_products, list) or not all(
        isinstance(item, str) for item in raw_products
    ):
        errors.append("LIDAR-SELECTION: selection products are missing")
        return None
    bbox = aoi.get("bbox_epsg3005")
    if (
        not isinstance(bbox, list)
        or len(bbox) != 4
        or not all(isinstance(item, (int, float)) for item in bbox)
    ):
        errors.append("LIDAR-SELECTION: selection bbox is invalid")
    tile_ids: set[str] = set()
    layer_ids: set[int] = set()
    for index, tile in enumerate(raw_tiles, start=1):
        if not isinstance(tile, dict):
            errors.append(f"LIDAR-SELECTION: tile {index} is not an object")
            continue
        tile_id = tile.get("tile_id")
        layer_id = tile.get("layer_id")
        if not isinstance(tile_id, str) or not tile_id:
            errors.append(f"LIDAR-SELECTION: tile {index} has no tile_id")
        else:
            tile_ids.add(tile_id)
        if not isinstance(layer_id, int):
            errors.append(f"LIDAR-SELECTION: tile {index} has no layer_id")
        else:
            layer_ids.add(layer_id)
    source_id = source.get("source_id")
    licence_id = source.get("licence_id")
    native_crs = source.get("native_crs")
    if not isinstance(source_id, str) or not source_id:
        errors.append("LIDAR-SELECTION: source_id is missing")
        return None
    if not isinstance(licence_id, str) or not licence_id:
        errors.append("LIDAR-SELECTION: licence_id is missing")
        return None
    if not isinstance(native_crs, str) or not native_crs:
        errors.append("LIDAR-SELECTION: native_crs is missing")
        return None
    return _SelectionFacts(
        source_id=source_id,
        licence_id=licence_id,
        native_crs=native_crs,
        tile_ids=tile_ids,
        layer_ids=layer_ids,
        products={str(item) for item in raw_products},
    )


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _bundle_member(root: Path, relative_path: str) -> Path | None:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        return None
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(payload: object) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _check_time(value: str, label: str, errors: list[str]) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"LIDAR-TIME: {label} is not an ISO timestamp")
        return
    if parsed.tzinfo is None:
        errors.append(f"LIDAR-TIME: {label} is not timezone-aware")


__all__ = [
    "BUNDLE_LAYOUT_VERSION",
    "CONSUMER_CONTRACT_KEYS",
    "DERIVED_PRODUCT_KINDS",
    "LIDARBC_LICENCE_ID",
    "LIDARBC_NATIVE_CRS",
    "LIDARBC_SOURCE_ID",
    "LIDAR_BUNDLE_REFERENCE_SCHEMA_VERSION",
    "MANIFEST_NAME",
    "PRODUCTS_DIR",
    "PRODUCT_KINDS",
    "PRODUCT_MANIFEST_SCHEMA_VERSION",
    "RASTER_PRODUCT_KINDS",
    "SELECTION_PROVENANCE_PATH",
    "SELECTION_SCHEMA_VERSION",
    "LidarBundleError",
    "LidarBundleManifest",
    "LidarBundleSummary",
    "LidarBundleValidation",
    "LidarProductProvenance",
    "LidarProductRecord",
    "bundle_reference",
    "load_lidar_bundle",
    "product_provenance",
    "validate_lidar_bundle",
    "write_bundle_reference",
]
