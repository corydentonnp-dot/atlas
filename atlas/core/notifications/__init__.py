"""Atlas notification system — abstraction over delivery channels.

TODO: Implement after scaffolding is approved.
Components:
- NotificationChannel interface (Telegram, email, push, log-only)
- NotificationService — route notifications to appropriate channel
- Priority levels: urgent, normal, low, digest-only
- Quiet hours enforcement
- Digest batching for low-priority items
- Delivery confirmation tracking
"""
