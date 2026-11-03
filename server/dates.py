"""Dates in generated documents: German TT.MM.JJJJ, English DD/MM/YYYY; stored values stay ISO."""
from datetime import date, datetime

try:
    from zoneinfo import ZoneInfo
    LOCAL = ZoneInfo('Europe/Berlin')
except Exception:  # container without time-zone data: fall back to the stored UTC date
    LOCAL = None


def display_date(value, de=True):
    """ISO date or timestamp -> local calendar date; anything unparseable is returned unchanged."""
    if not value:
        return '-'
    try:
        if isinstance(value, str) and len(value) == 10:
            day = date.fromisoformat(value)
        else:
            moment = value if isinstance(value, datetime) else datetime.fromisoformat(value)
            day = (moment.astimezone(LOCAL) if LOCAL and moment.tzinfo else moment).date()
    except (TypeError, ValueError):
        return str(value)
    return day.strftime('%d.%m.%Y' if de else '%d/%m/%Y')
