"""Pure reference semantics for the preregistered action-QBC v6 audit.

This module is copy-on-write relative to the frozen v5 implementation.  It contains no
lockbox, worker, model, controller, or filesystem operations.  The contract is frozen by
``prereg-action-qbc-v6-finite-grid-evidence-v1`` at commit
``a7f4da2d1e4773c3396243b12e983df910941c0c``.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final, TypeAlias, cast

import numpy as np

from .types import Action, ActionKind, Grid, Prediction

JsonScalar: TypeAlias = str | int | float | bool | None  # noqa: UP040
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]  # noqa: UP040
Shape: TypeAlias = tuple[int, int]  # noqa: UP040

GRID_EVIDENCE_SCHEMA_VERSION: Final = "action-qbc-v6-grid-evidence-table-v1"
GRID_EVIDENCE_ENCODING: Final = "int16-le-c-v1"
FINITE_GRID_SEMANTICS_ID: Final = "action-qbc-v6-padded-finite-grid-v1"
PAYLOAD_CAP_BYTES: Final = 67_108_864

PALETTE_TRANSFORM_NAME: Final = "palette_bijection"
TRANSLATION_PLUS_TRANSFORM_NAME: Final = "translation_row_plus_3_col_plus_5"
TRANSLATION_MINUS_TRANSFORM_NAME: Final = "translation_row_minus_3_col_minus_5"
SCALE_TRANSFORM_NAME: Final = "scale_2_nearest_neighbor"
TRANSLATION_DELTAS: Final[Mapping[str, tuple[int, int]]] = MappingProxyType(
    {
        TRANSLATION_PLUS_TRANSFORM_NAME: (3, 5),
        TRANSLATION_MINUS_TRANSFORM_NAME: (-3, -5),
    }
)
VISUAL_TRANSFORM_NAMES: Final = (
    PALETTE_TRANSFORM_NAME,
    TRANSLATION_PLUS_TRANSFORM_NAME,
    TRANSLATION_MINUS_TRANSFORM_NAME,
    SCALE_TRANSFORM_NAME,
)

REASON_ORDER: Final = (
    "base_pipeline_unavailable",
    "visual_pipeline_failed",
    "scientific_record_schema_invalid",
    "claimed_comparison_schema_invalid",
    "transform_contract_invalid",
    "required_action_mapping_missing",
    "mapped_action_frontier_mismatch",
    "compiler_role_mismatch",
    "gibbs_weight_mismatch",
    "rolewise_cost_mismatch",
    "invalid_root_prediction",
    "prediction_label_outside_palette_domain",
    "scale_output_shape_outside_prediction_domain",
    "transformed_prediction_shape_mismatch",
    "translation_prediction_overflow",
    "mapped_prediction_grid_mismatch",
    "mapped_prediction_state_mismatch",
    "mapped_prediction_level_delta_mismatch",
    "selector_numeric_diagnostic_mismatch",
    "selector_disposition_or_rank_mismatch",
    "mapped_controller_decision_mismatch",
    "mapped_robust_exploitation_set_mismatch",
    "mapped_myopic_utility_set_mismatch",
    "mapped_cross_level_utility_set_mismatch",
    "mapped_robust_exploitation_result_mismatch",
    "comparison_parity_mismatch",
)
_REASON_INDEX: Final = MappingProxyType(
    {reason: index for index, reason in enumerate(REASON_ORDER)}
)

_GRID_TABLE_KEYS: Final = frozenset({"schema_version", "blobs"})
_GRID_BLOB_KEYS: Final = frozenset(
    {"reference", "encoding", "shape", "byte_count", "data_base64", "sha256"}
)
_TRANSFORM_CONTRACT_KEYS: Final = frozenset(
    {"name", "background_label", "parameters", "contract_sha256"}
)


class V6ReferenceError(ValueError):
    """Base class for deterministic v6 reference-contract failures."""


class GridEvidenceTableError(V6ReferenceError):
    """The global content-addressed prediction-grid table is invalid."""


class TransformContractError(V6ReferenceError):
    """A compact registered visual-transform contract is invalid."""


class ActionMapError(V6ReferenceError):
    """A registered visual action map differs from its exact reconstruction."""


class ComparisonSchemaError(V6ReferenceError):
    """A comparison core or finalized comparison has a noncanonical schema."""


def canonical_json_bytes(value: JsonValue) -> bytes:
    """Return the canonical JSON representation used by the v6 evidence contract."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_sha256(value: JsonValue) -> str:
    """Hash canonical JSON bytes."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def canonicalize_reasons(reasons: Iterable[str]) -> tuple[str, ...]:
    """Deduplicate known reasons and return their preregistered order."""

    unique = set(reasons)
    unknown = unique.difference(_REASON_INDEX)
    if unknown:
        raise V6ReferenceError(f"unknown v6 comparison reason: {sorted(unknown)[0]}")
    return tuple(sorted(unique, key=_REASON_INDEX.__getitem__))


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_lower_hex(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _exact_mapping(value: object, keys: frozenset[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise V6ReferenceError(f"{label} does not have its exact registered keys")
    if not all(isinstance(key, str) for key in value):
        raise V6ReferenceError(f"{label} contains a non-string key")
    return cast(Mapping[str, object], value)


def _shape(value: object, label: str) -> Shape:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(not _is_plain_int(item) for item in value)
    ):
        raise GridEvidenceTableError(f"{label} is not a two-integer shape")
    rows, columns = cast(list[int], value)
    if not 1 <= rows <= 64 or not 1 <= columns <= 64:
        raise GridEvidenceTableError(f"{label} lies outside the Prediction grid domain")
    return rows, columns


def _canonical_grid_bytes(prediction: Prediction) -> tuple[Shape, bytes]:
    if sys.byteorder != "little":
        raise GridEvidenceTableError("v6 grid evidence requires a little-endian platform")
    shape, signature_bytes, _state, _level_delta = prediction.signature()
    canonical = np.ascontiguousarray(prediction.next_grid, dtype=np.dtype("<i2")).tobytes(order="C")
    if signature_bytes != canonical:
        raise GridEvidenceTableError(
            "canonical int16-le grid bytes differ from Prediction.signature()"
        )
    return shape, canonical


def _reference(digest: str, shape: Shape) -> str:
    return f"{digest}:{shape[0]}:{shape[1]}:{GRID_EVIDENCE_ENCODING}"


def parse_grid_evidence_reference(value: object) -> tuple[str, Shape, str]:
    """Parse and canonicalize one grid-evidence reference key."""

    if not isinstance(value, str):
        raise GridEvidenceTableError("grid-evidence reference is not a string")
    parts = value.split(":")
    if len(parts) != 4:
        raise GridEvidenceTableError("grid-evidence reference does not have four fields")
    digest, rows_text, columns_text, encoding = parts
    if not _is_lower_hex(digest, 64):
        raise GridEvidenceTableError("grid-evidence reference digest is malformed")
    if (
        not rows_text.isascii()
        or not rows_text.isdecimal()
        or not columns_text.isascii()
        or not columns_text.isdecimal()
    ):
        raise GridEvidenceTableError("grid-evidence dimensions are not ASCII decimal")
    rows = int(rows_text)
    columns = int(columns_text)
    if rows_text != str(rows) or columns_text != str(columns):
        raise GridEvidenceTableError("grid-evidence dimensions are not canonical decimal")
    if not 1 <= rows <= 64 or not 1 <= columns <= 64:
        raise GridEvidenceTableError("grid-evidence dimensions lie outside [1,64]")
    if encoding != GRID_EVIDENCE_ENCODING:
        raise GridEvidenceTableError("grid-evidence reference encoding is not registered")
    if value != _reference(digest, (rows, columns)):
        raise GridEvidenceTableError("grid-evidence reference is not canonical")
    return digest, (rows, columns), encoding


def grid_evidence_reference(prediction: Prediction) -> str:
    """Return the canonical content reference for a non-null prediction grid."""

    shape, raw = _canonical_grid_bytes(prediction)
    return _reference(hashlib.sha256(raw).hexdigest(), shape)


def build_grid_blob(prediction: Prediction) -> dict[str, JsonValue]:
    """Build one exact six-key canonical blob entry."""

    shape, raw = _canonical_grid_bytes(prediction)
    digest = hashlib.sha256(raw).hexdigest()
    return {
        "reference": _reference(digest, shape),
        "encoding": GRID_EVIDENCE_ENCODING,
        "shape": [shape[0], shape[1]],
        "byte_count": len(raw),
        "data_base64": base64.b64encode(raw).decode("ascii"),
        "sha256": digest,
    }


def empty_grid_evidence_table() -> dict[str, JsonValue]:
    """Return the exact empty table used by terminal payload fallbacks."""

    return {"schema_version": GRID_EVIDENCE_SCHEMA_VERSION, "blobs": []}


@dataclass(slots=True)
class GridEvidenceRegistry:
    """Mutable producer-side registry with deterministic content-addressed serialization."""

    _blobs: dict[str, dict[str, JsonValue]] = field(default_factory=dict, init=False)

    def add_prediction(self, prediction: Prediction | None) -> str | None:
        """Register a prediction grid and return its shared reference; null stays null."""

        if prediction is None:
            return None
        blob = build_grid_blob(prediction)
        reference = cast(str, blob["reference"])
        existing = self._blobs.get(reference)
        if existing is not None and existing != blob:
            raise GridEvidenceTableError("grid-evidence reference collision")
        self._blobs[reference] = blob
        return reference

    def add_predictions(self, predictions: Iterable[Prediction | None]) -> tuple[str | None, ...]:
        """Register prediction occurrences without deduplicating their returned references."""

        return tuple(self.add_prediction(prediction) for prediction in predictions)

    @property
    def references(self) -> tuple[str, ...]:
        return tuple(sorted(self._blobs))

    def as_json(self) -> dict[str, JsonValue]:
        """Serialize exactly one blob per unique reference in lexical reference order."""

        return {
            "schema_version": GRID_EVIDENCE_SCHEMA_VERSION,
            "blobs": [dict(self._blobs[reference]) for reference in sorted(self._blobs)],
        }


def validate_prediction_grid_reference(
    reference: object,
    *,
    grid_bytes_sha256: object,
    grid_shape: object,
) -> str:
    """Bind a serialized prediction's reference to its existing digest and shape."""

    digest, shape, _encoding = parse_grid_evidence_reference(reference)
    if grid_bytes_sha256 != digest:
        raise GridEvidenceTableError("prediction reference digest differs from its signature")
    if not isinstance(grid_shape, list) or grid_shape != [shape[0], shape[1]]:
        raise GridEvidenceTableError("prediction reference shape differs from its signature")
    return cast(str, reference)


