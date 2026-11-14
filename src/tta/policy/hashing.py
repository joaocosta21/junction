"""The policy hash: SHA-256 of the canonical rules plus the profile in force.

Canonical form as in Gabriela's `AIMO/policy/policy_check.py`: JSON with sorted keys and no spaces, so
comments, layout and key order do not change the hash and any change of content does.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from tta.contracts.common import JsonDict
from tta.contracts.policy import BuyerProfile

HASH_PREFIX = "sha256:"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def policy_hash(canonical_rules: JsonDict, profile: BuyerProfile) -> str:
    """Money and ratios of the profile enter as JSON numbers, so 750 and 750.00 hash alike."""
    payload = {"rules": canonical_rules, "profile": profile.model_dump(mode="json")}
    return HASH_PREFIX + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
