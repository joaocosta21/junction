"""The parser's own calendar rule: which date a buyer's text names (task FIX-9).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for": the model's `needed_by`
must be the date this rule gives, and a recorded `needed_by` is re-resolved with it on another day.

- "Today" is the date in Europe/Helsinki, where the buyers and the supplier are (the Valio `timeNow` is Helsinki
  time, AIMO/docs/API.md section 6.1), whatever the offset of the clock's reading.
- A weekday is the first such day after today: "by Monday" on Monday is the Monday after. "Next Monday" is the
  same day as "Monday" (the instruction the model is given says the same).
- Finnish and Swedish weekday names in any form, and the Finnish short forms ma, ti, ke, pe and su (task T18).
- "today", "tomorrow", "the day after tomorrow", and their Finnish and Swedish words; an explicit date:
  2026-11-20, 20.11. or 20.11.2026, 20/11/2026, 20 November or November 20th. A date without a year is the
  next such date from today, unless it passed less than 180 days ago: "10.11." said on 14 November is four days
  past, not next year's (replan A2b H1; the limit is ours). "Yesterday" is the day before today, so it is refused
  as past and never dropped.
- A day-shaped wording that is no date ("31 February", "31.2.") is named by `impossible_dates`, and "next Friday"
  said in the week that still holds a Friday by `next_weekday_in_doubt` (this Friday or the one after?), so the
  rule-based reader asks instead of reading the request as undated or guessing (review finding S4). `named_dates`
  itself is unchanged: a model's `needed_by` is held to it as before.
- English short weekdays ("by Mon", "before Thu") only right after "by", "before", "until", "till", "on" or
  "next": "sun", "sat" and "wed" are also everyday words (review finding P1).
- "Before Friday" is the day before at the latest, Thursday: a delivery on the Friday itself would not be before
  it. "By Friday" stays Friday (review finding P7, decided 14 Nov 2026). `before_days` names the wordings, so the
  reading can say it.
- A decimal (1.5) or a fraction (1/2) is never read as a date: a dotted date needs its closing dot or a year,
  a date with a slash needs a year.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta, timezone, tzinfo
from functools import cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

HELSINKI = "Europe/Helsinki"
# Finland keeps the EU rule: UTC+2, and UTC+3 from 01:00 UTC on the last Sunday of March to 01:00 UTC on the
# last Sunday of October. Used only when the machine has no time zone database.
WINTER_OFFSET, SUMMER_OFFSET = timedelta(hours=2), timedelta(hours=3)
SWITCH_HOUR_UTC = 1
MARCH, OCTOBER, LAST_DAY = 3, 10, 31
SUNDAY = 6
DAYS_IN_A_WEEK = 7
RECENTLY_PAST_DAYS = 180  # a date without a year that passed within this many days is past, not next year (ours)

_WEEKDAYS_EN_SHORT = {"mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3, "thurs": 3, "fri": 4, "sat": 5,
                      "sun": 6}
_BEFORE_A_SHORT_WEEKDAY = frozenset({"by", "before", "until", "till", "on", "next"})
_BEFORE = re.compile(r"\bbefore\s+(?:(?:the|next)\s+)?$")
_WEEKDAYS_EN = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
# Finnish and Swedish weekday names, matched at the start of a word: "maanantaina" (on Monday), "maanantaiksi"
# (by Monday), "maanantaihin" (by Monday), "måndagen" (task T18).
_WEEKDAYS_FI = ("maanantai", "tiistai", "keskiviikko", "torstai", "perjantai", "lauantai", "sunnuntai")
_WEEKDAYS_SV = ("måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag")
# The Finnish short forms a kitchen writes on a list ("Maito 1000 l — ma"), as whole words. "to" (Thursday) and
# "la" (Saturday) are left out: they are also English and French words ("allergic to", "à la carte").
_WEEKDAYS_FI_SHORT = {"ma": 0, "ti": 1, "ke": 2, "pe": 4, "su": 6}
_MONTHS_EN = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
              "november", "december")
_MONTHS_FI = ("tammikuu", "helmikuu", "maaliskuu", "huhtikuu", "toukokuu", "kesäkuu", "heinäkuu", "elokuu",
              "syyskuu", "lokakuu", "marraskuu", "joulukuu")
_MONTHS_SV = ("januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober",
              "november", "december")
_RELATIVE = (  # longest first: "the day after tomorrow" is not "tomorrow"
    (re.compile(r"\bday after tomorrow\b|\bylihuomen|\bi\s?övermorgon\b"), 2),
    (re.compile(r"\btomorrow\b|\bhuomen|\bhuomis|\bi\s?morgon\b"), 1),
    (re.compile(r"\btoday\b|\btänään\b|\bi\s?dag\b"), 0),
    (re.compile(r"\byesterday\b|\beilen\b|\bi\s?går\b"), -1),
)
_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_DOTTED = re.compile(r"(?<![\d.,])(\d{1,2})\.(\d{1,2})\.(\d{4})?(?![\d,]|\.\d)")
_SLASHED = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4})(?![\d/])")
_MONTH_WORD = r"([a-zäöå]{3,})"
_DAY_MONTH = re.compile(r"(?<![\d.,])(\d{1,2})(?:st|nd|rd|th)?\.?\s+(?:of\s+)?" + _MONTH_WORD + r"(?:\s+(\d{4}))?")
_MONTH_DAY = re.compile(_MONTH_WORD + r"\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s+(\d{4}))?")
_WORD = re.compile(r"[^\W\d_]+")
Span = tuple[int, int]
_NEXT_WEEKDAY = re.compile(r"\b(?:next|ensi|nästa)\s+([^\W\d_]+)")


@cache
def helsinki_zone() -> tzinfo | None:
    """The Helsinki time zone, or `None` on a machine without a time zone database."""
    try:
        return ZoneInfo(HELSINKI)
    except ZoneInfoNotFoundError:
        return None


def _last_sunday(year: int, month: int) -> date:
    last = date(year, month, LAST_DAY)
    return last - timedelta(days=(last.weekday() - SUNDAY) % DAYS_IN_A_WEEK)


def eu_helsinki_offset(instant: datetime) -> timedelta:
    """Helsinki's offset from UTC at this instant by the EU rule."""
    utc = instant.astimezone(UTC)
    start, end = (datetime.combine(_last_sunday(utc.year, month), datetime.min.time(), UTC)
                  + timedelta(hours=SWITCH_HOUR_UTC) for month in (MARCH, OCTOBER))
    return SUMMER_OFFSET if start <= utc < end else WINTER_OFFSET