def _decode_grid_blob(value: object) -> tuple[str, Grid]:
    try:
        row = _exact_mapping(value, _GRID_BLOB_KEYS, "grid-evidence blob")
    except V6ReferenceError as error:
        raise GridEvidenceTableError(str(error)) from error
    reference = row["reference"]
    digest, reference_shape, reference_encoding = parse_grid_evidence_reference(reference)
    if row["encoding"] != reference_encoding:
        raise GridEvidenceTableError("grid blob encoding differs from its reference")
    shape = _shape(row["shape"], "grid blob shape")
    if shape != reference_shape:
        raise GridEvidenceTableError("grid blob shape differs from its reference")
    byte_count = row["byte_count"]
    if not _is_plain_int(byte_count) or byte_count != 2 * shape[0] * shape[1]:
        raise GridEvidenceTableError("grid blob byte count is invalid")
    if row["sha256"] != digest:
        raise GridEvidenceTableError("grid blob digest differs from its reference")
    encoded = row["data_base64"]
    if (
        not isinstance(encoded, str)
        or not encoded.isascii()
        or any(character.isspace() for character in encoded)
    ):
        raise GridEvidenceTableError("grid blob base64 is not canonical ASCII")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise GridEvidenceTableError("grid blob base64 is invalid") from error
    if base64.b64encode(raw).decode("ascii") != encoded:
        raise GridEvidenceTableError("grid blob base64 has an alternate spelling")
    if len(raw) != byte_count:
        raise GridEvidenceTableError("decoded grid blob byte count is invalid")
    if hashlib.sha256(raw).hexdigest() != digest:
        raise GridEvidenceTableError("decoded grid blob digest is invalid")
    decoded = np.frombuffer(raw, dtype=np.dtype("<i2")).reshape(shape)
    if decoded.size and (int(decoded.min()) < np.iinfo(np.int16).min or int(decoded.max()) > 255):
        raise GridEvidenceTableError("decoded grid lies outside the Prediction cell domain")
    grid = np.array(decoded, dtype=np.int16, copy=True, order="C")
    grid.flags.writeable = False
    return cast(str, reference), grid


