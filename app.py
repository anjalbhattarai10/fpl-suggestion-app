from __future__ import annotations

import html
import re
from textwrap import dedent
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


st.set_page_config(
    page_title="FPL Scout",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    .stApp {
        color: #24152c;
        background:
            radial-gradient(circle at top right, rgba(0, 255, 135, 0.10), transparent 28%),
            linear-gradient(180deg, #f7f8fc 0%, #eef1f7 100%);
    }

    .stApp p,
    .stApp label,
    .stApp h1,
    .stApp h2,
    .stApp h3,
    .stApp h4,
    .stApp h5,
    .stApp h6 {
        color: #24152c;
    }

    div[data-testid="stMarkdownContainer"] code {
        color: #24152c;
        background: #ece7ef;
    }

    .block-container {
        max-width: 1500px;
        padding-top: 1.5rem;
        padding-bottom: 3rem;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #160025 0%, #37003c 60%, #4b0055 100%);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }

    section[data-testid="stSidebar"] * {
        color: #ffffff;
    }

    section[data-testid="stSidebar"] p {
        color: rgba(255, 255, 255, 0.82);
    }

    section[data-testid="stSidebar"] label {
        color: #ffffff !important;
        font-weight: 650;
    }

    section[data-testid="stSidebar"] div[data-testid="stCaptionContainer"] p {
        color: rgba(255, 255, 255, 0.70) !important;
        line-height: 1.4;
    }

    section[data-testid="stSidebar"] details {
        padding: 0.25rem 0.5rem;
        border: 1px solid rgba(255, 255, 255, 0.16);
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.06);
    }

    section[data-testid="stSidebar"] .stButton > button {
        color: #37003c;
        background: #00ff87;
    }

    section[data-testid="stSidebar"] .stButton > button:hover {
        color: #37003c;
        background: #ffffff;
    }

    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #00ff87;
    }

    .hero {
        position: relative;
        overflow: hidden;
        padding: 2rem 2.2rem;
        margin-bottom: 1.3rem;
        border-radius: 24px;
        color: white;
        background: linear-gradient(120deg, #1f0031 0%, #37003c 48%, #720061 100%);
        box-shadow: 0 18px 45px rgba(55, 0, 60, 0.22);
    }

    .hero::after {
        content: "";
        position: absolute;
        width: 260px;
        height: 260px;
        right: -80px;
        top: -110px;
        border-radius: 50%;
        background: rgba(0, 255, 135, 0.16);
    }

    .hero-kicker {
        margin-bottom: 0.35rem;
        color: #00ff87;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.15em;
        text-transform: uppercase;
    }

    .hero h1 {
        margin: 0;
        color: white;
        font-size: clamp(2rem, 4vw, 3.5rem);
        line-height: 1.05;
    }

    .hero p {
        max-width: 760px;
        margin: 0.8rem 0 0;
        color: rgba(255, 255, 255, 0.82);
        font-size: 1rem;
    }

    div[data-testid="stMetric"] {
        padding: 1.1rem 1.2rem;
        border: 1px solid rgba(55, 0, 60, 0.08);
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.92);
        box-shadow: 0 8px 24px rgba(25, 20, 45, 0.06);
    }

    div[data-testid="stMetricLabel"] {
        color: #6f6879;
        font-weight: 600;
    }

    div[data-testid="stMetricValue"] {
        color: #37003c;
        font-weight: 800;
    }

    button[data-baseweb="tab"] {
        height: 3.2rem;
        padding-left: 1.1rem;
        padding-right: 1.1rem;
        font-weight: 700;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        color: #37003c;
        border-bottom-color: #00ff87;
    }

    .sidebar-guide {
        margin: 0.5rem 0 1rem;
        padding: 0.9rem;
        border: 1px solid rgba(255, 255, 255, 0.14);
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.07);
    }

    .sidebar-guide-title {
        margin-bottom: 0.4rem;
        color: #00ff87;
        font-size: 0.86rem;
        font-weight: 800;
    }

    .sidebar-guide-text {
        color: rgba(255, 255, 255, 0.78);
        font-size: 0.78rem;
        line-height: 1.45;
    }

    .section-heading {
        margin: 0.6rem 0 1rem;
    }

    .section-heading h2 {
        margin-bottom: 0.2rem;
        color: #24152c;
    }

    .section-heading p {
        margin-top: 0;
        color: #7e7484;
    }

    .player-card {
        min-height: 300px;
        padding: 1.15rem;
        border: 1px solid rgba(55, 0, 60, 0.08);
        border-radius: 20px;
        background: rgba(255, 255, 255, 0.96);
        box-shadow: 0 12px 30px rgba(31, 16, 40, 0.09);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .player-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 16px 36px rgba(31, 16, 40, 0.14);
    }

    .player-card-top {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 0.8rem;
    }

    .player-photo {
        width: 88px;
        height: 108px;
        object-fit: contain;
        object-position: bottom;
        border-radius: 15px;
        background: linear-gradient(145deg, rgba(55, 0, 60, 0.08), rgba(0, 255, 135, 0.10));
    }

    .player-placeholder {
        width: 88px;
        height: 108px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 15px;
        background: linear-gradient(145deg, rgba(55, 0, 60, 0.08), rgba(0, 255, 135, 0.10));
        font-size: 2rem;
    }

    .club-logo {
        width: 45px;
        height: 45px;
        object-fit: contain;
    }

    .player-card h3 {
        margin: 0.8rem 0 0.1rem;
        color: #2a1731;
        font-size: 1.15rem;
    }

    .player-meta {
        color: #807586;
        font-size: 0.86rem;
    }

    .score-row {
        display: flex;
        justify-content: space-between;
        margin-top: 0.9rem;
        padding-top: 0.75rem;
        border-top: 1px solid #ece7ef;
    }

    .score-pill {
        padding: 0.35rem 0.75rem;
        border-radius: 999px;
        color: #37003c;
        background: #00ff87;
        font-weight: 800;
    }

    .price-pill {
        padding: 0.35rem 0.75rem;
        border-radius: 999px;
        color: white;
        background: #37003c;
        font-weight: 700;
    }

    .reason {
        margin-top: 0.85rem;
        color: #685d6e;
        font-size: 0.82rem;
        line-height: 1.45;
    }

    div[data-testid="stDataFrame"] {
        overflow: hidden;
        border: 1px solid rgba(55, 0, 60, 0.08);
        border-radius: 16px;
        box-shadow: 0 9px 25px rgba(25, 20, 45, 0.05);
    }

    .stButton > button {
        border: 0;
        border-radius: 12px;
        color: white;
        background: #37003c;
        font-weight: 700;
    }

    .stButton > button:hover {
        border: 0;
        color: #37003c;
        background: #00ff87;
    }

    .detail-header {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 1rem 0;
    }

    .detail-player-photo {
        width: 130px;
        height: 150px;
        object-fit: contain;
        border-radius: 18px;
        background: linear-gradient(145deg, rgba(55, 0, 60, 0.08), rgba(0, 255, 135, 0.10));
    }

    .detail-club-logo {
        width: 58px;
        height: 58px;
        object-fit: contain;
    }

    @media (max-width: 800px) {
        .block-container {
            padding-left: 0.8rem;
            padding-right: 0.8rem;
        }

        .hero {
            padding: 1.5rem;
            border-radius: 18px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def safe_image_url(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()



def render_html(markup: str) -> None:
    """Render multiline HTML without Markdown treating indented tags as code."""
    compact = re.sub(r"\s+", " ", dedent(markup)).strip()
    st.markdown(compact, unsafe_allow_html=True)


def render_player_card(player: pd.Series, rank: int) -> None:
    player_name = html.escape(str(player.get("web_name", "Unknown")))
    team_name = html.escape(str(player.get("team_name", "Unknown")))
    position = html.escape(str(player.get("position", "UNK")))
    explanation = html.escape(str(player.get("Why this player", "")))

    player_photo = safe_image_url(player.get("player_photo"))
    team_logo = safe_image_url(player.get("team_logo"))

    photo_html = (
        f'<img class="player-photo" src="{html.escape(player_photo)}" alt="{player_name}">'
        if player_photo
        else '<div class="player-placeholder">👤</div>'
    )

    logo_html = (
        f'<img class="club-logo" src="{html.escape(team_logo)}" alt="{team_name}">'
        if team_logo
        else ""
    )

    st.markdown(
        dedent(
            f"""
            <div class="player-card">
                <div class="player-card-top">
                    {photo_html}
                    <div>
                        <div style="
                            color:#8d8392;
                            font-size:0.72rem;
                            font-weight:800;
                            letter-spacing:0.12em;
                            text-align:right;
                        ">
                            PICK #{rank}
                        </div>
                        {logo_html}
                    </div>
                </div>
                <h3>{player_name}</h3>
                <div class="player-meta">
                    {team_name} &nbsp;•&nbsp; {position}
                </div>
                <div class="score-row">
                    <span class="score-pill">
                        {float(player.get("suggestion_score", 0)):.1f}
                    </span>
                    <span class="price-pill">
                        £{float(player.get("price", 0)):.1f}m
                    </span>
                </div>
                <div class="reason">{explanation}</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )



def _comparison_metric_value(player: pd.Series, column: str) -> float:
    value = player.get(column, 0)
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def comparison_recommendation(selected: pd.DataFrame) -> Tuple[pd.Series, List[str]]:
    """Choose the strongest overall player and explain the decision.

    The final recommendation uses the app's existing suggestion score as the
    primary decision measure, then explains the strongest category advantages.
    """
    ranked = selected.sort_values(
        ["suggestion_score", "form_score", "fixtures_score", "minutes_score"],
        ascending=False,
    )
    winner = ranked.iloc[0]

    comparison_metrics = [
        ("suggestion_score", "overall model score"),
        ("form_score", "recent form"),
        ("fixtures_score", "upcoming fixtures"),
        ("minutes_score", "playing-time security"),
        ("availability_score", "availability"),
        ("value_score", "budget value"),
        ("team_impact_score", "team and player influence"),
        ("recent_points", "recent points"),
        ("recent_xgi", "recent expected goal involvement"),
    ]

    reasons: List[str] = []
    winner_name = str(winner.get("web_name", "The recommended player"))

    for column, label in comparison_metrics:
        if column not in selected.columns:
            continue

        values = pd.to_numeric(selected[column], errors="coerce").fillna(0)
        winner_value = _comparison_metric_value(winner, column)
        best_value = float(values.max())

        if abs(winner_value - best_value) < 0.001:
            ties = int((values.round(3) == round(best_value, 3)).sum())
            if ties == 1:
                reasons.append(
                    f"{winner_name} leads the comparison for {label} "
                    f"with {winner_value:.1f}."
                )

    if not reasons:
        reasons.append(
            f"{winner_name} has the highest balanced score across the selected "
            "form, fixture, minutes, availability, value and team-impact factors."
        )

    price_values = pd.to_numeric(selected.get("price", 0), errors="coerce").fillna(0)
    if _comparison_metric_value(winner, "price") == float(price_values.min()):
        reasons.append(
            f"{winner_name} is also the least expensive option at "
            f"£{_comparison_metric_value(winner, 'price'):.1f}m."
        )

    return winner, reasons[:4]


def player_best_use(player: pd.Series, selected: pd.DataFrame) -> str:
    """Describe the scenario in which a compared player is most attractive."""
    metric_labels = {
        "form_score": "recent form and immediate returns",
        "fixtures_score": "the upcoming fixture schedule",
        "minutes_score": "secure minutes and lower rotation risk",
        "availability_score": "fitness and availability",
        "value_score": "budget value",
        "team_impact_score": "team quality and influence",
        "recent_xgi": "recent attacking involvement",
    }

    advantages = []

    for column, label in metric_labels.items():
        if column not in selected.columns:
            continue
        values = pd.to_numeric(selected[column], errors="coerce").fillna(0)
        player_value = _comparison_metric_value(player, column)
        if abs(player_value - float(values.max())) < 0.001:
            advantages.append(label)

    player_price = _comparison_metric_value(player, "price")
    prices = pd.to_numeric(selected.get("price", 0), errors="coerce").fillna(0)
    if len(prices) and abs(player_price - float(prices.min())) < 0.001:
        advantages.append("the lowest purchase price")

    if not advantages:
        return (
            "A balanced alternative, but this player does not lead the selected "
            "group in a major comparison category."
        )

    if len(advantages) == 1:
        return f"Best suited when you prioritize {advantages[0]}."

    return (
        "Best suited when you prioritize "
        + ", ".join(advantages[:-1])
        + f", and {advantages[-1]}."
    )

def parse_squad_input(text: str, players: pd.DataFrame) -> Tuple[List[int], List[str]]:
    tokens = [token.strip() for token in re.split(r"[,\n;]+", text) if token.strip()]
    ids: List[int] = []
    unmatched: List[str] = []
    exact_names: Dict[str, int] = {}

    player_id_set = set(players["player_id"].astype(int))

    for _, row in players.iterrows():
        for value in [row.get("player_name", ""), row.get("web_name", "")]:
            exact_names[str(value).strip().lower()] = int(row["player_id"])

    for token in tokens:
        if token.isdigit() and int(token) in player_id_set:
            ids.append(int(token))
        elif token.lower() in exact_names:
            ids.append(exact_names[token.lower()])
        else:
            matches = players[
                players["player_name"].str.contains(re.escape(token), case=False, na=False)
                | players["web_name"].str.contains(re.escape(token), case=False, na=False)
            ]
            if len(matches) == 1:
                ids.append(int(matches.iloc[0]["player_id"]))
            else:
                unmatched.append(token)

    return list(dict.fromkeys(ids)), unmatched


def transfer_suggestions(
    scored: pd.DataFrame,
    squad_ids: List[int],
    bank: float,
) -> pd.DataFrame:
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

        affordable["score_gain"] = (
            affordable["suggestion_score"] - outgoing["suggestion_score"]
        )
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

    if not rows:
        return pd.DataFrame()

    return (
        pd.DataFrame(rows)
        .sort_values("Score gain", ascending=False)
        .head(20)
    )


st.markdown(
    """
    <div class="hero">
        <div class="hero-kicker">Live FPL decision support</div>
        <h1>FPL Scout</h1>
        <p>
            Discover transfers, compare players and adjust the model
            to match your Fantasy Premier League strategy.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


try:
    players, teams, _, state = bootstrap_frames()
    fixtures = get_fixtures()
except FPLDataError as exc:
    st.error(str(exc))
    st.info(
        "The FPL API may be temporarily unavailable or between seasons. "
        "Try refreshing the data later."
    )
    st.stop()


with st.sidebar:
    st.markdown("## ⚽ FPL Scout")
    st.caption(
        "Personalize the ranking model. Higher weights give a factor "
        "more influence over the final player score."
    )

    st.markdown(
        """
        <div class="sidebar-guide">
            <div class="sidebar-guide-title">How to use these controls</div>
            <div class="sidebar-guide-text">
                Start with the default settings. Increase a weight when that
                factor matters more to your strategy. The app automatically
                normalizes all weights, so they do not need to add up to 100.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Analysis range")

    lookback = st.slider(
        "Recent form window",
        min_value=3,
        max_value=5,
        value=5,
        help=(
            "Number of completed gameweeks used to measure recent points, "
            "minutes and expected goal involvement."
        ),
    )
    st.caption(
        f"Using the most recent {lookback} completed gameweeks."
    )

    horizon = st.slider(
        "Upcoming fixture window",
        min_value=3,
        max_value=5,
        value=5,
        help=(
            "Number of future gameweeks used to calculate fixture difficulty."
        ),
    )
    st.caption(
        f"Evaluating fixtures across the next {horizon} gameweeks."
    )

    st.markdown("---")
    st.markdown("### Ranking priorities")
    st.caption(
        "Move a slider right to make that factor more important."
    )

    weights = {}

    weights["form"] = st.slider(
        "Recent performance",
        0,
        100,
        int(DEFAULT_WEIGHTS["form"]),
        help="Rewards recent FPL points and expected goal involvement.",
    )
    st.caption("Recent points, attacking output and xGI.")

    weights["fixtures"] = st.slider(
        "Fixture quality",
        0,
        100,
        int(DEFAULT_WEIGHTS["fixtures"]),
        help="Rewards players with easier upcoming opponents.",
    )
    st.caption("Upcoming difficulty and double-gameweek potential.")

    weights["minutes"] = st.slider(
        "Playing-time security",
        0,
        100,
        int(DEFAULT_WEIGHTS["minutes"]),
        help="Rewards regular starters and reduces rotation risk.",
    )
    st.caption("Recent minutes, starts and season involvement.")

    weights["availability"] = st.slider(
        "Fitness and availability",
        0,
        100,
        int(DEFAULT_WEIGHTS["availability"]),
        help="Uses official chance-of-playing and injury news.",
    )
    st.caption("Injury status, suspension and chance of playing.")

    weights["value"] = st.slider(
        "Budget value",
        0,
        100,
        int(DEFAULT_WEIGHTS["value"]),
        help="Rewards players delivering more output for their price.",
    )
    st.caption("Points per £m, price movement and transfer momentum.")

    weights["team_impact"] = st.slider(
        "Team and player influence",
        0,
        100,
        int(DEFAULT_WEIGHTS["team_impact"]),
        help="Measures team strength and the player's contribution.",
    )
    st.caption("Club quality plus the player's role within the team.")

    with st.expander("Recommended presets"):
        st.markdown(
            """
            **Balanced:** Keep the default values.

            **Short-term transfer:** Increase Recent performance and
            Fixture quality.

            **Safe starter:** Increase Playing-time security and
            Fitness and availability.

            **Budget squad:** Increase Budget value.
            """
        )

    st.markdown("---")

    if st.button("↻ Refresh live data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


with st.spinner("Building live player scores..."):
    recent = recent_live_stats(state.finished_gws, lookback)
    fixture_features = upcoming_fixture_features(
        fixtures,
        teams,
        state.next_gw,
        horizon,
    )
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
m4.metric(
    "Recent live GWs loaded",
    len(sorted(state.finished_gws)[-lookback:]),
)


rank_tab, compare_tab, transfer_tab, detail_tab, methodology_tab = st.tabs(
    [
        "Player rankings",
        "Compare players",
        "Transfer planner",
        "Player detail",
        "Methodology & data health",
    ]
)


with rank_tab:
    c1, c2, c3 = st.columns(3)

    position = c1.selectbox(
        "Position",
        ["All", "GK", "DEF", "MID", "FWD"],
    )

    maximum_available_price = float(max(4.0, scored["price"].max()))
    max_price = c2.slider(
        "Maximum price (£m)",
        3.5,
        maximum_available_price,
        maximum_available_price,
        0.1,
    )

    team_options = ["All"] + sorted(
        scored["team_name"].dropna().unique().tolist()
    )
    team_filter = c3.selectbox("Team", team_options)

    filtered = scored[scored["price"] <= max_price].copy()

    if position != "All":
        filtered = filtered[filtered["position"] == position]

    if team_filter != "All":
        filtered = filtered[filtered["team_name"] == team_filter]

    st.markdown(
        """
        <div class="section-heading">
            <h2>Top suggestions</h2>
            <p>
                The strongest options based on your active filters
                and model weights.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    top_players = filtered.head(4)

    if top_players.empty:
        st.info("No players match the selected filters.")
    else:
        card_columns = st.columns(len(top_players))

        for rank, ((_, player_row), card_column) in enumerate(
            zip(top_players.iterrows(), card_columns),
            start=1,
        ):
            with card_column:
                render_player_card(player_row, rank)

    st.markdown("### Full player rankings")

    display_cols = [
        "team_logo",
        "web_name",
        "team_short",
        "position",
        "next_opponents",
        "price",
        "suggestion_score",
        "form_score",
        "fixtures_score",
        "minutes_score",
        "availability_score",
        "value_score",
        "team_impact_score",
        "recent_points",
        "recent_minutes",
        "recent_xgi",
        "avg_fdr",
        "chance",
        "news",
        "Why this player",
    ]

    rename = {
        "team_logo": "Club",
        "web_name": "Player",
        "team_short": "Team",
        "position": "Pos",
        "price": "Price",
        "suggestion_score": "Score",
        "form_score": "Form",
        "fixtures_score": "Fixtures",
        "minutes_score": "Minutes",
        "availability_score": "Availability",
        "value_score": "Value",
        "team_impact_score": "Team impact",
        "recent_points": "Recent pts",
        "recent_minutes": "Recent mins",
        "recent_xgi": "Recent xGI",
        "avg_fdr": "Avg FDR",
        "next_opponents": "Next opponents",
        "chance": "Chance %",
        "news": "Official news",
    }

    table = filtered[
        [column for column in display_cols if column in filtered.columns]
    ].rename(columns=rename)

    numeric_round = [
        "Price",
        "Score",
        "Form",
        "Fixtures",
        "Minutes",
        "Availability",
        "Value",
        "Team impact",
        "Recent xGI",
        "Avg FDR",
    ]

    for column in numeric_round:
        if column in table:
            table[column] = pd.to_numeric(
                table[column],
                errors="coerce",
            ).round(2)

    if "Next opponents" in table.columns:
        table["Next opponents"] = (
            table["Next opponents"]
            .fillna("")
            .astype(str)
            .str.replace(", ", "  •  ", regex=False)
        )

    st.dataframe(
        table,
        hide_index=True,
        use_container_width=True,
        height=650,
        column_config={
            "Club": st.column_config.ImageColumn(
                "Club",
                width="small",
            ),
            "Player": st.column_config.TextColumn(
                "Player",
                width="medium",
            ),
            "Team": st.column_config.TextColumn(
                "Team",
                width="small",
            ),
            "Pos": st.column_config.TextColumn(
                "Pos",
                width="small",
            ),
            "Next opponents": st.column_config.TextColumn(
                "Next 5 opponents",
                help=(
                    "Upcoming league opponents from the FPL fixtures endpoint. "
                    "(H) means home and (A) means away."
                ),
                width="large",
            ),
            "Price": st.column_config.NumberColumn(
                "Price",
                format="£%.1fm",
            ),
            "Score": st.column_config.ProgressColumn(
                "Score",
                min_value=0,
                max_value=100,
                format="%.1f",
            ),
            "Form": st.column_config.ProgressColumn(
                "Form",
                min_value=0,
                max_value=100,
                format="%.1f",
            ),
            "Fixtures": st.column_config.ProgressColumn(
                "Fixtures",
                min_value=0,
                max_value=100,
                format="%.1f",
            ),
            "Minutes": st.column_config.ProgressColumn(
                "Minutes",
                min_value=0,
                max_value=100,
                format="%.1f",
            ),
            "Availability": st.column_config.ProgressColumn(
                "Availability",
                min_value=0,
                max_value=100,
                format="%.1f",
            ),
            "Value": st.column_config.ProgressColumn(
                "Value",
                min_value=0,
                max_value=100,
                format="%.1f",
            ),
            "Team impact": st.column_config.ProgressColumn(
                "Team impact",
                min_value=0,
                max_value=100,
                format="%.1f",
            ),
            "Official news": st.column_config.TextColumn(
                "Official news",
                width="large",
            ),
            "Why this player": st.column_config.TextColumn(
                "Why this player",
                width="large",
            ),
        },
    )


with compare_tab:
    st.markdown(
        """
        <div class="section-heading">
            <h2>Compare up to three players</h2>
            <p>
                Select two or three players to compare their price, current form,
                fixtures, minutes, availability, value and overall influence.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    player_options = (
        scored.sort_values("suggestion_score", ascending=False)["web_name"]
        .dropna()
        .astype(str)
        .tolist()
    )

    default_players = player_options[:3] if len(player_options) >= 3 else player_options

    selected_names = st.multiselect(
        "Players to compare",
        options=player_options,
        default=default_players,
        max_selections=3,
        help="Choose at least two players. You can compare a maximum of three.",
    )

    if len(selected_names) < 2:
        st.info("Select at least two players to begin the comparison.")
    else:
        selected = (
            scored[scored["web_name"].isin(selected_names)]
            .copy()
            .set_index("web_name")
            .loc[selected_names]
            .reset_index()
        )

        winner, winner_reasons = comparison_recommendation(selected)

        st.markdown(
            f"""
            <div class="viz-callout">
                <strong>Best overall choice: {html.escape(str(winner["web_name"]))}</strong><br>
                {html.escape(" ".join(winner_reasons))}
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### Player summary")

        summary_columns = st.columns(len(selected))

        for column, (_, player_row) in zip(summary_columns, selected.iterrows()):
            with column:
                render_player_card(player_row, 1)
                st.caption(player_best_use(player_row, selected))

        comparison_rows = [
            ("Overall score", "suggestion_score", False),
            ("Price (£m)", "price", True),
            ("Recent form", "form_score", False),
            ("Fixture quality", "fixtures_score", False),
            ("Playing-time security", "minutes_score", False),
            ("Availability", "availability_score", False),
            ("Budget value", "value_score", False),
            ("Team impact", "team_impact_score", False),
            ("Recent points", "recent_points", False),
            ("Recent minutes", "recent_minutes", False),
            ("Recent xGI", "recent_xgi", False),
            ("Average FDR", "avg_fdr", True),
            ("Chance of playing (%)", "chance", False),
        ]

        matrix_data = {"Metric": []}

        for name in selected_names:
            matrix_data[name] = []

        for label, column_name, lower_is_better in comparison_rows:
            if column_name not in selected.columns:
                continue

            matrix_data["Metric"].append(label)

            values = pd.to_numeric(
                selected[column_name],
                errors="coerce",
            ).fillna(0)

            best_value = float(values.min() if lower_is_better else values.max())

            for _, player_row in selected.iterrows():
                value = _comparison_metric_value(player_row, column_name)
                marker_symbol = " ★" if abs(value - best_value) < 0.001 else ""

                if column_name == "price":
                    formatted = f"£{value:.1f}m"
                elif column_name in {"recent_points", "recent_minutes", "chance"}:
                    formatted = f"{value:.0f}"
                else:
                    formatted = f"{value:.1f}"

                matrix_data[str(player_row["web_name"])].append(
                    formatted + marker_symbol
                )

        st.markdown("### Side-by-side comparison")
        st.caption(
            "★ marks the strongest result in each row. Lower is better only "
            "for price and average fixture difficulty."
        )

        st.dataframe(
            pd.DataFrame(matrix_data),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Metric": st.column_config.TextColumn(
                    "Metric",
                    width="medium",
                )
            },
        )

        st.markdown("### Which player is better for which reason?")

        explanation_columns = st.columns(len(selected))

        for column, (_, player_row) in zip(
            explanation_columns,
            selected.iterrows(),
        ):
            with column:
                player_name = html.escape(str(player_row["web_name"]))
                team_name = html.escape(str(player_row.get("team_name", "")))
                use_case = html.escape(player_best_use(player_row, selected))

                strengths = []
                weakness = []

                category_columns = [
                    ("form_score", "form"),
                    ("fixtures_score", "fixtures"),
                    ("minutes_score", "minutes"),
                    ("availability_score", "availability"),
                    ("value_score", "value"),
                    ("team_impact_score", "team influence"),
                ]

                for metric_column, metric_label in category_columns:
                    if metric_column not in selected.columns:
                        continue

                    values = pd.to_numeric(
                        selected[metric_column],
                        errors="coerce",
                    ).fillna(0)

                    player_value = _comparison_metric_value(
                        player_row,
                        metric_column,
                    )

                    if abs(player_value - float(values.max())) < 0.001:
                        strengths.append(metric_label)

                    if abs(player_value - float(values.min())) < 0.001:
                        weakness.append(metric_label)

                strength_text = (
                    ", ".join(strengths)
                    if strengths
                    else "balanced profile"
                )
                weakness_text = (
                    ", ".join(weakness)
                    if weakness
                    else "no clear category weakness"
                )

                st.markdown(
                    f"""
                    <div class="card">
                        <h3>{player_name}</h3>
                        <p><strong>{team_name}</strong></p>
                        <p>{use_case}</p>
                        <p><strong>Leads in:</strong> {html.escape(strength_text)}</p>
                        <p><strong>Trails in:</strong> {html.escape(weakness_text)}</p>
                        <p>
                            <strong>Overall score:</strong>
                            {_comparison_metric_value(player_row, "suggestion_score"):.1f}
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.info(
            "The recommendation uses your current sidebar weights. Changing "
            "those weights can change which player is considered the best fit."
        )



with transfer_tab:
    st.markdown(
        """
        <div class="section-heading">
            <h2>Transfer planner</h2>
            <p>
                Choose one player from your squad and the app will recommend
                stronger, affordable replacements in the same position.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    planner_left, planner_right = st.columns([1.4, 1.6], gap="large")

    with planner_left:
        st.markdown("### 1. Select the player to replace")

        position_order = {"GK": 0, "DEF": 1, "MID": 2, "FWD": 3}
        planner_players = scored.copy()
        planner_players["_position_order"] = (
            planner_players["position"].map(position_order).fillna(9)
        )
        planner_players = planner_players.sort_values(
            ["_position_order", "suggestion_score"],
            ascending=[True, False],
        )

        player_label_lookup = {
            (
                f"{row['web_name']} · {row['team_short']} · "
                f"{row['position']} · £{float(row['price']):.1f}m"
            ): int(row["player_id"])
            for _, row in planner_players.iterrows()
        }

        selected_out_label = st.selectbox(
            "Player to sell",
            options=list(player_label_lookup.keys()),
            help=(
                "Select the player you are considering transferring out. "
                "Recommendations will stay within the same FPL position."
            ),
        )

        outgoing_id = player_label_lookup[selected_out_label]
        outgoing = scored[scored["player_id"] == outgoing_id].iloc[0]

        bank = st.number_input(
            "Money available in the bank (£m)",
            min_value=0.0,
            max_value=20.0,
            value=0.0,
            step=0.1,
            help="This amount is added to the selected player's selling price.",
        )

        max_budget = float(outgoing["price"]) + float(bank)

        st.markdown(
            f"""
            <div class="sidebar-guide" style="
                background:#ffffff;
                border:1px solid rgba(55,0,60,.10);
                margin-top:1rem;
            ">
                <div class="sidebar-guide-title" style="color:#37003c;">
                    Available replacement budget
                </div>
                <div style="
                    color:#24152c;
                    font-size:1.8rem;
                    font-weight:800;
                    margin:.15rem 0;
                ">
                    £{max_budget:.1f}m
                </div>
                <div style="color:#6f6879;font-size:.82rem;">
                    £{float(outgoing['price']):.1f}m player value
                    + £{float(bank):.1f}m in the bank
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### 2. Set your preference")

        planner_priority = st.radio(
            "What matters most for this transfer?",
            [
                "Best overall",
                "Immediate returns",
                "Easy fixtures",
                "Secure starter",
                "Best value",
            ],
            help=(
                "This preference changes how the recommendations are ordered "
                "inside the transfer planner only."
            ),
        )

        priority_column = {
            "Best overall": "suggestion_score",
            "Immediate returns": "form_score",
            "Easy fixtures": "fixtures_score",
            "Secure starter": "minutes_score",
            "Best value": "value_score",
        }[planner_priority]

        exclude_same_team = st.checkbox(
            "Exclude players from the same club",
            value=False,
            help="Useful when you want to diversify your squad.",
        )

        st.markdown("---")
        affordable_players_container = st.container()

    with planner_right:
        st.markdown("### Current player")

        out_photo = safe_image_url(outgoing.get("player_photo"))
        out_logo = safe_image_url(outgoing.get("team_logo"))
        out_name = html.escape(str(outgoing["web_name"]))
        out_team = html.escape(str(outgoing["team_name"]))
        out_position = html.escape(str(outgoing["position"]))

        out_photo_html = (
            f'<img class="detail-player-photo" src="{html.escape(out_photo)}" '
            f'alt="{out_name}">'
            if out_photo
            else '<div class="player-placeholder">👤</div>'
        )
        out_logo_html = (
            f'<img class="detail-club-logo" src="{html.escape(out_logo)}" '
            f'alt="{out_team}">'
            if out_logo
            else ""
        )

        st.markdown(
            dedent(
                f"""
                <div class="detail-header" style="
                    background:#ffffff;
                    border:1px solid rgba(55,0,60,.08);
                    border-radius:18px;
                    padding:1rem 1.2rem;
                    margin-bottom:1rem;
                ">
                    {out_photo_html}
                    {out_logo_html}
                    <div>
                        <div style="
                            color:#807586;
                            font-size:.8rem;
                            font-weight:700;
                            text-transform:uppercase;
                            letter-spacing:.08em;
                        ">
                            Transfer out · {out_team} · {out_position}
                        </div>
                        <h2 style="margin:.2rem 0;color:#2b1731;">
                            {out_name}
                        </h2>
                        <div style="color:#6f6879;">
                            £{float(outgoing['price']):.1f}m ·
                            Score {float(outgoing['suggestion_score']):.1f}
                        </div>
                    </div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        candidates = scored[
            (scored["player_id"] != outgoing_id)
            & (scored["position"] == outgoing["position"])
            & (scored["price"] <= max_budget)
        ].copy()

        if exclude_same_team:
            candidates = candidates[
                candidates["team_name"] != outgoing["team_name"]
            ]

        candidates["score_gain"] = (
            candidates["suggestion_score"]
            - float(outgoing["suggestion_score"])
        )
        candidates["money_remaining"] = max_budget - candidates["price"]
        candidates["priority_gain"] = (
            candidates[priority_column]
            - float(outgoing.get(priority_column, 0))
        )

        candidates = candidates.sort_values(
            [priority_column, "suggestion_score", "score_gain"],
            ascending=False,
        )

        positive_candidates = candidates[
            candidates["score_gain"] > 0
        ].head(5)

        if positive_candidates.empty:
            st.info(
                "No affordable same-position player currently has a higher "
                "overall score. Try increasing the bank amount or changing "
                "the sidebar weights."
            )

            with affordable_players_container:
                st.markdown("### Other affordable players")
                st.caption(
                    "These options fit the budget, although none currently "
                    "improves the overall model score."
                )

                fallback_columns = [
                    "team_logo",
                    "web_name",
                    "team_short",
                    "price",
                    "suggestion_score",
                    "score_gain",
                ]

                fallback_table = candidates.head(8)[
                    [
                        column
                        for column in fallback_columns
                        if column in candidates.columns
                    ]
                ].rename(
                    columns={
                        "team_logo": "Club",
                        "web_name": "Player",
                        "team_short": "Team",
                        "price": "Price",
                        "suggestion_score": "Score",
                        "score_gain": "Gain",
                    }
                )

                st.dataframe(
                    fallback_table,
                    hide_index=True,
                    use_container_width=True,
                    height=430,
                    column_config={
                        "Club": st.column_config.ImageColumn(
                            "Club",
                            width="small",
                        ),
                        "Price": st.column_config.NumberColumn(
                            "Price",
                            format="£%.1fm",
                        ),
                        "Score": st.column_config.NumberColumn(
                            "Score",
                            format="%.1f",
                        ),
                        "Gain": st.column_config.NumberColumn(
                            "Gain",
                            format="%+.1f",
                        ),
                    },
                )
        else:
            best_pick = positive_candidates.iloc[0]

            st.markdown("### Best recommendation")

            gain = float(best_pick["score_gain"])
            money_left = float(best_pick["money_remaining"])

            recommendation_reasons = []
            reason_metrics = [
                ("form_score", "stronger recent form"),
                ("fixtures_score", "better upcoming fixtures"),
                ("minutes_score", "more secure playing time"),
                ("availability_score", "better availability"),
                ("value_score", "better value for money"),
                ("team_impact_score", "stronger team and player influence"),
            ]

            for metric, label in reason_metrics:
                incoming_value = float(best_pick.get(metric, 0) or 0)
                outgoing_value = float(outgoing.get(metric, 0) or 0)
                if incoming_value >= outgoing_value + 4:
                    recommendation_reasons.append(label)

            if not recommendation_reasons:
                recommendation_reasons.append(
                    "a stronger balanced score across the model"
                )

            best_name = html.escape(str(best_pick["web_name"]))
            best_team = html.escape(str(best_pick["team_name"]))
            best_photo = safe_image_url(best_pick.get("player_photo"))
            best_logo = safe_image_url(best_pick.get("team_logo"))

            best_photo_html = (
                f'<img class="detail-player-photo" src="{html.escape(best_photo)}" '
                f'alt="{best_name}">'
                if best_photo
                else '<div class="player-placeholder">👤</div>'
            )
            best_logo_html = (
                f'<img class="detail-club-logo" src="{html.escape(best_logo)}" '
                f'alt="{best_team}">'
                if best_logo
                else ""
            )

            render_html(
                f"""
                    <div style="
                        background:linear-gradient(135deg,#37003c,#6f005f);
                        color:white;
                        border-radius:22px;
                        padding:1.25rem;
                        margin-bottom:1rem;
                    ">
                        <div style="
                            color:#00ff87;
                            font-size:.75rem;
                            font-weight:800;
                            letter-spacing:.12em;
                            text-transform:uppercase;
                        ">
                            Recommended transfer
                        </div>

                        <div style="
                            display:flex;
                            align-items:center;
                            gap:1rem;
                            margin-top:.8rem;
                            flex-wrap:wrap;
                        ">
                            {best_photo_html}
                            {best_logo_html}

                            <div style="flex:1;min-width:180px;">
                                <div style="
                                    color:rgba(255,255,255,.72);
                                    font-size:.8rem;
                                ">
                                    Transfer in · {best_team}
                                </div>
                                <div style="
                                    color:white;
                                    font-size:1.7rem;
                                    font-weight:800;
                                ">
                                    {best_name}
                                </div>
                                <div style="
                                    color:rgba(255,255,255,.78);
                                    margin-top:.2rem;
                                ">
                                    £{float(best_pick['price']):.1f}m ·
                                    {html.escape(str(best_pick['position']))}
                                </div>
                            </div>

                            <div style="
                                display:grid;
                                grid-template-columns:repeat(2,minmax(100px,1fr));
                                gap:.7rem;
                                min-width:250px;
                            ">
                                <div style="
                                    background:rgba(255,255,255,.10);
                                    border-radius:14px;
                                    padding:.8rem;
                                ">
                                    <div style="
                                        color:rgba(255,255,255,.65);
                                        font-size:.72rem;
                                    ">
                                        Score gain
                                    </div>
                                    <div style="
                                        color:#00ff87;
                                        font-size:1.45rem;
                                        font-weight:800;
                                    ">
                                        +{gain:.1f}
                                    </div>
                                </div>

                                <div style="
                                    background:rgba(255,255,255,.10);
                                    border-radius:14px;
                                    padding:.8rem;
                                ">
                                    <div style="
                                        color:rgba(255,255,255,.65);
                                        font-size:.72rem;
                                    ">
                                        Money left
                                    </div>
                                    <div style="
                                        color:white;
                                        font-size:1.45rem;
                                        font-weight:800;
                                    ">
                                        £{money_left:.1f}m
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    """
            )

            st.markdown("#### Why this transfer is recommended")
            for reason in recommendation_reasons[:4]:
                st.markdown(f"✅ {reason.capitalize()}")

            before_after_1, before_after_2, before_after_3 = st.columns(3)
            before_after_1.metric(
                "Current score",
                f"{float(outgoing['suggestion_score']):.1f}",
            )
            before_after_2.metric(
                "Replacement score",
                f"{float(best_pick['suggestion_score']):.1f}",
                delta=f"+{gain:.1f}",
            )
            before_after_3.metric(
                "Bank after transfer",
                f"£{money_left:.1f}m",
            )

            st.markdown("### Alternative recommendations")

            alternative_columns = st.columns(
                min(3, len(positive_candidates))
            )

            for card_column, (_, candidate) in zip(
                alternative_columns,
                positive_candidates.head(3).iterrows(),
            ):
                with card_column:
                    candidate_name = html.escape(
                        str(candidate["web_name"])
                    )
                    candidate_team = html.escape(
                        str(candidate["team_name"])
                    )
                    candidate_logo = safe_image_url(
                        candidate.get("team_logo")
                    )
                    logo_html = (
                        f'<img class="club-logo" '
                        f'src="{html.escape(candidate_logo)}" '
                        f'alt="{candidate_team}">'
                        if candidate_logo
                        else ""
                    )

                    best_categories = []
                    for metric, label in reason_metrics:
                        if float(candidate.get(metric, 0) or 0) >= float(
                            outgoing.get(metric, 0) or 0
                        ) + 4:
                            best_categories.append(label)

                    summary_reason = (
                        ", ".join(best_categories[:2])
                        if best_categories
                        else "stronger overall balance"
                    )

                    render_html(
                        f"""
                            <div class="player-card" style="min-height:250px;">
                                <div class="player-card-top">
                                    <div>
                                        <div style="
                                            color:#8d8392;
                                            font-size:.72rem;
                                            font-weight:800;
                                            text-transform:uppercase;
                                        ">
                                            Alternative
                                        </div>
                                        <h3>{candidate_name}</h3>
                                        <div class="player-meta">
                                            {candidate_team} ·
                                            {html.escape(str(candidate['position']))}
                                        </div>
                                    </div>
                                    {logo_html}
                                </div>

                                <div class="score-row">
                                    <span class="score-pill">
                                        +{float(candidate['score_gain']):.1f}
                                    </span>
                                    <span class="price-pill">
                                        £{float(candidate['price']):.1f}m
                                    </span>
                                </div>

                                <div class="reason">
                                    Best for {html.escape(summary_reason)}.
                                    Leaves £{float(candidate['money_remaining']):.1f}m
                                    in the bank.
                                </div>
                            </div>
                            """
                    )

            with affordable_players_container:
                st.markdown("### Other affordable players")
                st.caption(
                    "Additional same-position options that fit your budget, "
                    "ranked using your selected transfer preference."
                )

                detailed_columns = [
                    "team_logo",
                    "web_name",
                    "team_short",
                    "price",
                    "suggestion_score",
                    "score_gain",
                    "money_remaining",
                ]

                affordable_table = candidates.head(8)[
                    [
                        column
                        for column in detailed_columns
                        if column in candidates.columns
                    ]
                ].rename(
                    columns={
                        "team_logo": "Club",
                        "web_name": "Player",
                        "team_short": "Team",
                        "price": "Price",
                        "suggestion_score": "Score",
                        "score_gain": "Gain",
                        "money_remaining": "Money left",
                    }
                )

                st.dataframe(
                    affordable_table,
                    hide_index=True,
                    use_container_width=True,
                    height=430,
                    column_config={
                        "Club": st.column_config.ImageColumn(
                            "Club",
                            width="small",
                        ),
                        "Player": st.column_config.TextColumn(
                            "Player",
                            width="medium",
                        ),
                        "Team": st.column_config.TextColumn(
                            "Team",
                            width="small",
                        ),
                        "Price": st.column_config.NumberColumn(
                            "Price",
                            format="£%.1fm",
                            width="small",
                        ),
                        "Score": st.column_config.NumberColumn(
                            "Score",
                            format="%.1f",
                            width="small",
                        ),
                        "Gain": st.column_config.NumberColumn(
                            "Gain",
                            format="%+.1f",
                            width="small",
                        ),
                        "Money left": st.column_config.NumberColumn(
                            "Money left",
                            format="£%.1fm",
                            width="small",
                        ),
                    },
                )


        st.caption(
            "Recommendations use your active sidebar weights and only compare "
            "players in the same FPL position who fit the available budget."
        )


with detail_tab:
    selected_name = st.selectbox(
        "Player",
        scored["web_name"].tolist(),
    )

    player = scored[
        scored["web_name"] == selected_name
    ].iloc[0]

    player_name = html.escape(str(player["web_name"]))
    team_name = html.escape(str(player["team_name"]))
    position_name = html.escape(str(player["position"]))
    player_photo = safe_image_url(player.get("player_photo"))
    team_logo = safe_image_url(player.get("team_logo"))

    photo_html = (
        f'<img class="detail-player-photo" src="{html.escape(player_photo)}" '
        f'alt="{player_name}">'
        if player_photo
        else '<div class="player-placeholder">👤</div>'
    )

    logo_html = (
        f'<img class="detail-club-logo" src="{html.escape(team_logo)}" '
        f'alt="{team_name}">'
        if team_logo
        else ""
    )

    st.markdown(
        dedent(
            f"""
            <div class="detail-header">
                {photo_html}
                {logo_html}
                <div>
                    <div style="
                        color:#807586;
                        font-size:0.85rem;
                        font-weight:700;
                        text-transform:uppercase;
                        letter-spacing:0.08em;
                    ">
                        {team_name} · {position_name}
                    </div>
                    <h2 style="margin:0.2rem 0 0;color:#2b1731;">
                        {player_name}
                    </h2>
                </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    d1, d2, d3, d4 = st.columns(4)
    d1.metric(
        "Suggestion score",
        f"{player['suggestion_score']:.1f}",
    )
    d2.metric(
        "Price",
        f"£{player['price']:.1f}m",
    )
    d3.metric(
        "Recent points",
        f"{player['recent_points']:.0f}",
    )
    d4.metric(
        "Official availability",
        f"{player['chance']:.0f}%",
    )

    st.write(why_player(player))

    if player.get("news"):
        st.warning(f"Official FPL news: {player['news']}")

    if player.get("secondary_status"):
        st.info(
            f"Secondary source: {player['secondary_status']}"
        )

    try:
        summary = get_element_summary(int(player["player_id"]))
        history = pd.DataFrame(summary.get("history", []))
        upcoming = pd.DataFrame(summary.get("fixtures", []))

        if not history.empty:
            keep = [
                column
                for column in [
                    "round",
                    "opponent_team",
                    "total_points",
                    "minutes",
                    "goals_scored",
                    "assists",
                    "expected_goals",
                    "expected_assists",
                    "value",
                ]
                if column in history.columns
            ]

            st.markdown("#### Match history from element-summary")
            st.dataframe(
                history[keep].tail(10),
                hide_index=True,
                use_container_width=True,
            )

        if not upcoming.empty:
            keep = [
                column
                for column in [
                    "event",
                    "is_home",
                    "difficulty",
                    "kickoff_time",
                    "team_h",
                    "team_a",
                ]
                if column in upcoming.columns
            ]

            st.markdown("#### Upcoming fixtures from element-summary")
            st.dataframe(
                upcoming[keep].head(8),
                hide_index=True,
                use_container_width=True,
            )

    except FPLDataError as exc:
        st.warning(str(exc))


with methodology_tab:
    st.markdown(
        """
### Formula

Each component is converted to a 0–100 score, mostly using
percentile ranks among current players.

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
        st.info(
            "Secondary injury scraping is disabled. "
            "Set SECONDARY_INJURY_URL as an environment variable "
            "or Streamlit secret to enable the generic best-effort scraper."
        )
    else:
        st.success(
            f"Secondary injury rows loaded: {len(secondary)}"
        )
        st.dataframe(
            secondary,
            hide_index=True,
            use_container_width=True,
        )

    st.write(
        "Official FPL endpoints are public but undocumented and can "
        "change without notice. Cached data expires after 30 minutes."
    )
