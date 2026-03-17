from types import SimpleNamespace

from src.validation_gates import ValidationGates


def test_input_to_extraction_pass(tmp_path):
    pdf = tmp_path / "form.pdf"
    pdf.write_text("dummy")
    llm = SimpleNamespace(main_loop=lambda: None)
    extracted = {"name": "Aryama"}

    gate = ValidationGates.input_to_extraction(str(pdf), llm, extracted)

    assert gate.passed is True
    assert gate.reason_codes == []


def test_input_to_extraction_fail_missing_pdf_and_bad_extraction():
    gate = ValidationGates.input_to_extraction(
        "C:/does-not-exist/form.pdf",
        llm=None,
        extracted=[],
    )

    assert gate.passed is False
    assert "INPUT_PDF_NOT_FOUND" in gate.reason_codes
    assert "LLM_NOT_CONFIGURED" in gate.reason_codes
    assert "EXTRACTION_NOT_DICT" in gate.reason_codes


def test_extraction_to_json_mandatory_and_completeness_checks():
    extracted = {"name": "Aryama", "email": ""}
    cfg = {"required_fields": ["name", "email"], "min_completeness_ratio": 1.0}

    gate = ValidationGates.extraction_to_json(extracted, cfg)

    assert gate.passed is False
    assert "MANDATORY_FIELDS_MISSING" in gate.reason_codes
    assert "COMPLETENESS_BELOW_THRESHOLD" in gate.reason_codes


def test_json_to_pdf_detects_mismatch_and_positional():
    extracted = {"name": "Aryama", "email": "a@x.com"}
    pdf_fields = ["full_name", "email_address"]

    mapping_result = SimpleNamespace(
        matched={"full_name": "Aryama"},
        positional_values=["a@x.com"],
    )
    cfg = {"required_pdf_fields": ["full_name", "email_address"]}

    gate = ValidationGates.json_to_pdf(extracted, pdf_fields, mapping_result, cfg)

    assert gate.passed is False
    assert "MANDATORY_PDF_FIELDS_UNMATCHED" in gate.reason_codes
    assert "POSITIONAL_FALLBACK_USED" in gate.reason_codes
    assert "PDF_FIELDS_UNMATCHED" in gate.reason_codes