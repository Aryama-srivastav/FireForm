from typing import Any, Optional

from pdfrw import PdfReader, PdfWriter
from src.semantic_mapper import SemanticMapper
from datetime import datetime
from src.validation_gates import ValidationGates


class Filler:
    def __init__(self):
        pass

    def fill_form(
        self,
        pdf_form: str,
        llm: Any,
        template_config: Optional[dict] = None,
        strict_validation: bool = True,
    ):
        """
        Fill a PDF form with values extracted by LLM.

        Fields are matched semantically (JSON key ↔ PDF widget name) first.
        Any unmatched fields fall back to visual-order positional assignment
        (top-to-bottom, left-to-right).

        Validation gates:
          1) Input -> Extraction
          2) Extraction -> JSON
          3) JSON -> PDF

        If strict_validation=True and any gate fails, PDF is not written.
        """
        cfg = template_config or {}
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        output_pdf = pdf_form[:-4] + "_" + ts + "_filled.pdf"
        validation_report_path = pdf_form[:-4] + "_" + ts + "_validation_report.json"

        validation_report = ValidationGates.new_report(source_pdf=pdf_form)

        # ── 1. Extract structured data from LLM ──────────────────────────────
        t2j = llm.main_loop()
        textbox_answers = t2j.get_data()  # {json_key: value}

        gate_1 = ValidationGates.input_to_extraction(pdf_form, llm, textbox_answers)
        validation_report.add_gate(gate_1)

        gate_2 = ValidationGates.extraction_to_json(
            textbox_answers if isinstance(textbox_answers, dict) else {},
            cfg,
        )
        validation_report.add_gate(gate_2)

        # ── 2. Collect PDF widgets in visual order (global across pages) ──────
        pdf = PdfReader(pdf_form)
        ordered_annots = []
        pdf_field_names = []

        for page in (pdf.pages or []):  # type: ignore[operator]
            if page.Annots:
                sorted_annots = sorted(
                    page.Annots, key=lambda a: (-float(a.Rect[1]), float(a.Rect[0]))
                )
                for annot in sorted_annots:
                    if annot.Subtype == "/Widget" and annot.T:
                        pdf_field_names.append(annot.T[1:-1])
                        ordered_annots.append(annot)

        # ── 3. Semantic mapping ───────────────────────────────────────────────
        mapper = SemanticMapper(cfg)
        result = mapper.map(textbox_answers, pdf_field_names)
        print(result.report())

        gate_3 = ValidationGates.json_to_pdf(
            textbox_answers if isinstance(textbox_answers, dict) else {},
            pdf_field_names,
            result,
            cfg,
        )
        validation_report.add_gate(gate_3)

        # Block final output if validation fails
        if strict_validation and not validation_report.passed:
            validation_report.write(validation_report_path, output_pdf=None)
            raise ValueError(
                f"Validation failed. Report generated at: {validation_report_path}"
            )

        # ── 4. Fill: semantic matches first, positional fallback for the rest ─
        positional_idx = 0
        for annot, pdf_field in zip(ordered_annots, pdf_field_names):
            if pdf_field in result.matched:
                annot.V = f"{result.matched[pdf_field]}"
                annot.AP = None
            elif positional_idx < len(result.positional_values):
                annot.V = f"{result.positional_values[positional_idx]}"
                annot.AP = None
                positional_idx += 1

        PdfWriter().write(output_pdf, pdf)
        validation_report.write(validation_report_path, output_pdf=output_pdf)

        return output_pdf
