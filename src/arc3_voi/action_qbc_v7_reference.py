"""Pure reference semantics for the preregistered action-QBC v7 diagnostic.

The module is deliberately side-effect free.  It owns the canonical byte encodings,
visual transforms, action maps, prediction-pair classification, snapshot/selection
digests, and the diagnostic-only compound selector.  It does not read scenes, start
workers, call a controller, or expose a runtime entrypoint.

The contract is frozen by
``prereg-action-qbc-v7-open-failure-decomposition-v1`` at commit
``f4a267757a7abbd72bc1aeb86e98811c521bf574``.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import struct
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final, Literal, TypeAlias, cast

import numpy as np

from .action_qbc_policy import (
    MAX_PROBES_PER_LEVEL,
    ActionQBCRow,
    ActionQBCSelection,
    VariantPolicyDecision,
    normalise_gibbs_weights,
    select_action_conditional_qbc,
)
from .planner import ExploitChoice, PlanningSnapshot
from .types import Action, ActionKind, GameState, Grid, Prediction

JsonScalar: TypeAlias = str | int | float | bool | None  # noqa: UP040
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]  # noqa: UP040
Shape: TypeAlias = tuple[int, int]  # noqa: UP040
Coordinate: TypeAlias = tuple[int, int]  # noqa: UP040
NumericRelation: TypeAlias = Literal["tolerance", "exact_binary64"]  # noqa: UP040

GRID_EVIDENCE_SCHEMA_VERSION: Final = "action-qbc-v7-grid-evidence-table-v1"
GRID_EVIDENCE_ENCODING: Final = "int16-le-c-v1"
EXPECTED_EXTERIOR_SUPPORT_SCHEMA_VERSION: Final = (
    "action-qbc-v7-expected-exterior-support-table-v1"
)
EXPECTED_EXTERIOR_SUPPORT_ENCODING: Final = "signed-coordinate-label-json-utf8-v1"
TRANSFORM_CONTRACT_SCHEMA_VERSION: Final = "action-qbc-v7-transform-contract-v1"
ACTION_MAP_SCHEMA_VERSION: Final = "action-qbc-v7-action-map-v1"
SNAPSHOT_DIGEST_SCHEMA_VERSION: Final = "action-qbc-v7-snapshot-digest-v1"
SELECTION_DIGEST_SCHEMA_VERSION: Final = "action-qbc-v7-selection-digest-v1"
COMPOUND_SELECTOR_VERSION: Final = (
    "action-qbc-v7-compound-selector-2^-40-dense-canonical-v1"
)
FIXED_QUANTUM_NUMERATOR: Final = 1
FIXED_QUANTUM_DENOMINATOR: Final = 1_099_511_627_776
ABSOLUTE_TOLERANCE: Final = 1e-12
RELATIVE_TOLERANCE: Final = 1e-12
PAYLOAD_CAP_BYTES: Final = 67_108_864

PALETTE_TRANSFORM_NAME: Final = "palette_bijection"
TRANSLATION_PLUS_TRANSFORM_NAME: Final = "translation_row_plus_3_col_plus_5"
TRANSLATION_MINUS_TRANSFORM_NAME: Final = "translation_row_minus_3_col_minus_5"
SCALE_TRANSFORM_NAME: Final = "scale_2_nearest_neighbor"
VISUAL_TRANSFORM_NAMES: Final = (
    PALETTE_TRANSFORM_NAME,
    TRANSLATION_PLUS_TRANSFORM_NAME,
    TRANSLATION_MINUS_TRANSFORM_NAME,
    SCALE_TRANSFORM_NAME,
)
TRANSLATION_DELTAS: Final[Mapping[str, tuple[int, int]]] = MappingProxyType(
    {
        TRANSLATION_PLUS_TRANSFORM_NAME: (3, 5),
        TRANSLATION_MINUS_TRANSFORM_NAME: (-3, -5),
    }
)
ROLE_ORDER: Final = (
    "conservative_evidence",
    "topology_contact",
    "homology_alignment",
    "symmetry_completion",
)
RAW_SELECTOR_IDENTITY: Final[Mapping[str, JsonValue]] = MappingProxyType(
    {
        "module": "arc3_voi.action_qbc_policy",
        "callable": "select_action_conditional_qbc",
        "policy_version": "action-conditional-outcome-qbc-v1",
        "runtime_version": "crosslevel-voi-runtime-v5",
        "source_bundle_sha256": (
            "a2d36168936f433157052e07d7eafca4f8a65fb49c0bb61800fe53744f2d5a9d"
        ),
    }
)
FIXED_SELECTOR_IDENTITY: Final[Mapping[str, JsonValue]] = MappingProxyType(
    {
        "version": COMPOUND_SELECTOR_VERSION,
        "raw_selector_identity": dict(RAW_SELECTOR_IDENTITY),
        "quantum_numerator": FIXED_QUANTUM_NUMERATOR,
        "quantum_denominator": FIXED_QUANTUM_DENOMINATOR,
        "rank_policy": "dense_by_integer_key",
        "tie_set_policy": "complete_integer_key_ties",
        "singleton_tie_break": "canonical_action_order",
        "positive_utility_gate": "integer_key_strictly_greater_than_zero",
    }
)
REASON_ORDER: Final = (
    "no_prepreregistered_observation",
    "base_pipeline_unavailable",
    "transformed_pipeline_unavailable",
    "pipeline_snapshot_invalid",
    "required_action_mapping_missing",
    "mapped_frontier_set_mismatch",
    "mapped_frontier_sequence_mismatch",
    "action_map_not_canonical_order_preserving",
    "compiler_role_mismatch",
    "gibbs_weight_nonfinite",
    "gibbs_weight_mismatch",
    "invalid_root_prediction",
    "prediction_label_outside_palette_domain",
    "scale_output_shape_outside_prediction_domain",
    "transformed_prediction_shape_mismatch",
    "observable_prediction_grid_mismatch",
    "expected_exterior_support_present",
    "prediction_game_state_mismatch",
    "prediction_level_delta_mismatch",
    "rolewise_cost_nonfinite",
    "rolewise_cost_mismatch",
    "raw_selector_numeric_mismatch",
    "raw_selector_eligibility_mismatch",
    "raw_selector_rank_mismatch",
    "raw_selector_set_mismatch",
    "raw_selector_gate_mismatch",
    "raw_selector_decision_mismatch",
    "fixed_selector_key_mismatch",
    "fixed_selector_numeric_mismatch",
    "fixed_selector_eligibility_mismatch",
    "fixed_selector_dense_rank_mismatch",
    "fixed_selector_set_mismatch",
    "fixed_selector_gate_mismatch",
    "fixed_selector_decision_mismatch",
    "isolated_action_map_not_bijective",
    "isolated_action_map_not_canonical_order_preserving",
    "isolated_signature_transform_not_injective",
    "v6_failure_vector_mismatch",
    "prepreregistered_base_observation_mismatch",
    "structural_gate_failed",
    "mechanism_gate_failed",
    "causal_diagnostic_false",
    "order_relation_mismatch",
    "control_expectation_mismatch",
    "resource_counter_mismatch",
    "forbidden_resource_use",
    "not_testable_due_upstream_mismatch",
)
_REASON_INDEX: Final = MappingProxyType(
    {reason: index for index, reason in enumerate(REASON_ORDER)}
)

_GRID_TABLE_KEYS: Final = frozenset({"schema_version", "blobs"})
_GRID_BLOB_KEYS: Final = frozenset(
    {"reference", "encoding", "shape", "byte_count", "data_base64", "sha256"}
)
_SUPPORT_TABLE_KEYS: Final = frozenset({"schema_version", "blobs"})
_SUPPORT_BLOB_KEYS: Final = frozenset(
    {"reference", "encoding", "entry_count", "byte_count", "data_base64", "sha256"}
)
_TRANSFORM_CONTRACT_KEYS: Final = frozenset(
    {
        "schema_version",
        "family",
        "scene_index",
        "transform_name",
        "source_shape",
        "actual_destination_shape",
        "isolated_destination_shape",
        "source_background_label",
        "destination_background_label",
        "parameters",
    }
)
_ACTION_MAP_KEYS: Final = frozenset(
    {
        "schema_version",
        "map_kind",
        "transform_contract_sha256",
        "source_shape",
        "destination_shape",
        "simple_actions",
        "action6_forward",
    }
)
_ACTION_KEYS: Final = frozenset({"kind", "row", "col"})
_ROLE_SOURCE_KEYS: Final = frozenset({"role", "source_sha256"})
_WEIGHT_KEYS: Final = frozenset({"role", "value"})
_ROOT_DIGEST_KEYS: Final = frozenset(
    {"action", "role", "grid_sha256", "grid_shape", "game_state", "level_delta"}
)
_COST_DIGEST_KEYS: Final = frozenset({"action", "role", "cost"})
_SNAPSHOT_KEYS: Final = frozenset(
    {
        "schema_version",
        "candidate_sequence",
        "source_roles",
        "normalized_weights",
        "root_predictions",
        "rolewise_costs",
    }
)
_SELECTION_KEYS: Final = frozenset(
    {
        "schema_version",
        "selector_identity",
        "candidate_records",
        "exploit_set",
        "m_maximizer_set",
        "x_maximizer_set",
        "m_decision",
        "x_decision",
    }
)
SCALAR_FIELD_ORDER: Final = (
    "outcome_concentration",
    "outcome_cell_count",
    "evsi",
    "catastrophe_mass",
    "m_utility",
    "x_utility",
    "eligible",
    "m_rank",
    "x_rank",
    "m_selected",
    "x_selected",
    "exploit_mean_cost",
    "exploit_standard_deviation",
    "exploit_score",
    "m_key",
    "x_key",
    "exploit_key",
)
_SCALAR_KEYS: Final = frozenset(SCALAR_FIELD_ORDER)
_DECISION_KEYS: Final = frozenset(
    {"action", "mode", "score", "gate_reason", "probe_candidate"}
)


class V7ReferenceError(ValueError):
    """Base class for deterministic v7 reference-contract failures."""


class GridEvidenceTableError(V7ReferenceError):
    """The global content-addressed grid table is invalid."""


class ExteriorSupportTableError(V7ReferenceError):
    """The content-addressed expected-exterior-support table is invalid."""


class TransformContractError(V7ReferenceError):
    """A visual-transform contract is malformed or differs from its semantics."""


class ActionMapError(V7ReferenceError):
    """An action map is malformed or differs from exact reconstruction."""


class PredictionPairError(V7ReferenceError):
    """A prediction-pair record cannot be constructed canonically."""


class SnapshotSchemaError(V7ReferenceError):
    """A snapshot digest preimage is not exact and addressable."""


class SelectionSchemaError(V7ReferenceError):
    """A selector result or digest preimage is not canonical."""


def canonical_json_bytes(value: JsonValue) -> bytes:
    """Return sorted-key compact ASCII-compatible UTF-8 JSON without a newline."""

    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise V7ReferenceError("value is not canonical finite JSON") from error


def canonical_sha256(value: JsonValue) -> str:
    """Hash canonical JSON bytes."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def canonicalize_reasons(reasons: Iterable[str]) -> tuple[str, ...]:
    """Deduplicate registered reasons and return their global frozen order."""

    unique = set(reasons)
    unknown = unique.difference(_REASON_INDEX)
    if unknown:
        raise V7ReferenceError(f"unknown v7 reason: {sorted(unknown)[0]}")
    return tuple(sorted(unique, key=_REASON_INDEX.__getitem__))


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_lower_hex(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _exact_mapping(
    value: object,
    keys: frozenset[str],
    label: str,
    *,
    error_type: type[V7ReferenceError] = V7ReferenceError,
) -> Mapping[str, object]:
    if (
        not isinstance(value, Mapping)
        or not all(isinstance(key, str) for key in value)
        or set(value) != keys
    ):
        raise error_type(f"{label} does not have its exact registered keys")
    return cast(Mapping[str, object], value)


def _validated_shape(
    value: object,
    label: str,
    *,
    error_type: type[V7ReferenceError] = V7ReferenceError,
) -> Shape:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or any(not _is_plain_int(item) for item in value)
    ):
        raise error_type(f"{label} is not a two-integer shape")
    rows, columns = cast(Sequence[int], value)
    if not 1 <= rows <= 64 or not 1 <= columns <= 64:
        raise error_type(f"{label} lies outside [1,64]")
    return rows, columns


def _validated_label(value: object, label: str) -> int:
    if not _is_plain_int(value) or not -32768 <= cast(int, value) <= 255:
        raise TransformContractError(f"{label} lies outside signed-int16/Prediction range")
    return cast(int, value)


def _coerce_grid(value: object, *, label: str = "grid") -> Grid:
    try:
        source = np.asarray(value)
    except (TypeError, ValueError) as error:
        raise GridEvidenceTableError(f"{label} is not an array") from error
    if source.ndim != 2 or source.shape[0] == 0 or source.shape[1] == 0:
        raise GridEvidenceTableError(f"{label} is not a nonempty two-dimensional grid")
    if source.shape[0] > 64 or source.shape[1] > 64:
        raise GridEvidenceTableError(f"{label} lies outside the 64-by-64 domain")
    if not np.issubdtype(source.dtype, np.integer):
        raise GridEvidenceTableError(f"{label} does not have integer cells")
    if source.size and (int(source.min()) < -32768 or int(source.max()) > 255):
        raise GridEvidenceTableError(f"{label} cells lie outside [-32768,255]")
    grid = np.array(source, dtype=np.dtype("<i2"), copy=True, order="C")
    grid.flags.writeable = False
    return grid


