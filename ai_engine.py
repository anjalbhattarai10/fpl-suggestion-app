from __future__ import annotations

"""
Phase 3 AI Scout engine.

This module does not call a paid language model. Instead, it creates explainable,
data-driven recommendations from the official FPL data already loaded by the app.

The purpose of keeping this logic in a separate file is to make Phase 3 easy to
test, maintain, and later connect to an external AI provider without changing the
rest of the application.
"""

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ScoutVerdict:
    """Structured recommendation returned by the AI Scout engine."""

    action: str
    confidence: float
    headline: str
    summary: str
    strengths: List[str]
    risks: List[str]


def _num(row: pd.Series, column: str, default: float = 0.0) -> float:
    """Safely convert a DataFrame value to float."""
    value = row.get(column, default)
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _bounded(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Clamp a numeric value to a safe range."""
    return max(low, min(high, float(value)))


def add_phase3_scores(players: pd.DataFrame) -> pd.DataFrame:
    """
    Add Phase 3 decision scores to the scored player DataFrame.

    New columns:
    - captain_score: identifies high-upside captain choices.
    - differential_score: rewards strong low-owned players.
    - risk_score: higher means greater injury, rotation or fixture risk.
    - ai_confidence: confidence in the recommendation based on data agreement.
    - price_momentum_score: estimates current transfer/price pressure.
    - fixture_swing_score: highlights strong upcoming fixture schedules.

    All scores use a 0-100 scale. They are model indicators, not guaranteed
    future FPL points.
    """
    df = players.copy()

    required = [
        "suggestion_score",
        "form_score",
        "fixtures_score",
        "minutes_score",
        "availability_score",
        "value_score",
        "team_impact_score",
        "selected_by_percent",
        "net_transfers_event",
        "chance",
        "avg_fdr",
        "recent_xgi",
        "form_api",
    ]
    for column in required:
        if column not in df.columns:
            df[column] = 0.0
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)

    # Captaincy emphasizes immediate upside, reliable minutes and availability.
    df["captain_score"] = (
        0.32 * df["form_score"]
        + 0.25 * df["fixtures_score"]
        + 0.18 * df["minutes_score"]
        + 0.15 * df["team_impact_score"]
        + 0.10 * df["availability_score"]
    ).clip(0, 100)

    # Goalkeepers and defenders can still rank, but captaincy normally rewards
    # attacking positions. The adjustment is modest rather than an exclusion.
    position_adjustment = df.get("position", "").map(
        {"GK": -8.0, "DEF": -4.0, "MID": 3.0, "FWD": 4.0}
    ).fillna(0.0)
    df["captain_score"] = (df["captain_score"] + position_adjustment).clip(0, 100)

    # Differential score balances quality with low ownership.
    ownership_opportunity = (100.0 - (df["selected_by_percent"] * 2.5)).clip(0, 100)
    df["differential_score"] = (
        0.30 * df["suggestion_score"]
        + 0.25 * df["form_score"]
        + 0.20 * df["fixtures_score"]
        + 0.15 * df["value_score"]
        + 0.10 * ownership_opportunity
    ).clip(0, 100)

    # Risk is intentionally higher when availability, minutes or fixtures are poor.
    availability_risk = 100.0 - df["availability_score"]
    minutes_risk = 100.0 - df["minutes_score"]
    fixture_risk = 100.0 - df["fixtures_score"]
    sentiment_risk = np.where(df["net_transfers_event"] < 0, 60.0, 20.0)

    df["risk_score"] = (
        0.40 * availability_risk
        + 0.30 * minutes_risk
        + 0.20 * fixture_risk
        + 0.10 * sentiment_risk
    ).clip(0, 100)

    # Confidence is high when the main model factors agree and risk is low.
    factor_columns = [
        "form_score",
        "fixtures_score",
        "minutes_score",
        "availability_score",
        "value_score",
        "team_impact_score",
    ]
    factor_std = df[factor_columns].std(axis=1).fillna(0.0)
    agreement = (100.0 - factor_std).clip(0, 100)
    df["ai_confidence"] = (
        0.45 * df["suggestion_score"]
        + 0.35 * agreement
        + 0.20 * (100.0 - df["risk_score"])
    ).clip(0, 100)

    # Transfer momentum is converted to a relative percentile so the scale adapts
    # automatically to the current gameweek.
    momentum_rank = df["net_transfers_event"].rank(pct=True, method="average") * 100.0
    df["price_momentum_score"] = (
        0.65 * momentum_rank
        + 0.20 * df["form_score"]
        + 0.15 * df["value_score"]
    ).clip(0, 100)

    # Fixture swing focuses on fixture quality and compares it with current form.
    df["fixture_swing_score"] = (
        0.70 * df["fixtures_score"]
        + 0.20 * df["team_impact_score"]
        + 0.10 * df["form_score"]
    ).clip(0, 100)

    return df.sort_values(
        ["suggestion_score", "ai_confidence"],
        ascending=[False, False],
    ).reset_index(drop=True)


def scout_verdict(player: pd.Series) -> ScoutVerdict:
    """
    Produce a human-readable Buy/Hold/Avoid verdict for one player.

    The verdict is deterministic and fully explainable. This makes it suitable
    for an academic or portfolio project because every recommendation can be
    traced back to visible data.
    """
    score = _num(player, "suggestion_score")
    confidence = _num(player, "ai_confidence")
    risk = _num(player, "risk_score")
    form = _num(player, "form_score")
    fixtures = _num(player, "fixtures_score")
    minutes = _num(player, "minutes_score")
    availability = _num(player, "availability_score")
    value = _num(player, "value_score")
    ownership = _num(player, "selected_by_percent")
    momentum = _num(player, "net_transfers_event")
    name = str(player.get("web_name", "This player"))

    if score >= 72 and risk <= 35:
        action = "BUY"
    elif score >= 58 and risk <= 55:
        action = "HOLD / CONSIDER"
    elif risk >= 65 or availability < 50:
        action = "AVOID"
    else:
        action = "WATCH"

    strengths: List[str] = []
    risks: List[str] = []

    if form >= 70:
        strengths.append("Strong recent form")
    if fixtures >= 70:
        strengths.append("Favorable upcoming fixtures")
    if minutes >= 75:
        strengths.append("Secure playing-time profile")
    if availability >= 90:
        strengths.append("Strong availability")
    if value >= 70:
        strengths.append("Good value for price")
    if ownership < 10 and score >= 60:
        strengths.append("Useful differential potential")
    if momentum > 25_000:
        strengths.append("Positive transfer momentum")

    if availability < 75:
        risks.append("Availability concern")
    if minutes < 55:
        risks.append("Rotation or minutes risk")
    if fixtures < 45:
        risks.append("Difficult fixture schedule")
    if momentum < -25_000:
        risks.append("Negative manager sentiment")
    if ownership > 45:
        risks.append("Limited differential upside")

    if not strengths:
        strengths.append("Balanced overall profile")
    if not risks:
        risks.append("No major model warning")

    headline = f"{action}: {name}"
    summary = (
        f"{name} has an overall model score of {score:.1f}/100, "
        f"AI confidence of {confidence:.0f}%, and risk score of {risk:.0f}/100."
    )

    return ScoutVerdict(
        action=action,
        confidence=_bounded(confidence),
        headline=headline,
        summary=summary,
        strengths=strengths[:4],
        risks=risks[:3],
    )


def captain_picks(players: pd.DataFrame, limit: int = 5) -> pd.DataFrame:
    """Return the strongest captain choices from available players."""
    available = players[
        (players["availability_score"] >= 65)
        & (players["minutes_score"] >= 55)
    ].copy()
    return available.sort_values(
        ["captain_score", "form_score", "fixtures_score"],
        ascending=False,
    ).head(limit)


def differential_picks(
    players: pd.DataFrame,
    ownership_limit: float = 10.0,
    limit: int = 10,
) -> pd.DataFrame:
    """Return high-quality players below the selected ownership threshold."""
    differentials = players[
        (players["selected_by_percent"] <= ownership_limit)
        & (players["availability_score"] >= 65)
        & (players["minutes_score"] >= 45)
    ].copy()
    return differentials.sort_values(
        ["differential_score", "suggestion_score"],
        ascending=False,
    ).head(limit)


def price_watch(players: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    """Return players with the strongest current price-rise pressure."""
    return players.sort_values(
        ["price_momentum_score", "net_transfers_event"],
        ascending=False,
    ).head(limit)


def fixture_swing_picks(players: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    """Return players whose upcoming schedule looks most attractive."""
    return players.sort_values(
        ["fixture_swing_score", "fixtures_score"],
        ascending=False,
    ).head(limit)
