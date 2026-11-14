"""The shape of `rules.yaml`: facts, rules, conditions and the texts built from them.

These models check the form of the file. What the rules may say to one another (declared facts, fixed
rules, verdicts) is checked in `tta.policy.validation`.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag, model_validator

from tta.contracts.common import ApproverRole, JsonDict, SubstitutionScope, Verdict
from tta.policy.text import unique

# {option.net_eur} is a fact; {reasons} and {roles} are filled in by the engine (decision sentences).
PLACEHOLDER = re.compile(r"\{([a-z_]+(?:\.[a-z_]+)?)\}")


class Op(StrEnum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS_ANY = "contains_any"
    IS_TRUE = "is_true"
    IS_FALSE = "is_false"
    NOT_EMPTY = "not_empty"
    IS_EMPTY = "is_empty"


UNARY_OPS = frozenset({Op.IS_TRUE, Op.IS_FALSE, Op.NOT_EMPTY, Op.IS_EMPTY})
NUMBER_OPS = frozenset({Op.GT, Op.GTE, Op.LT, Op.LTE})
TRUTH_OPS = frozenset({Op.IS_TRUE, Op.IS_FALSE})
LIST_FACT_OPS = frozenset({Op.NOT_EMPTY, Op.IS_EMPTY, Op.CONTAINS_ANY})
LIST_VALUE_OPS = frozenset({Op.IN, Op.NOT_IN, Op.CONTAINS_ANY})


class FactType(StrEnum):
    STRING = "string"
    BOOL = "bool"
    ENUM = "enum"
    LIST = "list"
    DATETIME = "datetime"
    MONEY = "money"  # prints with two decimals: 1,980.77
    LIMIT = "limit"  # money as it is set in a profile: 750
    RATIO = "ratio"  # prints as a percentage: 74.9%
    NUMBER = "number"


NUMBER_TYPES = frozenset({FactType.MONEY, FactType.LIMIT, FactType.RATIO, FactType.NUMBER})


class FactSource(StrEnum):
    PROFILE = "profile"
    OPTION = "option"
    CONTEXT = "context"
    ENGINE = "engine"


class Scope(StrEnum):
    LINE = "line"  # judged once for every line of the option
    ORDER = "order"  # judged once for the option as a whole


class Trigger(StrEnum):
    WHEN = "when"
    MISSING_FACT = "missing_fact"


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class FactSpec(_Strict):
    type: FactType
    source: FactSource
    label: str = Field(min_length=1)  # what a person calls it; used when the fact is missing
    values: tuple[str, ...] = ()
    note: str | None = None
    missing_role: ApproverRole | None = None  # who decides when it is missing


class FactRef(_Strict):
    """A condition's value that is another fact."""

    fact: str


Scalar = bool | int | float | str


class Condition(_Strict):
    fact: str
    op: Op
    value: FactRef | Scalar | tuple[Scalar, ...] | None = None

    @property
    def has_value(self) -> bool:
        return "value" in self.model_fields_set


def _node_kind(node: Any) -> str:
    if isinstance(node, dict):
        return "condition" if "fact" in node else "group"
    return "condition" if isinstance(node, Condition) else "group"


Node = Annotated[
    Annotated[Condition, Tag("condition")] | Annotated["When", Tag("group")],
    Discriminator(_node_kind),
]


class When(_Strict):
    """One group of conditions: every one must hold (`all`) or at least one (`any`). Groups nest."""

    all_of: tuple[Node, ...] = Field(default=(), alias="all")
    any_of: tuple[Node, ...] = Field(default=(), alias="any")

    @model_validator(mode="after")
    def _exactly_one_list(self) -> When:
        if bool(self.all_of) == bool(self.any_of):
            raise ValueError("a `when` group holds exactly one of `all` or `any`, with at least one condition")
        return self

    @property
    def nodes(self) -> tuple[Condition | When, ...]:
        return self.all_of or self.any_of


