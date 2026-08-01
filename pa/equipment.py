"""FEMA Schedule of Equipment Rates.

Rates cover ownership and operation of APPLICANT-OWNED equipment in good mechanical
condition: depreciation, overhead, maintenance, field repairs, fuel, lubricants,
tires, and OSHA equipment. Two things they do not cover, and both are common errors:

  * Operator labor. That is claimed separately as force account labor.
  * Standby time. Equipment must be in actual operation performing eligible work.

Rented equipment is not billed at these rates -- it is billed at the invoice amount,
and the applicant must be able to show a rent-versus-buy analysis if the rental runs
long (PAPPG p.87).

Reference: 44 CFR 206.228. The bundled schedule applies to disasters declared on or
after July 26, 2023.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RATES_CSV = Path(__file__).resolve().parent.parent / "data" / "equipment_rates_2025.csv"


@dataclass(frozen=True)
class EquipmentRate:
    cost_code: str
    equipment: str
    manufacturer: str
    specification: str
    capacity: str
    hp: str
    notes: str
    unit: str
    rate: float

    @property
    def label(self) -> str:
        bits = [self.equipment]
        detail = self.capacity or self.specification or self.manufacturer
        if detail:
            bits.append(detail)
        return " — ".join(bits) + f"  (${self.rate:,.2f}/{self.unit.lower()})"

    @property
    def search_text(self) -> str:
        return " ".join((
            self.cost_code, self.equipment, self.manufacturer,
            self.specification, self.capacity, self.notes,
        )).lower()


def _clean(value: str) -> str:
    """Normalize text carried over from the source workbook.

    The published schedule contains U+FFFD where a separator or degree sign was lost
    upstream, which renders as a replacement box. Substitute a space and collapse
    rather than guess at the original glyph -- these are free-text specification
    fields, and the cost code and rate are what actually drive the claim.
    """
    return re.sub(r"\s+", " ", (value or "").replace("�", " ")).strip()


@lru_cache(maxsize=1)
def load_rates() -> tuple[EquipmentRate, ...]:
    if not RATES_CSV.exists():
        return ()
    with RATES_CSV.open(newline="", encoding="utf-8") as f:
        return tuple(
            EquipmentRate(
                cost_code=_clean(row["cost_code"]),
                equipment=_clean(row["equipment"]),
                manufacturer=_clean(row["manufacturer"]),
                specification=_clean(row["specification"]),
                capacity=_clean(row["capacity"]),
                hp=_clean(row["hp"]),
                notes=_clean(row["notes"]),
                unit=_clean(row["unit"]) or "Hour",
                rate=float(row["rate"]),
            )
            for row in csv.DictReader(f)
        )


def search(query: str, limit: int = 40) -> list[EquipmentRate]:
    """Rank by all-terms-match, preferring hits in the equipment name."""
    rates = load_rates()
    q = (query or "").strip().lower()
    if not q:
        return list(rates[:limit])
    terms = q.split()

    scored: list[tuple[int, EquipmentRate]] = []
    for r in rates:
        hay = r.search_text
        if not all(t in hay for t in terms):
            continue
        score = 0
        name = r.equipment.lower()
        if name.startswith(terms[0]):
            score -= 2
        if all(t in name for t in terms):
            score -= 1
        scored.append((score, r))

    scored.sort(key=lambda sr: (sr[0], sr[1].equipment, sr[1].rate))
    return [r for _, r in scored[:limit]]


def by_cost_code(code: str) -> EquipmentRate | None:
    return next((r for r in load_rates() if r.cost_code == str(code).strip()), None)


def equipment_families() -> list[str]:
    """Distinct equipment names, for a picker."""
    return sorted({r.equipment for r in load_rates()})


def is_equipment_not_supply(unit_cost: float, useful_life_years: float,
                            capitalization_level: float,
                            statutory_floor: float = 10_000.0) -> tuple[bool, str]:
    """The equipment-vs-supply test (PAPPG p.87, 2 CFR 200.1).

    Equipment has a useful life of more than one year AND a per-unit acquisition cost
    at or above the LESSER of the applicant's own capitalization level and $10,000.
    Anything else is a supply, which matters at disposition: unused supplies under
    $10,000 in the aggregate are not deducted on small projects.
    """
    threshold = min(capitalization_level, statutory_floor)
    if useful_life_years <= 1:
        return False, (
            f"Useful life of {useful_life_years:g} year(s) does not exceed one year — "
            "this is a SUPPLY, not equipment."
        )
    if unit_cost < threshold:
        return False, (
            f"Per-unit cost ${unit_cost:,.2f} is below the ${threshold:,.2f} threshold "
            f"(the lesser of the applicant's ${capitalization_level:,.2f} "
            f"capitalization level and the ${statutory_floor:,.2f} statutory figure) — "
            "this is a SUPPLY."
        )
    return True, (
        f"Useful life exceeds one year and per-unit cost ${unit_cost:,.2f} meets the "
        f"${threshold:,.2f} threshold — this is EQUIPMENT. On a large project, if it "
        f"is no longer needed and its fair market value is ${statutory_floor:,.0f} or "
        "more at the work completion deadline, the applicant must compensate FEMA."
    )
