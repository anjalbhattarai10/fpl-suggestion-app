from __future__ import annotations

"""
Phase 4 squad analysis engine.

This module contains the rules and calculations used when the application moves
from recommending one player at a time to evaluating a complete FPL squad.

Why this file exists
--------------------
Keeping squad logic outside app.py gives the project a cleaner architecture:

* app.py controls Streamlit widgets and presentation.
* scoring.py scores individual players.
* ai_engine.py adds Phase 3 player-level intelligence.
* squad_engine.py validates and evaluates groups of players.

This separation makes the code easier to test and prevents the Streamlit page
from becoming responsible for business rules.
"""

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import pandas as pd


# Official 15-player FPL squad structure.
REQUIRED_POSITION_COUNTS: Dict[str, int] = {
    "GK": 2,
    "DEF": 5,
    "MID": 5,
    "FWD": 3,
}

# Legal starting formations. Every formation contains one goalkeeper and ten
# outfield players. The values describe DEF-MID-FWD counts.
LEGAL_FORMATIONS: Tuple[Tuple[int, int, int], ...] = (
    (3, 4, 3),
    (3, 5, 2),
    (4, 3, 3),
    (4, 4, 2),
    (4, 5, 1),
    (5, 2, 3),
    (5, 3, 2),
    (5, 4, 1),
)


@dataclass(frozen=True)
class SquadValidation:
    """Structured result returned by validate_squad()."""

    is_valid: bool
    errors: List[str]
    warnings: List[str]


@dataclass(frozen=True)
class SquadRatings:
    """High-level squad ratings shown in the Team Center dashboard."""

    overall: float
    starting_xi: float
    bench: float
    captaincy: float
    fixtures: float
    availability: float
    value: float
    risk: float


def _numeric(series: pd.Series, default: float = 0.0) -> pd.Series:
    """Return a safe numeric Series without changing the original DataFrame."""
    return pd.to_numeric(series, errors="coerce").fillna(default)


def _mean(frame: pd.DataFrame, column: str, default: float = 0.0) -> float:
    """Safely calculate the mean of a model column."""
    if frame.empty or column not in frame.columns:
        return default
    values = _numeric(frame[column])
    return float(values.mean()) if len(values) else default


def validate_squad(
    squad: pd.DataFrame,
    budget: float = 100.0,
    require_complete_squad: bool = True,
) -> SquadValidation:
    """
    Validate a selected squad against standard FPL rules.

    Checks performed
    ----------------
    1. Exactly 15 unique players when require_complete_squad=True.
    2. Correct positional structure: 2 GK, 5 DEF, 5 MID, 3 FWD.
    3. No more than three players from one club.
    4. Total price does not exceed the supplied budget.
    5. No duplicate player IDs.

    Warnings are separated from errors so the interface can distinguish between
    invalid squads and valid squads that may still be strategically unbalanced.
    """
    errors: List[str] = []
    warnings: List[str] = []

    if squad.empty:
        return SquadValidation(
            is_valid=False,
            errors=["No players have been selected."],
            warnings=[],
        )

    if "player_id" in squad.columns:
        duplicate_count = int(squad["player_id"].duplicated().sum())
        if duplicate_count:
            errors.append(f"Remove {duplicate_count} duplicate player selection(s).")

    if require_complete_squad and len(squad) != 15:
        errors.append(f"A complete FPL squad needs 15 players; currently selected: {len(squad)}.")

    if "position" in squad.columns:
        position_counts = squad["position"].value_counts().to_dict()
        for position, required in REQUIRED_POSITION_COUNTS.items():
            actual = int(position_counts.get(position, 0))
            if require_complete_squad and actual != required:
                errors.append(
                    f"{position}: select exactly {required}; currently selected: {actual}."
                )

    if "team" in squad.columns:
        club_counts = squad["team"].value_counts()
        overloaded = club_counts[club_counts > 3]
        for team_id, count in overloaded.items():
            if "team_name" in squad.columns:
                names = squad.loc[squad["team"] == team_id, "team_name"].dropna()
                club_name = str(names.iloc[0]) if not names.empty else str(team_id)
            else:
                club_name = str(team_id)
            errors.append(f"{club_name}: maximum three players allowed; selected: {int(count)}.")

    squad_cost = float(_numeric(squad.get("price", pd.Series(dtype=float))).sum())
    if squad_cost > budget + 1e-9:
        errors.append(
            f"Squad costs £{squad_cost:.1f}m, which exceeds the £{budget:.1f}m budget."
        )

    # Strategy warnings do not make the squad invalid.
    if squad_cost < budget - 5.0:
        warnings.append(
            f"£{budget - squad_cost:.1f}m is unused. Consider whether the squad can be upgraded."
        )

    if "availability_score" in squad.columns:
        risky = squad[_numeric(squad["availability_score"]) < 65]
        if len(risky) >= 2:
            warnings.append(f"{len(risky)} selected players have meaningful availability concerns.")

    if "minutes_score" in squad.columns:
        rotation_risks = squad[_numeric(squad["minutes_score"]) < 55]
        if len(rotation_risks) >= 3:
            warnings.append(f"{len(rotation_risks)} selected players have notable minutes risk.")

    return SquadValidation(
        is_valid=not errors,
        errors=errors,
        warnings=warnings,
    )


