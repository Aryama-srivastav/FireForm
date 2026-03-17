from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


@dataclass
class GateResult:
    name: str
    passed: bool
    reason_codes: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    run_id: str
    created_at: str
    source_pdf: str
    gates: list[GateResult] = field(default_factory=list)
    output_pdf: str | None = None

    @property
    def passed(self) -> bool:
        return all(g.passed for g in self.gates)

    def add_gate(self, gate: GateResult) -> None:
        self.gates.append(gate)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["passed"] = self.passed
        return payload

    def write(self, report_path: str, output_pdf: str | None = None) -> str:
        if output_pdf:
            self.output_pdf = output_pdf
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        return report_path


class ValidationGates:
    @staticmethod
    def input_to_extraction(pdf_form: str, llm: Any, extracted: Any) -> GateResult:
        reasons: list[str] = []
        details: dict[str, Any] = {}

        if not pdf_form or not os.path.exists(pdf_form):
            reasons.append("INPUT_PDF_NOT_FOUND")

        if llm is None or not hasattr(llm, "main_loop"):
            reasons.append("LLM_NOT_CONFIGURED")

        if not isinstance(extracted, dict):
            reasons.append("EXTRACTION_NOT_DICT")
        elif not extracted:
            reasons.append("EXTRACTION_EMPTY")

        details["extracted_key_count"] = len(extracted) if isinstance(extracted, dict) else 0

        return GateResult(
            name="Input -> Extraction",
            passed=len(reasons) == 0,
            reason_codes=reasons,
            details=details,
        )

    @staticmethod
    def extraction_to_json(extracted: dict[str, Any], template_config: dict[str, Any]) -> GateResult:
        reasons: list[str] = []
        details: dict[str, Any] = {}
        required_fields: list[str] = template_config.get("required_fields", []) if template_config else []

        missing_required = [k for k in required_fields if not extracted.get(k)]
        if missing_required:
            reasons.append("MANDATORY_FIELDS_MISSING")

        non_empty_count = sum(1 for _, v in extracted.items() if v not in (None, "", []))
        total_count = len(extracted)
        completeness_ratio = (non_empty_count / total_count) if total_count else 0.0

        min_ratio = float(template_config.get("min_completeness_ratio", 0.8)) if template_config else 0.8
        if total_count == 0 or completeness_ratio < min_ratio:
            reasons.append("COMPLETENESS_BELOW_THRESHOLD")

        details.update(
            {
                "total_extracted_fields": total_count,
                "non_empty_fields": non_empty_count,
                "completeness_ratio": round(completeness_ratio, 4),
                "min_required_ratio": min_ratio,
                "missing_required_fields": missing_required,
            }
        )

        return GateResult(
            name="Extraction -> JSON",
            passed=len(reasons) == 0,
            reason_codes=reasons,
            details=details,
        )

    @staticmethod
    def json_to_pdf(
        extracted: dict[str, Any],
        pdf_field_names: list[str],
        mapping_result: Any,
        template_config: dict[str, Any],
    ) -> GateResult:
        reasons: list[str] = []
        details: dict[str, Any] = {}

        matched: dict[str, Any] = getattr(mapping_result, "matched", {}) or {}
        positional_values: list[Any] = getattr(mapping_result, "positional_values", []) or []

        unmatched_pdf_fields = [f for f in pdf_field_names if f not in matched]
        required_pdf_fields: list[str] = template_config.get("required_pdf_fields", []) if template_config else []
        missing_required_pdf = [f for f in required_pdf_fields if f not in matched]

        if not pdf_field_names:
            reasons.append("PDF_WIDGETS_NOT_FOUND")

        if missing_required_pdf:
            reasons.append("MANDATORY_PDF_FIELDS_UNMATCHED")

        if positional_values:
            reasons.append("POSITIONAL_FALLBACK_USED")

        if unmatched_pdf_fields:
            reasons.append("PDF_FIELDS_UNMATCHED")

        # Simple mismatch signal between extracted volume and semantic matches
        if len(extracted) > 0 and len(matched) == 0:
            reasons.append("JSON_TO_PDF_MAPPING_EMPTY")

        details.update(
            {
                "pdf_field_count": len(pdf_field_names),
                "matched_pdf_fields_count": len(matched),
                "unmatched_pdf_fields": unmatched_pdf_fields,
                "missing_required_pdf_fields": missing_required_pdf,
                "positional_fallback_count": len(positional_values),
            }
        )

        return GateResult(
            name="JSON -> PDF",
            passed=len(reasons) == 0,
            reason_codes=reasons,
            details=details,
        )

    @staticmethod
    def new_report(source_pdf: str) -> ValidationReport:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        return ValidationReport(
            run_id=run_id,
            created_at=datetime.now().isoformat(),
            source_pdf=source_pdf,
        )