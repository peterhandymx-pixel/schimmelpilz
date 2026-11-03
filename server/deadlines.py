"""Calculation aid for German statutory periods (§§ 187, 188, 193 BGB; § 222 ZPO).

Bounded scope: forward periods in days, weeks, months or years, statewide public holidays 2015–2035.
Not covered: periods counted backwards, hour periods, municipal holidays (e.g. Augsburger Friedensfest,
Mariä Himmelfahrt in Catholic parts of Bavaria, Fronleichnam in parts of Saxony/Thuringia), court-specific
closures, service/delivery fictions (e.g. § 122 AO, § 41 VwVfG) and any legal assessment of which period applies.
"""
import calendar
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

FIRST_YEAR, LAST_YEAR = 2015, 2035
STATES = {
    'BW': 'Baden-Württemberg', 'BY': 'Bayern', 'BE': 'Berlin', 'BB': 'Brandenburg', 'HB': 'Bremen', 'HH': 'Hamburg',
    'HE': 'Hessen', 'MV': 'Mecklenburg-Vorpommern', 'NI': 'Niedersachsen', 'NW': 'Nordrhein-Westfalen',
    'RP': 'Rheinland-Pfalz', 'SL': 'Saarland', 'SN': 'Sachsen', 'ST': 'Sachsen-Anhalt', 'SH': 'Schleswig-Holstein', 'TH': 'Thüringen',
}


def easter(year):
    """Gregorian Easter Sunday (anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def holidays(year, state):
    """Statewide public holidays {date: name}. state=None gives the nationwide holidays only."""
    if not FIRST_YEAR <= year <= LAST_YEAR:
        raise ValueError('year_unsupported')
    sunday = easter(year)
    result = {
        date(year, 1, 1): 'Neujahr', sunday - timedelta(days=2): 'Karfreitag', sunday + timedelta(days=1): 'Ostermontag',
        date(year, 5, 1): 'Tag der Arbeit', sunday + timedelta(days=39): 'Christi Himmelfahrt', sunday + timedelta(days=50): 'Pfingstmontag',
        date(year, 10, 3): 'Tag der Deutschen Einheit', date(year, 12, 25): '1. Weihnachtstag', date(year, 12, 26): '2. Weihnachtstag',
    }
    if year == 2017:
        result[date(2017, 10, 31)] = 'Reformationstag (bundesweit 2017)'
    if not state:
        return result
    if state in {'BW', 'BY', 'ST'}:
        result[date(year, 1, 6)] = 'Heilige Drei Könige'
    if (state == 'BE' and year >= 2019) or (state == 'MV' and year >= 2023):
        result[date(year, 3, 8)] = 'Internationaler Frauentag'
    if state == 'BE' and year in {2020, 2025}:
        result[date(year, 5, 8)] = 'Tag der Befreiung (einmalig)'
    if state in {'BW', 'BY', 'HE', 'NW', 'RP', 'SL'}:
        result[sunday + timedelta(days=60)] = 'Fronleichnam'
    if state == 'SL':
        result[date(year, 8, 15)] = 'Mariä Himmelfahrt'
    if state == 'TH' and year >= 2019:
        result[date(year, 9, 20)] = 'Weltkindertag'
    if state in {'BB', 'MV', 'SN', 'ST', 'TH'} or (state in {'HB', 'HH', 'NI', 'SH'} and year >= 2018):
        result[date(year, 10, 31)] = 'Reformationstag'
    if state in {'BW', 'BY', 'NW', 'RP', 'SL'}:
        result[date(year, 11, 1)] = 'Allerheiligen'
    if state == 'SN':
        # Wednesday before 23 November.
        day = date(year, 11, 22)
        result[day - timedelta(days=(day.weekday() - 2) % 7)] = 'Buß- und Bettag'
    return result


def add_months(start, months):
    """(target date or None if the day number does not exist, last day of the target month)."""
    index = start.month - 1 + months
    year, month = start.year + index // 12, index % 12 + 1
    last = calendar.monthrange(year, month)[1]
    return (date(year, month, start.day) if start.day <= last else None), date(year, month, last)


def raw_end(start, amount, unit, start_type):
    """End of the period before § 193 BGB / § 222 Abs. 2 ZPO."""
    inclusive = start_type == 'day_start'  # § 187 Abs. 2 BGB: the starting day itself counts.
    if unit == 'days':
        return start + timedelta(days=amount - 1 if inclusive else amount), ('§ 188 Abs. 1 BGB')
    if unit == 'weeks':
        return start + timedelta(days=7 * amount - (1 if inclusive else 0)), ('§ 188 Abs. 2 BGB')
    months = amount * (12 if unit == 'years' else 1)
    corresponding, last = add_months(start, months)
    if corresponding is None:
        return last, '§ 188 Abs. 3 BGB'
    return (corresponding - timedelta(days=1) if inclusive else corresponding), '§ 188 Abs. 2 BGB'


def calculate(start, amount, unit, start_type='event', state=None, shift=True):
    end, rule = raw_end(start, amount, unit, start_type)
    if not FIRST_YEAR <= end.year <= LAST_YEAR or not FIRST_YEAR <= start.year <= LAST_YEAR:
        raise ValueError('year_unsupported')
    skipped, final = [], end
    while shift:
        names = holidays(final.year, state)
        if final.weekday() >= 5:
            skipped.append({'date': final.isoformat(), 'reason': 'Samstag' if final.weekday() == 5 else 'Sonntag'})
        elif final in names:
            skipped.append({'date': final.isoformat(), 'reason': names[final]})
        else:
            break
        final += timedelta(days=1)
    first_day = start if start_type == 'day_start' else start + timedelta(days=1)
    return {
        'start': start.isoformat(), 'first_day': first_day.isoformat(), 'raw_end': end.isoformat(), 'end': final.isoformat(),
        'rule': rule, 'start_rule': '§ 187 Abs. 2 BGB' if start_type == 'day_start' else '§ 187 Abs. 1 BGB',
        'shifted': final != end, 'skipped': skipped, 'state': state, 'state_name': STATES.get(state, 'nur bundesweite Feiertage'),
        'scope': 'calculation_aid_not_legal_verification',
    }


class DeadlineInput(BaseModel):
    model_config = {'extra': 'forbid'}
    start_date: date
    amount: int = Field(ge=1, le=1000)
    unit: Literal['days', 'weeks', 'months', 'years']
    start_type: Literal['event', 'day_start'] = 'event'
    state: Literal['BW', 'BY', 'BE', 'BB', 'HB', 'HH', 'HE', 'MV', 'NI', 'NW', 'RP', 'SL', 'SN', 'ST', 'SH', 'TH'] | None = None
    shift_non_working_days: bool = True


def router(require_user):
    routes = APIRouter()

    @routes.post('/api/deadlines/calculate')
    def calculate_deadline(payload: DeadlineInput, user: dict = Depends(require_user)):
        try:
            return calculate(payload.start_date, payload.amount, payload.unit, payload.start_type, payload.state, payload.shift_non_working_days)
        except (ValueError, OverflowError):
            raise HTTPException(422, f'Supported years: {FIRST_YEAR}–{LAST_YEAR}') from None

    @routes.get('/api/deadlines/holidays')
    def list_holidays(year: int, state: str | None = None, user: dict = Depends(require_user)):
        if state is not None and state not in STATES:
            raise HTTPException(422, 'Unknown state')
        try:
            return [{'date': day.isoformat(), 'name': name} for day, name in sorted(holidays(year, state).items())]
        except ValueError:
            raise HTTPException(422, f'Supported years: {FIRST_YEAR}–{LAST_YEAR}') from None

    return routes
