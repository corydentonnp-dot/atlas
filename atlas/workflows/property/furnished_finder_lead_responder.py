"""Workflow #13: Furnished Finder Lead Responder — Phase 1 Priority.

Auto-responds to Furnished Finder inquiries with a templated response,
screens the lead, and queues for user review.

Recommended phase: 1 (quick_win_score: 10)
Trust level: draft
Required credentials: Gmail (FF notifications arrive via email)
Category: property

TODO: Implement after scaffolding is approved.

Workflow states:
- idle -> lead_received -> screened -> draft_reply_prepared -> sent | rejected

Service interface:
- parse_lead(email) -> FurnishedFinderLead
- screen_lead(lead) -> ScreeningResult
- draft_response(lead, screening) -> DraftResponse
- send_response(draft, approval) -> None

Schemas needed:
- FurnishedFinderLead(name, dates, guests, budget, message, source_email)
- ScreeningResult(score, flags, recommendation)
- DraftResponse(to, subject, body, is_auto_approved)
"""

# TODO: Implement BaseWorkflow subclass
# TODO: Implement lead parsing from FF email format
# TODO: Add screening criteria configuration
# TODO: Add response templates
# TODO: Add schemas and tests