def validate_grid_evidence_table(
    value: object,
    *,
    expected_references: Iterable[str | None],
) -> Mapping[str, Grid]:
    """Validate the exact global table and return immutable decoded grids by reference."""

    try:
        table = _exact_mapping(value, _GRID_TABLE_KEYS, "grid-evidence table")
    except V6ReferenceError as error:
        raise GridEvidenceTableError(str(error)) from error
    if table["schema_version"] != GRID_EVIDENCE_SCHEMA_VERSION:
        raise GridEvidenceTableError("grid-evidence table schema identity is invalid")
    blobs = table["blobs"]
    if not isinstance(blobs, list):
        raise GridEvidenceTableError("grid-evidence blobs value is not a list")
    decoded: dict[str, Grid] = {}
    observed_order: list[str] = []
    for blob in blobs:
        reference, grid = _decode_grid_blob(blob)
        if reference in decoded:
            raise GridEvidenceTableError("grid-evidence table contains a duplicate blob")
        decoded[reference] = grid
        observed_order.append(reference)
    if observed_order != sorted(observed_order):
        raise GridEvidenceTableError("grid-evidence blobs are not in lexical reference order")
    expected: set[str] = set()
    for expected_reference in expected_references:
        if expected_reference is None:
            continue
        parsed_digest, parsed_shape, _encoding = parse_grid_evidence_reference(expected_reference)
        expected.add(_reference(parsed_digest, parsed_shape))
    if set(decoded) != expected:
        raise GridEvidenceTableError("grid-evidence referenced set is not exact")
    return MappingProxyType(decoded)


