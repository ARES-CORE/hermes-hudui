from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_top_bar_tabs_are_resize_safe() -> None:
    top_bar = (ROOT / "frontend/src/components/TopBar.tsx").read_text()

    assert 'data-testid="top-bar"' in top_bar
    assert 'data-testid="top-tabs"' in top_bar
    assert "w-full min-w-0 overflow-visible relative z-40" in top_bar
    assert "flex-1 min-w-0 overflow-x-auto" in top_bar
    assert "scrollbarWidth: 'thin'" in top_bar
    assert "scrollIntoView" in top_bar
