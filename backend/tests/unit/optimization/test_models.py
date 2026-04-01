from hiresense.optimization.domain.models import OptimizationResult, SectionChange


def test_section_change_creation() -> None:
    change = SectionChange(
        section_name="SUMMARY",
        original="Backend developer with Python experience",
        optimized="Backend engineer specializing in scalable Python APIs with FastAPI and PostgreSQL",
        reason="Aligned with job requirements for API development",
    )
    assert change.section_name == "SUMMARY"
    assert "FastAPI" in change.optimized


def test_optimization_result_creation() -> None:
    changes = [
        SectionChange(
            section_name="SUMMARY",
            original="Original text",
            optimized="Optimized text",
            reason="Better alignment",
        )
    ]
    result = OptimizationResult(
        id="opt-1",
        match_id="match-1",
        job_id="job-1",
        cv_id="cv-1",
        changes=changes,
        original_tex="\\section*{SUMMARY}\nOriginal text",
        optimized_tex="\\section*{SUMMARY}\nOptimized text",
        improvement_summary="Improved summary section alignment",
    )
    assert result.match_id == "match-1"
    assert len(result.changes) == 1
    assert result.optimized_tex != result.original_tex


def test_optimization_result_defaults() -> None:
    result = OptimizationResult(
        id="opt-2",
        match_id="match-2",
        job_id="job-2",
        cv_id="cv-2",
        original_tex="",
        optimized_tex="",
    )
    assert result.changes == []
    assert result.improvement_summary is None
