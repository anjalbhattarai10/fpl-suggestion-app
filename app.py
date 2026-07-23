from __future__ import annotations

import re
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

from explanations import why_player
from fpl_data import (
    FPLDataError,
    attach_secondary_injuries,
    bootstrap_frames,
    get_element_summary,
    get_fixtures,
    optional_secondary_injury_rows,
    recent_live_stats,
    team_strength_features,
    upcoming_fixture_features,
)
from scoring import DEFAULT_WEIGHTS, build_scores

st.set_page_config(page_title="FPL Player Suggestion App", page_icon="⚽", layout="wide")


def parse_squad_input(text: str, players: pd.DataFrame) -> Tuple[List[int], List[str]]:
    tokens = [token.strip() for token in re.split(r"[,\n;]+", text) if token.strip()]
    ids: List[int] = []
    unmatched: List[str] = []
    exact_names: Dict[str, int] = {}
    for _, row in players.iterrows():
        for value in [row.get("player_name", ""), row.get("web_name", "")]:
            exact_names[str(value).strip().lower()] = int(row["player_id"])

    for token in tokens:
        if token.isdigit() and int(token) in set(players["player_id"].astype(int)):
            ids.append(int(token))
        elif token.lower() in exact_names:
            ids.append(exact_names[token.lower()])
        else:
            # Conservative partial match: accept only a unique result.
            matches = players[
                players["player_name"].str.contains(re.escape(token), case=False, na=False)
                | players["web_name"].str.contains(re.escape(token), case=False, na=False)
            ]
            if len(matches) == 1:
                ids.append(int(matches.iloc[0]["player_id"]))
            else:
                unmatched.append(token)
    return list(dict.fromkeys(ids)), unmatched


def transfer_suggestions(scored: pd.DataFrame, squad_ids: List[int], bank: float) -> pd.DataFrame:
    squad = scored[scored["player_id"].isin(squad_ids)].copy()
    candidates = scored[~scored["player_id"].isin(squad_ids)].copy()
    rows = []
    for _, outgoing in squad.iterrows():
        affordable = candidates[
            (candidates["position"] == outgoing["position"])
            & (candidates["price"] <= outgoing["price"] + bank)
        ].copy()
        if affordable.empty:
            continue
        affordable["score_gain"] = affordable["suggestion_score"] - outgoing["suggestion_score"]
        affordable["price_difference"] = affordable["price"] - outgoing["price"]
        for _, incoming in affordable.nlargest(3, "score_gain").iterrows():
            if incoming["score_gain"] <= 0:
                continue
            rows.append(
                {
                    "Transfer out": outgoing["web_name"],
                    "Transfer in": incoming["web_name"],
                    "Position": outgoing["position"],
                    "Out price": outgoing["price"],
                    "In price": incoming["price"],
                    "Score gain": incoming["score_gain"],
                    "Why": why_player(incoming),
                }
            )
    return pd.DataFrame(rows).sort_values("Score gain", ascending=False).head(20) if rows else pd.DataFrame()


st.title("⚽ FPL Player Suggestion App")
st.caption("Live, adjustable player rankings using the public FPL endpoints. Scores are decision support—not guaranteed forecasts.")

try:
    players, teams, _, state = bootstrap_frames()
    fixtures = get_fixtures()
except FPLDataError as exc:
    st.error(str(exc))
    st.info("The FPL API may be temporarily unavailable or between seasons. Try Refresh data later.")
    st.stop()

with st.sidebar:
    st.header("Model settings")
    lookback = st.slider("Recent gameweeks", 3, 5, 5)
    horizon = st.slider("Fixture horizon", 3, 5, 5)
    st.subheader("Weights")
    weights = {
        "form": st.slider("Recent form", 0, 100, int(DEFAULT_WEIGHTS["form"])),
        "fixtures": st.slider("Fixtures", 0, 100, int(DEFAULT_WEIGHTS["fixtures"])),
        "minutes": st.slider("Minutes / rotation", 0, 100, int(DEFAULT_WEIGHTS["minutes"])),
        "availability": st.slider("Availability", 0, 100, int(DEFAULT_WEIGHTS["availability"])),
        "value": st.slider("Price value", 0, 100, int(DEFAULT_WEIGHTS["value"])),
        "team_impact": st.slider("Team impact", 0, 100, int(DEFAULT_WEIGHTS["team_impact"])),
    }
    if st.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()

