import pytest
from app.services.review import advance, can_perform, STATUSES, TRANSITIONS

def test_happy_path():
    s = "DRAFT"
    for action in ("generate", "submit", "submit", "approve", "publish"):
        s = advance(s, action)
    assert s == "PUBLISHED"

def test_reject_returns_to_content_review():
    assert advance("MEDICAL_REVIEW", "reject") == "CONTENT_REVIEW"

@pytest.mark.parametrize("status,action", [("DRAFT", "publish"), ("CONTENT_REVIEW", "approve"),
                                           ("PUBLISHED", "reject"), ("MEDICAL_REVIEW", "bogus")])
def test_illegal_transition_raises(status, action):
    with pytest.raises(ValueError):
        advance(status, action)

def test_every_transition_targets_a_known_status():
    assert all(a in STATUSES and b in STATUSES for (a, _), b in TRANSITIONS.items())

def test_only_medical_reviewers_approve_or_reject():
    for action in ("approve", "reject"):
        assert can_perform("MEDICAL_REVIEWER", action) and can_perform("SUPER_ADMIN", action)
        assert not can_perform("CONTENT_EDITOR", action) and not can_perform("STUDENT", action)
    assert can_perform("CONTENT_EDITOR", "submit") and not can_perform("MEDICAL_REVIEWER", "publish")