def canonical_grid_bytes(value: object) -> tuple[Shape, bytes]:
    """Validate and encode a grid as signed little-endian int16 in C order."""

    grid = _coerce_grid(value)
    shape = (int(grid.shape[0]), int(grid.shape[1]))
    return shape, np.ascontiguousarray(grid, dtype=np.dtype("<i2")).tobytes(order="C")


def _grid_reference(digest: str, shape: Shape) -> str:
    return f"{digest}:{shape[0]}:{shape[1]}:{GRID_EVIDENCE_ENCODING}"


def parse_grid_evidence_reference(value: object) -> tuple[str, Shape, str]:
    """Parse a canonical grid reference and reject alternate spellings."""

    if not isinstance(value, str):
        raise GridEvidenceTableError("grid-evidence reference is not a string")
    fields = value.split(":")
    if len(fields) != 4:
        raise GridEvidenceTableError("grid-evidence reference does not have four fields")
    digest, rows_text, columns_text, encoding = fields
    if not _is_lower_hex(digest, 64):
        raise GridEvidenceTableError("grid-evidence reference digest is malformed")
    if not rows_text.isascii() or not rows_text.isdecimal():
        raise GridEvidenceTableError("grid row count is not canonical ASCII decimal")
    if not columns_text.isascii() or not columns_text.isdecimal():
        raise GridEvidenceTableError("grid column count is not canonical ASCII decimal")
    rows, columns = int(rows_text), int(columns_text)
    if rows_text != str(rows) or columns_text != str(columns):
        raise GridEvidenceTableError("grid dimensions have an alternate decimal spelling")
    shape = _validated_shape(
        [rows, columns], "grid reference shape", error_type=GridEvidenceTableError
    )
    if encoding != GRID_EVIDENCE_ENCODING or value != _grid_reference(digest, shape):
        raise GridEvidenceTableError("grid-evidence reference is not canonical")
    return digest, shape, encoding


def grid_evidence_reference(value: object) -> str:
    """Return the content reference for one structurally valid grid."""

    shape, raw = canonical_grid_bytes(value)
    return _grid_reference(hashlib.sha256(raw).hexdigest(), shape)


def build_grid_blob(value: object) -> dict[str, JsonValue]:
    """Build one exact six-key canonical grid blob."""

    shape, raw = canonical_grid_bytes(value)
    digest = hashlib.sha256(raw).hexdigest()
    return {
        "reference": _grid_reference(digest, shape),
        "encoding": GRID_EVIDENCE_ENCODING,
        "shape": [shape[0], shape[1]],
        "byte_count": len(raw),
        "data_base64": base64.b64encode(raw).decode("ascii"),
        "sha256": digest,
    }


def empty_grid_evidence_table() -> dict[str, JsonValue]:
    """Return the exact empty grid table used by global terminal fallbacks."""

    return {"schema_version": GRID_EVIDENCE_SCHEMA_VERSION, "blobs": []}


@dataclass(slots=True)
class GridEvidenceRegistry:
    """Producer-side content-addressed grid registry with exact sharing."""

    _blobs: dict[str, dict[str, JsonValue]] = field(default_factory=dict, init=False)

    def add_grid(self, value: object | None) -> str | None:
        if value is None:
            return None
        blob = build_grid_blob(value)
        reference = cast(str, blob["reference"])
        previous = self._blobs.get(reference)
        if previous is not None and previous != blob:
            raise GridEvidenceTableError("grid-evidence reference collision")
        self._blobs[reference] = blob
        return reference

    def add_prediction(self, prediction: Prediction | None) -> str | None:
        return self.add_grid(None if prediction is None else prediction.next_grid)

    @property
    def references(self) -> tuple[str, ...]:
        return tuple(sorted(self._blobs))

    def as_json(self) -> dict[str, JsonValue]:
        return {
            "schema_version": GRID_EVIDENCE_SCHEMA_VERSION,
            "blobs": [dict(self._blobs[reference]) for reference in sorted(self._blobs)],
        }


def _decode_grid_blob(value: object) -> tuple[str, Grid]:
    row = _exact_mapping(
        value,
        _GRID_BLOB_KEYS,
        "grid-evidence blob",
        error_type=GridEvidenceTableError,
    )
    digest, reference_shape, reference_encoding = parse_grid_evidence_reference(
        row["reference"]
    )
    if row["encoding"] != reference_encoding:
        raise GridEvidenceTableError("grid blob encoding differs from its reference")
    shape = _validated_shape(
        row["shape"], "grid blob shape", error_type=GridEvidenceTableError
    )
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
    if len(raw) != byte_count or hashlib.sha256(raw).hexdigest() != digest:
        raise GridEvidenceTableError("decoded grid bytes differ from blob identity")
    decoded = np.frombuffer(raw, dtype=np.dtype("<i2")).reshape(shape)
    grid = _coerce_grid(decoded, label="decoded grid")
    if canonical_grid_bytes(grid)[1] != raw:
        raise GridEvidenceTableError("decoded grid does not re-encode canonically")
    return cast(str, row["reference"]), grid


def validate_grid_evidence_table(
    value: object,
    *,
    expected_references: Iterable[str | None],
) -> Mapping[str, Grid]:
    """Validate all grid blobs and require exact occurrence-reference coverage."""

    table = _exact_mapping(
        value,
        _GRID_TABLE_KEYS,
        "grid-evidence table",
        error_type=GridEvidenceTableError,
    )
    if table["schema_version"] != GRID_EVIDENCE_SCHEMA_VERSION:
        raise GridEvidenceTableError("grid-evidence schema identity is invalid")
    blobs = table["blobs"]
    if not isinstance(blobs, list):
        raise GridEvidenceTableError("grid-evidence blobs is not a list")
    decoded: dict[str, Grid] = {}
    order: list[str] = []
    for blob in blobs:
        reference, grid = _decode_grid_blob(blob)
        if reference in decoded:
            raise GridEvidenceTableError("grid-evidence table contains a duplicate blob")
        decoded[reference] = grid
        order.append(reference)
    if order != sorted(order):
        raise GridEvidenceTableError("grid-evidence blobs are not lexically sorted")
    expected: set[str] = set()
    for expected_reference in expected_references:
        if expected_reference is None:
            continue
        digest, shape, _encoding = parse_grid_evidence_reference(expected_reference)
        expected.add(_grid_reference(digest, shape))
    if set(decoded) != expected:
        raise GridEvidenceTableError("grid-evidence reference set is not exact")
    return MappingProxyType(decoded)


SupportEntry: TypeAlias = tuple[int, int, int]  # noqa: UP040


def canonical_support_entries(entries: Iterable[Sequence[int]]) -> tuple[SupportEntry, ...]:
    """Validate, deduplicate, and lexically order signed exterior triples."""

    normalized: list[SupportEntry] = []
    for entry in entries:
        if (
            not isinstance(entry, (list, tuple))
            or len(entry) != 3
            or any(not _is_plain_int(item) for item in entry)
        ):
            raise ExteriorSupportTableError("support entry is not a signed integer triple")
        row, column, label = cast(Sequence[int], entry)
        if not -32768 <= label <= 32767:
            raise ExteriorSupportTableError("support label lies outside signed int16")
        normalized.append((row, column, label))
    if len(set(normalized)) != len(normalized):
        raise ExteriorSupportTableError("support entries are not distinct")
    return tuple(sorted(normalized))


def _support_bytes(entries: Iterable[Sequence[int]]) -> tuple[tuple[SupportEntry, ...], bytes]:
    canonical = canonical_support_entries(entries)
    value: JsonValue = [[row, column, label] for row, column, label in canonical]
    return canonical, canonical_json_bytes(value)


def _support_reference(digest: str, entry_count: int) -> str:
    return f"{digest}:{entry_count}:{EXPECTED_EXTERIOR_SUPPORT_ENCODING}"


def parse_expected_exterior_support_reference(value: object) -> tuple[str, int, str]:
    """Parse a canonical exterior-support content reference."""

    if not isinstance(value, str):
        raise ExteriorSupportTableError("support reference is not a string")
    fields = value.split(":")
    if len(fields) != 3:
        raise ExteriorSupportTableError("support reference does not have three fields")
    digest, count_text, encoding = fields
    if not _is_lower_hex(digest, 64):
        raise ExteriorSupportTableError("support reference digest is malformed")
    if not count_text.isascii() or not count_text.isdecimal():
        raise ExteriorSupportTableError("support entry count is not ASCII decimal")
    count = int(count_text)
    if count_text != str(count):
        raise ExteriorSupportTableError("support count has an alternate decimal spelling")
    if encoding != EXPECTED_EXTERIOR_SUPPORT_ENCODING:
        raise ExteriorSupportTableError("support reference encoding is not registered")
    if value != _support_reference(digest, count):
        raise ExteriorSupportTableError("support reference is not canonical")
    return digest, count, encoding


def expected_exterior_support_reference(entries: Iterable[Sequence[int]]) -> str:
    canonical, raw = _support_bytes(entries)
    return _support_reference(hashlib.sha256(raw).hexdigest(), len(canonical))


def build_expected_exterior_support_blob(
    entries: Iterable[Sequence[int]],
) -> dict[str, JsonValue]:
    """Build one exact seven-key expected-exterior-support blob."""

    canonical, raw = _support_bytes(entries)
    digest = hashlib.sha256(raw).hexdigest()
    return {
        "reference": _support_reference(digest, len(canonical)),
        "encoding": EXPECTED_EXTERIOR_SUPPORT_ENCODING,
        "entry_count": len(canonical),
        "byte_count": len(raw),
        "data_base64": base64.b64encode(raw).decode("ascii"),
        "sha256": digest,
    }


def empty_expected_exterior_support_table() -> dict[str, JsonValue]:
    return {"schema_version": EXPECTED_EXTERIOR_SUPPORT_SCHEMA_VERSION, "blobs": []}


@dataclass(slots=True)
class ExteriorSupportRegistry:
    """Producer-side content-addressed registry for translation support manifests."""

    _blobs: dict[str, dict[str, JsonValue]] = field(default_factory=dict, init=False)

    def add(self, entries: Iterable[Sequence[int]] | None) -> str | None:
        if entries is None:
            return None
        blob = build_expected_exterior_support_blob(entries)
        reference = cast(str, blob["reference"])
        previous = self._blobs.get(reference)
        if previous is not None and previous != blob:
            raise ExteriorSupportTableError("support reference collision")
        self._blobs[reference] = blob
        return reference

    @property
    def references(self) -> tuple[str, ...]:
        return tuple(sorted(self._blobs))

    def as_json(self) -> dict[str, JsonValue]:
        return {
            "schema_version": EXPECTED_EXTERIOR_SUPPORT_SCHEMA_VERSION,
            "blobs": [dict(self._blobs[reference]) for reference in sorted(self._blobs)],
        }


def _decode_support_blob(value: object) -> tuple[str, tuple[SupportEntry, ...]]:
    row = _exact_mapping(
        value,
        _SUPPORT_BLOB_KEYS,
        "expected-exterior-support blob",
        error_type=ExteriorSupportTableError,
    )
    digest, reference_count, encoding = parse_expected_exterior_support_reference(
        row["reference"]
    )
    if row["encoding"] != encoding or row["sha256"] != digest:
        raise ExteriorSupportTableError("support blob identity differs from its reference")
    entry_count = row["entry_count"]
    byte_count = row["byte_count"]
    if not _is_plain_int(entry_count) or entry_count != reference_count:
        raise ExteriorSupportTableError("support blob entry count is invalid")
    if not _is_plain_int(byte_count) or cast(int, byte_count) < 2:
        raise ExteriorSupportTableError("support blob byte count is invalid")
    encoded = row["data_base64"]
    if (
        not isinstance(encoded, str)
        or not encoded.isascii()
        or any(character.isspace() for character in encoded)
    ):
        raise ExteriorSupportTableError("support blob base64 is not canonical ASCII")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ExteriorSupportTableError("support blob base64 is invalid") from error
    if base64.b64encode(raw).decode("ascii") != encoded:
        raise ExteriorSupportTableError("support blob base64 has an alternate spelling")
    if len(raw) != byte_count or hashlib.sha256(raw).hexdigest() != digest:
        raise ExteriorSupportTableError("decoded support bytes differ from blob identity")
    try:
        text = raw.decode("utf-8")
        parsed = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExteriorSupportTableError("support blob is not UTF-8 JSON") from error
    if not isinstance(parsed, list):
        raise ExteriorSupportTableError("decoded support manifest is not a list")
    canonical = canonical_support_entries(parsed)
    canonical_value: JsonValue = [[r, c, label] for r, c, label in canonical]
    if len(canonical) != entry_count or canonical_json_bytes(canonical_value) != raw:
        raise ExteriorSupportTableError("support manifest is not canonically encoded")
    return cast(str, row["reference"]), canonical


