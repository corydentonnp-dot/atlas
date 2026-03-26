"""Playwright browser automation adapter.

TODO: Implement after scaffolding is approved.
Required: playwright package installed, ENABLE_BROWSER_AUTOMATION=true

Capabilities:
- navigate(url) -> Page
- screenshot(page, path) -> None
- fill_form(page, selectors_values) -> None
- click(page, selector) -> None
- extract_text(page, selector) -> str
- wait_for(page, selector, timeout) -> None
- run_script(page, js_code) -> Any

WARNING: Browser automations are inherently fragile.
Each workflow using this adapter should have graceful fallback
and human escalation when automation fails.
"""
