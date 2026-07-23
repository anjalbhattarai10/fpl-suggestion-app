from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from ai_engine import add_phase3_scores

DEFAULT_WEIGHTS = {
    "form": 30.0,
    "fixtures": 20.0,
    "minutes": 15.0,
    "availability": 15.0,
    "value": 10.0,
    "team_impact": 10.0,
}


def percentile_score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if numeric.notna().sum() <= 1:
        return pd.Series(50.0, index=series.index)
    ranks = numeric.rank(pct=True, method="average") * 100.0
    if not higher_is_better:
        ranks = 100.0 - ranks
    return ranks.fillna(0.0).clip(0, 100)


def _normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
    clean = {key: max(float(weights.get(key, 0.0)), 0.0) for key in DEFAULT_WEIGHTS}
    total = sum(clean.values())
    if total <= 0:
        return {key: 1.0 / len(clean) for key in clean}
    return {key: value / total for key, value in clean.items()}


def build_scores(players: pd.DataFrame, weights: Dict[str, float], lookback: int) -> pd.DataFrame:
    df = players.copy()
    for col in [
        "recent_points", "recent_minutes", "recent_starts", "recent_goals", "recent_assists",
        "recent_xg", "recent_xa", "recent_xgi", "matches_seen", "fixture_score_raw",
        "team_attack_raw", "team_defence_raw", "price", "total_points", "season_minutes",
        "transfers_in_event", "transfers_out_event", "cost_change_event", "chance",
    ]:
        if col not in df:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # During preseason or before recent live data exists, the API's form field is a useful fallback.
    no_recent = df["matches_seen"] <= 0
    df["recent_points_per_match"] = np.where(
        df["matches_seen"] > 0,
        df["recent_points"] / df["matches_seen"].replace(0, np.nan),
        df.get("form_api", 0.0),
    )
    df["recent_xgi_per90"] = np.where(
        df["recent_minutes"] > 0,
        df["recent_xgi"] * 90.0 / df["recent_minutes"].replace(0, np.nan),
        0.0,
    )

    # FORM: 70% recent FPL points rate + 30% expected goal involvement per 90.
    df["form_score"] = (
        0.70 * percentile_score(df["recent_points_per_match"])
        + 0.30 * percentile_score(df["recent_xgi_per90"])
    ).clip(0, 100)

    # FIXTURES: already mapped from FDR to 0..100 in fpl_data.py.
    df["fixtures_score"] = df["fixture_score_raw"].fillna(0).clip(0, 100)

    # MINUTES/ROTATION: recent minutes capacity and starts. A player with 90 minutes
    # and one start per observed match approaches 100.
    observed = df["matches_seen"].replace(0, max(1, lookback))
    minute_ratio = (df["recent_minutes"] / (90.0 * observed)).clip(0, 1)
    start_ratio = (df["recent_starts"] / observed).clip(0, 1)
    season_nailing = (df["season_minutes"] / max(1.0, df["season_minutes"].max())).clip(0, 1)
    df["minutes_score"] = (55 * minute_ratio + 30 * start_ratio + 15 * season_nailing).clip(0, 100)
    df.loc[no_recent, "minutes_score"] = percentile_score(df.loc[no_recent, "season_minutes"]) if no_recent.any() else df.loc[no_recent, "minutes_score"]

    # AVAILABILITY: official chance plus status/news penalties. A second source can
    # flag disagreement but does not silently override official FPL data.
    status_factor = df.get("status", "a").map({"a": 1.0, "d": 0.75, "i": 0.25, "s": 0.0, "u": 0.0, "n": 0.0}).fillna(0.6)
    news_penalty = np.where(df.get("news", "").astype(str).str.strip().ne(""), 8.0, 0.0)
    disagreement_penalty = np.where(df.get("injury_source_disagreement", False), 8.0, 0.0)
    df["availability_score"] = (df["chance"].clip(0, 100) * status_factor - news_penalty - disagreement_penalty).clip(0, 100)

    # VALUE: current points per million plus short-term transfer/price momentum.
    df["points_per_million"] = df["total_points"] / df["price"].replace(0, np.nan)
    net_transfers = df["transfers_in_event"] - df["transfers_out_event"]
    df["value_score"] = (
        0.75 * percentile_score(df["points_per_million"])
        + 0.15 * percentile_score(net_transfers)
        + 0.10 * percentile_score(df["cost_change_event"])
    ).clip(0, 100)

    # TEAM IMPACT: attackers use team attack strength and share of team xGI; GK/DEF
    # use defence strength and clean-sheet involvement. This is a proxy because the
    # official API does not publish live betting clean-sheet odds.
    team_xgi = df.groupby("team")["expected_goal_involvements"].transform("sum").replace(0, np.nan)
    xgi_share = (df["expected_goal_involvements"] / team_xgi).fillna(0)
    team_points = df.groupby("team")["total_points"].transform("sum").replace(0, np.nan)
    points_share = (df["total_points"] / team_points).fillna(0)
    attack_component = 0.55 * percentile_score(df["team_attack_raw"]) + 0.45 * percentile_score(xgi_share)
    defence_component = 0.55 * percentile_score(df["team_defence_raw"]) + 0.45 * percentile_score(points_share)
    df["team_impact_score"] = np.where(df["position"].isin(["GK", "DEF"]), defence_component, attack_component)
    df["team_impact_score"] = pd.Series(df["team_impact_score"], index=df.index).clip(0, 100)

    normalized = _normalize_weights(weights)
    df["suggestion_score"] = (
        normalized["form"] * df["form_score"]
        + normalized["fixtures"] * df["fixtures_score"]
        + normalized["minutes"] * df["minutes_score"]
        + normalized["availability"] * df["availability_score"]
        + normalized["value"] * df["value_score"]
        + normalized["team_impact"] * df["team_impact_score"]
    ).clip(0, 100)

    df = add_phase3_scores(df)
    return df.sort_values(["suggestion_score", "total_points"], ascending=[False, False]).reset_index(drop=True)