@dataclass(frozen=True, slots=True)
class TransformContract:
    """Validated compact visual-transform contract bound by canonical SHA-256."""

    name: str
    background_label: int
    parameters: Mapping[str, JsonValue]
    contract_sha256: str

    def as_json(self) -> dict[str, JsonValue]:
        return {
            "name": self.name,
            "background_label": self.background_label,
            "parameters": dict(self.parameters),
            "contract_sha256": self.contract_sha256,
        }

    def core_json(self) -> dict[str, JsonValue]:
        return {
            "name": self.name,
            "background_label": self.background_label,
            "parameters": dict(self.parameters),
        }


def _normalise_transform_parameters(name: str, value: object) -> dict[str, JsonValue]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise TransformContractError("transform parameters are not a string-keyed mapping")
    parameters = cast(Mapping[str, object], value)
    if name == PALETTE_TRANSFORM_NAME:
        if set(parameters) != {"forward_palette"}:
            raise TransformContractError("palette parameters do not have their exact keys")
        palette = parameters["forward_palette"]
        if (
            not isinstance(palette, list)
            or len(palette) != 16
            or any(not _is_plain_int(item) for item in palette)
            or sorted(cast(list[int], palette)) != list(range(16))
        ):
            raise TransformContractError("forward palette is not a permutation of labels 0..15")
        return {"forward_palette": list(cast(list[int], palette))}
    if name in TRANSLATION_DELTAS:
        if set(parameters) != {"row_delta", "col_delta"}:
            raise TransformContractError("translation parameters do not have their exact keys")
        row_delta = parameters["row_delta"]
        col_delta = parameters["col_delta"]
        if not _is_plain_int(row_delta) or not _is_plain_int(col_delta):
            raise TransformContractError("translation deltas are not integers")
        if (row_delta, col_delta) != TRANSLATION_DELTAS[name]:
            raise TransformContractError("translation deltas differ from the registered name")
        return {"row_delta": cast(int, row_delta), "col_delta": cast(int, col_delta)}
    if name == SCALE_TRANSFORM_NAME:
        if set(parameters) != {"factor", "action6_destination_cell"}:
            raise TransformContractError("scale parameters do not have their exact keys")
        if (
            parameters["factor"] != 2
            or isinstance(parameters["factor"], bool)
            or parameters["action6_destination_cell"] != "top_left_of_scaled_2x2_block"
        ):
            raise TransformContractError("scale parameters differ from the registered contract")
        return {
            "factor": 2,
            "action6_destination_cell": "top_left_of_scaled_2x2_block",
        }
    raise TransformContractError(f"unknown v6 visual transform: {name!r}")


def make_transform_contract(
    name: str | Mapping[str, object],
    *,
    background_label: int | None = None,
    parameters: Mapping[str, object] | None = None,
) -> TransformContract:
    """Build and hash an exact compact transform contract."""

    if isinstance(name, Mapping):
        manifest = name
        raw_name = manifest.get("name")
        raw_background = manifest.get("background_label")
        raw_parameters = manifest.get("parameters")
        if not isinstance(raw_name, str) or not _is_plain_int(raw_background):
            raise TransformContractError("manifest transform identity is malformed")
        if not isinstance(raw_parameters, Mapping):
            raise TransformContractError("manifest transform parameters are malformed")
        name = raw_name
        background_label = cast(int, raw_background)
        raw_parameter_map = cast(Mapping[str, object], raw_parameters)
        if name == PALETTE_TRANSFORM_NAME:
            parameters = {"forward_palette": raw_parameter_map.get("forward_palette")}
        elif name in TRANSLATION_DELTAS:
            parameters = {
                "row_delta": raw_parameter_map.get("row_delta"),
                "col_delta": raw_parameter_map.get("col_delta"),
            }
        elif name == SCALE_TRANSFORM_NAME:
            parameters = {
                "factor": raw_parameter_map.get("factor"),
                "action6_destination_cell": raw_parameter_map.get("action6_destination_cell"),
            }
        else:
            raise TransformContractError(f"unknown v6 visual transform: {name!r}")
    if name not in VISUAL_TRANSFORM_NAMES:
        raise TransformContractError(f"unknown v6 visual transform: {name!r}")
    if (
        background_label is None
        or not _is_plain_int(background_label)
        or not 0 <= background_label <= 15
    ):
        raise TransformContractError("transform background label lies outside 0..15")
    if parameters is None:
        raise TransformContractError("transform parameters are missing")
    normalized = _normalise_transform_parameters(name, parameters)
    core: dict[str, JsonValue] = {
        "name": name,
        "background_label": background_label,
        "parameters": normalized,
    }
    return TransformContract(
        name=name,
        background_label=background_label,
        parameters=MappingProxyType(normalized),
        contract_sha256=canonical_sha256(core),
    )