def helsinki_date(instant: datetime) -> date:
    """The date in Helsinki at this instant. Raises `ValueError` for a time with no offset."""
    if instant.utcoffset() is None:
        raise ValueError("a date in Helsinki needs a time with an offset, not a naive one")
    zone = helsinki_zone() or timezone(eu_helsinki_offset(instant))
    return instant.astimezone(zone).date()


def _month(word: str) -> int | None:
    """1 to 12 for an English month name or its first three letters, a Finnish month name in any form, or a
    Swedish month name."""
    for number, name in enumerate(_MONTHS_EN, start=1):
        if word == name or (len(word) == len("nov") and name.startswith(word)):
            return number
    if word in _MONTHS_SV:
        return _MONTHS_SV.index(word) + 1
    return next((number for number, name in enumerate(_MONTHS_FI, start=1) if word.startswith(name)), None)


def _dated(day: int, month: int, year: str | None, today: date) -> date | None:
    """The date, or `None` when there is no such date. Without a year, the next such date from today."""
    try:
        if year is not None:
            return date(int(year), month, day)
        this_year = date(today.year, month, day)
        if this_year >= today or (today - this_year).days < RECENTLY_PAST_DAYS:
            return this_year
        return date(today.year + 1, month, day)
    except ValueError:  # 31 February and the like
        return None


def _explicit(folded: str, today: date) -> list[tuple[Span, date | None]]:
    """Where each wording shaped like a date stands, with its date; `None` when there is no such date."""
    found = [(match.span(), _dated(int(match[3]), int(match[2]), match[1], today)) for match in _ISO.finditer(folded)]
    for pattern in (_DOTTED, _SLASHED):
        found += [(match.span(), _dated(int(match[1]), int(match[2]), match[3] or None, today))
                  for match in pattern.finditer(folded)]
    for pattern, day, word in ((_DAY_MONTH, 1, 2), (_MONTH_DAY, 2, 1)):
        for match in pattern.finditer(folded):
            month = _month(match[word])
            if month is not None:
                found.append((match.span(), _dated(int(match[day]), month, match[3] or None, today)))
    return found


def impossible_dates(text: str, today: date) -> tuple[str, ...]:
    """Each wording shaped like a date that is no date, as written: "31 february", "31.2."."""
    folded = text.casefold()
    return tuple(" ".join(folded[start:end].split()) for (start, end), day in _explicit(folded, today) if day is None)