def select_best_starting_xi(squad: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    """
    Select the strongest legal starting XI and return the bench.

    How the algorithm works
    -----------------------
    * One goalkeeper is always selected.
    * Every legal DEF-MID-FWD formation is evaluated.
    * Players are ranked by a starting suitability score.
    * The formation with the highest combined suitability score is chosen.
    * Remaining players become the bench and are ordered by suitability.

    The suitability score combines overall recommendation, fixtures, playing
    time and availability. This avoids choosing a high-upside player who is
    unlikely to start in real life.
    """
    if squad.empty:
        return squad.copy(), squad.copy(), "N/A"

    frame = squad.copy()

    # Create missing inputs defensively so this function remains reusable.
    for column in [
        "suggestion_score",
        "fixtures_score",
        "minutes_score",
        "availability_score",
        "captain_score",
    ]:
        if column not in frame.columns:
            frame[column] = 0.0
        frame[column] = _numeric(frame[column])

    frame["_start_score"] = (
        0.55 * frame["suggestion_score"]
        + 0.18 * frame["fixtures_score"]
        + 0.15 * frame["minutes_score"]
        + 0.12 * frame["availability_score"]
    )

    goalkeepers = frame[frame["position"] == "GK"].sort_values(
        "_start_score", ascending=False
    )
    if goalkeepers.empty:
        return pd.DataFrame(), frame.drop(columns=["_start_score"]), "Invalid"

    best_result = None
    best_total = float("-inf")
    best_formation = "Invalid"

    for defenders, midfielders, forwards in LEGAL_FORMATIONS:
        required = {
            "DEF": defenders,
            "MID": midfielders,
            "FWD": forwards,
        }

        selected_parts = [goalkeepers.head(1)]
        legal = True

        for position, count in required.items():
            pool = frame[frame["position"] == position].sort_values(
                "_start_score", ascending=False
            )
            if len(pool) < count:
                legal = False
                break
            selected_parts.append(pool.head(count))

        if not legal:
            continue

        candidate = pd.concat(selected_parts, ignore_index=False)
        total = float(candidate["_start_score"].sum())

        if total > best_total:
            best_total = total
            best_result = candidate
            best_formation = f"{defenders}-{midfielders}-{forwards}"

    if best_result is None:
        return pd.DataFrame(), frame.drop(columns=["_start_score"]), "Invalid"

    starting_ids = set(best_result["player_id"].astype(int))
    bench = frame[~frame["player_id"].astype(int).isin(starting_ids)].sort_values(
        "_start_score", ascending=False
    )

    return (
        best_result.sort_values(
            ["position", "_start_score"],
            ascending=[True, False],
        ).drop(columns=["_start_score"]),
        bench.drop(columns=["_start_score"]),
        best_formation,
    )


def analyze_budget(squad: pd.DataFrame, budget: float = 100.0) -> pd.DataFrame:
    """
    Summarize squad spending by position.

    The returned DataFrame is designed for direct display in Streamlit and also
    supports future charts without recalculating values in app.py.
    """
    rows: List[Dict[str, float | str | int]] = []

    for position in ["GK", "DEF", "MID", "FWD"]:
        group = squad[squad["position"] == position]
        cost = float(_numeric(group.get("price", pd.Series(dtype=float))).sum())
        rows.append(
            {
                "Position": position,
                "Players": int(len(group)),
                "Spend": round(cost, 1),
                "Share of squad budget %": round((cost / budget * 100.0) if budget else 0.0, 1),
                "Average player price": round(cost / len(group), 2) if len(group) else 0.0,
            }
        )

    total_cost = float(_numeric(squad.get("price", pd.Series(dtype=float))).sum())
    rows.append(
        {
            "Position": "BANK",
            "Players": 0,
            "Spend": round(max(0.0, budget - total_cost), 1),
            "Share of squad budget %": round(max(0.0, budget - total_cost) / budget * 100.0, 1)
            if budget
            else 0.0,
            "Average player price": 0.0,
        }
    )

    return pd.DataFrame(rows)


def rate_squad(squad: pd.DataFrame) -> SquadRatings:
    """
    Calculate the Phase 4 dashboard ratings.

    The ratings are intentionally transparent and use existing player-level
    model scores. No hidden external model is required.
    """
    if squad.empty:
        return SquadRatings(*(0.0 for _ in range(8)))

    starters, bench, _ = select_best_starting_xi(squad)

    overall = _mean(squad, "suggestion_score")
    starting_xi = _mean(starters, "suggestion_score")
    bench_score = _mean(bench, "suggestion_score")
    captaincy = float(
        _numeric(starters.get("captain_score", pd.Series(dtype=float))).nlargest(2).mean()
    ) if not starters.empty else 0.0
    fixtures = _mean(starters, "fixtures_score")
    availability = _mean(squad, "availability_score")
    value = _mean(squad, "value_score")
    risk = _mean(squad, "risk_score")

    # Overall squad rating rewards the starting XI most, while still considering
    # bench depth, captaincy and fitness.
    combined = (
        0.48 * starting_xi
        + 0.14 * bench_score
        + 0.14 * captaincy
        + 0.10 * fixtures
        + 0.08 * availability
        + 0.06 * value
    )

    return SquadRatings(
        overall=max(0.0, min(100.0, combined)),
        starting_xi=max(0.0, min(100.0, starting_xi)),
        bench=max(0.0, min(100.0, bench_score)),
        captaincy=max(0.0, min(100.0, captaincy)),
        fixtures=max(0.0, min(100.0, fixtures)),
        availability=max(0.0, min(100.0, availability)),
        value=max(0.0, min(100.0, value)),
        risk=max(0.0, min(100.0, risk)),
    )


def choose_captains(starting_xi: pd.DataFrame) -> Tuple[pd.Series | None, pd.Series | None]:
    """
    Choose captain and vice-captain from the selected starting XI.

    Captain score comes from Phase 3. Availability and minutes are used as
    tie-breakers to prefer reliable starters.
    """
    if starting_xi.empty:
        return None, None

    ranked = starting_xi.copy()
    for column in ["captain_score", "availability_score", "minutes_score"]:
        if column not in ranked.columns:
            ranked[column] = 0.0
        ranked[column] = _numeric(ranked[column])

    ranked = ranked.sort_values(
        ["captain_score", "availability_score", "minutes_score"],
        ascending=False,
    )

    captain = ranked.iloc[0] if len(ranked) >= 1 else None
    vice = ranked.iloc[1] if len(ranked) >= 2 else None
    return captain, vice


def fixture_matrix(squad: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
    """
    Convert each player's comma-separated fixture string into a matrix.

    Example output columns:
        Player | Team | GW+1 | GW+2 | GW+3 | GW+4 | GW+5

    The current data pipeline stores opponent labels rather than individual FDR
    values for every future match, so this matrix presents opponent and venue.
    """
    rows: List[Dict[str, str]] = []

    for _, player in squad.iterrows():
        opponents = [
            value.strip()
            for value in str(player.get("next_opponents", "")).split(",")
            if value.strip()
        ]

        row: Dict[str, str] = {
            "Player": str(player.get("web_name", "Unknown")),
            "Team": str(player.get("team_short", "")),
        }

        for index in range(horizon):
            row[f"GW+{index + 1}"] = opponents[index] if index < len(opponents) else "—"

        rows.append(row)

    return pd.DataFrame(rows)


def chip_readiness(squad: pd.DataFrame) -> Dict[str, Dict[str, str | float]]:
    """
    Estimate readiness for the four main FPL chips.

    These are strategic indicators rather than official recommendations. The
    function keeps both a numeric score and a plain-language reason so app.py can
    render cards without duplicating business logic.
    """
    ratings = rate_squad(squad)
    starters, bench, _ = select_best_starting_xi(squad)

    weak_players = int(
        (_numeric(squad.get("suggestion_score", pd.Series(dtype=float))) < 50).sum()
    )
    injury_concerns = int(
        (_numeric(squad.get("availability_score", pd.Series(dtype=float))) < 65).sum()
    )

    bench_strength = _mean(bench, "suggestion_score")
    best_captain = float(
        _numeric(starters.get("captain_score", pd.Series(dtype=float))).max()
    ) if not starters.empty else 0.0

    wildcard_score = min(100.0, weak_players * 12.0 + injury_concerns * 10.0)
    free_hit_score = min(100.0, (100.0 - ratings.fixtures) * 0.7 + injury_concerns * 8.0)
    bench_boost_score = min(
        100.0,
        0.55 * bench_strength
        + 0.25 * _mean(bench, "fixtures_score")
        + 0.20 * _mean(bench, "availability_score"),
    )
    triple_captain_score = min(
        100.0,
        0.65 * best_captain
        + 0.20 * _mean(starters, "fixtures_score")
        + 0.15 * _mean(starters, "availability_score"),
    )

    def label(score: float) -> str:
        if score >= 75:
            return "High"
        if score >= 55:
            return "Medium"
        return "Low"

    return {
        "Wildcard": {
            "score": wildcard_score,
            "level": label(wildcard_score),
            "reason": f"{weak_players} weak picks and {injury_concerns} availability concerns detected.",
        },
        "Free Hit": {
            "score": free_hit_score,
            "level": label(free_hit_score),
            "reason": "Higher when the squad has poor short-term fixtures or multiple absences.",
        },
        "Bench Boost": {
            "score": bench_boost_score,
            "level": label(bench_boost_score),
            "reason": f"Bench model strength is {bench_strength:.1f}/100.",
        },
        "Triple Captain": {
            "score": triple_captain_score,
            "level": label(triple_captain_score),
            "reason": f"Best available captain score is {best_captain:.1f}/100.",
        },
    }
