"""Atlas event bus — in-process async event system.

TODO: Implement after scaffolding is approved.
Components:
- Event base class with type, source, timestamp, payload
- EventBus for publish/subscribe
- Event handlers registration
- Workflow trigger matching (event type -> workflow)
- Optional Redis Pub/Sub for cross-process events
"""
