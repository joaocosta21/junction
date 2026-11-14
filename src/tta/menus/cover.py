"""What one option of a menu's offer covers, said per ingredient (lane FIX-M, review row C3-F8).

Scores on the 30% "working end-to-end demo" (scenario 7, the chocolate cake) and the 20% "how precisely the agent
matches what the buyer actually asked for". An option that leaves an ingredient out carried the policy's sentence
alone: "the needed-by date ... is not met" when nothing was late, and "only 0% of the quantity of request line 2 is
covered" when four of seven ingredients were covered in full. Here the same facts are said as a baker reads them:
how many ingredients the option covers in full, which it does not and why (no confirmed stock, not in the recording,
cannot arrive in time), and what another option does about them. An ingredient is named by what it is, never by a
line number or product ids.

Nothing here chooses a product, changes an offer or decides: the verdict, the rules that fired and who must sign are
the policy's, read from the option's decision. Two of its sentences are replaced by the count above, and only for an
option with a gap that a person must confirm: the fill rule's, and the date rule's for the option as a whole when
every product the option holds arrives in time. Every other rule keeps its sentence, word for word.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from tta.availability.wording import format_day
from tta.contracts.common import ApproverRole, AvailabilityState, ClaimName, ClaimStatus, ExclusionReason, Verdict
from tta.contracts.offer import Offer, OfferLine, OfferOption
from tta.contracts.policy import FiredRule
from tta.menus.earliest import arrives_after
from tta.menus.needs import Need
from tta.menus.wording import (
    LATE_REASONS,
    choice_words,
    exclusion_words,
    joined,
    only_missing_from_recording,
    type_words,
)

ZERO, WHOLE = Decimal(0), Decimal(1)
PERCENT = Decimal(100)
# The two rules whose sentences the count replaces (`tta.policy`, rules.yaml): the minimum fill, and the needed-by
# date judged for the option as a whole (the same rule judged per line carries a product id and is never replaced).
FILL_RULE, DATE_RULE = "P-03", "F-07"
NO_STOCK_REASONS = frozenset({ExclusionReason.QUANTITY_NOT_CONFIRMED, ExclusionReason.OUT_OF_STOCK})
# A product that has a delivery day and cannot make the day asked. With one on the line, "no confirmed stock"
# is said of what can still arrive: such a product may well have stock.
MISSES_THE_DAY = frozenset({ExclusionReason.CUTOFF_PASSED, ExclusionReason.LATE_FOR_NEEDED_BY})
IN_TIME_ONLY = " that can arrive by {day}"
ROLE_WORDS: Mapping[ApproverRole, str] = {
    ApproverRole.PURCHASING_MANAGER: "the purchasing manager",
    ApproverRole.DIETITIAN: "the dietitian",
    ApproverRole.FINANCE: "finance",
}
IN_FULL = "{count} of the {total} ingredients {are} covered in full: {names}."
NONE_IN_FULL = "None of the {total} ingredients is covered in full."
IN_PART = "Covered in part: {names}."
ELSEWHERE = "; option {rank} offers {them}."
ELSEWHERE_UNCONFIRMED = "; option {rank} offers {them} with a quantity Valio Aimo has not confirmed."
ELSEWHERE_LATER = "; option {rank} offers {them} for {day}."
NOWHERE = ": no option offers {them}."
IN_TIME = "What this option holds arrives by {day}."
NOT_COMPLETE = "An order that is not complete goes to a person."
NEEDS = "It needs {roles}."


class Why(StrEnum):
    """Why an option holds nothing for an ingredient."""

    NO_CONFIRMED_STOCK = "NO_CONFIRMED_STOCK"
    NOT_RECORDED = "NOT_RECORDED"
    TOO_LATE = "TOO_LATE"
    NOT_OFFERED = "NOT_OFFERED"


# Of several ingredients ("{names} {have} ..."), and of one inside its own sentence ("it ...").
OF_THEM: Mapping[Why, str] = {
    Why.NO_CONFIRMED_STOCK: "{names} {have} no confirmed stock{detail}, so {they} {are} not in this option",
    Why.NOT_RECORDED: (
        "{names} {are} not in this demo's recording of Valio Aimo's data, so no price or stock is known for {them}"
    ),
    Why.TOO_LATE: "{names} cannot arrive by {day}, so {they} {are} not in this option",
    Why.NOT_OFFERED: "{names} {are} not in this option{detail}",
}
OF_IT: Mapping[Why, str] = {
    Why.NO_CONFIRMED_STOCK: "it has no confirmed stock{detail}",
    Why.NOT_RECORDED: "it is not in this demo's recording of Valio Aimo's data",
    Why.TOO_LATE: "it cannot arrive by {day}",
    Why.NOT_OFFERED: "no product of it is in that option",
}


@dataclass(frozen=True)
class Gap:
    """One ingredient an option holds nothing for: why, and the other option that offers it, if one does."""

    name: str
    why: Why
    elsewhere: int | None = None  # the rank of the first other option that holds a product for it
    later: date | None = None  # the day that option's products arrive, when it is after the day asked
    # What narrows the reason: " that can arrive by Monday 16 Nov" after "no confirmed stock", or the reasons the
    # products dropped out when none of the three reasons above says it.
    detail: str = ""

    @property
    def group(self) -> tuple[Why, int | None, date | None, str]:
        return self.why, self.elsewhere, self.later, self.detail


@dataclass(frozen=True)
class Cover:
    """What one option covers of the menu's lines, each named as an ingredient."""

    total: int
    full: tuple[str, ...] = ()
    part: tuple[tuple[str, Decimal], ...] = ()  # (the ingredient, the share covered)
    gaps: tuple[Gap, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.part and not self.gaps


def line_names(needs: Sequence[Need]) -> tuple[str, ...]:
    """`flour`, `cocoa powder`: each line by its product type; with the words of its name (`cream (whipping)`) only
    when two lines of the menu share a type."""
    types = Counter(need.choice.product_type for need in needs)
    return tuple(
        type_words(need.choice.product_type) if types[need.choice.product_type] == 1 else choice_words(need.choice)
        for need in needs
    )


def _lines(option: OfferOption, index: int) -> list[OfferLine]:
    return [line for line in option.lines if line.request_line_index == index]


def _fill(option: OfferOption, index: int) -> Decimal:
    return next((entry.fill_ratio for entry in option.coverage if entry.request_line_index == index), ZERO)


def gap_of(offer: Offer, option: OfferOption, index: int, name: str, needed_by: date | None) -> Gap:
    """Why `option` holds nothing for request line `index`, read from the offer: another option's products for it,
    else the reasons its candidates dropped out."""
    other = next((each for each in offer.options if each.option_id != option.option_id and _lines(each, index)), None)
    excluded = [item for item in offer.excluded if item.request_line_index == index]
    reasons = {item.reason for item in excluded}
    if other is not None:
        lines = _lines(other, index)
        later = arrives_after(lines, needed_by)
        if later is not None:
            return Gap(name, Why.TOO_LATE, other.rank, later)
        if not any(line.availability.state is AvailabilityState.QUANTITY_NOT_CONFIRMED for line in lines):
            return Gap(name, Why.NOT_OFFERED, other.rank)
        in_time_only = needed_by is not None and bool(reasons & MISSES_THE_DAY)
        detail = IN_TIME_ONLY.format(day=format_day(needed_by)) if in_time_only else ""
        return Gap(name, Why.NO_CONFIRMED_STOCK, other.rank, detail=detail)
    if only_missing_from_recording(excluded):
        return Gap(name, Why.NOT_RECORDED)
    if needed_by is not None and reasons and reasons <= set(LATE_REASONS):
        return Gap(name, Why.TOO_LATE)
    if reasons and reasons <= NO_STOCK_REASONS:
        return Gap(name, Why.NO_CONFIRMED_STOCK)
    return Gap(name, Why.NOT_OFFERED, detail=f" ({exclusion_words(excluded)})" if excluded else "")


def cover_of(offer: Offer, option: OfferOption, names: Sequence[str], needed_by: date | None) -> Cover:
    """What `option` covers of the offer's request lines, each under its name in `names`."""
    full: list[str] = []
    part: list[tuple[str, Decimal]] = []
    gaps: list[Gap] = []
    for index, name in enumerate(names):
        fill = _fill(option, index)
        if fill >= WHOLE:
            full.append(name)
        elif fill > ZERO:
            part.append((name, fill))
        else:
            gaps.append(gap_of(offer, option, index, name, needed_by))
    return Cover(total=len(names), full=tuple(full), part=tuple(part), gaps=tuple(gaps))


def share_words(fill: Decimal) -> str:
    """`83%`, rounded down: a share short of the whole never reads as 100%."""
    return f"{int(fill * PERCENT)}%"


def why_words(gap: Gap, needed_by: date | None) -> str:
    """`it has no confirmed stock`: the reason of one ingredient, for its own sentence."""
    day = format_day(needed_by) if needed_by is not None else "the day asked"
    return OF_IT[gap.why].format(day=day, detail=gap.detail)


def _gap_words(gaps: Sequence[Gap], needed_by: date | None) -> str:
    """One sentence for the ingredients that share a reason and the option that offers them."""
    first, many = gaps[0], len(gaps) > 1
    names = joined([gap.name for gap in gaps])
    words = {
        "names": names[0].upper() + names[1:], "have": "have" if many else "has", "are": "are" if many else "is",
        "they": "they" if many else "it", "them": "them" if many else "it", "detail": first.detail,
        "day": format_day(needed_by) if needed_by is not None else "the day asked",
    }
    said = OF_THEM[first.why].format(**words)
    if first.elsewhere is None:
        return said + NOWHERE.format(them=words["them"])
    if first.later is not None:
        return said + ELSEWHERE_LATER.format(rank=first.elsewhere, them=words["them"], day=format_day(first.later))
    tail = ELSEWHERE_UNCONFIRMED if first.why is Why.NO_CONFIRMED_STOCK else ELSEWHERE
    return said + tail.format(rank=first.elsewhere, them=words["them"])


def cover_words(cover: Cover, needed_by: date | None) -> str:
    """`4 of the 7 ingredients are covered in full: ... Sugar, eggs and butter have no confirmed stock, so ...`.
    Empty for an option that covers every ingredient in full."""
    if cover.complete:
        return ""
    said: list[str] = []
    if cover.total > 1:
        are = "is" if len(cover.full) == 1 else "are"
        counted = IN_FULL.format(count=len(cover.full), total=cover.total, are=are, names=joined(cover.full))
        said.append(counted if cover.full else NONE_IN_FULL.format(total=cover.total))
    if cover.part:
        said.append(IN_PART.format(names=joined([f"{name} ({share_words(fill)})" for name, fill in cover.part])))
    groups: dict[tuple[Why, int | None, date | None, str], list[Gap]] = {}
    for gap in cover.gaps:
        groups.setdefault(gap.group, []).append(gap)
    said.extend(_gap_words(group, needed_by) for group in groups.values())
    return " ".join(said)


def _in_time(option: OfferOption, needed_by: date) -> bool:
    """Every product the option holds states a delivery day, Valio Aimo's data confirms it, and it is in time."""
    for line in option.lines:
        statuses = [check.status for check in line.claims if check.claim is ClaimName.DELIVERY_DATE]
        day = line.availability.available_date
        if not statuses or any(status is not ClaimStatus.CONFIRMED for status in statuses):
            return False
        if day is None or day > needed_by:
            return False
    return True


def decision_words(option: OfferOption, cover: Cover, needed_by: date | None) -> str:
    """Who must confirm the option and why. The policy's own sentence, unless the option has a gap that a person
    must confirm: then the count already says what the fill rule and the date rule for the whole option say, and
    every other rule that fired keeps its own sentence."""
    decision = option.decision
    if decision is None:
        return ""
    if cover.complete or decision.verdict is not Verdict.APPROVAL:
        return decision.sentence
    on_time = needed_by is not None and bool(cover.gaps) and _in_time(option, needed_by)

    def counted(rule: FiredRule) -> bool:
        return rule.rule_id == FILL_RULE or (rule.rule_id == DATE_RULE and rule.product_id is None and on_time)

    asking = [rule for rule in decision.fired if rule.verdict is Verdict.APPROVAL]
    replaced = [rule for rule in asking if counted(rule)]
    if not replaced:
        return decision.sentence
    dated = needed_by is not None and any(rule.rule_id == DATE_RULE for rule in replaced)
    said = [IN_TIME.format(day=format_day(needed_by))] if dated else []
    said.append(NOT_COMPLETE)
    said.extend(dict.fromkeys(rule.sentence for rule in asking if not counted(rule)))
    if decision.required_roles:
        roles = [ROLE_WORDS.get(role, role.value.replace("_", " ")) for role in decision.required_roles]
        said.append(NEEDS.format(roles=joined(roles)))
    return " ".join(said)
