from __future__ import annotations

from typing import List

import pandas as pd

from ai_engine import scout_verdict


def _num(row: pd.Series, column: str, default: float = 0.0) -> float:
    value = row.get(column, default)
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _ownership_label(ownership: float) -> str:
    if ownership < 5:
        return "ultra-differential"
    if ownership < 10:
        return "differential"
    if ownership < 25:
        return "moderately owned"
    if ownership < 40:
        return "popular"
    return "highly owned"


def recommendation_tag(row: pd.Series) -> str:
    """Return a short, player-specific recommendation category."""
    ownership = _num(row, "selected_by_percent")
    net_transfers = _num(row, "net_transfers_event")
    form = _num(row, "form_api")
    value = _num(row, "value_score")
    fixtures = _num(row, "fixtures_score")
    minutes = _num(row, "minutes_score")
    xgi = _num(row, "expected_goal_involvements")
    chance = _num(row, "chance", 100)

    if chance < 75:
        return "High-risk pick"
    if ownership < 10 and (form >= 4 or xgi >= 3 or value >= 70):
        return "Differential target"
    if net_transfers >= 50_000:
        return "Trending transfer"
    if fixtures >= 70:
        return "Fixture-led pick"
    if value >= 75:
        return "Value pick"
    if minutes >= 80:
        return "Safe starter"
    return "Balanced option"


def why_player(row: pd.Series) -> str:
    """Create a concise, player-specific explanation from official FPL data."""

    name = str(row.get("web_name", "This player"))
    position = str(row.get("position", ""))
    price = _num(row, "price")
    score = _num(row, "suggestion_score")
    ownership = _num(row, "selected_by_percent")
    transfers_in = _num(row, "transfers_in_event")
    transfers_out = _num(row, "transfers_out_event")
    net_transfers = _num(
        row,
        "net_transfers_event",
        transfers_in - transfers_out,
    )
    form_api = _num(row, "form_api")
    total_points = _num(row, "total_points")
    season_minutes = _num(row, "season_minutes")
    expected_goals = _num(row, "expected_goals")
    expected_assists = _num(row, "expected_assists")
    expected_xgi = _num(row, "expected_goal_involvements")
    ict = _num(row, "ict_index")
    threat = _num(row, "threat")
    creativity = _num(row, "creativity")
    avg_fdr = _num(row, "avg_fdr", 3.0)
    fixtures_score = _num(row, "fixtures_score")
    minutes_score = _num(row, "minutes_score")
    value_score = _num(row, "value_score")
    chance = _num(row, "chance", 100.0)
    news = str(row.get("news", "")).strip()
    opponents = str(row.get("next_opponents", "")).strip()

    reasons: List[str] = []

    # Use the most meaningful available performance signal.
    if form_api >= 6:
        reasons.append(f"excellent official form of {form_api:.1f}")
    elif form_api >= 4:
        reasons.append(f"solid official form of {form_api:.1f}")
    elif total_points >= 150:
        reasons.append(f"elite season output of {total_points:.0f} points")
    elif total_points >= 90:
        reasons.append(f"reliable season output of {total_points:.0f} points")

    # Position-aware underlying data.
    if position in {"MID", "FWD"}:
        if expected_xgi >= 8:
            reasons.append(f"strong attacking involvement with {expected_xgi:.1f} xGI")
        elif expected_goals >= 5:
            reasons.append(f"goal threat backed by {expected_goals:.1f} xG")
        elif expected_assists >= 4:
            reasons.append(f"creative upside backed by {expected_assists:.1f} xA")
        elif threat >= 500:
            reasons.append(f"high attacking threat score of {threat:.0f}")
        elif creativity >= 500:
            reasons.append(f"strong creativity score of {creativity:.0f}")
    else:
        if season_minutes >= 2500:
            reasons.append(f"very secure role with {season_minutes:.0f} season minutes")
        elif minutes_score >= 80:
            reasons.append("strong playing-time security")
        elif ict >= 100:
            reasons.append(f"solid all-round ICT index of {ict:.1f}")

    # Fixtures only when they are clearly informative.
    if avg_fdr <= 2.5 or fixtures_score >= 70:
        reasons.append(f"favorable upcoming schedule (average FDR {avg_fdr:.1f})")
    elif avg_fdr >= 3.5:
        reasons.append(f"more difficult upcoming schedule (average FDR {avg_fdr:.1f})")

    # Ownership and manager behavior.
    ownership_profile = _ownership_label(ownership)
    if ownership < 10 and score >= 60:
        reasons.append(f"{ownership_profile} appeal at {ownership:.1f}% ownership")
    elif ownership >= 40:
        reasons.append(f"strong manager backing at {ownership:.1f}% ownership")
    elif ownership > 0:
        reasons.append(f"{ownership_profile} ownership of {ownership:.1f}%")

    if net_transfers >= 100_000:
        reasons.append(f"rapidly rising demand with {net_transfers:+,.0f} net transfers")
    elif net_transfers >= 20_000:
        reasons.append(f"positive manager momentum ({net_transfers:+,.0f} net transfers)")
    elif net_transfers <= -100_000:
        reasons.append(f"heavy selling pressure ({net_transfers:+,.0f} net transfers)")
    elif net_transfers <= -20_000:
        reasons.append(f"negative manager momentum ({net_transfers:+,.0f} net transfers)")

    if value_score >= 75:
        reasons.append(f"excellent value at £{price:.1f}m")

    # Avoid generic fallback based on 100% availability.
    if not reasons:
        reasons.append(
            f"a balanced model score of {score:.1f} at £{price:.1f}m"
        )

    cautions: List[str] = []
    if chance < 100:
        cautions.append(f"official availability is {chance:.0f}%")
    if news:
        cautions.append("there is an active official FPL news flag")
    if minutes_score < 45 and season_minutes < 1000:
        cautions.append("minutes and rotation security are weaker")
    if net_transfers <= -50_000:
        cautions.append("manager sentiment is currently negative")
    if avg_fdr >= 3.5:
        cautions.append("fixtures are relatively difficult")

    tag = recommendation_tag(row)
    explanation = f"{tag}: {name} offers " + ", ".join(reasons[:4]) + "."

    if cautions:
        explanation += " Watch-out: " + "; ".join(cautions[:2]) + "."

    if opponents:
        explanation += f" Next: {opponents}."

    return explanation



def ai_scout_explanation(row: pd.Series) -> str:
    """
    Convert the structured AI Scout verdict into a concise display sentence.

    Keeping this formatter in explanations.py preserves the existing separation:
    ai_engine.py decides, while explanations.py turns decisions into text.
    """
    verdict = scout_verdict(row)
    strengths = "; ".join(verdict.strengths)
    risks = "; ".join(verdict.risks)
    return (
        f"{verdict.headline}. {verdict.summary} "
        f"Strengths: {strengths}. Risks: {risks}."
    )
