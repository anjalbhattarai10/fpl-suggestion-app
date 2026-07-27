from __future__ import annotations

"""
Phase 4 optimization utilities.

This module builds valid squads and searches for coordinated two-player
transfers. The algorithms are deliberately transparent and dependency-light,
so the project does not need a commercial solver.

The optimization approach is heuristic rather than mathematically guaranteed
to find the global optimum. It is designed to be fast enough for Streamlit and
easy to understand in a portfolio review.
"""

from itertools import combinations
from typing import Dict, List, Sequence, Tuple

import pandas as pd

from squad_engine import REQUIRED_POSITION_COUNTS, validate_squad


def _numeric(series: pd.Series, default: float = 0.0) -> pd.Series:
    """Convert a Series to numeric values safely."""
    return pd.to_numeric(series, errors="coerce").fillna(default)


def _club_count(selected: pd.DataFrame, team_id: int) -> int:
    """Count how many currently selected players belong to one club."""
    if selected.empty or "team" not in selected.columns:
        return 0
    return int((selected["team"] == team_id).sum())


def build_wildcard_squad(
    players: pd.DataFrame,
    budget: float = 100.0,
    strategy: str = "Balanced",
    candidate_pool_per_position: int = 45,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Build a valid 15-player wildcard squad using a greedy value-aware search.

    Strategy presets
    ----------------
    Balanced:
        Uses the existing suggestion score.
    Form:
        Gives more emphasis to recent form and captaincy.
    Fixtures:
        Gives more emphasis to the upcoming schedule.
    Value:
        Gives more emphasis to value score and affordability.
    Safe:
        Gives more emphasis to minutes and availability.

    Algorithm steps
    ---------------
    1. Calculate a strategy-specific optimizer score.
    2. Keep a manageable candidate pool for each position.
    3. Select mandatory players position by position.
    4. Respect the three-player club limit.
    5. Reserve enough budget for the cheapest remaining required slots.
    6. Run a local upgrade pass using any remaining bank.

    The function returns both the squad and notes explaining any limitations.
    """
    if players.empty:
        return pd.DataFrame(), ["No player data was available."]

    frame = players.copy()
    required_columns = [
        "suggestion_score",
        "form_score",
        "fixtures_score",
        "minutes_score",
        "availability_score",
        "value_score",
        "captain_score",
        "risk_score",
        "price",
    ]
    for column in required_columns:
        if column not in frame.columns:
            frame[column] = 0.0
        frame[column] = _numeric(frame[column])

    formulas: Dict[str, pd.Series] = {
        "Balanced": (
            0.55 * frame["suggestion_score"]
            + 0.15 * frame["captain_score"]
            + 0.15 * frame["value_score"]
            + 0.15 * (100.0 - frame["risk_score"])
        ),
        "Form": (
            0.38 * frame["form_score"]
            + 0.27 * frame["suggestion_score"]
            + 0.20 * frame["captain_score"]
            + 0.15 * frame["minutes_score"]
        ),
        "Fixtures": (
            0.40 * frame["fixtures_score"]
            + 0.30 * frame["suggestion_score"]
            + 0.15 * frame["team_impact_score"]
            + 0.15 * frame["availability_score"]
        ),
        "Value": (
            0.42 * frame["value_score"]
            + 0.28 * frame["suggestion_score"]
            + 0.15 * frame["minutes_score"]
            + 0.15 * frame["availability_score"]
        ),
        "Safe": (
            0.32 * frame["minutes_score"]
            + 0.28 * frame["availability_score"]
            + 0.25 * frame["suggestion_score"]
            + 0.15 * frame["fixtures_score"]
        ),
    }

    frame["_optimizer_score"] = formulas.get(strategy, formulas["Balanced"])
    frame = frame[
        (frame["price"] > 0)
        & (frame["availability_score"] >= 35)
    ].copy()

    # Candidate pools improve speed and remove players who are very unlikely to
    # be selected. Value per price is used as a secondary sorting signal.
    frame["_score_per_million"] = frame["_optimizer_score"] / frame["price"].replace(0, 1)

    pools: Dict[str, pd.DataFrame] = {}
    for position, count in REQUIRED_POSITION_COUNTS.items():
        pool = frame[frame["position"] == position].sort_values(
            ["_optimizer_score", "_score_per_million"],
            ascending=False,
        )
        pools[position] = pool.head(max(candidate_pool_per_position, count * 5))

    selected = pd.DataFrame(columns=frame.columns)
    notes: List[str] = []

    # Fill positions in an order that typically protects scarce premium slots.
    selection_order = ["FWD", "MID", "DEF", "GK"]

    for position in selection_order:
        required_count = REQUIRED_POSITION_COUNTS[position]
        pool = pools[position].copy()

        while int((selected["position"] == position).sum()) < required_count:
            remaining_requirements = {
                pos: REQUIRED_POSITION_COUNTS[pos] - int((selected["position"] == pos).sum())
                for pos in REQUIRED_POSITION_COUNTS
            }

            candidates = []
            for _, player in pool.iterrows():
                if int(player["player_id"]) in set(selected.get("player_id", pd.Series(dtype=int)).astype(int)):
                    continue
                if _club_count(selected, int(player["team"])) >= 3:
                    continue

                proposed_cost = float(_numeric(selected.get("price", pd.Series(dtype=float))).sum()) + float(player["price"])

                # Reserve the cheapest possible price for all slots that would
                # remain after selecting this candidate.
                reserve = 0.0
                feasible = True
                for pos, remaining_count in remaining_requirements.items():
                    adjusted_count = remaining_count - (1 if pos == position else 0)
                    if adjusted_count <= 0:
                        continue

                    eligible = pools[pos][
                        ~pools[pos]["player_id"].isin(selected.get("player_id", pd.Series(dtype=int)))
                    ].copy()
                    if len(eligible) < adjusted_count:
                        feasible = False
                        break
                    reserve += float(eligible.nsmallest(adjusted_count, "price")["price"].sum())

                if not feasible or proposed_cost + reserve > budget + 1e-9:
                    continue

                candidates.append(player)

            if not candidates:
                notes.append(
                    f"Could not complete {position} selections within the current constraints."
                )
                break

            # The first valid candidate is the highest optimizer score because the
            # pool is already sorted.
            chosen = candidates[0]
            selected = pd.concat(
                [selected, chosen.to_frame().T],
                ignore_index=True,
            )

    # Upgrade pass: use remaining bank to swap selected players for better players
    # of the same position while preserving club limits.
    if len(selected) == 15:
        improved = True
        passes = 0

        while improved and passes < 4:
            improved = False
            passes += 1

            for selected_index, current in selected.copy().iterrows():
                available_budget = (
                    budget
                    - float(_numeric(selected["price"]).sum())
                    + float(current["price"])
                )

                alternatives = frame[
                    (frame["position"] == current["position"])
                    & (frame["price"] <= available_budget + 1e-9)
                    & (~frame["player_id"].isin(selected["player_id"]))
                    & (frame["_optimizer_score"] > float(current["_optimizer_score"]) + 0.25)
                ].sort_values("_optimizer_score", ascending=False)

                for _, candidate in alternatives.iterrows():
                    same_club_without_current = int(
                        (
                            selected.drop(index=selected_index)["team"]
                            == candidate["team"]
                        ).sum()
                    )
                    if same_club_without_current >= 3:
                        continue

                    selected.loc[selected_index] = candidate
                    improved = True
                    break

    selected = selected.drop(
        columns=["_optimizer_score", "_score_per_million"],
        errors="ignore",
    )

    validation = validate_squad(selected, budget=budget, require_complete_squad=True)
    notes.extend(validation.errors)
    notes.extend(validation.warnings)

    return selected.reset_index(drop=True), notes


def optimize_two_transfers(
    squad: pd.DataFrame,
    player_pool: pd.DataFrame,
    bank: float = 0.0,
    limit: int = 10,
    candidate_limit_per_position: int = 10,
) -> pd.DataFrame:
    """Return the best legal coordinated two-transfer plans.

    This implementation avoids repeatedly constructing and validating complete
    DataFrames inside the deepest loop. It pre-builds small position-specific
    candidate pools, checks prices and club limits using dictionaries, and only
    creates a final DataFrame after the search is complete.

    The result is a fast, explainable heuristic suitable for Streamlit.
    """

    result_columns = [
        "Transfer out 1",
        "Transfer out 2",
        "Transfer in 1",
        "Transfer in 2",
        "Position 1",
        "Position 2",
        "Outgoing cost",
        "Incoming cost",
        "Money remaining",
        "Combined score gain",
        "Incoming average score",
    ]

    if len(squad) != 15 or player_pool.empty:
        return pd.DataFrame(columns=result_columns)

    required_columns = {
        "player_id",
        "web_name",
        "position",
        "team",
        "price",
        "suggestion_score",
    }
    if not required_columns.issubset(squad.columns):
        return pd.DataFrame(columns=result_columns)
    if not required_columns.issubset(player_pool.columns):
        return pd.DataFrame(columns=result_columns)

    squad_frame = squad.copy()
    pool_frame = player_pool.copy()

    numeric_columns = [
        "player_id",
        "team",
        "price",
        "suggestion_score",
        "value_score",
        "availability_score",
    ]
    for column in numeric_columns:
        if column not in squad_frame.columns:
            squad_frame[column] = 0.0
        if column not in pool_frame.columns:
            pool_frame[column] = 0.0
        squad_frame[column] = pd.to_numeric(
            squad_frame[column], errors="coerce"
        ).fillna(0.0)
        pool_frame[column] = pd.to_numeric(
            pool_frame[column], errors="coerce"
        ).fillna(0.0)

    squad_ids = set(squad_frame["player_id"].astype(int))
    outsiders = pool_frame[
        ~pool_frame["player_id"].astype(int).isin(squad_ids)
    ].copy()

    # Exclude clearly unusable candidates before creating position pools.
    if "availability_score" in outsiders.columns:
        outsiders = outsiders[outsiders["availability_score"] >= 35].copy()
    outsiders = outsiders[outsiders["price"] > 0].copy()

    # A balanced optimization score prevents the search from selecting a player
    # solely because of one unusually high input.
    outsiders["_pair_score"] = (
        0.70 * outsiders["suggestion_score"]
        + 0.18 * outsiders.get("value_score", 0.0)
        + 0.12 * outsiders.get("availability_score", 0.0)
    )

    candidate_pools: Dict[str, List[Dict[str, object]]] = {}
    for position in REQUIRED_POSITION_COUNTS:
        position_pool = outsiders[
            outsiders["position"] == position
        ].sort_values(
            ["_pair_score", "suggestion_score", "price"],
            ascending=[False, False, True],
        ).head(max(4, int(candidate_limit_per_position)))

        candidate_pools[position] = position_pool.to_dict("records")

    base_club_counts = (
        squad_frame["team"].astype(int).value_counts().to_dict()
    )

    outgoing_records = squad_frame.to_dict("records")
    results: List[Dict[str, object]] = []

    for outgoing_a, outgoing_b in combinations(outgoing_records, 2):
        position_a = str(outgoing_a["position"])
        position_b = str(outgoing_b["position"])

        incoming_pool_a = candidate_pools.get(position_a, [])
        incoming_pool_b = candidate_pools.get(position_b, [])
        if not incoming_pool_a or not incoming_pool_b:
            continue

        outgoing_cost = float(outgoing_a["price"]) + float(outgoing_b["price"])
        maximum_incoming_cost = outgoing_cost + float(bank)
        outgoing_score = (
            float(outgoing_a["suggestion_score"])
            + float(outgoing_b["suggestion_score"])
        )

        # Remove the outgoing players from the club-count baseline once per pair.
        club_counts = dict(base_club_counts)
        for outgoing in (outgoing_a, outgoing_b):
            team_id = int(outgoing["team"])
            club_counts[team_id] = max(0, club_counts.get(team_id, 0) - 1)

        # For two different positions, every player in pool A can pair with every
        # player in pool B. For equal positions, combinations avoid duplicate and
        # reversed candidate pairs.
        if position_a == position_b:
            incoming_pairs = combinations(incoming_pool_a, 2)
        else:
            incoming_pairs = (
                (incoming_a, incoming_b)
                for incoming_a in incoming_pool_a
                for incoming_b in incoming_pool_b
            )

        for incoming_a, incoming_b in incoming_pairs:
            incoming_a_id = int(incoming_a["player_id"])
            incoming_b_id = int(incoming_b["player_id"])
            if incoming_a_id == incoming_b_id:
                continue

            incoming_cost = (
                float(incoming_a["price"]) + float(incoming_b["price"])
            )
            if incoming_cost > maximum_incoming_cost + 1e-9:
                continue

            team_a = int(incoming_a["team"])
            team_b = int(incoming_b["team"])

            # Fast maximum-three-per-club validation.
            if team_a == team_b:
                if club_counts.get(team_a, 0) + 2 > 3:
                    continue
            else:
                if club_counts.get(team_a, 0) + 1 > 3:
                    continue
                if club_counts.get(team_b, 0) + 1 > 3:
                    continue

            incoming_score = (
                float(incoming_a["suggestion_score"])
                + float(incoming_b["suggestion_score"])
            )
            score_gain = incoming_score - outgoing_score
            if score_gain <= 0:
                continue

            results.append(
                {
                    "Transfer out 1": str(outgoing_a["web_name"]),
                    "Transfer out 2": str(outgoing_b["web_name"]),
                    "Transfer in 1": str(incoming_a["web_name"]),
                    "Transfer in 2": str(incoming_b["web_name"]),
                    "Position 1": position_a,
                    "Position 2": position_b,
                    "Outgoing cost": round(outgoing_cost, 1),
                    "Incoming cost": round(incoming_cost, 1),
                    "Money remaining": round(
                        maximum_incoming_cost - incoming_cost, 1
                    ),
                    "Combined score gain": round(score_gain, 2),
                    "Incoming average score": round(incoming_score / 2.0, 2),
                }
            )

    if not results:
        return pd.DataFrame(columns=result_columns)

    results_frame = pd.DataFrame(results)

    # Remove duplicate plans where the same four players appear in a reversed
    # display order.
    results_frame["_plan_key"] = results_frame.apply(
        lambda row: (
            tuple(sorted([row["Transfer out 1"], row["Transfer out 2"]])),
            tuple(sorted([row["Transfer in 1"], row["Transfer in 2"]])),
        ),
        axis=1,
    )
    results_frame = (
        results_frame.sort_values(
            ["Combined score gain", "Money remaining", "Incoming average score"],
            ascending=[False, False, False],
        )
        .drop_duplicates("_plan_key")
        .head(max(1, int(limit)))
        .drop(columns="_plan_key")
        .reset_index(drop=True)
    )

    return results_frame[result_columns]

