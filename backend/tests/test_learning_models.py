from app.models.learning import QuizQuestion, BanditEvent

def test_quiz_question_links_structure_and_difficulty():
    q = QuizQuestion(id="q1", lesson_id="spine_001", structure_id="spine.lumbar_region",
                     difficulty="medium", prompt="How many lumbar vertebrae?",
                     correct="5", choices=["3", "4", "5", "6"], review_status="APPROVED")
    assert q.difficulty == "medium" and q.correct == "5"

def test_bandit_event_roundtrips_context():
    e = BanditEvent(id="b1", user_id="u1", action="spine.lumbar_region|hard",
                    context_json={"mastery": 0.2}, reward=1.0)
    assert e.context_json["mastery"] == 0.2
