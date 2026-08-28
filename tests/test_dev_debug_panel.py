from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
THINKING_JS = (PROJECT_ROOT / "static" / "js" / "thinking.js").read_text(encoding="utf-8")
THINKING_CSS = (PROJECT_ROOT / "static" / "css" / "thinking.css").read_text(encoding="utf-8")


def test_dev_debug_panel_has_a_collapsible_persisted_toggle_contract():
    assert "dev-debug-toggle" in THINKING_JS
    assert "dev-debug-content" in THINKING_JS
    assert "aria-expanded" in THINKING_JS
    assert "sessionStorage" in THINKING_JS
    assert ".dev-debug-panel.is-collapsed .dev-debug-content" in THINKING_CSS
