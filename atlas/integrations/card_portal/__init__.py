"""Card/account portal adapter interface.

TODO: Implement after scaffolding is approved.
Generic interface for interacting with credit card / bank portals.
Each portal implementation would be a separate subclass.

Capabilities:
- get_transactions(start, end) -> list[Transaction]
- get_balance() -> Balance
- get_statements(months) -> list[Statement]
- get_promo_apr_details() -> list[PromoAPR]
- check_offers() -> list[CardOffer]
"""
