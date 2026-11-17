from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMenu

from tilenamer.grid import GridReference
from tilenamer.model import AssetAssignment, AssignmentModel
from tilenamer.placement_window import PlacementPreviewSource, PlacementPreviewWindow
from tilenamer.preferences import Preferences
from tilenamer.theme import colors_for
from tilenamer.ui import MainWindow


ROOT = Path(__file__).resolve().parents[1]


def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def preferences(path: Path) -> Preferences:
    return Preferences(QSettings(str(path), QSettings.Format.IniFormat))


def _linear(channel: int) -> float:
    value = channel / 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def _contrast(foreground: QColor | str, background: QColor | str) -> float:
    def luminance(value: QColor | str) -> float:
        color = value if isinstance(value, QColor) else QColor(value)
        return (
            0.2126 * _linear(color.red())
            + 0.7152 * _linear(color.green())
            + 0.0722 * _linear(color.blue())
        )

    first, second = luminance(foreground), luminance(background)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


def _preview(tmp_path: Path, model: AssignmentModel | None = None):
    app()
    prefs = preferences(tmp_path / "prefs.ini")
    source = PlacementPreviewSource(
        model or AssignmentModel(), Image.new("RGBA", (128, 128), (40, 90, 140, 255)),
        GridReference(), prefs.alpha_colors(),
    )
    host = MainWindow(ROOT, prefs)
    preview = PlacementPreviewWindow(
        host, lambda: source, host.app_icon, prefs.theme, prefs,
    )
    preview.resize(900, 620)
    preview.show()
    app().processEvents()
    preview.canvas.set_grid_visible(False)
    return host, preview, prefs


def test_semantic_text_tokens_are_readable_in_light_and_dark() -> None:
    for theme in ("light", "dark"):
        colors = colors_for(theme)
        for background in (colors.window, colors.panel, colors.field):
            assert _contrast(colors.primary_text, background) >= 4.5
        assert _contrast(colors.secondary_text, colors.panel) >= 4.5
        assert _contrast(colors.warning, colors.window) >= 4.5
        assert _contrast(colors.error, colors.window) >= 4.5


def test_fresh_defaults_and_existing_guide_preference_are_respected(tmp_path: Path) -> None:
    fresh = preferences(tmp_path / "fresh.ini")
    assert fresh.placement_guide_enabled is False
    assert fresh.placement_diagnostic_enabled is True
    assert fresh.placement_diagnostic_opacity == 100

    existing = preferences(tmp_path / "existing.ini")
    existing.placement_guide_enabled = True
    existing.placement_guide_opacity = 42
    existing.settings.sync()
    restored = preferences(tmp_path / "existing.ini")
    assert restored.placement_guide_enabled is True
    assert restored.placement_guide_opacity == 42


def test_empty_actual_four_layer_states_are_independent(tmp_path: Path) -> None:
    host, preview, _prefs = _preview(tmp_path)
    result = preview.canvas.result
    assert result is not None
    assert not result.ready_roles
    assert all(cell.assignment_identity is None for cell in result.cells)
    assert preview.summary_label.text().startswith("준비 0 /")

    preview.guide_toggle.setChecked(False)
    preview.diagnostic_toggle.setChecked(False)
    app().processEvents()
    empty = preview.canvas.grab().toImage()

    preview.guide_toggle.setChecked(True)
    app().processEvents()
    guide_only = preview.canvas.grab().toImage()

    preview.guide_toggle.setChecked(False)
    preview.diagnostic_toggle.setChecked(True)
    app().processEvents()
    diagnostic_only = preview.canvas.grab().toImage()

    preview.guide_toggle.setChecked(True)
    app().processEvents()
    guide_and_diagnostic = preview.canvas.grab().toImage()

    assert empty != guide_only
    assert empty != diagnostic_only
    assert guide_only != guide_and_diagnostic
    assert diagnostic_only != guide_and_diagnostic
    hit = preview.canvas.hit_test(preview.canvas.logical_cell_center((0, 0)))
    assert hit is not None and hit.assignment_identity is None
    assert preview.canvas.result is result
    host.close()