with st.spinner("Building live player scores..."):
    recent = recent_live_stats(state.finished_gws, lookback)
    fixture_features = upcoming_fixture_features(fixtures, teams, state.next_gw, horizon)
    strength = team_strength_features(teams)
    secondary = optional_secondary_injury_rows()

    model = players.merge(recent, on="player_id", how="left")
    model = model.merge(fixture_features, on="team", how="left")
    model = model.merge(strength, on="team", how="left")
    model = attach_secondary_injuries(model, secondary)
    model["next_opponents"] = model.get("next_opponents", "").fillna("")
    model["fixture_score_raw"] = model.get("fixture_score_raw", 0).fillna(0)
    scored = build_scores(model, weights, lookback)
    scored["Why this player"] = scored.apply(why_player, axis=1)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Players", len(scored))
m2.metric("Current/last GW", state.current_gw or "Preseason")
m3.metric("Next GW", state.next_gw or "TBD")
m4.metric("Recent live GWs loaded", len(sorted(state.finished_gws)[-lookback:]))

rank_tab, transfer_tab, detail_tab, methodology_tab = st.tabs(["Player rankings", "Transfer in / out", "Player detail", "Methodology & data health"])

with rank_tab:
    c1, c2, c3 = st.columns(3)
    position = c1.selectbox("Position", ["All", "GK", "DEF", "MID", "FWD"])
    max_price = c2.slider("Maximum price (£m)", 3.5, float(max(4.0, scored["price"].max())), float(max(4.0, scored["price"].max())), 0.1)
    team_options = ["All"] + sorted(scored["team_name"].dropna().unique().tolist())
    team_filter = c3.selectbox("Team", team_options)

    filtered = scored[scored["price"] <= max_price].copy()
    if position != "All":
        filtered = filtered[filtered["position"] == position]
    if team_filter != "All":
        filtered = filtered[filtered["team_name"] == team_filter]

    display_cols = [
        "web_name", "team_short", "position", "price", "suggestion_score", "form_score",
        "fixtures_score", "minutes_score", "availability_score", "value_score",
        "team_impact_score", "recent_points", "recent_minutes", "recent_xgi",
        "avg_fdr", "next_opponents", "chance", "news", "Why this player",
    ]
    rename = {
        "web_name": "Player", "team_short": "Team", "position": "Pos", "price": "Price",
        "suggestion_score": "Score", "form_score": "Form", "fixtures_score": "Fixtures",
        "minutes_score": "Minutes", "availability_score": "Availability", "value_score": "Value",
        "team_impact_score": "Team impact", "recent_points": "Recent pts",
        "recent_minutes": "Recent mins", "recent_xgi": "Recent xGI", "avg_fdr": "Avg FDR",
        "next_opponents": "Next opponents", "chance": "Chance %", "news": "Official news",
    }
    table = filtered[[c for c in display_cols if c in filtered.columns]].rename(columns=rename)
    numeric_round = ["Price", "Score", "Form", "Fixtures", "Minutes", "Availability", "Value", "Team impact", "Recent xGI", "Avg FDR"]
    for col in numeric_round:
        if col in table:
            table[col] = pd.to_numeric(table[col], errors="coerce").round(2)
    st.dataframe(table, hide_index=True, use_container_width=True, height=650)