def validate_transform_contract(
    value: object,
    *,
    expected_sha256: str | None = None,
) -> TransformContract:
    """Validate an exact four-key contract and bind it to its registered digest."""

    try:
        row = _exact_mapping(value, _TRANSFORM_CONTRACT_KEYS, "transform contract")
    except V6ReferenceError as error:
        raise TransformContractError(str(error)) from error
    name = row["name"]
    if not isinstance(name, str):
        raise TransformContractError("transform name is not a string")
    background_label = row["background_label"]
    if not _is_plain_int(background_label):
        raise TransformContractError("transform background label is not an integer")
    contract = make_transform_contract(
        name,
        background_label=cast(int, background_label),
        parameters=cast(Mapping[str, object], row["parameters"]),
    )
    supplied_digest = row["contract_sha256"]
    if (
        not _is_lower_hex(supplied_digest, 64)
        or supplied_digest != contract.contract_sha256
        or (expected_sha256 is not None and expected_sha256 != contract.contract_sha256)
    ):
        raise TransformContractError("transform contract digest or registration binding differs")
    return contract


Coordinate: TypeAlias = tuple[int, int]  # noqa: UP040


@dataclass(frozen=True, slots=True)
class ReconstructedActionMap:
    """Exact partial ACTION6 bijection and its canonical manifest representation."""

    forward: Mapping[Coordinate, Coordinate]
    source_shape: Shape
    destination_shape: Shape
    domain: str

    def as_json(self) -> dict[str, JsonValue]:
        forward_rows: list[JsonValue] = [
            [[source[0], source[1]], [destination[0], destination[1]]]
            for source, destination in sorted(self.forward.items())
        ]
        inverse_rows: list[JsonValue] = [
            [[destination[0], destination[1]], [source[0], source[1]]]
            for source, destination in sorted(self.forward.items(), key=lambda item: item[1])
        ]
        core: dict[str, JsonValue] = {
            "domain": self.domain,
            "simple_forward": [["ACTION3", "ACTION3"]],
            "simple_inverse": [["ACTION3", "ACTION3"]],
            "action6_forward": forward_rows,
            "action6_inverse": inverse_rows,
        }
        return {**core, "content_sha256": canonical_sha256(core)}


def _validated_action_shape(value: Shape) -> Shape:
    rows, columns = value
    if (
        not _is_plain_int(rows)
        or not _is_plain_int(columns)
        or not 1 <= rows <= 64
        or not 1 <= columns <= 64
    ):
        raise ActionMapError("action-map source shape lies outside [1,64]")
    return rows, columns


def reconstruct_action_map(
    contract: TransformContract,
    source_shape: Shape,
) -> ReconstructedActionMap:
    """Reconstruct the registered partial ACTION6 map from compact semantics."""

    rows, columns = _validated_action_shape(source_shape)
    forward: dict[Coordinate, Coordinate] = {}
    if contract.name == PALETTE_TRANSFORM_NAME:
        destination_shape = (rows, columns)
        domain = "all_32x32_action6_cells"
        for row in range(rows):
            for column in range(columns):
                forward[(row, column)] = (row, column)
    elif contract.name in TRANSLATION_DELTAS:
        destination_shape = (rows, columns)
        domain = "exact_in_bounds_partial_action6_domain"
        row_delta, column_delta = TRANSLATION_DELTAS[contract.name]
        for row in range(rows):
            for column in range(columns):
                destination = (row + row_delta, column + column_delta)
                if 0 <= destination[0] < rows and 0 <= destination[1] < columns:
                    forward[(row, column)] = destination
    elif contract.name == SCALE_TRANSFORM_NAME:
        destination_shape = (2 * rows, 2 * columns)
        if destination_shape[0] > 64 or destination_shape[1] > 64:
            raise ActionMapError("scaled action-map destination lies outside [1,64]")
        domain = "all_base_action6_cells_to_top_left_scaled_cells"
        for row in range(rows):
            for column in range(columns):
                forward[(row, column)] = (2 * row, 2 * column)
    else:
        raise ActionMapError("unknown transform in action-map reconstruction")
    if len(set(forward.values())) != len(forward):
        raise ActionMapError("reconstructed action map is not a partial bijection")
    return ReconstructedActionMap(
        forward=MappingProxyType(forward),
        source_shape=(rows, columns),
        destination_shape=destination_shape,
        domain=domain,
    )


def validate_manifest_action_map(
    value: object,
    expected: ReconstructedActionMap,
) -> None:
    """Require byte-for-byte canonical equality with the reconstructed full map."""

    expected_json = expected.as_json()
    if not isinstance(value, Mapping):
        raise ActionMapError("manifest action map is not a mapping")
    try:
        observed = canonical_json_bytes(cast(JsonValue, dict(value)))
    except (TypeError, ValueError) as error:
        raise ActionMapError("manifest action map is not canonical JSON") from error
    if observed != canonical_json_bytes(expected_json):
        raise ActionMapError("manifest action map differs from exact reconstruction")


