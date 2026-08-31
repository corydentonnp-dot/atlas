"""Sanitization: keep the research dataset free of contact/commerce data.

The study deliberately excludes seller-contact and purchasing information.
Structured fields are extracted from a whitelist, but any free text carried
into the dataset (product titles, description snippets) is additionally
scrubbed here as a second line of defense.
"""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Phone-like sequences: international or long digit runs with separators.
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
_CONTACT_KEYWORD_RE = re.compile(
    r"(?:whats\s?app|wechat|telegram|signal|viber|line\s+id|skype|kik|qq|"
    r"contact\s+us|call\s+us|text\s+us|hotline)"
    r"[^.;\n]{0,60}",
    re.IGNORECASE,
)
_PAYMENT_RE = re.compile(
    r"(?:western\s+union|moneygram|paypal|zelle|venmo|cash\s?app|bank\s+(?:transfer|wire)|"
    r"wire\s+transfer|bitcoin|btc|usdt|ethereum|crypto(?:currency)?|credit\s+card|visa|"
    r"mastercard|payment\s+(?:method|instruction)s?|checkout|how\s+to\s+(?:pay|order))"
    r"[^.;\n]{0,80}",
    re.IGNORECASE,
)
_SHIPPING_RE = re.compile(
    r"(?:free\s+shipping|shipping\s+(?:time|cost|fee|method|info)|ships?\s+(?:from|to|within)|"
    r"delivery\s+(?:time|within)|ems|dhl|fedex|ups\b|epacket|tracking\s+number)"
    r"[^.;\n]{0,80}",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_STOCK_RE = re.compile(
    r"(?:in\s+stock|out\s+of\s+stock|stock\s+alert|back\s+in\s+stock|pre-?order\s+now|"
    r"order\s+now|buy\s+now|add\s+to\s+cart)[^.;\n]{0,40}",
    re.IGNORECASE,
)

_ALL_PATTERNS = (
    _EMAIL_RE,
    _CONTACT_KEYWORD_RE,
    _PHONE_RE,
    _PAYMENT_RE,
    _SHIPPING_RE,
    _URL_RE,
    _STOCK_RE,
)


def scrub_text(text: str) -> str:
    """Remove contact, payment, shipping, stock, and URL fragments from text."""
    cleaned = text
    for pattern in _ALL_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def contains_excluded_content(text: str) -> bool:
    return any(p.search(text) for p in _ALL_PATTERNS)
