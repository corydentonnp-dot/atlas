"""Workflow #2: Unanswered Question Detector — Phase 2.

Scans messages for explicit questions directed at you that remain unanswered.

Recommended phase: 2 (quick_win_score: 7)
Trust level: draft
Required credentials: Gmail or message source access
Category: communication

TODO: Implement after scaffolding is approved.

Workflow states:
- idle -> scanning -> questions_found -> notified -> resolved

Service interface:
- scan_for_questions(lookback_days) -> list[UnansweredQuestion]
- classify_question(message) -> QuestionType
- suggest_answer(question) -> str | None
"""

# TODO: Implement BaseWorkflow subclass
# TODO: Implement question detection (NLP/pattern matching)
# TODO: Add Pydantic schemas
# TODO: Add tests
