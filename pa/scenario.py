"""Scenario serialization.

A scenario is a plain JSON file. That matters for three reasons: an instructor can
author one in a text editor, a jurisdiction can keep theirs out of this repository
entirely, and a scenario written for one disaster carries its own ruleset overrides
so it does not silently inherit another disaster's thresholds.
"""

from __future__ import annotations

import json
from dataclasses import asdict, fields, is_dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

from .models import (
    Applicant,
    CodeStandard,
    CostType,
    Disaster,
    DonatedResourceLine,
    EmployeeClass,
    EquipmentLine,
    LaborLine,
    MitigationProposal,
    Project,
    Scenario,
    SimpleCostLine,
    Site,
)
from .rules import (
    AppealRules,
    CodesAndStandardsRules,
    CostShare,
    Deadlines,
    DocumentationRules,
    EHPTriggers,
    InsuranceRules,
    ManagementCostRules,
    MitigationRules,
    RuleSet,
    Section428Rules,
    Thresholds,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCENARIO_DIR = DATA_DIR / "scenarios"


# -- helpers -------------------------------------------------------------------


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _parse_date(v: Any) -> date | None:
    if not v:
        return None
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


def _enum_value(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _dump(obj: Any) -> Any:
    """dataclass -> JSON-safe dict, converting dates and enums."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _dump(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, date):
        return obj.isoformat()
    if hasattr(obj, "value"):
        return obj.value
    if isinstance(obj, (list, tuple)):
        return [_dump(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _dump(v) for k, v in obj.items()}
    return obj


def _load_dc(cls, data: dict | None, date_fields: tuple[str, ...] = (), enums: dict | None = None):
    """Build a dataclass from a dict, ignoring unknown keys so old files still load."""
    if not data:
        return cls()
    known = {f.name for f in fields(cls)}
    kwargs = {k: v for k, v in data.items() if k in known}
    for df in date_fields:
        if df in kwargs:
            kwargs[df] = _parse_date(kwargs[df])
    for name, enum_cls in (enums or {}).items():
        if name in kwargs and kwargs[name] is not None:
            kwargs[name] = enum_cls(kwargs[name])
    return cls(**kwargs)


# -- rules -----------------------------------------------------------------


def _dump_rules(r: RuleSet) -> dict:
    return {
        "name": r.name,
        "policy_version": r.policy_version,
        "thresholds": asdict(r.thresholds),
        "cost_share": {"federal": r.cost_share.federal},
        "deadlines": asdict(r.deadlines),
        "mitigation": asdict(r.mitigation),
        "management": asdict(r.management),
        "documentation": asdict(r.documentation),
        "insurance": asdict(r.insurance),
        "section_428": asdict(r.section_428),
        "appeals": asdict(r.appeals),
        "spa_required_categories": list(r.spa_required_categories),
    }


def _load_rules(data: dict | None) -> RuleSet:
    if not data:
        return RuleSet()
    s428 = _load_dc(Section428Rules, data.get("section_428"))
    # asdict turns the tier tuples into lists; restore them so the ruleset stays
    # hashable and frozen-comparable.
    if isinstance(s428.debris_cost_share_tiers, list):
        s428 = replace(
            s428,
            debris_cost_share_tiers=tuple(
                tuple(t) for t in s428.debris_cost_share_tiers),
        )
    return RuleSet(
        name=data.get("name", RuleSet.name),
        policy_version=data.get("policy_version", RuleSet.policy_version),
        thresholds=_load_dc(Thresholds, data.get("thresholds")),
        cost_share=_load_dc(CostShare, data.get("cost_share")),
        deadlines=_load_dc(Deadlines, data.get("deadlines")),
        mitigation=_load_dc(MitigationRules, data.get("mitigation")),
        management=_load_dc(ManagementCostRules, data.get("management")),
        documentation=_load_dc(DocumentationRules, data.get("documentation")),
        insurance=_load_dc(InsuranceRules, data.get("insurance")),
        section_428=s428,
        codes_and_standards=CodesAndStandardsRules(),
        appeals=_load_dc(AppealRules, data.get("appeals")),
        ehp=EHPTriggers(),
        spa_required_categories=tuple(
            data.get("spa_required_categories", RuleSet.spa_required_categories)
        ),
    )


# -- projects --------------------------------------------------------------


def _load_project(data: dict) -> Project:
    p = _load_dc(
        Project,
        {k: v for k, v in data.items()
         if k not in ("labor", "equipment", "costs", "donated", "mitigation",
                      "codes_and_standards")},
        date_fields=("debris_completion_date",),
    )
    p.codes_and_standards = [
        _load_dc(CodeStandard, x) for x in data.get("codes_and_standards", [])
    ]
    p.labor = [
        _load_dc(LaborLine, x, date_fields=("work_date",),
                 enums={"employee_class": EmployeeClass})
        for x in data.get("labor", [])
    ]
    p.equipment = [_load_dc(EquipmentLine, x) for x in data.get("equipment", [])]
    p.costs = [
        _load_dc(SimpleCostLine, x, date_fields=("contract_date",),
                 enums={"cost_type": CostType})
        for x in data.get("costs", [])
    ]
    p.donated = [_load_dc(DonatedResourceLine, x) for x in data.get("donated", [])]
    p.mitigation = [_load_dc(MitigationProposal, x) for x in data.get("mitigation", [])]
    return p


# -- public API ------------------------------------------------------------


def scenario_to_dict(s: Scenario) -> dict:
    return {
        "schema": 1,
        "title": s.title,
        "description": s.description,
        "source_note": s.source_note,
        "applicant": asdict(s.applicant),
        "disaster": _dump(s.disaster),
        "rules": _dump_rules(s.rules),
        "sites": [_dump(x) for x in s.sites],
        "projects": [_dump(x) for x in s.projects],
    }


def scenario_from_dict(data: dict) -> Scenario:
    s = Scenario(
        title=data.get("title", "Untitled Scenario"),
        description=data.get("description", ""),
        source_note=data.get("source_note", ""),
        applicant=_load_dc(Applicant, data.get("applicant")),
        disaster=_load_dc(
            Disaster, data.get("disaster"),
            date_fields=("declaration_date", "incident_start", "incident_end",
                         "rsm_date", "designation_date", "rpa_submitted_date",
                         "exploratory_call_date"),
        ),
        rules=_load_rules(data.get("rules")),
    )
    s.sites = [
        _load_dc(Site, x, date_fields=("work_start_date",))
        for x in data.get("sites", [])
    ]
    s.projects = [_load_project(x) for x in data.get("projects", [])]
    return s


def save_scenario(s: Scenario, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scenario_to_dict(s), indent=2), encoding="utf-8")
    return path


def load_scenario(path: str | Path) -> Scenario:
    return scenario_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def list_scenarios() -> list[tuple[str, Path]]:
    """Every bundled scenario, as (title, path)."""
    out: list[tuple[str, Path]] = []
    if not SCENARIO_DIR.exists():
        return out
    for p in sorted(SCENARIO_DIR.glob("*.json")):
        try:
            title = json.loads(p.read_text(encoding="utf-8")).get("title", p.stem)
        except (json.JSONDecodeError, OSError):
            title = p.stem
        out.append((title, p))
    return out


def blank_scenario() -> Scenario:
    return Scenario(
        title="New Scenario",
        applicant=Applicant(),
        disaster=Disaster(),
        rules=RuleSet(),
    )
