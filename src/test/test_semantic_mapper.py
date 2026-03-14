from src.semantic_mapper import SemanticMapper, MappingResult


# ── helpers ───────────────────────────────────────────────────────────────────

def make_mapper(config=None):
    return SemanticMapper(config)


# ── exact match ───────────────────────────────────────────────────────────────

def test_exact_case_insensitive_match():
    mapper = make_mapper()
    extracted = {"Employee's name": "John Doe"}
    pdf_fields = ["employee's name"]
    result = mapper.map(extracted, pdf_fields)
    assert "employee's name" in result.matched
    assert result.matched["employee's name"] == "John Doe"
    assert result.unmapped_json_keys == []


# ── explicit config mapping ───────────────────────────────────────────────────

def test_explicit_config_mapping():
    config = {"field_mappings": {"Employee's name": "EmployeeName"}}
    mapper = make_mapper(config)
    extracted = {"Employee's name": "Jane Doe"}
    pdf_fields = ["EmployeeName", "Date"]
    result = mapper.map(extracted, pdf_fields)
    assert result.matched["EmployeeName"] == "Jane Doe"


# ── alias match ───────────────────────────────────────────────────────────────

def test_alias_match():
    config = {"aliases": {"Employee's name": ["worker name"]}}
    mapper = make_mapper(config)
    extracted = {"Employee's name": "Alice"}
    pdf_fields = ["worker name"]
    result = mapper.map(extracted, pdf_fields)
    assert result.matched["worker name"] == "Alice"


# ── fuzzy match ───────────────────────────────────────────────────────────────

def test_fuzzy_match():
    mapper = make_mapper()
    extracted = {"employee email": "test@test.com"}
    pdf_fields = ["EmployeeEmail"]
    result = mapper.map(extracted, pdf_fields)
    assert "EmployeeEmail" in result.matched
    assert result.matched["EmployeeEmail"] == "test@test.com"


# ── positional fallback ───────────────────────────────────────────────────────

def test_positional_fallback_for_unmatched_key():
    mapper = make_mapper()
    extracted = {"xqzwrandom": "some_value"}
    pdf_fields = ["Text1"]
    result = mapper.map(extracted, pdf_fields)
    assert "xqzwrandom" in result.unmapped_json_keys
    assert "some_value" in result.positional_values


# ── required field warning ────────────────────────────────────────────────────

def test_required_field_warning_when_missing():
    config = {"required_fields": ["Date"]}
    mapper = make_mapper(config)
    extracted = {"Employee's name": "Bob"}
    pdf_fields = ["employee s name"]
    result = mapper.map(extracted, pdf_fields)
    assert any("Date" in w for w in result.warnings)


def test_no_warning_when_required_field_matched():
    config = {
        "required_fields": ["Employee's name"],
        "field_mappings": {"Employee's name": "EmployeeName"},
    }
    mapper = make_mapper(config)
    extracted = {"Employee's name": "Bob"}
    pdf_fields = ["EmployeeName"]
    result = mapper.map(extracted, pdf_fields)
    assert result.warnings == []


# ── multiple fields, partial semantic match ───────────────────────────────────

def test_mixed_semantic_and_positional():
    mapper = make_mapper()
    extracted = {
        "employee email": "a@b.com",
        "zzznomatch": "fallback_value",
    }
    pdf_fields = ["EmployeeEmail", "SomeOtherField"]
    result = mapper.map(extracted, pdf_fields)
    assert result.matched["EmployeeEmail"] == "a@b.com"
    assert "fallback_value" in result.positional_values


# ── report output ─────────────────────────────────────────────────────────────

def test_report_contains_key_sections():
    mapper = make_mapper()
    extracted = {"employee name": "John"}
    pdf_fields = ["employee name", "Date"]
    result = mapper.map(extracted, pdf_fields)
    report = result.report()
    assert "Semantic Mapping Report" in report
    assert "Matched" in report
    assert "Unmapped PDF fields" in report