def next_weekday_in_doubt(text: str, today: date) -> tuple[str, date, date] | None:
    """"Next Friday" said while this week still holds a Friday: the words, that Friday and the one after. `None`
    when the text says no "next" before a weekday, or the first such day is already in the week after."""
    for match in _NEXT_WEEKDAY.finditer(text.casefold()):
        weekday = _weekday(match[1])
        if weekday is None:
            continue
        first = today + timedelta(days=(weekday - today.weekday() - 1) % DAYS_IN_A_WEEK + 1)
        if first.isocalendar()[:2] == today.isocalendar()[:2]:
            return " ".join(match.group().split()), first, first + timedelta(days=DAYS_IN_A_WEEK)
    return None


def _weekday(word: str) -> int | None:
    """0 for Monday to 6 for Sunday: an English name, a Finnish or Swedish name in any form, a Finnish short form."""
    if word in _WEEKDAYS_EN:
        return _WEEKDAYS_EN.index(word)
    if word in _WEEKDAYS_FI_SHORT:
        return _WEEKDAYS_FI_SHORT[word]
    for names in (_WEEKDAYS_FI, _WEEKDAYS_SV):
        weekday = next((number for number, name in enumerate(names) if word.startswith(name)), None)
        if weekday is not None:
            return weekday
    return None


def _weekday_dates(folded: str, today: date) -> list[tuple[Span, date]]:
    found = []
    before = ""
    for match in _WORD.finditer(folded):
        word = match.group()
        weekday = _weekday(word)
        if weekday is None and before in _BEFORE_A_SHORT_WEEKDAY:
            weekday = _WEEKDAYS_EN_SHORT.get(word)
        if weekday is not None:
            ahead = (weekday - today.weekday() - 1) % DAYS_IN_A_WEEK + 1  # 1 to 7: always after today
            found.append((match.span(), today + timedelta(days=ahead)))
        before = word
    return found


def _relative_dates(folded: str, today: date) -> list[tuple[Span, date]]:
    found = []
    for pattern, ahead in _RELATIVE:
        match = pattern.search(folded)
        if match is not None:
            found.append((match.span(), today + timedelta(days=ahead)))
            folded = pattern.sub(lambda said: " " * len(said.group()), folded)  # the places stay where they are
    return found


def _days(folded: str, today: date) -> list[tuple[Span, date, bool]]:
    """Each day the text names: where, the date it is needed by, and whether "before" stands right before it
    (the date is then the day before the one named)."""
    named = [*_relative_dates(folded, today), *_weekday_dates(folded, today),
             *((span, day) for span, day in _explicit(folded, today) if day is not None)]
    found = []
    for span, day in named:
        before = _BEFORE.search(folded[:span[0]]) is not None
        found.append((span, day - timedelta(days=1) if before else day, before))
    return found


def before_days(text: str, today: date) -> tuple[tuple[str, date], ...]:
    """Each "before <day>" of the text as written, with the day the goods are then needed by: the day before."""
    folded = text.casefold()
    said = []
    for (start, end), day, before in sorted(_days(folded, today)):
        if before:
            words = folded[folded.rindex("before", 0, start):end]
            said.append((" ".join(words.split()), day))
    return tuple(said)


def date_spans(folded: str) -> tuple[tuple[int, int], ...]:
    """Where an explicit date stands in the casefolded text (2026-11-20, 20.11., 20/11/2026, 20 November), so the
    rule-based reader does not take its digits for a quantity (task FALLBACK-1)."""
    spans = [match.span() for pattern in (_ISO, _DOTTED, _SLASHED) for match in pattern.finditer(folded)]
    spans += [match.span() for match in _DAY_MONTH.finditer(folded) if _month(match.group(2)) is not None]
    spans += [match.span() for match in _MONTH_DAY.finditer(folded) if _month(match.group(1)) is not None]
    return tuple(sorted(spans))


def day_spans(text: str, today: date) -> tuple[Span, ...]:
    """Where each day the text names stands: a weekday, "tomorrow", a date."""
    return tuple(sorted(span for span, _, _ in _days(text.casefold(), today)))


def is_month(word: str) -> bool:
    """True for a month name the calendar rule knows ("November", "nov", "marraskuuta")."""
    return _month(word.casefold()) is not None


def named_dates(text: str, today: date) -> tuple[date, ...]:
    """Every date the text names, by the rule above, each once and in date order. Empty when it names none."""
    return tuple(sorted({day for _, day, _ in _days(text.casefold(), today)}))
