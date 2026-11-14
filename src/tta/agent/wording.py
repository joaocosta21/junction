"""Words for a preference, a certificate label, a claim and a strictness: one table for the text check and the
rule-based reader (task FALLBACK-1).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for": the model's `prefer` and
`required_labels` pass only when the text has a word for them (`tta.agent.textcheck`), and the rule-based reader
(`tta.agent.rules_reader`) reads them from the same words, so its reading always passes the same check. The tables
are short and ours; a phrase they do not know never makes a reading pass.
- preferences: "as soon as possible", "earliest" (EARLIEST); "most reliable" (RELIABILITY); "lowest carbon",
  "lower emissions", "carbon footprint" (LOWER_CARBON); "cheapest", "lowest price" (PRICE, the default);
- certificate labels: the 16 `packagingMarkedLabel` ids of the catalog that are certificates
  (AIMO/docs/PRODUCT-DATA.md section 3.5), by their common names: "organic", "MSC", "Fairtrade" and the others;
- claims: "lactose-free" and "gluten-free" only, with their Finnish and Swedish words. A claim is never an allergen
  exclusion (AIMO/docs/SCHEMA-AND-CODES.md section 2.4);
- strictness: "strict" (STRICT) and "declared only" (DECLARED_ONLY).
Every pattern runs on the casefolded text.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence

from tta.contracts.common import AllergenStrictness, Preference

Span = tuple[int, int]

_PREFERENCES: Sequence[tuple[Preference, re.Pattern[str]]] = (
    (Preference.EARLIEST, re.compile(
        r"\bas soon as possible\b|\basap\b|\bearliest\b|\bsoonest\b|\bfastest\b|\bquickest\b"
        r"|\bmahdollisimman pian\b|\bsnarast\b"
    )),
    (Preference.RELIABILITY, re.compile(r"\breliab(?:le|ly|ility)\b|\bluotettav|\bpålitlig")),
    (Preference.LOWER_CARBON, re.compile(
        r"\b(?:low|lower|lowest|least|smallest)[\s-]+(?:carbon|co2|emissions?|climate impact)\b"
        r"|\bcarbon footprint\b|\bhiilijalanjälj|\bklimatavtryck"
    )),
    (Preference.PRICE, re.compile(r"\bcheap(?:est|er)?\b|\b(?:lowest|best|low) (?:price|cost)\b|\bhalvin|\bbilligast")),
)

# The certificate ids of `packagingMarkedLabel`, in the order of AIMO/docs/PRODUCT-DATA.md section 3.5. The three
# temperature ids (warmTemperature, coolTemperature, freezeTemperature) are not certificates and are left out.
_LABELS: Sequence[tuple[str, re.Pattern[str]]] = (
    ("GOODS_FROM_FINLAND_BLUE_SWAN", re.compile(r"\bblue swan\b|\bgoods from finland\b|\bhyvää suomesta\b")),
    ("MADE_IN_FINLAND_FLAG_WITH_KEY", re.compile(r"\bkey flag\b|\bavainlippu|\bmade in finland\b")),
    ("FINNISH_HEART_SYMBOL", re.compile(r"\bheart symbol\b|\bsydänmerk")),
    ("EU_ORGANIC_FARMING", re.compile(r"\borganic\b|\bluomu|\bekologisk")),
    ("SVANEN", re.compile(r"\bsvanen\b|\bnordic swan\b|\bjoutsenmerk")),
    ("RAINFOREST_ALLIANCE", re.compile(r"\brainforest alliance\b")),
    ("EU_ECO_LABEL", re.compile(r"\beu eco[\s-]?label\b|\beu flower\b")),
    ("MARINE_STEWARDSHIP_COUNCIL_LABEL", re.compile(r"\bmsc\b|\bmarine stewardship\b")),
    ("FAIR_TRADE_MARK", re.compile(r"\bfair[\s-]?trade\b|\breilun? kaup")),
    ("AQUACULTURE_STEWARDSHIP_COUNCIL", re.compile(r"\basc\b|\baquaculture stewardship\b")),
    ("KRAV_MARK", re.compile(r"\bkrav\b")),
    ("OFFICIAL_ECO_LABEL_SUN", re.compile(r"\bsun (?:eco[\s-]?)?label\b")),
    ("SOIL_ASSOCIATION_ORGANIC_SYMBOL", re.compile(r"\bsoil association\b")),
    ("PUHTAASTI_KOTIMAINEN", re.compile(r"\bpuhtaasti kotimainen\b")),
    ("DOLPHIN_SAFE", re.compile(r"\bdolphin[\s-]safe\b")),
    ("UTZ_CERTIFIED", re.compile(r"\butz\b")),
)
LABEL_CODES: tuple[str, ...] = tuple(code for code, _ in _LABELS)

_CLAIMS: Sequence[tuple[str, re.Pattern[str]]] = (
    ("FREE_FROM_LACTOSE", re.compile(r"\blactose[\s-]*free\b|\blaktoositon|\blaktoosittom|\blaktosfri")),
    ("FREE_FROM_GLUTEN", re.compile(r"\bgluten[\s-]*free\b|\bgluteeniton|\bgluteenittom|\bglutenfri")),
)

_STRICTNESS: Sequence[tuple[AllergenStrictness, re.Pattern[str]]] = (
    (AllergenStrictness.STRICT, re.compile(r"\bstrict(?:ly)?\b")),
    (AllergenStrictness.DECLARED_ONLY, re.compile(r"\bdeclared(?: allergens)? only\b|\bonly declared\b")),
)

# A substitute for a product is not that product (the model's rule 3): only a model reads such a request.
SUBSTITUTE = re.compile(r"\bsubstitut|\breplacement|\binstead\b|\balternative|\bkorvik|\bvastike|\bersättning")


def _found[T](table: Sequence[tuple[T, re.Pattern[str]]], folded: str) -> Iterator[tuple[T, Span]]:
    for value, pattern in table:
        for match in pattern.finditer(folded):
            yield value, match.span()


def preferences_in(folded: str) -> list[tuple[Preference, Span]]:
    """Each preference the text names, with where it stands."""
    return list(_found(_PREFERENCES, folded))


def labels_in(folded: str) -> list[tuple[str, Span]]:
    """Each certificate label the text names, as its catalog id, with where it stands."""
    return list(_found(_LABELS, folded))


def claims_in(folded: str) -> list[tuple[str, Span]]:
    """Each claim the text names ("lactose-free", "gluten-free"), as its nutritionalClaim id."""
    return list(_found(_CLAIMS, folded))


def strictness_in(folded: str) -> list[tuple[AllergenStrictness, Span]]:
    """Each strictness the text names, with where it stands."""
    return list(_found(_STRICTNESS, folded))
