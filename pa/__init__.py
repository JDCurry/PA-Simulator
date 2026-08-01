"""Public Assistance reimbursement engine.

A disaster-agnostic implementation of the FEMA PA project formulation, cost
buildup, eligibility, and closeout rules. The UI in ``ui/`` is one consumer of
this package; the engine has no Streamlit dependency and can be driven from a
script, a notebook, or a test.
"""

from .costing import CostSummary, ScenarioTotals, summarize_project, summarize_scenario
from .formulation import auto_group, classify, review_grouping
from .models import (
    Applicant,
    Disaster,
    DonatedResourceLine,
    EquipmentLine,
    LaborLine,
    MitigationProposal,
    Project,
    Scenario,
    SimpleCostLine,
    Site,
)
from .rules import CATEGORIES, DEFAULT_RULES, RuleSet
from .scenario import load_scenario, save_scenario, scenario_from_dict, scenario_to_dict
from .scoring import score
from .validation import review

__version__ = "0.1.0"

__all__ = [
    "Applicant", "Disaster", "Site", "Project", "Scenario",
    "LaborLine", "EquipmentLine", "SimpleCostLine", "DonatedResourceLine",
    "MitigationProposal",
    "RuleSet", "CATEGORIES", "DEFAULT_RULES",
    "summarize_project", "summarize_scenario", "CostSummary", "ScenarioTotals",
    "auto_group", "classify", "review_grouping",
    "review", "score",
    "load_scenario", "save_scenario", "scenario_to_dict", "scenario_from_dict",
]
