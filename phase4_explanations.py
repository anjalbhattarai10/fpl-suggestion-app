from __future__ import annotations

"""
Plain-language explanation helpers for Phase 4.

The squad engine calculates facts and scores. This module converts those facts
into manager-friendly explanations. Keeping language generation separate avoids
mixing presentation text with optimization rules.
"""

from typing import List

import pandas as pd

from squad_engine import SquadRatings


def squad_summary(ratings: SquadRatings) -> str:
    """
    Produce one concise dashboard summary from the eight squad ratings.
    """
    strengths: List[str] = []
    concerns: List[str] = []

    if ratings.starting_xi >= 75:
        strengths.append("a strong starting XI")
    if ratings.captaincy >= 75:
        strengths.append("high-quality captaincy")
    if ratings.fixtures >= 70:
        strengths.append("a favorable fixture outlook")
    if ratings.bench >= 65:
        strengths.append("useful bench depth")
    if ratings.value >= 70:
        strengths.append("efficient budget value")

    if ratings.availability < 65:
        concerns.append("availability")
    if ratings.bench < 50:
        concerns.append("bench depth")
    if ratings.captaincy < 55:
        concerns.append("captaincy")
    if ratings.fixtures < 50:
        concerns.append("upcoming fixtures")
    if ratings.risk >= 55:
        concerns.append("overall player risk")

    strength_text = ", ".join(strengths) if strengths else "a balanced profile"
    concern_text = ", ".join(concerns) if concerns else "no major structural warning"

    return (
        f"The squad rates {ratings.overall:.1f}/100 and offers {strength_text}. "
        f"The main review area is {concern_text}."
    )


def wildcard_summary(squad: pd.DataFrame, notes: List[str], budget: float) -> str:
    """
    Explain the generated wildcard squad and any optimizer limitations.
    """
    if squad.empty:
        return "The optimizer could not produce a squad with the selected settings."

    cost = float(pd.to_numeric(squad["price"], errors="coerce").fillna(0).sum())
    score = float(
        pd.to_numeric(squad["suggestion_score"], errors="coerce").fillna(0).mean()
    )
    bank = max(0.0, budget - cost)

    message = (
        f"The generated squad costs £{cost:.1f}m, leaves £{bank:.1f}m in the bank, "
        f"and has an average player recommendation score of {score:.1f}/100."
    )

    if notes:
        message += " Review note: " + " ".join(notes[:2])

    return message


def starting_xi_summary(
    starters: pd.DataFrame,
    bench: pd.DataFrame,
    formation: str,
) -> str:
    """
    Explain why the selected formation was chosen.
    """
    if starters.empty:
        return "A legal starting XI could not be created from the selected players."

    starter_score = float(
        pd.to_numeric(starters["suggestion_score"], errors="coerce").fillna(0).mean()
    )
    bench_score = float(
        pd.to_numeric(bench["suggestion_score"], errors="coerce").fillna(0).mean()
    ) if not bench.empty else 0.0

    return (
        f"The model selected a {formation} formation. The starting XI averages "
        f"{starter_score:.1f}/100, compared with {bench_score:.1f}/100 for the bench."
    )


def budget_warnings(budget_table: pd.DataFrame) -> List[str]:
    """
    Create strategic budget warnings from the position allocation table.
    """
    warnings: List[str] = []

    if budget_table.empty:
        return warnings

    spend = budget_table.set_index("Position")["Spend"].to_dict()

    if float(spend.get("GK", 0)) > 10.5:
        warnings.append("Goalkeeper spending is relatively high.")
    if float(spend.get("DEF", 0)) > 30.0:
        warnings.append("A large share of budget is committed to defenders.")
    if float(spend.get("MID", 0)) < 32.0:
        warnings.append("Midfield investment may be light.")
    if float(spend.get("FWD", 0)) < 20.0:
        warnings.append("Forward investment may limit premium attacking options.")
    if float(spend.get("BANK", 0)) > 3.0:
        warnings.append("More than £3.0m remains unused in the bank.")

    if not warnings:
        warnings.append("Budget distribution is reasonably balanced.")

    return warnings
