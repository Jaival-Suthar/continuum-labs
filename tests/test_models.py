from continuum.core.models import InvestigationResult


def test_investigation_result():
    result = InvestigationResult(question="Why did X happen?")
    assert result.question == "Why did X happen?"
    assert result.paths == []
