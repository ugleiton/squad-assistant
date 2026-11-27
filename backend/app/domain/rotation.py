from datetime import date

from .enums import RotationMode


def period_key(mode: RotationMode, day: date) -> str | None:
    if mode == RotationMode.daily:
        return day.isoformat()
    if mode == RotationMode.weekly:
        year, week, _ = day.isocalendar()
        return f"{year}-W{week:02d}"
    return None


def next_facilitator(
    participant_ids: list[int],
    mode: RotationMode,
    current_id: int | None,
    current_period: str | None,
    day: date,
) -> tuple[int | None, str | None]:
    """Return (facilitator_id, period_key) for `day`.

    The facilitator stays the same within a period (a day or an ISO week) and moves to the next
    active participant, in order, when a new period starts. If the current facilitator left the
    rotation, the next one in order after their old position is not knowable, so we start over."""
    if mode == RotationMode.none or not participant_ids:
        return None, None
    key = period_key(mode, day)
    if current_id in participant_ids and current_period == key:
        return current_id, key
    if current_id in participant_ids:
        idx = (participant_ids.index(current_id) + 1) % len(participant_ids)
    else:
        idx = 0
    return participant_ids[idx], key