def map_action(action: Action, action_map: ReconstructedActionMap) -> Action:
    """Map a required action, raising when ACTION6 is outside the registered partial domain."""

    if action.kind is not ActionKind.ACTION6:
        return action
    assert action.row is not None and action.col is not None
    destination = action_map.forward.get((action.row, action.col))
    if destination is None:
        raise ActionMapError("required ACTION6 action is outside the registered partial map")
    try:
        return Action(ActionKind.ACTION6, destination[0], destination[1])
    except (TypeError, ValueError) as error:
        raise ActionMapError("mapped ACTION6 destination lies outside the Action domain") from error


@dataclass(frozen=True, slots=True)
class PredictionPairComparison:
    """Reference result for one ordered base/transformed hypothesis prediction pair."""

    reasons: tuple[str, ...]
    overflow_nonbackground_count: int = 0

    @property
    def passes(self) -> bool:
        return not self.reasons


def _append_prediction_metadata_reasons(
    reasons: list[str], base: Prediction, transformed: Prediction
) -> None:
    if base.game_state != transformed.game_state:
        reasons.append("mapped_prediction_state_mismatch")
    if base.level_delta != transformed.level_delta:
        reasons.append("mapped_prediction_level_delta_mismatch")


def _palette_pair(
    base: Prediction, transformed: Prediction, contract: TransformContract
) -> PredictionPairComparison:
    reasons: list[str] = []
    if base.next_grid.shape != transformed.next_grid.shape:
        reasons.append("transformed_prediction_shape_mismatch")
    base_in_domain = bool(np.all((base.next_grid >= 0) & (base.next_grid <= 15)))
    transformed_in_domain = bool(
        np.all((transformed.next_grid >= 0) & (transformed.next_grid <= 15))
    )
    if not base_in_domain or not transformed_in_domain:
        reasons.append("prediction_label_outside_palette_domain")
    if base_in_domain and base.next_grid.shape == transformed.next_grid.shape:
        palette = np.asarray(contract.parameters["forward_palette"], dtype=np.int16)
        expected = palette[base.next_grid]
        if not np.array_equal(expected, transformed.next_grid):
            reasons.append("mapped_prediction_grid_mismatch")
    _append_prediction_metadata_reasons(reasons, base, transformed)
    return PredictionPairComparison(canonicalize_reasons(reasons))


def _scale_pair(base: Prediction, transformed: Prediction) -> PredictionPairComparison:
    reasons: list[str] = []
    rows, columns = (int(base.next_grid.shape[0]), int(base.next_grid.shape[1]))
    expected_shape = (2 * rows, 2 * columns)
    output_in_domain = expected_shape[0] <= 64 and expected_shape[1] <= 64
    if not output_in_domain:
        reasons.append("scale_output_shape_outside_prediction_domain")
    if transformed.next_grid.shape != expected_shape:
        reasons.append("transformed_prediction_shape_mismatch")
    if output_in_domain and transformed.next_grid.shape == expected_shape:
        expected = np.repeat(np.repeat(base.next_grid, 2, axis=0), 2, axis=1)
        if not np.array_equal(expected, transformed.next_grid):
            reasons.append("mapped_prediction_grid_mismatch")
    _append_prediction_metadata_reasons(reasons, base, transformed)
    return PredictionPairComparison(canonicalize_reasons(reasons))


def _translation_pair(
    base: Prediction, transformed: Prediction, contract: TransformContract
) -> PredictionPairComparison:
    reasons: list[str] = []
    rows, columns = (int(base.next_grid.shape[0]), int(base.next_grid.shape[1]))
    row_delta, col_delta = TRANSLATION_DELTAS[contract.name]
    non_background_rows, non_background_columns = np.nonzero(
        base.next_grid != contract.background_label
    )
    overflow = sum(
        1
        for row, column in zip(non_background_rows, non_background_columns, strict=True)
        if not (0 <= int(row) + row_delta < rows and 0 <= int(column) + col_delta < columns)
    )
    if overflow:
        reasons.append("translation_prediction_overflow")
    same_shape = base.next_grid.shape == transformed.next_grid.shape
    if not same_shape:
        reasons.append("transformed_prediction_shape_mismatch")
    if same_shape:
        pad_rows, pad_columns = abs(row_delta), abs(col_delta)
        padded_shape = (rows + 2 * pad_rows, columns + 2 * pad_columns)
        embedded_base = np.full(padded_shape, contract.background_label, dtype=np.int16)
        embedded_actual = np.full(padded_shape, contract.background_label, dtype=np.int16)
        embedded_base[
            pad_rows : pad_rows + rows,
            pad_columns : pad_columns + columns,
        ] = base.next_grid
        embedded_actual[
            pad_rows : pad_rows + rows,
            pad_columns : pad_columns + columns,
        ] = transformed.next_grid
        expected = np.full(padded_shape, contract.background_label, dtype=np.int16)
        expected[
            pad_rows + row_delta : pad_rows + row_delta + rows,
            pad_columns + col_delta : pad_columns + col_delta + columns,
        ] = embedded_base[
            pad_rows : pad_rows + rows,
            pad_columns : pad_columns + columns,
        ]
        if not np.array_equal(expected, embedded_actual):
            reasons.append("mapped_prediction_grid_mismatch")
    _append_prediction_metadata_reasons(reasons, base, transformed)
    return PredictionPairComparison(canonicalize_reasons(reasons), overflow)


