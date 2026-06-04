"""MVP JSON Schema validation for task outputs and verifier evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional


class OutputValidationError(ValueError):
    def __init__(self, *, path: str, expected: str, actual: Any) -> None:
        self.path = path
        self.expected = expected
        self.actual = actual
        super().__init__(f"{path}: expected {expected}; actual {_preview(actual)}")


@dataclass(frozen=True)
class VerifierEvidence:
    status: str
    proof: str
    audit_log_ref: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "proof": self.proof,
            "audit_log_ref": self.audit_log_ref,
        }


def validate_task_output(output: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    if "status" not in output:
        raise OutputValidationError(path="$.status", expected="required status field", actual="<missing>")
    _validate_value(output, schema, "$")


def _validate_value(value: Any, schema: Mapping[str, Any], path: str) -> None:
    if "enum" in schema and value not in schema["enum"]:
        raise OutputValidationError(path=path, expected=f"one of {schema['enum']!r}", actual=value)

    expected_type = schema.get("type")
    if expected_type is not None and not _matches_type(value, expected_type):
        raise OutputValidationError(path=path, expected=str(expected_type), actual=value)

    if expected_type == "object" or "properties" in schema or "required" in schema:
        if not isinstance(value, Mapping):
            raise OutputValidationError(path=path, expected="object", actual=value)
        for key in schema.get("required", []):
            if key not in value:
                raise OutputValidationError(path=f"{path}.{key}", expected="required field", actual="<missing>")
        for key, child_schema in schema.get("properties", {}).items():
            if key in value:
                _validate_value(value[key], child_schema, f"{path}.{key}")

    if expected_type == "array" and "items" in schema:
        for index, item in enumerate(value):
            _validate_value(item, schema["items"], f"{path}[{index}]")


def _matches_type(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, Mapping)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def _preview(value: Any) -> str:
    text = repr(value)
    if len(text) > 120:
        return text[:117] + "..."
    return text
