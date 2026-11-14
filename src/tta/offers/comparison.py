"""What an option offers besides its price: delivery dates, delivery reliability, carbon footprint and labels.

Task SUST-1, the brief's "Delivery time & sustainability comparison". Every figure is over the lines that have a
value, and the number of lines without one is stated: a missing value is unknown (AIMO/FINDINGS.md section 6).
The carbon figure is an estimate: the amount delivered (sales units times the pack size) times kg CO2e per kg
from the carbon footprint file, which is close to category-level (task SUST-1, measured over the whole file). A
litre is counted as a kilogram: our assumption, close for milk and plant drinks, not for every product.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from tta.availability.wording import format_amount, format_day
from tta.contracts.common import Preference, Unit
from tta.contracts.offer import OfferLine, OptionComparison
from tta.offers.wording import counted

CARBON_PLACES = 2
RELIABILITY_PERCENT_PLACES = 1
PERCENT = Decimal(100)
MEASURES = (Unit.L, Unit.KG)
LITRE_AS_KILOGRAM = ", a litre counted as a kilogram"


def compare(lines: Sequence[OfferLine]) -> OptionComparison:
    dates = [line.availability.available_date for line in lines if line.availability.available_date is not None]
    reliabilities = [line.delivery_reliability for line in lines if line.delivery_reliability is not None]
    carbon = [amount for amount in (carbon_of(line) for line in lines) if amount is not None]
    values = {
        "earliest_delivery": min(dates, default=None),
        "latest_delivery": max(dates, default=None),
        "delivery_unknown_lines": len(lines) - len(dates),
        "lowest_reliability": min(reliabilities, default=None),
        "reliability_unknown_lines": len(lines) - len(reliabilities),
        "carbon_kg_co2e": sum(carbon, Decimal(0)) if carbon else None,
        "carbon_unknown_lines": len(lines) - len(carbon),
        "labels_on_every_line": _on_every_line(lines),
    }
    draft = OptionComparison(**values, sentence="")
    litres = any(line.pack_size.unit is Unit.L and carbon_of(line) is not None for line in lines)
    return draft.model_copy(update={"sentence": _sentence(draft, len(lines), litres)})


def carbon_of(line: OfferLine) -> Decimal | None:
    """kg CO2e of what the line delivers; `None` when the footprint or the amount in kg or litres is not known."""
    per_kg, pack = line.carbon_kg_co2e_per_kg, line.pack_size
    if per_kg is None or not pack.is_known or pack.unit not in MEASURES or pack.value is None:
        return None
    return line.quantity * pack.value * per_kg


def _on_every_line(lines: Sequence[OfferLine]) -> tuple[str, ...]:
    if not lines:
        return ()
    return tuple(label for label in lines[0].labels if all(label in line.labels for line in lines[1:]))


def _sentence(comparison: OptionComparison, line_count: int, litres: bool) -> str:
    reliability = "Lowest delivery reliability" if comparison.lowest_reliability is not None else "Delivery reliability"
    return " ".join((
        _delivery(comparison), f"{reliability} {reliability_phrase(comparison)}.",
        f"Carbon footprint {carbon_phrase(comparison)}{LITRE_AS_KILOGRAM if litres else ''}.",
        _labels(comparison.labels_on_every_line, line_count),
    ))


def _labels(labels: tuple[str, ...], line_count: int) -> str:
    if labels:
        where = "" if line_count == 1 else " on every line"
        return f"Certificate labels{where}: {', '.join(labels)}."
    return "No certificate label stated." if line_count == 1 else "No certificate label is on every line."


def _delivery(comparison: OptionComparison) -> str:
    earliest, latest = comparison.earliest_delivery, comparison.latest_delivery
    unknown = comparison.delivery_unknown_lines
    if earliest is None or latest is None:
        return f"Delivery date unknown for {counted(unknown, 'line')}."
    when = f"on {format_day(earliest)}" if earliest == latest else (
        f"between {format_day(earliest)} and {format_day(latest)}"
    )
    rest = f", unknown for {counted(unknown, 'line')}" if unknown else ""
    return f"Delivery {when}{rest}."


def percent(ratio: Decimal) -> str:
    """`100%`, `96.7%`."""
    value = (ratio * PERCENT).quantize(Decimal(1).scaleb(-RELIABILITY_PERCENT_PLACES), rounding=ROUND_HALF_UP)
    return f"{format_amount(value.normalize())}%"


def reliability_phrase(comparison: OptionComparison) -> str:
    """`100%`, `96.7%, unknown for 1 line`, or `unknown for 2 lines`."""
    unknown = comparison.reliability_unknown_lines
    if comparison.lowest_reliability is None:
        return f"unknown for {counted(unknown, 'line')}"
    known = percent(comparison.lowest_reliability)
    return f"{known}, unknown for {counted(unknown, 'line')}" if unknown else known


def kilograms(value: Decimal) -> str:
    """`43.5`, `1,100`."""
    rounded = value.quantize(Decimal(1).scaleb(-CARBON_PLACES), rounding=ROUND_HALF_UP)
    return format_amount(rounded.normalize())


def carbon_phrase(comparison: OptionComparison) -> str:
    """`about 43.5 kg CO2e`, `about 12 kg CO2e, unknown for 1 line`, or `unknown for 2 lines`."""
    unknown = comparison.carbon_unknown_lines
    if comparison.carbon_kg_co2e is None:
        return f"unknown for {counted(unknown, 'line')}"
    known = f"about {kilograms(comparison.carbon_kg_co2e)} kg CO2e"
    return f"{known}, unknown for {counted(unknown, 'line')}" if unknown else known


def gain(prefer: Preference, preferred: OptionComparison, cheapest: OptionComparison) -> str:
    """What the preferred option gives for its higher price: `a delivery reliability of at least 100% instead
    of unknown`. Empty when the two read the same for the key."""
    if prefer is Preference.RELIABILITY:
        better, worse = _at_least(preferred), _at_least(cheapest)
        return f"a delivery reliability of {better} instead of {worse}" if better != worse else ""
    if prefer is Preference.EARLIEST:
        better, worse = _by(preferred), _by(cheapest)
        return f"delivery by {better} instead of {worse}" if better != worse else ""
    if prefer is Preference.LOWER_CARBON:
        better, worse = carbon_phrase(preferred), carbon_phrase(cheapest)
        return f"{better} instead of {worse}" if better != worse else ""
    return ""


def _at_least(comparison: OptionComparison) -> str:
    if comparison.lowest_reliability is None:
        return "unknown"
    return f"at least {reliability_phrase(comparison)}"


def _by(comparison: OptionComparison) -> str:
    latest = comparison.latest_delivery
    if latest is None:
        return "an unknown date"
    unknown = comparison.delivery_unknown_lines
    return f"{format_day(latest)}, unknown for {counted(unknown, 'line')}" if unknown else format_day(latest)