def compare_prediction_pair(
    base: Prediction | None,
    transformed: Prediction | None,
    contract: TransformContract,
) -> PredictionPairComparison:
    """Apply the exact palette, scale, or padded-translation reference relation."""

    if base is None or transformed is None:
        return PredictionPairComparison(("invalid_root_prediction",))
    if contract.name == PALETTE_TRANSFORM_NAME:
        return _palette_pair(base, transformed, contract)
    if contract.name == SCALE_TRANSFORM_NAME:
        return _scale_pair(base, transformed)
    if contract.name in TRANSLATION_DELTAS:
        return _translation_pair(base, transformed, contract)
    raise TransformContractError(f"unknown validated transform: {contract.name!r}")


_COMPARISON_CORE_KEYS: Final = frozenset(
    {
        "mapped_action_count",
        "unmapped_action_count",
        "prediction_pair_count",
        "overflow_nonbackground_count",
        "reasons",
        "passes",
    }
)
_FINAL_COMPARISON_KEYS: Final = frozenset(
    {
        "status",
        "semantics_id",
        "mapped_action_count",
        "unmapped_action_count",
        "prediction_pair_count",
        "overflow_nonbackground_count",
        "reasons",
        "passes",
        "parity",
    }
)
_PIPELINE_REASONS: Final = frozenset(REASON_ORDER[:2])
_DERIVATION_REASONS: Final = frozenset(REASON_ORDER[2:5])
_EVALUATED_REASONS: Final = frozenset(REASON_ORDER[5:25])


def _nonnegative_count(value: object, label: str) -> int:
    if not _is_plain_int(value) or cast(int, value) < 0:
        raise ComparisonSchemaError(f"{label} is not a non-negative integer")
    return cast(int, value)


def make_comparison_core(
    *,
    mapped_action_count: int,
    unmapped_action_count: int,
    prediction_pair_count: int,
    overflow_nonbackground_count: int,
    reasons: Iterable[str],
) -> dict[str, JsonValue]:
    """Build the exact six-key authoritative/claimed evaluated comparison core."""

    counts = (
        _nonnegative_count(mapped_action_count, "mapped action count"),
        _nonnegative_count(unmapped_action_count, "unmapped action count"),
        _nonnegative_count(prediction_pair_count, "prediction-pair count"),
        _nonnegative_count(overflow_nonbackground_count, "overflow count"),
    )
    ordered = canonicalize_reasons(reasons)
    if any(reason not in _EVALUATED_REASONS for reason in ordered):
        raise ComparisonSchemaError("evaluated core contains a non-evaluated reason")
    return {
        "mapped_action_count": counts[0],
        "unmapped_action_count": counts[1],
        "prediction_pair_count": counts[2],
        "overflow_nonbackground_count": counts[3],
        "reasons": list(ordered),
        "passes": not ordered,
    }


def validate_comparison_core(value: object) -> dict[str, JsonValue]:
    """Validate and return one exact evaluated six-key comparison core."""

    try:
        row = _exact_mapping(value, _COMPARISON_CORE_KEYS, "comparison core")
    except V6ReferenceError as error:
        raise ComparisonSchemaError(str(error)) from error
    reasons = row["reasons"]
    if not isinstance(reasons, list) or any(not isinstance(reason, str) for reason in reasons):
        raise ComparisonSchemaError("comparison-core reasons are not a string list")
    ordered = canonicalize_reasons(cast(list[str], reasons))
    if list(ordered) != reasons or any(reason not in _EVALUATED_REASONS for reason in ordered):
        raise ComparisonSchemaError("comparison-core reasons are not canonical evaluated reasons")
    passes = row["passes"]
    if not isinstance(passes, bool) or passes is not (not ordered):
        raise ComparisonSchemaError("comparison-core pass flag differs from its reasons")
    return make_comparison_core(
        mapped_action_count=_nonnegative_count(row["mapped_action_count"], "mapped action count"),
        unmapped_action_count=_nonnegative_count(
            row["unmapped_action_count"], "unmapped action count"
        ),
        prediction_pair_count=_nonnegative_count(
            row["prediction_pair_count"], "prediction-pair count"
        ),
        overflow_nonbackground_count=_nonnegative_count(
            row["overflow_nonbackground_count"], "overflow count"
        ),
        reasons=ordered,
    )


