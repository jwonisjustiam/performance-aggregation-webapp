"""Shared SKU extraction and matching helpers."""

from __future__ import annotations

import re
from typing import Iterable


SKU_PATTERN = re.compile(
    r"(?<![A-Z0-9])((?:SM|EP|GP|FP|EF|ET|EB|EI)-[A-Z0-9]{4,})(?![A-Z0-9])",
    flags=re.IGNORECASE,
)


def normalize_sku(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "")).upper()


def extract_sku_code(*values: object) -> str:
    """Return the first Samsung-style SKU embedded in the supplied values."""
    for value in values:
        match = SKU_PATTERN.search(str(value or ""))
        if match:
            return normalize_sku(match.group(1))
    return ""


def sku_matches_any(value: object, allowed_skus: Iterable[object]) -> bool:
    """Match exact SKUs and shortened model codes such as SM-L350N."""
    sku = normalize_sku(value)
    if not sku:
        return False
    sku_family = sku.split("-", 1)[0]
    for candidate_value in allowed_skus:
        candidate = normalize_sku(candidate_value)
        if not candidate or candidate.split("-", 1)[0] != sku_family:
            continue
        if sku == candidate:
            return True
        if len(sku) >= 7 and len(candidate) >= 7 and (
            candidate.startswith(sku) or sku.startswith(candidate)
        ):
            return True
    return False
