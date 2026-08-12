from __future__ import annotations

from dataclasses import dataclass

from .models import (
    GAME_SIDE_LEFT,
    GAME_SIDE_RIGHT,
    LAYOUT_AUTOMATIC,
    LAYOUT_CUSTOM,
    LAYOUT_EQUAL_HALVES,
    LAYOUT_GAME_16_9,
    LAYOUT_MODES,
    TargetRect,
)


GAME_ASPECT_WIDTH = 16
GAME_ASPECT_HEIGHT = 9
MIN_SECONDARY_WIDTH = 320
AUTO_EQUAL_TOLERANCE_PIXELS = 4


@dataclass(slots=True, frozen=True)
class ZoneLayout:
    """Resolved game/secondary zones for one physical monitor."""

    monitor: TargetRect
    game: TargetRect
    secondary: TargetRect
    requested_mode: str
    effective_mode: str
    game_side: str

    @property
    def description(self) -> str:
        mode = {
            LAYOUT_EQUAL_HALVES: "50/50",
            LAYOUT_GAME_16_9: "Spiel 16:9 + Restflaeche",
            LAYOUT_CUSTOM: "Benutzerdefiniert",
        }.get(self.effective_mode, self.effective_mode)
        side = "links" if self.game_side == GAME_SIDE_LEFT else "rechts"
        return f"{mode}; Spiel {side}"


def calculate_layout(
    monitor: TargetRect,
    mode: str,
    game_side: str = GAME_SIDE_LEFT,
) -> ZoneLayout:
    """Calculate two non-overlapping zones that cover the selected monitor.

    ``automatic`` chooses equal halves when each half is effectively 16:9
    (typical 32:9 monitors). On other sufficiently wide monitors it preserves
    a 16:9 game area and assigns the remaining strip to the second window.
    """

    monitor.validate()
    normalized_mode = mode.strip().casefold()
    if normalized_mode not in LAYOUT_MODES or normalized_mode == LAYOUT_CUSTOM:
        raise ValueError("Dieser Layoutmodus kann nicht automatisch berechnet werden.")
    if game_side not in (GAME_SIDE_LEFT, GAME_SIDE_RIGHT):
        raise ValueError("Die Spielseite muss links oder rechts sein.")

    effective_mode = normalized_mode
    if normalized_mode == LAYOUT_AUTOMATIC:
        effective_mode = _automatic_mode(monitor)

    if effective_mode == LAYOUT_EQUAL_HALVES:
        left_width = monitor.width // 2
        right_width = monitor.width - left_width
    elif effective_mode == LAYOUT_GAME_16_9:
        game_width = _sixteen_nine_width(monitor.height)
        remaining = monitor.width - game_width
        if remaining < MIN_SECONDARY_WIDTH:
            raise ValueError(
                "Der Monitor ist fuer 16:9 plus Restflaeche nicht breit genug. "
                "Waehle 50/50 oder Benutzerdefiniert."
            )
        if game_side == GAME_SIDE_LEFT:
            left_width, right_width = game_width, remaining
        else:
            left_width, right_width = remaining, game_width
    else:  # Defensive guard if a new mode is added without a calculator.
        raise ValueError("Unbekannter Layoutmodus.")

    left = TargetRect(
        monitor.x,
        monitor.y,
        left_width,
        monitor.height,
    )
    right = TargetRect(
        monitor.x + left_width,
        monitor.y,
        right_width,
        monitor.height,
    )
    game = left if game_side == GAME_SIDE_LEFT else right
    secondary = right if game_side == GAME_SIDE_LEFT else left
    game.validate()
    secondary.validate()
    return ZoneLayout(
        monitor=monitor,
        game=game,
        secondary=secondary,
        requested_mode=normalized_mode,
        effective_mode=effective_mode,
        game_side=game_side,
    )


def _automatic_mode(monitor: TargetRect) -> str:
    game_width = _sixteen_nine_width(monitor.height)
    if abs(monitor.width - (game_width * 2)) <= AUTO_EQUAL_TOLERANCE_PIXELS:
        return LAYOUT_EQUAL_HALVES
    if monitor.width - game_width >= MIN_SECONDARY_WIDTH:
        return LAYOUT_GAME_16_9
    return LAYOUT_EQUAL_HALVES


def _sixteen_nine_width(height: int) -> int:
    # An even width is friendlier to common video encoders and game renderers.
    width = round(height * GAME_ASPECT_WIDTH / GAME_ASPECT_HEIGHT)
    return width if width % 2 == 0 else width - 1