def _final_comparison(
    *,
    status: str,
    core: Mapping[str, JsonValue],
    parity: JsonValue,
) -> dict[str, JsonValue]:
    return {
        "status": status,
        "semantics_id": FINITE_GRID_SEMANTICS_ID,
        "mapped_action_count": core["mapped_action_count"],
        "unmapped_action_count": core["unmapped_action_count"],
        "prediction_pair_count": core["prediction_pair_count"],
        "overflow_nonbackground_count": core["overflow_nonbackground_count"],
        "reasons": core["reasons"],
        "passes": core["passes"],
        "parity": parity,
    }


def pipeline_error_comparison(reason: str) -> dict[str, JsonValue]:
    """Build an exact nine-key pipeline-error comparison."""

    if reason not in _PIPELINE_REASONS:
        raise ComparisonSchemaError("pipeline error reason is not registered")
    core: dict[str, JsonValue] = {
        "mapped_action_count": 0,
        "unmapped_action_count": 0,
        "prediction_pair_count": 0,
        "overflow_nonbackground_count": 0,
        "reasons": [reason],
        "passes": False,
    }
    return _final_comparison(status="pipeline_error", core=core, parity=None)


def derivation_error_comparison(reason: str) -> dict[str, JsonValue]:
    """Build an exact nine-key addressable authoritative-derivation error."""

    if reason not in _DERIVATION_REASONS:
        raise ComparisonSchemaError("derivation error reason is not registered")
    core: dict[str, JsonValue] = {
        "mapped_action_count": 0,
        "unmapped_action_count": 0,
        "prediction_pair_count": 0,
        "overflow_nonbackground_count": 0,
        "reasons": [reason],
        "passes": False,
    }
    return _final_comparison(
        status="authoritative_derivation_error",
        core=core,
        parity=None,
    )


def finalize_evaluated_comparison(
    authoritative_core: object,
    claimed_core: object,
) -> dict[str, JsonValue]:
    """Finalize equality or preserve both cores in the exact parity-mismatch schema."""

    authoritative = validate_comparison_core(authoritative_core)
    claimed = validate_comparison_core(claimed_core)
    if claimed == authoritative:
        return _final_comparison(status="evaluated", core=authoritative, parity=None)
    parity: dict[str, JsonValue] = {
        "claimed": claimed,
        "authoritative": authoritative,
        "claimed_sha256": canonical_sha256(claimed),
        "authoritative_sha256": canonical_sha256(authoritative),
    }
    outer: dict[str, JsonValue] = {
        "mapped_action_count": 0,
        "unmapped_action_count": 0,
        "prediction_pair_count": 0,
        "overflow_nonbackground_count": 0,
        "reasons": ["comparison_parity_mismatch"],
        "passes": False,
    }
    return _final_comparison(
        status="authoritative_derivation_error",
        core=outer,
        parity=parity,
    )


__all__ = [
    "FINITE_GRID_SEMANTICS_ID",
    "GRID_EVIDENCE_ENCODING",
    "GRID_EVIDENCE_SCHEMA_VERSION",
    "PALETTE_TRANSFORM_NAME",
    "PAYLOAD_CAP_BYTES",
    "REASON_ORDER",
    "SCALE_TRANSFORM_NAME",
    "TRANSLATION_DELTAS",
    "TRANSLATION_MINUS_TRANSFORM_NAME",
    "TRANSLATION_PLUS_TRANSFORM_NAME",
    "VISUAL_TRANSFORM_NAMES",
    "ActionMapError",
    "ComparisonSchemaError",
    "GridEvidenceRegistry",
    "GridEvidenceTableError",
    "JsonValue",
    "PredictionPairComparison",
    "ReconstructedActionMap",
    "TransformContract",
    "TransformContractError",
    "V6ReferenceError",
    "build_grid_blob",
    "canonical_json_bytes",
    "canonical_sha256",
    "canonicalize_reasons",
    "compare_prediction_pair",
    "derivation_error_comparison",
    "empty_grid_evidence_table",
    "finalize_evaluated_comparison",
    "grid_evidence_reference",
    "make_comparison_core",
    "make_transform_contract",
    "map_action",
    "parse_grid_evidence_reference",
    "pipeline_error_comparison",
    "reconstruct_action_map",
    "validate_comparison_core",
    "validate_grid_evidence_table",
    "validate_manifest_action_map",
    "validate_prediction_grid_reference",
    "validate_transform_contract",
]