def test_diagnostic_controls_persist_without_changing_counts_or_actual(tmp_path: Path) -> None:
    model = AssignmentModel({
        "Platform_Center": [AssetAssignment("Platform_Center", 0, 0)],
    })
    host, preview, prefs = _preview(tmp_path, model)
    preview.family_combo.setCurrentText("Platform")
    preview.pattern_combo.setCurrentText("단일")
    preview.refresh_preview()
    result = preview.canvas.result
    assert result is not None
    counts = (
        result.missing_counts, result.no_fit_counts, result.fallback_counts,
        result.ready_roles, preview.summary_label.text(), preview.missing_label.text(),
    )
    actual_keys = {identity: pixmap.cacheKey() for identity, pixmap in preview.canvas.pixmaps.items()}

    preview.diagnostic_toggle.setChecked(False)
    preview.diagnostic_opacity_slider.setValue(37)
    preview.guide_toggle.setChecked(not preview.guide_toggle.isChecked())
    app().processEvents()

    current = preview.canvas.result
    assert current is result
    assert (
        current.missing_counts, current.no_fit_counts, current.fallback_counts,
        current.ready_roles, preview.summary_label.text(), preview.missing_label.text(),
    ) == counts
    assert {identity: pixmap.cacheKey() for identity, pixmap in preview.canvas.pixmaps.items()} == actual_keys
    assert preview.canvas.diagnostics_enabled is False
    assert preview.canvas.diagnostic_opacity == 37
    prefs.settings.sync()
    restored = preferences(tmp_path / "prefs.ini")
    assert restored.placement_diagnostic_enabled is False
    assert restored.placement_diagnostic_opacity == 37
    host.close()


def test_diagnostic_opacity_changes_only_the_diagnostic_pixels(tmp_path: Path) -> None:
    host, preview, _prefs = _preview(tmp_path)
    preview.guide_toggle.setChecked(False)
    preview.diagnostic_toggle.setChecked(True)
    result = preview.canvas.result
    assert result is not None
    logical_state = (result.missing_counts, result.no_fit_counts, result.ready_roles)

    preview.diagnostic_opacity_slider.setValue(10)
    app().processEvents()
    faint = preview.canvas.grab().toImage()
    preview.diagnostic_opacity_slider.setValue(100)
    app().processEvents()
    strong = preview.canvas.grab().toImage()

    assert faint != strong
    assert (result.missing_counts, result.no_fit_counts, result.ready_roles) == logical_state
    preview.diagnostic_toggle.setChecked(False)
    hit = preview.canvas.hit_test(preview.canvas.logical_cell_center((0, 0)))
    assert hit is not None and hit.assignment_identity is None
    host.close()


def test_preview_theme_matrix_keeps_controls_and_footer_readable(tmp_path: Path) -> None:
    host, preview, _prefs = _preview(tmp_path)
    for theme in ("light", "dark"):
        preview.apply_theme(theme)
        colors = colors_for(theme)
        app().processEvents()
        for guide_enabled in (False, True):
            for diagnostic_enabled in (False, True):
                preview.guide_toggle.setChecked(guide_enabled)
                preview.diagnostic_toggle.setChecked(diagnostic_enabled)
                app().processEvents()
                assert not preview.canvas.grab().isNull()
                assert preview.summary_label.isVisible()
                assert preview.missing_label.isVisible()
        assert _contrast(colors.primary_text, colors.panel) >= 4.5
        assert _contrast(colors.error, colors.panel) >= 4.5
        disabled = preview.guide_opacity_label.palette().color(
            QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText,
        )
        assert disabled.isValid()
    host.close()


def test_preview_is_top_level_button_only_and_reuses_window(tmp_path: Path) -> None:
    qt = app()
    window = MainWindow(ROOT, preferences(tmp_path / "prefs.ini"))
    view_menu = window.findChild(QMenu, "viewMenu")
    assert view_menu is not None
    assert "배치 미리보기" not in {action.text() for action in view_menu.actions()}
    assert window.placement_preview_button.text() == "배치 미리보기"

    window.placement_preview_button.click()
    qt.processEvents()
    first = window.placement_preview_window
    assert first is not None and first.isVisible()
    window.placement_preview_button.click()
    qt.processEvents()
    assert window.placement_preview_window is first
    window.close()