class AuthorityText(_Strict):
    """A plain-language text for GET /v1/authority, used when `when` holds for the profile."""

    when: When | None = None
    text: str = Field(min_length=1)


class RoleWhen(_Strict):
    """Another role for a rule's question, taken when `when` holds: the dietitian where the buyer names one."""

    when: When
    role: ApproverRole


class RuleSpec(_Strict):
    id: str = Field(min_length=1)
    fixed: bool  # True: holds for every buyer; no profile can switch it off
    title: str = Field(min_length=1)
    group: str | None = None  # the plain statement a fixed rule belongs to (`groups`); None for a profile rule
    scope: Scope | None = None
    trigger: Trigger = Trigger.WHEN
    when: When | None = None
    verdict: Verdict
    approver_role: ApproverRole | None = None
    # Who signs instead, by the first entry whose `when` holds. It changes who is asked, never whether a person is.
    approver_role_when: tuple[RoleWhen, ...] = ()
    message: str = Field(min_length=1)
    records: tuple[str, ...] = ()
    authority: tuple[AuthorityText, ...] = ()
    justification: str = Field(min_length=1)


class AccessRule(_Strict):
    """A fixed rule enforced where the caller's identity is known, not by the engine (F-06)."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    group: str | None = None
    enforced_by: str
    outcome: str
    text: str = Field(min_length=1)
    justification: str


class Defaults(_Strict):
    verdict_when_no_rule_fires: Verdict
    on_missing_fact: Verdict
    missing_fact_approver_role: ApproverRole


class RoleSpec(_Strict):
    name: str = Field(min_length=1)  # as it reads in a sentence: "the purchasing manager"
    decides: str


class AuthoritySection(_Strict):
    note: str = Field(min_length=1)
    summary: tuple[AuthorityText, ...]


class Rulebook(_Strict):
    policy_id: str
    version: str
    verdicts: tuple[Verdict, ...]
    defaults: Defaults
    roles: dict[ApproverRole, RoleSpec]
    substitution_scopes: dict[SubstitutionScope, tuple[str, ...]]
    groups: dict[str, str]  # the fixed rules as a few plain statements: key -> the statement a customer reads
    facts: dict[str, FactSpec]
    rules: tuple[RuleSpec, ...]
    access_rules: tuple[AccessRule, ...] = ()
    decision_sentences: dict[Verdict, str]
    authority: AuthoritySection

    @property
    def fixed_rule_ids(self) -> frozenset[str]:
        """Every rule no profile may touch: the fixed rules and the access rules."""
        fixed = {rule.id for rule in self.rules if rule.fixed}
        return frozenset(fixed | {rule.id for rule in self.access_rules})

    def canonical(self) -> JsonDict:
        """The form that is hashed: plain JSON values, independent of key order, comments and layout."""
        return self.model_dump(mode="json", by_alias=True)


When.model_rebuild()
Rulebook.model_rebuild()


def conditions_of(when: When) -> Iterator[Condition]:
    for node in when.nodes:
        if isinstance(node, Condition):
            yield node
        else:
            yield from conditions_of(node)


def facts_in_when(when: When | None) -> tuple[str, ...]:
    """Every fact a group reads, on either side of a condition."""
    if when is None:
        return ()
    names: list[str] = []
    for condition in conditions_of(when):
        names.append(condition.fact)
        if isinstance(condition.value, FactRef):
            names.append(condition.value.fact)
    return unique(names)


def placeholders(template: str) -> tuple[str, ...]:
    return unique(PLACEHOLDER.findall(template))


def facts_read_by(rule: RuleSpec) -> tuple[str, ...]:
    """The facts written to the decision when the rule fires: its conditions, its message, its records, and
    what decided who signs."""
    in_message = [name for name in placeholders(rule.message) if not name.startswith("missing.")]
    for_role = [name for entry in rule.approver_role_when for name in facts_in_when(entry.when)]
    return unique([*facts_in_when(rule.when), *in_message, *rule.records, *for_role])