def validate_expected_exterior_support_table(
    value: object,
    *,
    expected_references: Iterable[str | None],
) -> Mapping[str, tuple[SupportEntry, ...]]:
    """Validate all support blobs and exact reference coverage."""

    table = _exact_mapping(
        value,
        _SUPPORT_TABLE_KEYS,
        "expected-exterior-support table",
        error_type=ExteriorSupportTableError,
    )
    if table["schema_version"] != EXPECTED_EXTERIOR_SUPPORT_SCHEMA_VERSION:
        raise ExteriorSupportTableError("support table schema identity is invalid")
    blobs = table["blobs"]
    if not isinstance(blobs, list):
        raise ExteriorSupportTableError("support blobs is not a list")
    decoded: dict[str, tuple[SupportEntry, ...]] = {}
    order: list[str] = []
    for blob in blobs:
        reference, entries = _decode_support_blob(blob)
        if reference in decoded:
            raise ExteriorSupportTableError("support table contains a duplicate blob")
        decoded[reference] = entries
        order.append(reference)
    if order != sorted(order):
        raise ExteriorSupportTableError("support blobs are not lexically sorted")
    expected: set[str] = set()
    for expected_reference in expected_references:
        if expected_reference is None:
            continue
        digest, count, _encoding = parse_expected_exterior_support_reference(
            expected_reference
        )
        expected.add(_support_reference(digest, count))
    if set(decoded) != expected:
        raise ExteriorSupportTableError("support reference set is not exact")
    return MappingProxyType(decoded)


@dataclass(frozen=True, slots=True)
class TransformContract:
    """One exact visual-transform contract and its derived SHA-256 identity."""

    family: str
    scene_index: int
    transform_name: str
    source_shape: Shape
    actual_destination_shape: Shape
    isolated_destination_shape: Shape
    source_background_label: int
    destination_background_label: int
    parameters: Mapping[str, JsonValue]
    contract_sha256: str

    def core_json(self) -> dict[str, JsonValue]:
        return {
            "schema_version": TRANSFORM_CONTRACT_SCHEMA_VERSION,
            "family": self.family,
            "scene_index": self.scene_index,
            "transform_name": self.transform_name,
            "source_shape": [self.source_shape[0], self.source_shape[1]],
            "actual_destination_shape": [
                self.actual_destination_shape[0],
                self.actual_destination_shape[1],
            ],
            "isolated_destination_shape": [
                self.isolated_destination_shape[0],
                self.isolated_destination_shape[1],
            ],
            "source_background_label": self.source_background_label,
            "destination_background_label": self.destination_background_label,
            "parameters": dict(self.parameters),
        }


def _normalize_transform_parameters(
    transform_name: str, value: object
) -> dict[str, JsonValue]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise TransformContractError("transform parameters are not a string-keyed mapping")
    parameters = cast(Mapping[str, object], value)
    if transform_name == PALETTE_TRANSFORM_NAME:
        if set(parameters) != {"forward_palette"}:
            raise TransformContractError("palette parameters do not have exact keys")
        palette = parameters["forward_palette"]
        if (
            not isinstance(palette, list)
            or len(palette) != 16
            or any(not _is_plain_int(label) for label in palette)
            or sorted(cast(list[int], palette)) != list(range(16))
        ):
            raise TransformContractError("forward palette is not a permutation of 0..15")
        return {"forward_palette": list(cast(list[int], palette))}
    if transform_name in TRANSLATION_DELTAS:
        if set(parameters) != {"delta_row", "delta_col"}:
            raise TransformContractError("translation parameters do not have exact keys")
        delta_row = parameters["delta_row"]
        delta_col = parameters["delta_col"]
        if not _is_plain_int(delta_row) or not _is_plain_int(delta_col):
            raise TransformContractError("translation deltas are not integers")
        if (delta_row, delta_col) != TRANSLATION_DELTAS[transform_name]:
            raise TransformContractError("translation deltas differ from transform name")
        return {"delta_row": cast(int, delta_row), "delta_col": cast(int, delta_col)}
    if transform_name == SCALE_TRANSFORM_NAME:
        if set(parameters) != {"factor"} or parameters["factor"] != 2:
            raise TransformContractError("scale parameters must be exactly factor two")
        return {"factor": 2}
    raise TransformContractError(f"unknown visual transform: {transform_name!r}")


def make_transform_contract(
    *,
    family: str,
    scene_index: int,
    transform_name: str,
    source_background_label: int,
    destination_background_label: int,
    parameters: Mapping[str, object],
) -> TransformContract:
    """Construct and hash one exact registered 32-by-32 transform contract."""

    if family not in {"homologue", "containment", "reflection"}:
        raise TransformContractError("transform family is not registered")
    if not _is_plain_int(scene_index) or not 0 <= scene_index <= 3:
        raise TransformContractError("scene index lies outside 0..3")
    source_background = _validated_label(source_background_label, "source background")
    destination_background = _validated_label(
        destination_background_label, "destination background"
    )
    if not 0 <= source_background <= 15 or not 0 <= destination_background <= 15:
        raise TransformContractError("registered scene backgrounds must lie in 0..15")
    normalized = _normalize_transform_parameters(transform_name, parameters)
    source_shape = (32, 32)
    if transform_name == PALETTE_TRANSFORM_NAME:
        actual_shape = isolated_shape = (32, 32)
        palette = cast(list[int], normalized["forward_palette"])
        if destination_background != palette[source_background]:
            raise TransformContractError("palette destination background is not mapped source")
    elif transform_name in TRANSLATION_DELTAS:
        actual_shape, isolated_shape = (32, 32), (38, 42)
        if destination_background != source_background:
            raise TransformContractError("translation must preserve the background label")
    elif transform_name == SCALE_TRANSFORM_NAME:
        actual_shape = isolated_shape = (64, 64)
        if destination_background != source_background:
            raise TransformContractError("scale must preserve the background label")
    else:
        raise TransformContractError(f"unknown visual transform: {transform_name!r}")
    provisional = TransformContract(
        family=family,
        scene_index=scene_index,
        transform_name=transform_name,
        source_shape=source_shape,
        actual_destination_shape=actual_shape,
        isolated_destination_shape=isolated_shape,
        source_background_label=source_background,
        destination_background_label=destination_background,
        parameters=MappingProxyType(normalized),
        contract_sha256="",
    )
    return TransformContract(
        family=provisional.family,
        scene_index=provisional.scene_index,
        transform_name=provisional.transform_name,
        source_shape=provisional.source_shape,
        actual_destination_shape=provisional.actual_destination_shape,
        isolated_destination_shape=provisional.isolated_destination_shape,
        source_background_label=provisional.source_background_label,
        destination_background_label=provisional.destination_background_label,
        parameters=provisional.parameters,
        contract_sha256=canonical_sha256(provisional.core_json()),
    )


def validate_transform_contract(
    value: object,
    *,
    expected_sha256: str | None = None,
) -> TransformContract:
    """Validate an exact ten-key contract core and optional registered digest."""

    row = _exact_mapping(
        value,
        _TRANSFORM_CONTRACT_KEYS,
        "transform contract",
        error_type=TransformContractError,
    )
    if row["schema_version"] != TRANSFORM_CONTRACT_SCHEMA_VERSION:
        raise TransformContractError("transform contract schema identity is invalid")
    if not isinstance(row["family"], str) or not isinstance(row["transform_name"], str):
        raise TransformContractError("transform string identity is malformed")
    contract = make_transform_contract(
        family=row["family"],
        scene_index=cast(int, row["scene_index"]),
        transform_name=row["transform_name"],
        source_background_label=cast(int, row["source_background_label"]),
        destination_background_label=cast(int, row["destination_background_label"]),
        parameters=cast(Mapping[str, object], row["parameters"]),
    )
    if row["source_shape"] != [32, 32]:
        raise TransformContractError("transform source shape is not [32,32]")
    if row["actual_destination_shape"] != list(contract.actual_destination_shape):
        raise TransformContractError("actual destination shape differs from semantics")
    if row["isolated_destination_shape"] != list(contract.isolated_destination_shape):
        raise TransformContractError("isolated destination shape differs from semantics")
    if expected_sha256 is not None and contract.contract_sha256 != expected_sha256:
        raise TransformContractError("transform contract digest differs from registration")
    return contract


@dataclass(frozen=True, slots=True)
class ReconstructedActionMap:
    """Exact actual/isolated ACTION6 injection and canonical hash preimage."""

    map_kind: Literal["actual", "isolated"]
    transform_contract_sha256: str
    source_shape: Shape
    destination_shape: Shape
    forward: Mapping[Coordinate, Coordinate]

    def as_json(self) -> dict[str, JsonValue]:
        return {
            "schema_version": ACTION_MAP_SCHEMA_VERSION,
            "map_kind": self.map_kind,
            "transform_contract_sha256": self.transform_contract_sha256,
            "source_shape": [self.source_shape[0], self.source_shape[1]],
            "destination_shape": [self.destination_shape[0], self.destination_shape[1]],
            "simple_actions": ["ACTION3"],
            "action6_forward": [
                [[source[0], source[1]], [destination[0], destination[1]]]
                for source, destination in sorted(self.forward.items())
            ],
        }

    @property
    def sha256(self) -> str:
        return canonical_sha256(self.as_json())

    @property
    def total(self) -> bool:
        return len(self.forward) == self.source_shape[0] * self.source_shape[1]


def reconstruct_action_map(
    contract: TransformContract,
    *,
    map_kind: Literal["actual", "isolated"],
) -> ReconstructedActionMap:
    """Rebuild the exact complete or intentionally partial registered action map."""

    if map_kind not in {"actual", "isolated"}:
        raise ActionMapError("action map kind is not actual or isolated")
    rows, columns = contract.source_shape
    destination_shape = (
        contract.actual_destination_shape
        if map_kind == "actual"
        else contract.isolated_destination_shape
    )
    forward: dict[Coordinate, Coordinate] = {}
    for row in range(rows):
        for column in range(columns):
            if contract.transform_name == PALETTE_TRANSFORM_NAME:
                destination = (row, column)
            elif contract.transform_name in TRANSLATION_DELTAS:
                delta_row, delta_col = TRANSLATION_DELTAS[contract.transform_name]
                if map_kind == "actual":
                    destination = (row + delta_row, column + delta_col)
                    if not (
                        0 <= destination[0] < destination_shape[0]
                        and 0 <= destination[1] < destination_shape[1]
                    ):
                        continue
                else:
                    destination = (
                        row + abs(delta_row) + delta_row,
                        column + abs(delta_col) + delta_col,
                    )
            elif contract.transform_name == SCALE_TRANSFORM_NAME:
                destination = (2 * row, 2 * column)
            else:
                raise ActionMapError("unknown transform in action-map reconstruction")
            if not (
                0 <= destination[0] < destination_shape[0]
                and 0 <= destination[1] < destination_shape[1]
            ):
                raise ActionMapError("reconstructed destination lies outside map shape")
            forward[(row, column)] = destination
    if len(set(forward.values())) != len(forward):
        raise ActionMapError("reconstructed action map is not injective")
    if map_kind == "isolated" and len(forward) != rows * columns:
        raise ActionMapError("isolated action map is not total")
    return ReconstructedActionMap(
        map_kind=map_kind,
        transform_contract_sha256=contract.contract_sha256,
        source_shape=contract.source_shape,
        destination_shape=destination_shape,
        forward=MappingProxyType(forward),
    )


def validate_action_map(
    value: object,
    contract: TransformContract,
    *,
    map_kind: Literal["actual", "isolated"],
    expected_sha256: str | None = None,
) -> ReconstructedActionMap:
    """Require exact canonical equality to independently reconstructed map bytes."""

    _exact_mapping(value, _ACTION_MAP_KEYS, "action map", error_type=ActionMapError)
    expected = reconstruct_action_map(contract, map_kind=map_kind)
    try:
        observed_bytes = canonical_json_bytes(
            cast(JsonValue, dict(cast(Mapping[str, object], value)))
        )
    except V7ReferenceError as error:
        raise ActionMapError("action map is not canonical JSON") from error
    if observed_bytes != canonical_json_bytes(expected.as_json()):
        raise ActionMapError("action map differs from exact reconstruction")
    if expected_sha256 is not None and expected.sha256 != expected_sha256:
        raise ActionMapError("action-map digest differs from registration")
    return expected


def action_to_json(action: Action | None) -> JsonValue:
    """Serialize one official uppercase action object; null is preserved."""

    if action is None:
        return None
    if action.kind is ActionKind.RESET:
        raise ActionMapError("RESET is excluded from v7 scientific action inventories")
    return {"kind": action.kind.name, "row": action.row, "col": action.col}