with transfer_tab:
    st.subheader("Paste your current 15-player squad")
    st.write("Use player names, web names, or FPL player IDs separated by commas or new lines.")
    squad_text = st.text_area("Squad", height=180, placeholder="Haaland\nSalah\n... or 351, 328, ...")
    bank = st.number_input("Money available in the bank (£m)", min_value=0.0, max_value=20.0, value=0.0, step=0.1)
    if squad_text.strip():
        squad_ids, unmatched = parse_squad_input(squad_text, scored)
        st.write(f"Matched {len(squad_ids)} unique players.")
        if unmatched:
            st.warning("Could not uniquely match: " + ", ".join(unmatched))
        if squad_ids:
            squad_table = scored[scored["player_id"].isin(squad_ids)][["web_name", "team_short", "position", "price", "suggestion_score", "Why this player"]]
            st.dataframe(squad_table.rename(columns={"web_name": "Player", "team_short": "Team", "position": "Pos", "price": "Price", "suggestion_score": "Score"}), hide_index=True, use_container_width=True)
            transfers = transfer_suggestions(scored, squad_ids, float(bank))
            if transfers.empty:
                st.info("No positive same-position upgrade was found within the selected budget.")
            else:
                st.dataframe(transfers.round({"Out price": 1, "In price": 1, "Score gain": 2}), hide_index=True, use_container_width=True)
                st.caption("This first version checks same-position affordability. It does not yet enforce the three-players-per-club rule across paired transfers.")

with detail_tab:
    selected_name = st.selectbox("Player", scored["web_name"].tolist())
    player = scored[scored["web_name"] == selected_name].iloc[0]
    st.markdown(f"### {player['web_name']} — {player['team_name']} ({player['position']})")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Suggestion score", f"{player['suggestion_score']:.1f}")
    d2.metric("Price", f"£{player['price']:.1f}m")
    d3.metric("Recent points", f"{player['recent_points']:.0f}")
    d4.metric("Official availability", f"{player['chance']:.0f}%")
    st.write(why_player(player))
    if player.get("news"):
        st.warning(f"Official FPL news: {player['news']}")
    if player.get("secondary_status"):
        st.info(f"Secondary source: {player['secondary_status']}")
    try:
        summary = get_element_summary(int(player["player_id"]))
        history = pd.DataFrame(summary.get("history", []))
        upcoming = pd.DataFrame(summary.get("fixtures", []))
        if not history.empty:
            keep = [c for c in ["round", "opponent_team", "total_points", "minutes", "goals_scored", "assists", "expected_goals", "expected_assists", "value"] if c in history.columns]
            st.markdown("#### Match history from element-summary")
            st.dataframe(history[keep].tail(10), hide_index=True, use_container_width=True)
        if not upcoming.empty:
            keep = [c for c in ["event", "is_home", "difficulty", "kickoff_time", "team_h", "team_a"] if c in upcoming.columns]
            st.markdown("#### Upcoming fixtures from element-summary")
            st.dataframe(upcoming[keep].head(8), hide_index=True, use_container_width=True)
    except FPLDataError as exc:
        st.warning(str(exc))

with methodology_tab:
    st.markdown(
        """
### Formula
Each component is converted to a 0–100 score, mostly using percentile ranks among current players.

`Final = normalized weighted average(Form, Fixtures, Minutes, Availability, Value, Team impact)`

- **Form:** 70% recent points per observed gameweek + 30% recent xGI per 90.
- **Fixtures:** official FDR converted so difficulty 1 is strongest and 5 is weakest, with a small double-gameweek bonus.
- **Minutes:** recent minute share, recent starts, and season minutes.
- **Availability:** official chance of playing, player status, news note, and optional source-disagreement penalty.
- **Value:** season points per £m, net transfer momentum, and current gameweek price movement.
- **Team impact:** team strength plus the player's share of team xGI for MID/FWD, or team points/defensive strength for GK/DEF.

The sliders do not need to total 100; the app normalizes them automatically.
        """
    )
    if secondary.empty:
        st.info("Secondary injury scraping is disabled. Set SECONDARY_INJURY_URL as an environment variable or Streamlit secret to enable the generic best-effort scraper.")
    else:
        st.success(f"Secondary injury rows loaded: {len(secondary)}")
        st.dataframe(secondary, hide_index=True, use_container_width=True)
    st.write("Official FPL endpoints are public but undocumented and can change without notice. Cached data expires after 30 minutes.")
