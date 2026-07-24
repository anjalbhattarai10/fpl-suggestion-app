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
    candidate_limit_per_position: int = 18,
) -> pd.DataFrame:
    """
    Search for coordinated two-player transfer combinations.

    Why pair optimization matters
    -----------------------------
    A one-player transfer cannot identify moves where a cheap downgrade funds a
    major upgrade elsewhere. This function evaluates pairs while respecting:

    * Total available budget.
    * Position-for-position replacement.
    * Maximum three players from one club.
    * No duplicate incoming players.

    Performance protection
    ----------------------
    Evaluating every possible FPL player pair would be expensive. Therefore the
    incoming pool is reduced to the top candidates for each position before
    combinations are generated.
    """
    if len(squad) < 2 or player_pool.empty:
        return pd.DataFrame()

    squad_ids = set(squad["player_id"].astype(int))
    outsiders = player_pool[~player_pool["player_id"].astype(int).isin(squad_ids)].copy()

    # Keep the most useful incoming candidates for each position.
    reduced_parts = []
    for position in REQUIRED_POSITION_COUNTS:
        reduced = outsiders[outsiders["position"] == position].sort_values(
            ["suggestion_score", "value_score", "availability_score"],
            ascending=False,
        ).head(candidate_limit_per_position)
        reduced_parts.append(reduced)
    outsiders = pd.concat(reduced_parts, ignore_index=True)

    results: List[Dict[str, object]] = []
    current_cost = float(_numeric(squad["price"]).sum())

    for (_, outgoing_a), (_, outgoing_b) in combinations(squad.iterrows(), 2):
        outgoing_positions = sorted([str(outgoing_a["position"]), str(outgoing_b["position"])])
        outgoing_price = float(outgoing_a["price"]) + float(outgoing_b["price"])
        outgoing_score = float(outgoing_a["suggestion_score"]) + float(outgoing_b["suggestion_score"])
        pair_budget = outgoing_price + bank

        candidate_rows = outsiders[
            outsiders["position"].isin(outgoing_positions)
        ]

        for (_, incoming_a), (_, incoming_b) in combinations(candidate_rows.iterrows(), 2):
            if int(incoming_a["player_id"]) == int(incoming_b["player_id"]):
                continue

            incoming_positions = sorted([str(incoming_a["position"]), str(incoming_b["position"])])
            if incoming_positions != outgoing_positions:
                continue

            incoming_price = float(incoming_a["price"]) + float(incoming_b["price"])
            if incoming_price > pair_budget + 1e-9:
                continue

            proposed = squad[
                ~squad["player_id"].isin(
                    [outgoing_a["player_id"], outgoing_b["player_id"]]
                )
            ].copy()
            proposed = pd.concat(
                [
                    proposed,
                    incoming_a.to_frame().T,
                    incoming_b.to_frame().T,
                ],
                ignore_index=True,
            )

            if proposed["team"].value_counts().max() > 3:
                continue

            gain = (
                float(incoming_a["suggestion_score"])
                + float(incoming_b["suggestion_score"])
                - outgoing_score
            )

            if gain <= 0:
                continue

            results.append(
                {
                    "Transfer out 1": outgoing_a["web_name"],
                    "Transfer out 2": outgoing_b["web_name"],
                    "Transfer in 1": incoming_a["web_name"],
                    "Transfer in 2": incoming_b["web_name"],
                    "Outgoing cost": outgoing_price,
                    "Incoming cost": incoming_price,
                    "Money left": pair_budget - incoming_price,
                    "Combined score gain": gain,
                    "Incoming fixtures": (
                        f"{incoming_a.get('next_opponents', '')} | "
                        f"{incoming_b.get('next_opponents', '')}"
                    ),
                }
            )

    if not results:
        return pd.DataFrame()

    return (
        pd.DataFrame(results)
        .sort_values(
            ["Combined score gain", "Money left"],
            ascending=[False, False],
        )
        .drop_duplicates(
            subset=[
                "Transfer out 1",
                "Transfer out 2",
                "Transfer in 1",
                "Transfer in 2",
            ]
        )
        .head(limit)
        .reset_index(drop=True)
    )