def action_from_json(value: object, *, shape: Shape | None = None) -> Action:
    """Parse an exact uppercase action object and optionally enforce its grid domain."""

    row = _exact_mapping(value, _ACTION_KEYS, "action", error_type=ActionMapError)
    kind = row["kind"]
    if not isinstance(kind, str) or kind not in {f"ACTION{index}" for index in range(1, 8)}:
        raise ActionMapError("action kind is not an official uppercase non-RESET action")
    try:
        action = Action(
            ActionKind[kind],
            cast(int | None, row["row"]),
            cast(int | None, row["col"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ActionMapError("action coordinates differ from its kind") from error
    if shape is not None and action.kind is ActionKind.ACTION6:
        rows, columns = _validated_shape(shape, "action grid shape", error_type=ActionMapError)
        assert action.row is not None and action.col is not None
        if action.row >= rows or action.col >= columns:
            raise ActionMapError("ACTION6 lies outside its registered grid shape")
    return action


def canonical_action_key(action: Action) -> tuple[int, int, int]:
    """Return official kind order, then ACTION6 row/column order."""

    if action.kind is ActionKind.RESET:
        raise ActionMapError("RESET has no v7 canonical scientific order")
    if action.kind is ActionKind.ACTION6:
        assert action.row is not None and action.col is not None
        return int(action.kind), action.row, action.col
    return int(action.kind), -1, -1


def canonical_actions(actions: Iterable[Action]) -> tuple[Action, ...]:
    """Validate a duplicate-free action set and return canonical action order."""

    values = tuple(actions)
    if len(set(values)) != len(values):
        raise ActionMapError("action collection contains duplicates")
    return tuple(sorted(values, key=canonical_action_key))


def map_action(action: Action, action_map: ReconstructedActionMap) -> Action:
    """Map ACTION3 identically and ACTION6 through the exact registered injection."""

    if action.kind is ActionKind.ACTION3:
        return action
    if action.kind is not ActionKind.ACTION6:
        raise ActionMapError("registered public action map covers only ACTION3 and ACTION6")
    assert action.row is not None and action.col is not None
    if action.row >= action_map.source_shape[0] or action.col >= action_map.source_shape[1]:
        raise ActionMapError("source ACTION6 lies outside action-map source shape")
    destination = action_map.forward.get((action.row, action.col))
    if destination is None:
        raise ActionMapError("required ACTION6 is absent from the partial map")
    return Action(ActionKind.ACTION6, destination[0], destination[1])


@dataclass(frozen=True, slots=True)
class FrontierRelation:
    """Mechanical set, sequence, completeness, and canonical-order comparison."""

    mapped_actions: tuple[Action, ...]
    unmapped_base_actions: tuple[Action, ...]
    extra_transformed_actions: tuple[Action, ...]
    set_equal: bool
    sequence_equal: bool
    canonical_order_preserving: bool
    reasons: tuple[str, ...]

    @property
    def passes(self) -> bool:
        return not self.reasons


def compare_frontiers(
    base_actions: Sequence[Action],
    transformed_actions: Sequence[Action],
    action_map: ReconstructedActionMap,
) -> FrontierRelation:
    """Compare actual transformed frontier to the mapped base sequence fail closed."""

    if not base_actions or not transformed_actions:
        raise ActionMapError("frontier inventories must be nonempty")
    if len(set(base_actions)) != len(base_actions) or len(set(transformed_actions)) != len(
        transformed_actions
    ):
        raise ActionMapError("frontier inventories contain duplicate actions")
    mapped: list[Action] = []
    unmapped: list[Action] = []
    for action in base_actions:
        try:
            mapped.append(map_action(action, action_map))
        except ActionMapError:
            unmapped.append(action)
    mapped_set = set(mapped)
    transformed_set = set(transformed_actions)
    extras = tuple(action for action in transformed_actions if action not in mapped_set)
    set_equal = not unmapped and mapped_set == transformed_set and len(mapped) == len(mapped_set)
    sequence_equal = not unmapped and tuple(mapped) == tuple(transformed_actions)
    mapped_pairs = [
        (base, destination)
        for base, destination in zip(
            (action for action in base_actions if action not in set(unmapped)), mapped, strict=True
        )
    ]
    canonical_order_preserving = all(
        (canonical_action_key(left_base) < canonical_action_key(right_base))
        == (canonical_action_key(left_mapped) < canonical_action_key(right_mapped))
        for index, (left_base, left_mapped) in enumerate(mapped_pairs)
        for right_base, right_mapped in mapped_pairs[index + 1 :]
    )
    reasons: list[str] = []
    if unmapped:
        reasons.append("required_action_mapping_missing")
    if not set_equal:
        reasons.append("mapped_frontier_set_mismatch")
    if not sequence_equal:
        reasons.append("mapped_frontier_sequence_mismatch")
    if not canonical_order_preserving:
        reasons.append("action_map_not_canonical_order_preserving")
    return FrontierRelation(
        mapped_actions=tuple(mapped),
        unmapped_base_actions=tuple(unmapped),
        extra_transformed_actions=extras,
        set_equal=set_equal,
        sequence_equal=sequence_equal,
        canonical_order_preserving=canonical_order_preserving,
        reasons=canonicalize_reasons(reasons),
    )


def pair_compiler_roles(
    base: Sequence[Mapping[str, object]],
    transformed: Sequence[Mapping[str, object]],
) -> tuple[dict[str, JsonValue], ...]:
    """Pair compiler sources by exact role, independently of list/source ordering."""

    def index(rows: Sequence[Mapping[str, object]], label: str) -> dict[str, str]:
        indexed: dict[str, str] = {}
        for item in rows:
            row = _exact_mapping(
                item,
                _ROLE_SOURCE_KEYS,
                f"{label} role record",
                error_type=SnapshotSchemaError,
            )
            role, digest = row["role"], row["source_sha256"]
            if not isinstance(role, str) or role not in ROLE_ORDER or role in indexed:
                raise SnapshotSchemaError(f"{label} compiler roles are missing/duplicate/unknown")
            if not _is_lower_hex(digest, 64):
                raise SnapshotSchemaError(f"{label} compiler source digest is malformed")
            indexed[role] = cast(str, digest)
        if set(indexed) != set(ROLE_ORDER):
            raise SnapshotSchemaError(f"{label} compiler role inventory is incomplete")
        return indexed

    base_by_role, transformed_by_role = index(base, "base"), index(transformed, "transformed")
    return tuple(
        {
            "role": role,
            "base_source_sha256": base_by_role[role],
            "transformed_source_sha256": transformed_by_role[role],
        }
        for role in ROLE_ORDER
    )


def tolerance_comparison(left: float, right: float) -> tuple[bool, float, float]:
    """Apply the inclusive registered absolute/relative binary64 tolerance."""

    left_value, right_value = float(left), float(right)
    if not math.isfinite(left_value) or not math.isfinite(right_value):
        return False, math.nan, math.nan
    delta = abs(left_value - right_value)
    bound = max(
        ABSOLUTE_TOLERANCE,
        RELATIVE_TOLERANCE * max(abs(left_value), abs(right_value)),
    )
    return delta <= bound, delta, bound


def binary64_equal(left: float, right: float) -> bool:
    """Compare exact IEEE-754 binary64 payloads, including signed zero."""

    left_value, right_value = float(left), float(right)
    return (
        math.isfinite(left_value)
        and math.isfinite(right_value)
        and struct.pack(">d", left_value) == struct.pack(">d", right_value)
    )


def numeric_sentinel(value: float) -> float | str:
    """Encode a primitive pre-selector finite value or its sole registered sentinel."""

    numeric = float(value)
    if math.isnan(numeric):
        return "nan"
    if numeric == math.inf:
        return "+inf"
    if numeric == -math.inf:
        return "-inf"
    return numeric


def palette_transform_grid(grid: object, contract: TransformContract) -> Grid:
    """Apply the registered 0..15 palette injection to a valid prediction grid."""

    if contract.transform_name != PALETTE_TRANSFORM_NAME:
        raise TransformContractError("palette transform called with a different contract")
    source = _coerce_grid(grid)
    if not bool(np.all((source >= 0) & (source <= 15))):
        raise PredictionPairError("prediction label lies outside palette domain")
    palette = np.asarray(contract.parameters["forward_palette"], dtype=np.int16)
    return _coerce_grid(palette[source])


def scale_transform_grid(grid: object, contract: TransformContract) -> Grid:
    """Repeat every row and column exactly twice inside the Prediction domain."""

    if contract.transform_name != SCALE_TRANSFORM_NAME:
        raise TransformContractError("scale transform called with a different contract")
    source = _coerce_grid(grid)
    shape = (2 * int(source.shape[0]), 2 * int(source.shape[1]))
    if shape[0] > 64 or shape[1] > 64:
        raise PredictionPairError("scale output shape lies outside Prediction domain")
    return _coerce_grid(np.repeat(np.repeat(source, 2, axis=0), 2, axis=1))


def translation_transform_grid(
    grid: object,
    contract: TransformContract,
) -> tuple[Grid, tuple[int, int]]:
    """Construct the complete augmented-plane translation and signed world origin."""

    if contract.transform_name not in TRANSLATION_DELTAS:
        raise TransformContractError("translation called with a different contract")
    source = _coerce_grid(grid)
    delta_row, delta_col = TRANSLATION_DELTAS[contract.transform_name]
    pad_row, pad_col = abs(delta_row), abs(delta_col)
    shape = (
        int(source.shape[0]) + 2 * pad_row,
        int(source.shape[1]) + 2 * pad_col,
    )
    if shape[0] > 64 or shape[1] > 64:
        raise PredictionPairError("augmented translation lies outside Prediction domain")
    expected = np.full(shape, contract.source_background_label, dtype=np.int16)
    start_row, start_col = pad_row + delta_row, pad_col + delta_col
    expected[
        start_row : start_row + source.shape[0],
        start_col : start_col + source.shape[1],
    ] = source
    return _coerce_grid(expected), (-pad_row, -pad_col)


def translation_known_viewport(
    augmented: object,
    *,
    origin: tuple[int, int],
    viewport_shape: Shape,
) -> Grid:
    """Extract only world coordinates ``[0,H) x [0,W)`` from an augmented grid."""

    grid = _coerce_grid(augmented)
    rows, columns = _validated_shape(viewport_shape, "viewport shape")
    start_row, start_col = -origin[0], -origin[1]
    if start_row < 0 or start_col < 0:
        raise PredictionPairError("augmented origin does not contain the known viewport")
    if start_row + rows > grid.shape[0] or start_col + columns > grid.shape[1]:
        raise PredictionPairError("known viewport lies outside augmented grid")
    return _coerce_grid(grid[start_row : start_row + rows, start_col : start_col + columns])


def translation_exterior_support(
    augmented: object,
    *,
    origin: tuple[int, int],
    viewport_shape: Shape,
    background_label: int,
) -> tuple[SupportEntry, ...]:
    """Enumerate expected non-background cells outside the known world viewport."""

    grid = _coerce_grid(augmented)
    rows, columns = _validated_shape(viewport_shape, "viewport shape")
    entries: list[SupportEntry] = []
    for array_row, array_col in np.argwhere(grid != background_label):
        world_row = int(array_row) + origin[0]
        world_col = int(array_col) + origin[1]
        if not (0 <= world_row < rows and 0 <= world_col < columns):
            entries.append((world_row, world_col, int(grid[array_row, array_col])))
    return canonical_support_entries(entries)


def _valid_prediction(value: object) -> Prediction | None:
    if not isinstance(value, Prediction):
        return None
    try:
        shape, raw = canonical_grid_bytes(value.next_grid)
    except GridEvidenceTableError:
        return None
    if shape != value.next_grid.shape or raw != value.next_grid.tobytes(order="C"):
        return None
    if value.game_state not in {GameState.NOT_FINISHED, GameState.WIN, GameState.GAME_OVER}:
        return None
    if not _is_plain_int(value.level_delta):
        return None
    return value


@dataclass(frozen=True, slots=True)
class PredictionPairRecord:
    """One fully derived ordered action-by-role prediction comparison."""

    record: Mapping[str, JsonValue]
    reasons: tuple[str, ...]

    @property
    def category(self) -> str:
        return cast(str, self.record["category"])

    @property
    def passes(self) -> bool:
        return cast(bool, self.record["passes"])


def compare_prediction_pair(
    *,
    action: Action,
    mapped_action: Action,
    role: str,
    base: object,
    transformed: object,
    contract: TransformContract,
    grid_registry: GridEvidenceRegistry,
    support_registry: ExteriorSupportRegistry,
) -> PredictionPairRecord:
    """Derive the exact v7 root pair record, grids, masks, support, and category."""

    if role not in ROLE_ORDER:
        raise PredictionPairError("prediction pair role is not registered")
    base_prediction = _valid_prediction(base)
    transformed_prediction = _valid_prediction(transformed)
    base_ref = grid_registry.add_prediction(base_prediction)
    transformed_ref = grid_registry.add_prediction(transformed_prediction)
    reasons: list[str] = []
    expected_ref: str | None = None
    expected_origin_row: int | None = None
    expected_origin_col: int | None = None
    mismatch_ref: str | None = None
    support_ref: str | None = None
    mismatch_count = 0
    exterior_count = 0
    base_shape_valid = (
        base_prediction is not None
        and tuple(base_prediction.next_grid.shape) == contract.source_shape
    )
    if base_prediction is None or transformed_prediction is None or not base_shape_valid:
        reasons.append("invalid_root_prediction")
    expected: Grid | None = None
    comparison_expected: Grid | None = None
    if base_shape_valid:
        assert base_prediction is not None
        if contract.transform_name == PALETTE_TRANSFORM_NAME:
            if not bool(
                np.all(
                    (base_prediction.next_grid >= 0)
                    & (base_prediction.next_grid <= 15)
                )
            ):
                reasons.append("prediction_label_outside_palette_domain")
            else:
                expected = palette_transform_grid(base_prediction.next_grid, contract)
                expected_origin_row = expected_origin_col = 0
        elif contract.transform_name == SCALE_TRANSFORM_NAME:
            expected_shape = (
                2 * int(base_prediction.next_grid.shape[0]),
                2 * int(base_prediction.next_grid.shape[1]),
            )
            if expected_shape[0] > 64 or expected_shape[1] > 64:
                reasons.append("scale_output_shape_outside_prediction_domain")
            else:
                expected = scale_transform_grid(base_prediction.next_grid, contract)
                expected_origin_row = expected_origin_col = 0
        elif contract.transform_name in TRANSLATION_DELTAS:
            expected, origin = translation_transform_grid(base_prediction.next_grid, contract)
            expected_origin_row, expected_origin_col = origin
            support = translation_exterior_support(
                expected,
                origin=origin,
                viewport_shape=contract.source_shape,
                background_label=contract.source_background_label,
            )
            support_ref = support_registry.add(support)
            exterior_count = len(support)
        else:
            raise TransformContractError("prediction pair has unknown transform")
    if transformed_prediction is not None and expected is not None:
        if tuple(transformed_prediction.next_grid.shape) != contract.actual_destination_shape:
            reasons.append("transformed_prediction_shape_mismatch")
            # This explicit second invalid rule suppresses expected/origin references.
            expected = None
            expected_origin_row = expected_origin_col = None
        elif contract.transform_name in TRANSLATION_DELTAS:
            assert expected_origin_row is not None and expected_origin_col is not None
            comparison_expected = translation_known_viewport(
                expected,
                origin=(expected_origin_row, expected_origin_col),
                viewport_shape=contract.actual_destination_shape,
            )
        else:
            comparison_expected = expected
    if expected is not None:
        expected_ref = grid_registry.add_grid(expected)
    if comparison_expected is not None and transformed_prediction is not None:
        actual = transformed_prediction.next_grid
        if tuple(comparison_expected.shape) == tuple(actual.shape):
            mismatch = np.not_equal(comparison_expected, actual).astype(np.int16)
            mismatch_count = int(np.count_nonzero(mismatch))
            mismatch_ref = grid_registry.add_grid(mismatch)
            if mismatch_count:
                reasons.append("observable_prediction_grid_mismatch")
    if exterior_count:
        reasons.append("expected_exterior_support_present")
    if base_prediction is not None and transformed_prediction is not None:
        if base_prediction.game_state != transformed_prediction.game_state:
            reasons.append("prediction_game_state_mismatch")
        if base_prediction.level_delta != transformed_prediction.level_delta:
            reasons.append("prediction_level_delta_mismatch")
    if base_prediction is not None and transformed_prediction is not None:
        state_equal = base_prediction.game_state == transformed_prediction.game_state
        delta_equal = base_prediction.level_delta == transformed_prediction.level_delta
    else:
        state_equal = delta_equal = False
    invalid = "invalid_root_prediction" in reasons or any(
        reason
        in {
            "prediction_label_outside_palette_domain",
            "scale_output_shape_outside_prediction_domain",
            "transformed_prediction_shape_mismatch",
        }
        for reason in reasons
    )
    observable = (
        not invalid
        and mismatch_count == 0
        and state_equal
        and delta_equal
    )
    full = observable and exterior_count == 0
    if invalid:
        category = "invalid_prediction"
    elif observable and exterior_count == 0:
        category = "fully_equivariant"
    elif observable and exterior_count > 0:
        category = "boundary_consistent_censored"
    else:
        category = "interior_or_metadata_mismatch"
    record: dict[str, JsonValue] = {
        "action": action_to_json(action),
        "mapped_action": action_to_json(mapped_action),
        "role": role,
        "base_prediction_ref": base_ref,
        "transformed_prediction_ref": transformed_ref,
        "expected_prediction_ref": expected_ref,
        "expected_origin_row": expected_origin_row,
        "expected_origin_col": expected_origin_col,
        "observable_mismatch_mask_ref": mismatch_ref,
        "expected_exterior_support_ref": support_ref,
        "game_state_equal": state_equal,
        "level_delta_equal": delta_equal,
        "observable_mismatch_cell_count": mismatch_count,
        "expected_exterior_nonbackground_count": exterior_count,
        "category": category,
        "passes": full,
    }
    return PredictionPairRecord(MappingProxyType(record), canonicalize_reasons(reasons))


def fixed_key(value: float) -> int:
    """Round finite binary64 ``value / 2^-40`` to nearest, with exact ties to even."""

    numeric = float(value)
    if not math.isfinite(numeric):
        raise SelectionSchemaError("fixed key requires a finite binary64 value")
    numerator, denominator = numeric.as_integer_ratio()
    scaled = numerator * FIXED_QUANTUM_DENOMINATOR
    sign = -1 if scaled < 0 else 1
    quotient, remainder = divmod(abs(scaled), denominator)
    doubled = 2 * remainder
    if doubled > denominator or (doubled == denominator and quotient % 2 == 1):
        quotient += 1
    return sign * quotient


@dataclass(frozen=True, slots=True)
class CompoundActionQBCRow:
    """Raw selector scalars plus comparison-only integer keys and dense ranks."""

    action: Action
    outcome_concentration: float
    outcome_cell_count: int
    evsi: float
    catastrophe_mass: float
    m_utility: float
    x_utility: float
    eligible: bool
    m_rank: int | None
    x_rank: int | None
    m_selected: bool
    x_selected: bool
    exploit_mean_cost: float
    exploit_standard_deviation: float
    exploit_score: float
    m_key: int
    x_key: int
    exploit_key: int


@dataclass(frozen=True, slots=True)
class CompoundActionQBCSelection:
    """Diagnostic-only compound fixed-key/dense/tied-set selection."""

    rows: tuple[CompoundActionQBCRow, ...]
    exploit_set: tuple[Action, ...]
    exploit: ExploitChoice
    m_decision: VariantPolicyDecision
    x_decision: VariantPolicyDecision
    m_utility_maximizers: tuple[Action, ...]
    x_utility_maximizers: tuple[Action, ...]
    historical_agreement: float
    historical_indifference: float
    normalized_weights: tuple[float, ...]


def _dense_ranks(keys: Sequence[int], eligible: Sequence[bool]) -> dict[int, int]:
    distinct = sorted(
        {key for key, allowed in zip(keys, eligible, strict=True) if allowed},
        reverse=True,
    )
    by_key = {key: rank for rank, key in enumerate(distinct, 1)}
    return {
        index: by_key[key]
        for index, (key, allowed) in enumerate(zip(keys, eligible, strict=True))
        if allowed
    }


def _compound_decision(
    raw: ActionQBCSelection,
    *,
    utility_name: Literal["m_utility", "x_utility"],
    utility_keys: Sequence[int],
    exploit_set: tuple[Action, ...],
    probes_used: int,
) -> tuple[VariantPolicyDecision, tuple[Action, ...], Action | None]:
    eligible_indices = [index for index, row in enumerate(raw.rows) if row.eligible]
    exploit_action = exploit_set[0]
    exploit_row = next(row for row in raw.rows if row.action == exploit_action)
    if not eligible_indices:
        return (
            VariantPolicyDecision(
                exploit_action,
                "exploit",
                exploit_row.exploit_score,
                "no_disagreement_eligible_action",
                None,
            ),
            (),
            None,
        )
    maximum_key = max(utility_keys[index] for index in eligible_indices)
    maximizers = canonical_actions(
        raw.rows[index].action
        for index in eligible_indices
        if utility_keys[index] == maximum_key
    )
    probe_candidate = maximizers[0]
    if probes_used >= MAX_PROBES_PER_LEVEL:
        return (
            VariantPolicyDecision(
                exploit_action,
                "exploit",
                exploit_row.exploit_score,
                "level_probe_cap_reached",
                probe_candidate,
            ),
            maximizers,
            None,
        )
    if maximum_key <= 0:
        return (
            VariantPolicyDecision(
                exploit_action,
                "exploit",
                exploit_row.exploit_score,
                "nonpositive_fixed_utility",
                probe_candidate,
            ),
            maximizers,
            None,
        )
    selected_row = next(row for row in raw.rows if row.action == probe_candidate)
    return (
        VariantPolicyDecision(
            probe_candidate,
            "probe",
            float(getattr(selected_row, utility_name)),
            "selected",
            probe_candidate,
        ),
        maximizers,
        probe_candidate,
    )


def select_compound_action_qbc(
    snapshot: PlanningSnapshot,
    *,
    cross_level_multiplier: float,
    probes_used: int,
    probe_cap: int,
) -> CompoundActionQBCSelection:
    """Run the frozen raw computation, then apply only the compound comparison policy."""

    if probe_cap != MAX_PROBES_PER_LEVEL or isinstance(probe_cap, bool):
        raise SelectionSchemaError("compound selector requires the registered probe cap")
    raw = select_action_conditional_qbc(
        snapshot,
        cross_level_multiplier=cross_level_multiplier,
        probes_used=probes_used,
        probe_cap=probe_cap,
    )
    m_keys = tuple(fixed_key(row.m_utility) for row in raw.rows)
    x_keys = tuple(fixed_key(row.x_utility) for row in raw.rows)
    exploit_keys = tuple(fixed_key(row.exploit_score) for row in raw.rows)
    eligible = tuple(row.eligible for row in raw.rows)
    m_ranks, x_ranks = _dense_ranks(m_keys, eligible), _dense_ranks(x_keys, eligible)
    minimum_exploit_key = min(exploit_keys)
    exploit_set = canonical_actions(
        row.action
        for row, key in zip(raw.rows, exploit_keys, strict=True)
        if key == minimum_exploit_key
    )
    m_decision, m_maximizers, m_selected = _compound_decision(
        raw,
        utility_name="m_utility",
        utility_keys=m_keys,
        exploit_set=exploit_set,
        probes_used=probes_used,
    )
    x_decision, x_maximizers, x_selected = _compound_decision(
        raw,
        utility_name="x_utility",
        utility_keys=x_keys,
        exploit_set=exploit_set,
        probes_used=probes_used,
    )
    rows = tuple(
        CompoundActionQBCRow(
            action=row.action,
            outcome_concentration=row.outcome_concentration,
            outcome_cell_count=row.outcome_cell_count,
            evsi=row.evsi,
            catastrophe_mass=row.catastrophe_mass,
            m_utility=row.m_utility,
            x_utility=row.x_utility,
            eligible=row.eligible,
            m_rank=m_ranks.get(index),
            x_rank=x_ranks.get(index),
            m_selected=row.action == m_selected,
            x_selected=row.action == x_selected,
            exploit_mean_cost=row.exploit_mean_cost,
            exploit_standard_deviation=row.exploit_standard_deviation,
            exploit_score=row.exploit_score,
            m_key=m_keys[index],
            x_key=x_keys[index],
            exploit_key=exploit_keys[index],
        )
        for index, row in enumerate(raw.rows)
    )
    exploit_row = next(row for row in rows if row.action == exploit_set[0])
    compound_exploit = ExploitChoice(
        action=exploit_row.action,
        score=exploit_row.exploit_score,
        mean_cost=exploit_row.exploit_mean_cost,
        standard_deviation=exploit_row.exploit_standard_deviation,
    )
    return CompoundActionQBCSelection(
        rows=rows,
        exploit_set=exploit_set,
        exploit=compound_exploit,
        m_decision=m_decision,
        x_decision=x_decision,
        m_utility_maximizers=m_maximizers,
        x_utility_maximizers=x_maximizers,
        historical_agreement=raw.historical_agreement,
        historical_indifference=raw.historical_indifference,
        normalized_weights=raw.normalized_weights,
    )


def build_snapshot_digest_preimage(
    snapshot: PlanningSnapshot,
    *,
    hypothesis_roles: Mapping[str, str],
    source_sha256_by_role: Mapping[str, str],
) -> dict[str, JsonValue]:
    """Build the exact role-ordered digest preimage from one planning snapshot.

    ``hypothesis_roles`` is deliberately explicit: list position and equal source text are
    never accepted as role identity.
    """

    if not snapshot.actions or not 1 <= len(snapshot.actions) <= 12:
        raise SnapshotSchemaError("snapshot candidate count lies outside 1..12")
    if len(set(snapshot.actions)) != len(snapshot.actions):
        raise SnapshotSchemaError("snapshot candidate sequence contains duplicates")
    if len(snapshot.hypothesis_ids) != len(ROLE_ORDER) or len(set(snapshot.hypothesis_ids)) != len(
        ROLE_ORDER
    ):
        raise SnapshotSchemaError("snapshot hypothesis inventory is not four unique items")
    if set(hypothesis_roles) != set(snapshot.hypothesis_ids):
        raise SnapshotSchemaError("hypothesis-role map does not cover the snapshot exactly")
    role_to_index: dict[str, int] = {}
    for index, hypothesis_id in enumerate(snapshot.hypothesis_ids):
        role = hypothesis_roles[hypothesis_id]
        if role not in ROLE_ORDER or role in role_to_index:
            raise SnapshotSchemaError("hypothesis roles are missing, duplicate, or unknown")
        role_to_index[role] = index
    if set(role_to_index) != set(ROLE_ORDER) or set(source_sha256_by_role) != set(ROLE_ORDER):
        raise SnapshotSchemaError("role/source inventory does not exactly cover registered roles")
    for digest in source_sha256_by_role.values():
        if not _is_lower_hex(digest, 64):
            raise SnapshotSchemaError("role source SHA-256 is malformed")
    if set(snapshot.predictions) != set(snapshot.actions):
        raise SnapshotSchemaError("prediction rows do not cover candidate actions exactly")
    if set(snapshot.costs) != set(snapshot.actions):
        raise SnapshotSchemaError("cost rows do not cover candidate actions exactly")
    try:
        normalized = normalise_gibbs_weights(snapshot.weights)
    except (TypeError, ValueError) as error:
        # Preserve non-finite primitive diagnostics below only when lengths remain
        # addressable; normalization itself must otherwise be well formed.
        if len(snapshot.weights) != len(ROLE_ORDER):
            raise SnapshotSchemaError("weight vector is not role-addressable") from error
        normalized = tuple(float(value) for value in snapshot.weights)
    source_roles: list[JsonValue] = []
    normalized_weights: list[JsonValue] = []
    for role in ROLE_ORDER:
        index = role_to_index[role]
        source_roles.append(
            {"role": role, "source_sha256": source_sha256_by_role[role]}
        )
        normalized_weights.append(
            {"role": role, "value": numeric_sentinel(normalized[index])}
        )
    root_predictions: list[JsonValue] = []
    rolewise_costs: list[JsonValue] = []
    for action in snapshot.actions:
        predictions = snapshot.predictions[action]
        costs = snapshot.costs[action]
        if len(predictions) != len(ROLE_ORDER) or len(costs) != len(ROLE_ORDER):
            raise SnapshotSchemaError("prediction/cost row is not role-addressable")
        for role in ROLE_ORDER:
            index = role_to_index[role]
            prediction = _valid_prediction(predictions[index])
            if prediction is None:
                grid_sha256: JsonValue = None
                grid_shape: JsonValue = None
                game_state: JsonValue = None
                level_delta: JsonValue = None
            else:
                shape, raw = canonical_grid_bytes(prediction.next_grid)
                grid_sha256 = hashlib.sha256(raw).hexdigest()
                grid_shape = [shape[0], shape[1]]
                game_state = prediction.game_state.value
                level_delta = prediction.level_delta
            action_json = action_to_json(action)
            root_predictions.append(
                {
                    "action": action_json,
                    "role": role,
                    "grid_sha256": grid_sha256,
                    "grid_shape": grid_shape,
                    "game_state": game_state,
                    "level_delta": level_delta,
                }
            )
            rolewise_costs.append(
                {
                    "action": action_json,
                    "role": role,
                    "cost": numeric_sentinel(float(costs[index])),
                }
            )
    preimage: dict[str, JsonValue] = {
        "schema_version": SNAPSHOT_DIGEST_SCHEMA_VERSION,
        "candidate_sequence": [action_to_json(action) for action in snapshot.actions],
        "source_roles": source_roles,
        "normalized_weights": normalized_weights,
        "root_predictions": root_predictions,
        "rolewise_costs": rolewise_costs,
    }
    return validate_snapshot_digest_preimage(preimage)


def _validated_json_action_list(value: object, label: str) -> list[JsonValue]:
    if not isinstance(value, list):
        raise SnapshotSchemaError(f"{label} is not a list")
    actions = [action_from_json(item) for item in value]
    if len(set(actions)) != len(actions):
        raise SnapshotSchemaError(f"{label} contains duplicate actions")
    return [action_to_json(action) for action in actions]


def validate_snapshot_digest_preimage(value: object) -> dict[str, JsonValue]:
    """Validate exact snapshot digest schema, role identity, ordering, and finiteness."""

    row = _exact_mapping(
        value,
        _SNAPSHOT_KEYS,
        "snapshot digest preimage",
        error_type=SnapshotSchemaError,
    )
    if row["schema_version"] != SNAPSHOT_DIGEST_SCHEMA_VERSION:
        raise SnapshotSchemaError("snapshot digest schema identity is invalid")
    candidates = _validated_json_action_list(row["candidate_sequence"], "candidate sequence")
    if not 1 <= len(candidates) <= 12:
        raise SnapshotSchemaError("candidate count lies outside 1..12")
    source_roles = row["source_roles"]
    if not isinstance(source_roles, list) or len(source_roles) != len(ROLE_ORDER):
        raise SnapshotSchemaError("source-role inventory is malformed")
    canonical_roles: list[JsonValue] = []
    for index, item in enumerate(source_roles):
        record = _exact_mapping(
            item,
            _ROLE_SOURCE_KEYS,
            "source-role record",
            error_type=SnapshotSchemaError,
        )
        if record["role"] != ROLE_ORDER[index] or not _is_lower_hex(
            record["source_sha256"], 64
        ):
            raise SnapshotSchemaError("source roles are not in exact registered order")
        canonical_roles.append(cast(JsonValue, dict(record)))
    weights = row["normalized_weights"]
    if not isinstance(weights, list) or len(weights) != len(ROLE_ORDER):
        raise SnapshotSchemaError("normalized-weight inventory is malformed")
    canonical_weights: list[JsonValue] = []
    numeric_weights: list[float] = []
    for index, item in enumerate(weights):
        record = _exact_mapping(
            item, _WEIGHT_KEYS, "weight record", error_type=SnapshotSchemaError
        )
        value_number = record["value"]
        if record["role"] != ROLE_ORDER[index] or isinstance(value_number, bool):
            raise SnapshotSchemaError("weight roles or values are malformed")
        if isinstance(value_number, str):
            if value_number not in {"nan", "+inf", "-inf"}:
                raise SnapshotSchemaError("weight sentinel is not registered")
        elif isinstance(value_number, (int, float)) and math.isfinite(float(value_number)):
            numeric_weights.append(float(value_number))
        else:
            raise SnapshotSchemaError("weight is neither finite nor a registered sentinel")
        canonical_weights.append(cast(JsonValue, dict(record)))
    if len(numeric_weights) == len(ROLE_ORDER) and not tolerance_comparison(
        math.fsum(numeric_weights), 1.0
    )[0]:
        raise SnapshotSchemaError("finite normalized weights do not sum to one")
    roots = row["root_predictions"]
    costs = row["rolewise_costs"]
    expected_count = len(candidates) * len(ROLE_ORDER)
    if not isinstance(roots, list) or len(roots) != expected_count:
        raise SnapshotSchemaError("root-prediction inventory is incomplete")
    if not isinstance(costs, list) or len(costs) != expected_count:
        raise SnapshotSchemaError("rolewise-cost inventory is incomplete")
    canonical_roots: list[JsonValue] = []
    canonical_costs: list[JsonValue] = []
    position = 0
    for candidate in candidates:
        for role in ROLE_ORDER:
            root = _exact_mapping(
                roots[position],
                _ROOT_DIGEST_KEYS,
                "root digest record",
                error_type=SnapshotSchemaError,
            )
            cost = _exact_mapping(
                costs[position],
                _COST_DIGEST_KEYS,
                "cost digest record",
                error_type=SnapshotSchemaError,
            )
            canonical_action = candidate
            if root["action"] != canonical_action or cost["action"] != canonical_action:
                raise SnapshotSchemaError("snapshot records are not in candidate order")
            if root["role"] != role or cost["role"] != role:
                raise SnapshotSchemaError("snapshot records are not in role order")
            nullable = (
                root["grid_sha256"],
                root["grid_shape"],
                root["game_state"],
                root["level_delta"],
            )
            if any(item is None for item in nullable):
                if any(item is not None for item in nullable):
                    raise SnapshotSchemaError("invalid root record is only partially null")
            else:
                if not _is_lower_hex(root["grid_sha256"], 64):
                    raise SnapshotSchemaError("root grid digest is malformed")
                _validated_shape(
                    root["grid_shape"], "root grid shape", error_type=SnapshotSchemaError
                )
                if root["game_state"] not in {state.value for state in GameState}:
                    raise SnapshotSchemaError("root game state is invalid")
                if not _is_plain_int(root["level_delta"]):
                    raise SnapshotSchemaError("root level delta is not a plain integer")
            cost_value = cost["cost"]
            if isinstance(cost_value, str):
                if cost_value not in {"nan", "+inf", "-inf"}:
                    raise SnapshotSchemaError("cost sentinel is not registered")
            elif (
                not isinstance(cost_value, (int, float))
                or isinstance(cost_value, bool)
                or not math.isfinite(float(cost_value))
            ):
                raise SnapshotSchemaError("cost is neither finite nor a registered sentinel")
            canonical_roots.append(cast(JsonValue, dict(root)))
            canonical_costs.append(cast(JsonValue, dict(cost)))
            position += 1
    return {
        "schema_version": SNAPSHOT_DIGEST_SCHEMA_VERSION,
        "candidate_sequence": candidates,
        "source_roles": canonical_roles,
        "normalized_weights": canonical_weights,
        "root_predictions": canonical_roots,
        "rolewise_costs": canonical_costs,
    }


def snapshot_digest(value: object) -> str:
    """Validate and hash one exact snapshot preimage."""

    return canonical_sha256(validate_snapshot_digest_preimage(value))


def _validate_serialized_scalars(value: object, *, fixed: bool) -> dict[str, JsonValue]:
    row = _exact_mapping(
        value,
        _SCALAR_KEYS,
        "selector scalar record",
        error_type=SelectionSchemaError,
    )
    finite_fields = (
        "outcome_concentration",
        "evsi",
        "catastrophe_mass",
        "m_utility",
        "x_utility",
        "exploit_mean_cost",
        "exploit_standard_deviation",
        "exploit_score",
    )
    canonical: dict[str, JsonValue] = {}
    for name in finite_fields:
        item = row[name]
        if (
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(float(item))
        ):
            raise SelectionSchemaError(f"selector scalar {name} is not finite numeric")
        canonical[name] = float(item)
    count = row["outcome_cell_count"]
    if not _is_plain_int(count) or cast(int, count) < 1:
        raise SelectionSchemaError("outcome-cell count is not a positive integer")
    canonical["outcome_cell_count"] = cast(int, count)
    for name in ("eligible", "m_selected", "x_selected"):
        item = row[name]
        if not isinstance(item, bool):
            raise SelectionSchemaError(f"selector scalar {name} is not Boolean")
        canonical[name] = item
    for name in ("m_rank", "x_rank"):
        item = row[name]
        if item is not None and (not _is_plain_int(item) or cast(int, item) < 1):
            raise SelectionSchemaError(f"selector scalar {name} is not positive/null")
        canonical[name] = cast(int | None, item)
    for name in ("m_key", "x_key", "exploit_key"):
        item = row[name]
        if fixed:
            if not _is_plain_int(item):
                raise SelectionSchemaError(f"compound scalar {name} is not an integer")
            canonical[name] = cast(int, item)
        else:
            if item is not None:
                raise SelectionSchemaError(f"raw scalar {name} is not null")
            canonical[name] = None
    return {name: canonical[name] for name in SCALAR_FIELD_ORDER}


def _validate_serialized_decision(
    value: object,
    *,
    action_set: set[Action],
) -> tuple[dict[str, JsonValue], Action, Action | None]:
    row = _exact_mapping(
        value,
        _DECISION_KEYS,
        "selector decision",
        error_type=SelectionSchemaError,
    )
    action = action_from_json(row["action"])
    if action not in action_set:
        raise SelectionSchemaError("decision action is not a candidate")
    probe_candidate = (
        None if row["probe_candidate"] is None else action_from_json(row["probe_candidate"])
    )
    if probe_candidate is not None and probe_candidate not in action_set:
        raise SelectionSchemaError("decision probe candidate is not a candidate")
    mode, score, gate_reason = row["mode"], row["score"], row["gate_reason"]
    if mode not in {"probe", "exploit"}:
        raise SelectionSchemaError("decision mode is not probe or exploit")
    if (
        isinstance(score, bool)
        or not isinstance(score, (int, float))
        or not math.isfinite(float(score))
    ):
        raise SelectionSchemaError("decision score is not finite numeric")
    if not isinstance(gate_reason, str):
        raise SelectionSchemaError("decision gate reason is not a string")
    canonical: dict[str, JsonValue] = {
        "action": action_to_json(action),
        "mode": mode,
        "score": float(score),
        "gate_reason": gate_reason,
        "probe_candidate": action_to_json(probe_candidate),
    }
    return canonical, action, probe_candidate


def validate_selection_digest_preimage(value: object) -> dict[str, JsonValue]:
    """Validate the exact outer selection preimage and its canonical action sets."""

    row = _exact_mapping(
        value,
        _SELECTION_KEYS,
        "selection digest preimage",
        error_type=SelectionSchemaError,
    )
    if row["schema_version"] != SELECTION_DIGEST_SCHEMA_VERSION:
        raise SelectionSchemaError("selection digest schema identity is invalid")
    identity = row["selector_identity"]
    if not isinstance(identity, Mapping) or not all(isinstance(key, str) for key in identity):
        raise SelectionSchemaError("selector identity is not a string-keyed object")
    try:
        identity_bytes = canonical_json_bytes(cast(JsonValue, dict(identity)))
    except V7ReferenceError as error:
        raise SelectionSchemaError("selector identity is not canonical JSON") from error
    if identity_bytes == canonical_json_bytes(cast(JsonValue, dict(RAW_SELECTOR_IDENTITY))):
        fixed = False
    elif identity_bytes == canonical_json_bytes(
        cast(JsonValue, dict(FIXED_SELECTOR_IDENTITY))
    ):
        fixed = True
    else:
        raise SelectionSchemaError("selector identity is not the registered raw/compound object")
    candidate_records = row["candidate_records"]
    if not isinstance(candidate_records, list) or not candidate_records:
        raise SelectionSchemaError("selection candidate records are empty or malformed")
    actions: list[Action] = []
    canonical_candidates: list[JsonValue] = []
    scalars_by_action: dict[Action, dict[str, JsonValue]] = {}
    for item in candidate_records:
        candidate_item = _exact_mapping(
            item,
            frozenset({"action", "scalars"}),
            "selection candidate record",
            error_type=SelectionSchemaError,
        )
        action = action_from_json(candidate_item["action"])
        if action in actions:
            raise SelectionSchemaError("selection contains duplicate candidate action")
        scalars = _validate_serialized_scalars(candidate_item["scalars"], fixed=fixed)
        actions.append(action)
        scalars_by_action[action] = scalars
        canonical_candidates.append({"action": action_to_json(action), "scalars": scalars})
    if not 1 <= len(actions) <= 12:
        raise SelectionSchemaError("selection candidate count lies outside 1..12")
    canonical_sets: dict[str, JsonValue] = {}
    parsed_sets: dict[str, tuple[Action, ...]] = {}
    action_set = set(actions)
    for name in ("exploit_set", "m_maximizer_set", "x_maximizer_set"):
        raw_set = row[name]
        if not isinstance(raw_set, list):
            raise SelectionSchemaError(f"{name} is not a list")
        parsed = tuple(action_from_json(item) for item in raw_set)
        if (
            len(set(parsed)) != len(parsed)
            or tuple(sorted(parsed, key=canonical_action_key)) != parsed
        ):
            raise SelectionSchemaError(f"{name} is not duplicate-free canonical order")
        if not set(parsed).issubset(action_set):
            raise SelectionSchemaError(f"{name} contains an unknown action")
        canonical_sets[name] = [action_to_json(action) for action in parsed]
        parsed_sets[name] = parsed
    exploit_measure = "exploit_key" if fixed else "exploit_score"
    minimum = min(
        cast(int | float, scalars_by_action[action][exploit_measure])
        for action in actions
    )
    expected_exploit = canonical_actions(
        action
        for action in actions
        if scalars_by_action[action][exploit_measure] == minimum
    )
    if parsed_sets["exploit_set"] != expected_exploit:
        raise SelectionSchemaError("exploit set is not the complete minimum comparison-key set")
    expected_maximizers: dict[str, tuple[Action, ...]] = {}
    for variant in ("m", "x"):
        eligible_actions = [
            action for action in actions if scalars_by_action[action]["eligible"] is True
        ]
        measure = f"{variant}_key" if fixed else f"{variant}_utility"
        if eligible_actions:
            maximum = max(
                cast(int | float, scalars_by_action[action][measure])
                for action in eligible_actions
            )
            expected = canonical_actions(
                action
                for action in eligible_actions
                if scalars_by_action[action][measure] == maximum
            )
        else:
            expected = ()
        expected_maximizers[variant] = expected
        if parsed_sets[f"{variant}_maximizer_set"] != expected:
            raise SelectionSchemaError(
                f"{variant} maximizer set is not the complete comparison-key tie set"
            )
        if fixed:
            keys = [cast(int, scalars_by_action[action][measure]) for action in actions]
            eligibility = [
                cast(bool, scalars_by_action[action]["eligible"]) for action in actions
            ]
            ranks = _dense_ranks(keys, eligibility)
        else:
            ranked = sorted(
                (
                    index
                    for index, action in enumerate(actions)
                    if scalars_by_action[action]["eligible"] is True
                ),
                key=lambda index: (
                    -cast(float, scalars_by_action[actions[index]][measure]),
                    index,
                ),
            )
            ranks = {index: rank for rank, index in enumerate(ranked, 1)}
        for index, action in enumerate(actions):
            expected_rank = ranks.get(index)
            if scalars_by_action[action][f"{variant}_rank"] != expected_rank:
                raise SelectionSchemaError(f"{variant} ranks do not follow registered policy")
    canonical_decisions: dict[str, JsonValue] = {}
    for decision_name in ("m_decision", "x_decision"):
        variant = decision_name[0]
        decision, action, probe_candidate = _validate_serialized_decision(
            row[decision_name], action_set=action_set
        )
        canonical_decisions[decision_name] = decision
        mode = decision["mode"]
        gate = decision["gate_reason"]
        maximizers = expected_maximizers[variant]
        expected_exploit_action = (
            expected_exploit[0]
            if fixed
            else next(action for action in actions if action in set(expected_exploit))
        )
        if mode == "probe":
            if not maximizers:
                raise SelectionSchemaError("probe decision exists without an eligible row")
            expected_probe = (
                maximizers[0]
                if fixed
                else next(candidate for candidate in actions if candidate in set(maximizers))
            )
            if gate != "selected" or action != expected_probe or probe_candidate != action:
                raise SelectionSchemaError("probe decision does not select the registered top row")
            utility = cast(float, scalars_by_action[action][f"{variant}_utility"])
            key_positive = (
                cast(int, scalars_by_action[action][f"{variant}_key"]) > 0
                if fixed
                else utility > 0.0
            )
            if not key_positive or not binary64_equal(cast(float, decision["score"]), utility):
                raise SelectionSchemaError("probe decision score/gate is internally inconsistent")
        else:
            if action != expected_exploit_action:
                raise SelectionSchemaError("exploit decision action is not registered minimizer")
            exploit_score = cast(float, scalars_by_action[action]["exploit_score"])
            if not binary64_equal(cast(float, decision["score"]), exploit_score):
                raise SelectionSchemaError("exploit decision score differs from its candidate")
            if not maximizers:
                if gate != "no_disagreement_eligible_action" or probe_candidate is not None:
                    raise SelectionSchemaError("no-eligible exploit gate is inconsistent")
            else:
                expected_probe = (
                    maximizers[0]
                    if fixed
                    else next(candidate for candidate in actions if candidate in set(maximizers))
                )
                if probe_candidate != expected_probe:
                    raise SelectionSchemaError("exploit decision retains the wrong probe candidate")
                allowed_gate = {
                    "level_probe_cap_reached",
                    "nonpositive_fixed_utility" if fixed else "nonpositive_utility",
                }
                if gate not in allowed_gate:
                    raise SelectionSchemaError("eligible exploit gate reason is not registered")
                nonpositive_gate = (
                    "nonpositive_fixed_utility" if fixed else "nonpositive_utility"
                )
                if gate == nonpositive_gate:
                    maximum_measure = (
                        cast(int, scalars_by_action[expected_probe][f"{variant}_key"])
                        if fixed
                        else cast(
                            float,
                            scalars_by_action[expected_probe][f"{variant}_utility"],
                        )
                    )
                    if maximum_measure > 0:
                        raise SelectionSchemaError("nonpositive gate has a positive top value")
        selected_action = action if mode == "probe" else None
        for candidate_action in actions:
            if scalars_by_action[candidate_action][f"{variant}_selected"] != (
                candidate_action == selected_action
            ):
                raise SelectionSchemaError(f"{variant} selected-membership flags are invalid")
    return {
        "schema_version": SELECTION_DIGEST_SCHEMA_VERSION,
        "selector_identity": cast(JsonValue, dict(identity)),
        "candidate_records": canonical_candidates,
        "exploit_set": canonical_sets["exploit_set"],
        "m_maximizer_set": canonical_sets["m_maximizer_set"],
        "x_maximizer_set": canonical_sets["x_maximizer_set"],
        "m_decision": canonical_decisions["m_decision"],
        "x_decision": canonical_decisions["x_decision"],
    }


def selection_digest(value: object) -> str:
    """Validate and hash one exact selection preimage."""

    return canonical_sha256(validate_selection_digest_preimage(value))


def decision_to_json(decision: VariantPolicyDecision) -> dict[str, JsonValue]:
    """Serialize one exact five-key finite selector decision."""

    if decision.mode not in {"probe", "exploit"}:
        raise SelectionSchemaError("selector decision mode is not probe or exploit")
    if not math.isfinite(float(decision.score)):
        raise SelectionSchemaError("selector decision score is not finite")
    if not isinstance(decision.gate_reason, str):
        raise SelectionSchemaError("selector gate reason is not a string")
    return {
        "action": action_to_json(decision.action),
        "mode": decision.mode,
        "score": float(decision.score),
        "gate_reason": decision.gate_reason,
        "probe_candidate": action_to_json(decision.probe_candidate),
    }


def _scalar_record(
    row: object,
    *,
    fixed: bool,
) -> dict[str, JsonValue]:
    values: dict[str, JsonValue] = {}
    finite_fields = (
        "outcome_concentration",
        "evsi",
        "catastrophe_mass",
        "m_utility",
        "x_utility",
        "exploit_mean_cost",
        "exploit_standard_deviation",
        "exploit_score",
    )
    for name in finite_fields:
        value = getattr(row, name, None)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SelectionSchemaError(f"selector scalar {name} is not numeric")
        numeric = float(value)
        if not math.isfinite(numeric):
            raise SelectionSchemaError(f"selector scalar {name} is not finite")
        values[name] = numeric
    count = getattr(row, "outcome_cell_count", None)
    if not _is_plain_int(count) or cast(int, count) < 1:
        raise SelectionSchemaError("outcome-cell count is not a positive integer")
    values["outcome_cell_count"] = cast(int, count)
    for name in ("eligible", "m_selected", "x_selected"):
        value = getattr(row, name, None)
        if not isinstance(value, bool):
            raise SelectionSchemaError(f"selector scalar {name} is not Boolean")
        values[name] = value
    for name in ("m_rank", "x_rank"):
        value = getattr(row, name, None)
        if value is not None and (not _is_plain_int(value) or cast(int, value) < 1):
            raise SelectionSchemaError(f"selector scalar {name} is not positive/null")
        values[name] = cast(int | None, value)
    for name in ("m_key", "x_key", "exploit_key"):
        value = getattr(row, name, None) if fixed else None
        if fixed and not _is_plain_int(value):
            raise SelectionSchemaError(f"compound selector key {name} is not an integer")
        values[name] = cast(int | None, value)
    return {name: values[name] for name in SCALAR_FIELD_ORDER}


def build_selection_digest_preimage(
    selection: ActionQBCSelection | CompoundActionQBCSelection,
) -> dict[str, JsonValue]:
    """Build and validate the exact raw or compound selection digest preimage."""

    fixed = isinstance(selection, CompoundActionQBCSelection)
    rows = selection.rows
    if not rows:
        raise SelectionSchemaError("selector returned no candidate rows")
    actions = tuple(row.action for row in rows)
    if len(set(actions)) != len(actions):
        raise SelectionSchemaError("selector candidate actions are not unique")
    candidate_records: list[JsonValue] = [
        {"action": action_to_json(row.action), "scalars": _scalar_record(row, fixed=fixed)}
        for row in rows
    ]
    if fixed:
        fixed_selection = cast(CompoundActionQBCSelection, selection)
        exploit_set = fixed_selection.exploit_set
        selector_identity = FIXED_SELECTOR_IDENTITY
    else:
        raw_selection = cast(ActionQBCSelection, selection)
        minimum_score = min(row.exploit_score for row in raw_selection.rows)
        exploit_set = canonical_actions(
            row.action for row in raw_selection.rows if row.exploit_score == minimum_score
        )
        selector_identity = RAW_SELECTOR_IDENTITY
    m_set = canonical_actions(selection.m_utility_maximizers)
    x_set = canonical_actions(selection.x_utility_maximizers)
    preimage: dict[str, JsonValue] = {
        "schema_version": SELECTION_DIGEST_SCHEMA_VERSION,
        "selector_identity": dict(selector_identity),
        "candidate_records": candidate_records,
        "exploit_set": [action_to_json(action) for action in exploit_set],
        "m_maximizer_set": [action_to_json(action) for action in m_set],
        "x_maximizer_set": [action_to_json(action) for action in x_set],
        "m_decision": decision_to_json(selection.m_decision),
        "x_decision": decision_to_json(selection.x_decision),
    }
    return validate_selection_digest_preimage(preimage)


def selection_details(
    selection: ActionQBCSelection | CompoundActionQBCSelection,
) -> dict[str, JsonValue]:
    """Return the exact base-layer selector details, including its canonical digest."""

    preimage = build_selection_digest_preimage(selection)
    return {
        "selection_sha256": canonical_sha256(preimage),
        "candidate_records": preimage["candidate_records"],
        "exploit_set": preimage["exploit_set"],
        "m_maximizer_set": preimage["m_maximizer_set"],
        "x_maximizer_set": preimage["x_maximizer_set"],
        "m_decision": preimage["m_decision"],
        "x_decision": preimage["x_decision"],
    }


@dataclass(frozen=True, slots=True)
class SelectorRelation:
    """One complete actual/isolated raw-or-compound selector relation."""

    details: Mapping[str, JsonValue]
    reasons: tuple[str, ...]

    @property
    def passes(self) -> bool:
        return not self.reasons


def _selection_sets(
    selection: ActionQBCSelection | CompoundActionQBCSelection,
) -> tuple[tuple[Action, ...], tuple[Action, ...], tuple[Action, ...]]:
    if isinstance(selection, CompoundActionQBCSelection):
        exploit_set = selection.exploit_set
    else:
        minimum_score = min(row.exploit_score for row in selection.rows)
        exploit_set = canonical_actions(
            row.action for row in selection.rows if row.exploit_score == minimum_score
        )
    return (
        canonical_actions(exploit_set),
        canonical_actions(selection.m_utility_maximizers),
        canonical_actions(selection.x_utility_maximizers),
    )


def _mapped_action(
    action: Action,
    action_map: ReconstructedActionMap | None,
) -> Action:
    return action if action_map is None else map_action(action, action_map)


def _mapped_action_json_list(
    actions: Sequence[Action],
    action_map: ReconstructedActionMap | None,
) -> list[JsonValue]:
    return [
        action_to_json(action)
        for action in canonical_actions(_mapped_action(action, action_map) for action in actions)
    ]


def _decision_relation(
    left: VariantPolicyDecision,
    right: VariantPolicyDecision,
    *,
    action_map: ReconstructedActionMap | None,
    numeric_relation: NumericRelation,
) -> tuple[bool, bool]:
    mapped_probe = (
        None
        if left.probe_candidate is None
        else _mapped_action(left.probe_candidate, action_map)
    )
    gate_equal = left.gate_reason == right.gate_reason
    decision_equal = (
        _mapped_action(left.action, action_map) == right.action
        and left.mode == right.mode
        and mapped_probe == right.probe_candidate
        and compare_numeric(left.score, right.score, numeric_relation)
    )
    return gate_equal, decision_equal


def compare_selector_selections(
    left: ActionQBCSelection | CompoundActionQBCSelection,
    right: ActionQBCSelection | CompoundActionQBCSelection,
    *,
    numeric_relation: NumericRelation,
    action_map: ReconstructedActionMap | None = None,
) -> SelectorRelation:
    """Compare complete selections with exact registered mismatch-count units.

    Actual transformed-pipeline callers use ``tolerance``; isolated and order callers use
    ``exact_binary64``.  Candidate rows are joined by mapped action identity, never index.
    """

    fixed = isinstance(left, CompoundActionQBCSelection)
    if fixed is not isinstance(right, CompoundActionQBCSelection):
        raise SelectionSchemaError("selector relation mixes raw and compound treatments")
    left_rows = cast(Sequence[ActionQBCRow | CompoundActionQBCRow], left.rows)
    right_rows = cast(Sequence[ActionQBCRow | CompoundActionQBCRow], right.rows)
    left_by_action = {row.action: row for row in left_rows}
    right_by_action = {row.action: row for row in right_rows}
    if len(left_by_action) != len(left_rows) or len(right_by_action) != len(right_rows):
        raise SelectionSchemaError("selector relation contains duplicate candidate actions")
    mapped_sequence = tuple(_mapped_action(row.action, action_map) for row in left_rows)
    if set(mapped_sequence) != set(right_by_action) or len(mapped_sequence) != len(
        right_by_action
    ):
        raise SelectionSchemaError("selector candidate inventories are not bijectively mapped")
    numeric_names = (
        "outcome_concentration",
        "outcome_cell_count",
        "evsi",
        "catastrophe_mass",
        "m_utility",
        "x_utility",
        "exploit_mean_cost",
        "exploit_standard_deviation",
        "exploit_score",
    )
    exact_names = (
        "eligible",
        "m_rank",
        "x_rank",
        "m_selected",
        "x_selected",
        "m_key",
        "x_key",
        "exploit_key",
    )
    candidate_records: list[JsonValue] = []
    numeric_count = 0
    eligibility_count = 0
    rank_count = 0
    selected_count = 0
    key_count = 0
    for left_row, mapped in zip(left_rows, mapped_sequence, strict=True):
        right_row = right_by_action[mapped]
        left_scalars = _scalar_record(left_row, fixed=fixed)
        right_scalars = _scalar_record(right_row, fixed=fixed)
        numeric_failures: list[JsonValue] = []
        for name in numeric_names:
            left_value, right_value = left_scalars[name], right_scalars[name]
            if name == "outcome_cell_count":
                agrees = left_value == right_value
            else:
                assert isinstance(left_value, (int, float)) and not isinstance(
                    left_value, bool
                )
                assert isinstance(right_value, (int, float)) and not isinstance(
                    right_value, bool
                )
                agrees = compare_numeric(left_value, right_value, numeric_relation)
            if not agrees:
                numeric_failures.append(name)
                numeric_count += 1
        exact_failures = [
            name for name in exact_names if left_scalars[name] != right_scalars[name]
        ]
        eligibility_count += int("eligible" in exact_failures)
        rank_count += sum(name in exact_failures for name in ("m_rank", "x_rank"))
        selected_count += sum(
            name in exact_failures for name in ("m_selected", "x_selected")
        )
        key_count += sum(
            name in exact_failures for name in ("m_key", "x_key", "exploit_key")
        )
        candidate_record: dict[str, JsonValue] = {
            "action": action_to_json(left_row.action),
            "mapped_action": action_to_json(mapped),
            "left": left_scalars,
            "right": right_scalars,
            "numeric_relation": numeric_relation,
            "numeric_failures": numeric_failures,
            "exact_failures": list(exact_failures),
        }
        candidate_records.append(candidate_record)
    left_exploit, left_m_set, left_x_set = _selection_sets(left)
    right_exploit, right_m_set, right_x_set = _selection_sets(right)
    mapped_sets = (
        _mapped_action_json_list(left_exploit, action_map),
        _mapped_action_json_list(left_m_set, action_map),
        _mapped_action_json_list(left_x_set, action_map),
    )
    right_sets = (
        [action_to_json(action) for action in right_exploit],
        [action_to_json(action) for action in right_m_set],
        [action_to_json(action) for action in right_x_set],
    )
    set_count = sum(
        left_set != right_set
        for left_set, right_set in zip(mapped_sets, right_sets, strict=True)
    )
    m_gate_equal, m_decision_equal = _decision_relation(
        left.m_decision,
        right.m_decision,
        action_map=action_map,
        numeric_relation=numeric_relation,
    )
    x_gate_equal, x_decision_equal = _decision_relation(
        left.x_decision,
        right.x_decision,
        action_map=action_map,
        numeric_relation=numeric_relation,
    )
    gate_count = int(not m_gate_equal) + int(not x_gate_equal)
    decision_count = int(not m_decision_equal) + int(not x_decision_equal)
    reasons: list[str] = []
    prefix = "fixed" if fixed else "raw"
    if fixed and key_count:
        reasons.append("fixed_selector_key_mismatch")
    if numeric_count:
        reasons.append(f"{prefix}_selector_numeric_mismatch")
    if eligibility_count:
        reasons.append(f"{prefix}_selector_eligibility_mismatch")
    if rank_count:
        reasons.append(
            "fixed_selector_dense_rank_mismatch"
            if fixed
            else "raw_selector_rank_mismatch"
        )
    if selected_count or set_count:
        reasons.append(f"{prefix}_selector_set_mismatch")
    if gate_count:
        reasons.append(f"{prefix}_selector_gate_mismatch")
    if decision_count:
        reasons.append(f"{prefix}_selector_decision_mismatch")
    details: dict[str, JsonValue] = {
        "candidate_records": candidate_records,
        "compared_candidate_count": len(candidate_records),
        "numeric_mismatch_count": numeric_count,
        "eligibility_mismatch_count": eligibility_count,
        "rank_mismatch_count": rank_count,
        "selected_membership_mismatch_count": selected_count,
        "set_mismatch_count": set_count,
        "gate_mismatch_count": gate_count,
        "decision_mismatch_count": decision_count,
        "key_mismatch_count": key_count,
        "left_exploit_set": [action_to_json(action) for action in left_exploit],
        "right_exploit_set": [action_to_json(action) for action in right_exploit],
        "left_m_maximizer_set": [action_to_json(action) for action in left_m_set],
        "right_m_maximizer_set": [action_to_json(action) for action in right_m_set],
        "left_x_maximizer_set": [action_to_json(action) for action in left_x_set],
        "right_x_maximizer_set": [action_to_json(action) for action in right_x_set],
        "left_m_decision": decision_to_json(left.m_decision),
        "right_m_decision": decision_to_json(right.m_decision),
        "left_x_decision": decision_to_json(left.x_decision),
        "right_x_decision": decision_to_json(right.x_decision),
    }
    return SelectorRelation(MappingProxyType(details), canonicalize_reasons(reasons))


def compare_numeric(left: float | int, right: float | int, relation: NumericRelation) -> bool:
    """Apply the registered actual-tolerance or isolated-exact scalar relation."""

    if relation == "tolerance":
        return tolerance_comparison(float(left), float(right))[0]
    if relation == "exact_binary64":
        return binary64_equal(float(left), float(right))
    raise SelectionSchemaError("unknown selector numeric relation")


__all__ = [
    "ABSOLUTE_TOLERANCE",
    "ACTION_MAP_SCHEMA_VERSION",
    "COMPOUND_SELECTOR_VERSION",
    "EXPECTED_EXTERIOR_SUPPORT_ENCODING",
    "EXPECTED_EXTERIOR_SUPPORT_SCHEMA_VERSION",
    "FIXED_QUANTUM_DENOMINATOR",
    "FIXED_QUANTUM_NUMERATOR",
    "FIXED_SELECTOR_IDENTITY",
    "GRID_EVIDENCE_ENCODING",
    "GRID_EVIDENCE_SCHEMA_VERSION",
    "PALETTE_TRANSFORM_NAME",
    "PAYLOAD_CAP_BYTES",
    "RAW_SELECTOR_IDENTITY",
    "REASON_ORDER",
    "RELATIVE_TOLERANCE",
    "ROLE_ORDER",
    "SCALAR_FIELD_ORDER",
    "SCALE_TRANSFORM_NAME",
    "SELECTION_DIGEST_SCHEMA_VERSION",
    "SNAPSHOT_DIGEST_SCHEMA_VERSION",
    "TRANSFORM_CONTRACT_SCHEMA_VERSION",
    "TRANSLATION_DELTAS",
    "TRANSLATION_MINUS_TRANSFORM_NAME",
    "TRANSLATION_PLUS_TRANSFORM_NAME",
    "VISUAL_TRANSFORM_NAMES",
    "ActionMapError",
    "CompoundActionQBCRow",
    "CompoundActionQBCSelection",
    "ExteriorSupportRegistry",
    "ExteriorSupportTableError",
    "FrontierRelation",
    "GridEvidenceRegistry",
    "GridEvidenceTableError",
    "JsonValue",
    "PredictionPairError",
    "PredictionPairRecord",
    "ReconstructedActionMap",
    "SelectionSchemaError",
    "SelectorRelation",
    "SnapshotSchemaError",
    "TransformContract",
    "TransformContractError",
    "V7ReferenceError",
    "action_from_json",
    "action_to_json",
    "binary64_equal",
    "build_expected_exterior_support_blob",
    "build_grid_blob",
    "build_selection_digest_preimage",
    "build_snapshot_digest_preimage",
    "canonical_action_key",
    "canonical_actions",
    "canonical_grid_bytes",
    "canonical_json_bytes",
    "canonical_sha256",
    "canonical_support_entries",
    "canonicalize_reasons",
    "compare_frontiers",
    "compare_numeric",
    "compare_prediction_pair",
    "compare_selector_selections",
    "decision_to_json",
    "empty_expected_exterior_support_table",
    "empty_grid_evidence_table",
    "expected_exterior_support_reference",
    "fixed_key",
    "grid_evidence_reference",
    "make_transform_contract",
    "map_action",
    "numeric_sentinel",
    "pair_compiler_roles",
    "palette_transform_grid",
    "parse_expected_exterior_support_reference",
    "parse_grid_evidence_reference",
    "reconstruct_action_map",
    "scale_transform_grid",
    "select_compound_action_qbc",
    "selection_details",
    "selection_digest",
    "snapshot_digest",
    "tolerance_comparison",
    "translation_exterior_support",
    "translation_known_viewport",
    "translation_transform_grid",
    "validate_action_map",
    "validate_expected_exterior_support_table",
    "validate_grid_evidence_table",
    "validate_selection_digest_preimage",
    "validate_snapshot_digest_preimage",
    "validate_transform_contract",
]
