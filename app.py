from __future__ import annotations

import html
import re
from textwrap import dedent
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

from ui_styles import apply_global_styles

from explanations import ai_scout_explanation, recommendation_tag, why_player
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
from squad_engine import (
    analyze_budget,
    chip_readiness,
    choose_captains,
    fixture_matrix,
    rate_squad,
    select_best_starting_xi,
    validate_squad,
)
from optimizer import build_wildcard_squad, optimize_two_transfers
from phase4_explanations import (
    budget_warnings,
    squad_summary,
    starting_xi_summary,
    wildcard_summary,
)
from ai_engine import (
    captain_picks,
    differential_picks,
    fixture_swing_picks,
    price_watch,
    scout_verdict,
)


st.set_page_config(
    page_title="FPL Scout",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_styles()


def safe_number(value: object, default: float = 0.0) -> float:
    """Return a finite number for UI rendering."""
    try:
        numeric = float(value)
        if pd.isna(numeric):
            return default
        return numeric
    except (TypeError, ValueError):
        return default


def ui_text(value: object, fallback: str = "N/A") -> str:
    """Return professional fallback text for missing UI values."""
    if value is None:
        return fallback
    try:
        if pd.isna(value):
            return fallback
    except (TypeError, ValueError):
        pass
    cleaned = str(value).strip()
    return cleaned or fallback


def reset_model_controls() -> None:
    """Restore sidebar model controls to their documented defaults."""
    st.session_state["ui_lookback"] = 5
    st.session_state["ui_horizon"] = 5
    for name, value in DEFAULT_WEIGHTS.items():
        st.session_state[f"ui_weight_{name}"] = int(value)


def reset_ranking_filters(default_price: float) -> None:
    """Restore player-ranking filters."""
    st.session_state["rank_position"] = "All"
    st.session_state["rank_max_price"] = float(default_price)
    st.session_state["rank_team"] = "All"


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



def score_band_class(score: float) -> str:
    if score < 40:
        return "weak"
    if score < 60:
        return "watch"
    if score < 75:
        return "good"
    return "strong"



def fixture_difficulty_category(value: float) -> str:
    """Convert official FPL difficulty (1-5) into manager-friendly wording."""
    try:
        difficulty = float(value)
    except (TypeError, ValueError):
        return "Unknown"

    if difficulty <= 2:
        return "Easy"
    if difficulty < 4:
        return "Medium"
    return "Hard"


def fixture_category_display(value: float) -> str:
    category = fixture_difficulty_category(value)
    if category == "Easy":
        return "🟢 Easy"
    if category == "Medium":
        return "🟡 Medium"
    if category == "Hard":
        return "🔴 Hard"
    return "⚪ Unknown"



def fixture_strip_html(opponents: object, average_fdr: float) -> str:
    raw = str(opponents or "").strip()
    if not raw:
        return '<span class="fixture-pill unknown">No fixture data</span>'

    category = fixture_difficulty_category(average_fdr).lower()
    items = [item.strip() for item in raw.split(",") if item.strip()][:5]
    return "".join(
        f'<span class="fixture-pill {category}">{html.escape(item)}</span>'
        for item in items
    )


def transfer_strengths(candidate: pd.Series, outgoing: pd.Series) -> List[str]:
    checks = [
        ("form_score", "better recent form"),
        ("fixtures_score", "easier upcoming fixtures"),
        ("minutes_score", "safer playing time"),
        ("availability_score", "better availability"),
        ("value_score", "better value"),
        ("team_impact_score", "stronger team impact"),
    ]
    strengths: List[str] = []
    for column, label in checks:
        if float(candidate.get(column, 0) or 0) >= float(outgoing.get(column, 0) or 0) + 4:
            strengths.append(label)

    if float(candidate.get("net_transfers_event", 0) or 0) > float(outgoing.get("net_transfers_event", 0) or 0):
        strengths.append("stronger manager momentum")

    if float(candidate.get("selected_by_percent", 0) or 0) < 10:
        strengths.append("differential potential")

    return strengths[:4]


def transfer_risks(candidate: pd.Series) -> List[str]:
    risks: List[str] = []
    if float(candidate.get("chance", 100) or 100) < 100:
        risks.append("availability concern")
    if float(candidate.get("minutes_score", 0) or 0) < 55:
        risks.append("rotation risk")
    if float(candidate.get("avg_fdr", 3) or 3) >= 3.5:
        risks.append("difficult fixture run")
    if float(candidate.get("net_transfers_event", 0) or 0) < 0:
        risks.append("negative transfer trend")
    if not risks:
        risks.append("no major model warning")
    return risks[:3]


def transfer_confidence(candidate: pd.Series) -> float:
    values = [
        float(candidate.get("minutes_score", 0) or 0),
        float(candidate.get("availability_score", 0) or 0),
        float(candidate.get("fixtures_score", 0) or 0),
        float(candidate.get("form_score", 0) or 0),
    ]
    return max(0.0, min(100.0, sum(values) / len(values)))


def render_transfer_candidate_card(
    candidate: pd.Series,
    outgoing: pd.Series,
    rank: int,
    max_budget: float,
) -> None:
    name = html.escape(str(candidate.get("web_name", "Unknown")))
    team = html.escape(str(candidate.get("team_name", "Unknown")))
    position = html.escape(str(candidate.get("position", "")))
    photo = safe_image_url(candidate.get("player_photo"))
    logo = safe_image_url(candidate.get("team_logo"))
    gain = float(candidate.get("score_gain", 0) or 0)
    price = float(candidate.get("price", 0) or 0)
    bank_left = max_budget - price
    confidence = transfer_confidence(candidate)

    photo_html = (
        f'<img class="advisor-photo" src="{html.escape(photo)}" alt="{name}">'
        if photo
        else '<div class="player-placeholder">👤</div>'
    )
    logo_html = (
        f'<img class="advisor-logo" src="{html.escape(logo)}" alt="{team}">'
        if logo
        else ""
    )

    strengths = transfer_strengths(candidate, outgoing)
    risks = transfer_risks(candidate)

    render_html(
        f"""
        <div class="advisor-card {'best' if rank == 1 else ''}">
            <div class="advisor-rank">
                {'Best recommendation' if rank == 1 else f'Alternative #{rank}'}
            </div>
            <div class="advisor-player-row">
                {photo_html}
                {logo_html}
                <div>
                    <div class="advisor-name">{name}</div>
                    <div class="advisor-sub">{team} · {position}</div>
                </div>
            </div>

            <div class="advisor-metrics">
                <div class="advisor-metric">
                    <div class="k">Overall score</div>
                    <div class="v">{float(candidate.get('suggestion_score', 0)):.1f}/100</div>
                </div>
                <div class="advisor-metric">
                    <div class="k">Score gain</div>
                    <div class="v">{gain:+.1f}</div>
                </div>
                <div class="advisor-metric">
                    <div class="k">Price</div>
                    <div class="v">£{price:.1f}m</div>
                </div>
                <div class="advisor-metric">
                    <div class="k">Bank left</div>
                    <div class="v">£{bank_left:.1f}m</div>
                </div>
                <div class="advisor-metric">
                    <div class="k">Ownership</div>
                    <div class="v">{float(candidate.get('selected_by_percent', 0)):.1f}%</div>
                </div>
                <div class="advisor-metric">
                    <div class="k">Confidence</div>
                    <div class="v">{confidence:.0f}%</div>
                </div>
            </div>

            <div class="fixture-strip">
                {fixture_strip_html(candidate.get('next_opponents', ''), float(candidate.get('avg_fdr', 3) or 3))}
            </div>

            <div class="pros-cons">
                <div class="pros">
                    <strong>Why to buy</strong><br>
                    {'<br>'.join('✓ ' + html.escape(item) for item in strengths) if strengths else '✓ Balanced improvement'}
                </div>
                <div class="cons">
                    <strong>Watch-outs</strong><br>
                    {'<br>'.join('• ' + html.escape(item) for item in risks)}
                </div>
            </div>
        </div>
        """
    )


def render_colored_breakdown(rows: List[Tuple[str, float]]) -> None:
    html_rows = []

    for label, raw_score in rows:
        score = max(0.0, min(100.0, float(raw_score)))
        band = score_band_class(score)

        html_rows.append(
            f"""
            <div class="breakdown-row">
                <div class="breakdown-label">{html.escape(label)}</div>
                <div class="breakdown-track">
                    <div class="breakdown-fill fill-{band}"
                         style="width:{score:.1f}%;">
                    </div>
                </div>
                <div class="breakdown-value value-{band}">
                    {score:.1f}
                </div>
            </div>
            """
        )

    render_html(
        """
        <div class="score-legend">
            <div class="score-weak">0–39<br>Weak</div>
            <div class="score-watch">40–59<br>Monitor</div>
            <div class="score-good">60–74<br>Good</div>
            <div class="score-strong">75–100<br>Strong</div>
        </div>
        <div class="breakdown-grid">
        """
        + "".join(html_rows)
        + "</div>"
    )



def _table_value_text(
    column: str,
    value: object,
    formats: Dict[str, str],
) -> str:
    """Format a table value with a professional missing-value fallback."""
    if value is None:
        return "N/A"
    try:
        if pd.isna(value):
            return "N/A"
    except (TypeError, ValueError):
        pass

    if column in formats:
        try:
            return formats[column].format(float(value))
        except (TypeError, ValueError):
            return ui_text(value)

    if isinstance(value, float):
        return f"{value:.1f}"
    return ui_text(value)


def render_pinned_player_table(
    frame: pd.DataFrame,
    *,
    key: str,
    pinned_columns: Tuple[str, ...] = ("Club", "Player", "Position", "Price"),
    image_columns: Tuple[str, ...] = ("Club", "Photo"),
    progress_columns: Tuple[str, ...] = (),
    formats: Dict[str, str] | None = None,
    height: int = 590,
) -> None:
    """Render a sortable table whose player identity columns stay visible."""
    if frame.empty:
        render_html(
            """
            <div class="empty-state">
                <div class="empty-state-icon">🔎</div>
                <div class="empty-state-title">No table results</div>
                <div class="empty-state-text">
                    Change the active filters or selections and try again.
                </div>
            </div>
            """
        )
        return

    formats = formats or {}
    table = frame.copy()

    if "Pos" in table.columns and "Position" not in table.columns:
        table = table.rename(columns={"Pos": "Position"})

    ordered_pinned = [column for column in pinned_columns if column in table.columns]
    remaining = [column for column in table.columns if column not in ordered_pinned]
    table = table[ordered_pinned + remaining]

    sort_left, sort_right = st.columns([2, 1])
    sort_column = sort_left.selectbox(
        "Sort table by",
        options=list(table.columns),
        key=f"{key}_sort_column",
        label_visibility="collapsed",
    )
    descending = sort_right.toggle(
        "Descending",
        value=True,
        key=f"{key}_sort_desc",
    )

    numeric_sort = pd.to_numeric(table[sort_column], errors="coerce")
    try:
        if numeric_sort.notna().any():
            table = table.assign(_sort_value=numeric_sort).sort_values(
                "_sort_value",
                ascending=not descending,
                na_position="last",
            ).drop(columns="_sort_value")
        else:
            table = table.sort_values(
                sort_column,
                ascending=not descending,
                na_position="last",
                key=lambda series: series.astype(str).str.lower(),
            )
    except (TypeError, ValueError):
        pass

    st.caption(
        "Club/photo, Player, Position and Price remain visible while you scroll "
        "horizontally."
    )

    widths = {
        "Club": 58,
        "Photo": 58,
        "Player": 170,
        "Position": 82,
        "Price": 82,
    }

    left_offsets: Dict[str, int] = {}
    current_left = 0
    for column in ordered_pinned:
        left_offsets[column] = current_left
        current_left += widths.get(column, 110)

    header_cells = []
    for column in table.columns:
        is_pinned = column in ordered_pinned
        css_class = "pinned-column" if is_pinned else ""
        style = (
            f' style="left:{left_offsets[column]}px;'
            f'min-width:{widths.get(column, 120)}px;'
            f'width:{widths.get(column, 120)}px;"'
            if is_pinned
            else ""
        )
        header_cells.append(
            f'<th class="{css_class}"{style}>{html.escape(str(column))}</th>'
        )

    rows = []
    for _, row in table.iterrows():
        cells = []
        for column in table.columns:
            value = row.get(column)
            is_pinned = column in ordered_pinned
            css_class = "pinned-column" if is_pinned else ""
            style = (
                f' style="left:{left_offsets[column]}px;'
                f'min-width:{widths.get(column, 120)}px;'
                f'width:{widths.get(column, 120)}px;"'
                if is_pinned
                else ""
            )

            if column in image_columns:
                image_url = safe_image_url(value)
                content = (
                    f'<img class="cell-image" src="{html.escape(image_url)}" alt="">'
                    if image_url
                    else "—"
                )
            elif column == "Player":
                content = (
                    f'<span class="player-cell">'
                    f'{html.escape(_table_value_text(column, value, formats))}'
                    f'</span>'
                )
            elif column == "Position":
                content = (
                    f'<span class="position-chip">'
                    f'{html.escape(_table_value_text(column, value, formats))}'
                    f'</span>'
                )
            elif column == "Price":
                content = (
                    f'<span class="price-cell">'
                    f'{html.escape(_table_value_text(column, value, formats))}'
                    f'</span>'
                )
            elif column in progress_columns:
                numeric = safe_number(value)
                bounded = max(0.0, min(100.0, numeric))
                content = (
                    '<div class="table-progress">'
                    '<div class="table-progress-track">'
                    f'<div class="table-progress-fill" style="width:{bounded:.1f}%;">'
                    '</div></div>'
                    f'<div class="table-progress-value">{numeric:.1f}</div>'
                    '</div>'
                )
            else:
                text = _table_value_text(column, value, formats)
                numeric_value = safe_number(value, 0.0)
                movement_column = (
                    "gain" in column.lower() or "transfer" in column.lower()
                )
                value_class = (
                    "positive-value"
                    if movement_column and numeric_value > 0
                    else "negative-value"
                    if movement_column and numeric_value < 0
                    else ""
                )
                content = f'<span class="{value_class}">{html.escape(text)}</span>'

            cells.append(f'<td class="{css_class}"{style}>{content}</td>')

        rows.append("<tr>" + "".join(cells) + "</tr>")

    render_html(
        f"""
        <div class="pinned-table-wrap" style="max-height:{int(height)}px;">
            <table class="pinned-player-table">
                <thead><tr>{''.join(header_cells)}</tr></thead>
                <tbody>{''.join(rows)}</tbody>
            </table>
        </div>
        """
    )


def render_sticky_rankings_table(table_data: pd.DataFrame) -> None:
    """Render rankings with pinned Club, Player, Position and Price columns."""
    frame = pd.DataFrame(
        {
            "Club": table_data.get("team_logo", ""),
            "Player": table_data.get("web_name", "N/A"),
            "Position": table_data.get("position", "N/A"),
            "Price": pd.to_numeric(table_data.get("price", 0), errors="coerce"),
            "Recommendation": pd.to_numeric(
                table_data.get("suggestion_score", 0), errors="coerce"
            ),
            "Form": pd.to_numeric(table_data.get("form_score", 0), errors="coerce"),
            "Total points": pd.to_numeric(
                table_data.get("total_points", 0), errors="coerce"
            ),
            "Owned by": pd.to_numeric(
                table_data.get("selected_by_percent", 0), errors="coerce"
            ),
            "Availability": pd.to_numeric(
                table_data.get("availability_score", 0), errors="coerce"
            ),
            "Fixtures": pd.to_numeric(
                table_data.get("fixtures_score", 0), errors="coerce"
            ),
            "Next fixtures": table_data.get("next_opponents", "N/A"),
            "Net transfers": pd.to_numeric(
                table_data.get("net_transfers_event", 0), errors="coerce"
            ),
            "Tag": table_data.apply(recommendation_tag, axis=1),
        }
    )

    render_pinned_player_table(
        frame,
        key="main_rankings",
        progress_columns=("Recommendation", "Form", "Availability", "Fixtures"),
        formats={
            "Price": "£{:.1f}m",
            "Total points": "{:.0f}",
            "Owned by": "{:.1f}%",
            "Net transfers": "{:+,.0f}",
        },
        height=610,
    )


def render_player_card(player: pd.Series, rank: int) -> None:
    """Render a complete player recommendation card."""
    player_name = html.escape(ui_text(player.get("web_name")))
    team_name = html.escape(ui_text(player.get("team_name")))
    position = html.escape(ui_text(player.get("position")))
    explanation = html.escape(ui_text(player.get("Why this player"), "No explanation available."))

    photo = safe_image_url(player.get("player_photo"))
    logo = safe_image_url(player.get("team_logo"))

    if photo:
        photo_html = (
            f'<div class="player-image-shell">'
            f'<img class="player-photo" src="{html.escape(photo)}" alt="{player_name}" '
            f'onerror="this.style.display=\'none\';this.parentElement.classList.add(\'image-failed\');">'
            f'<div class="player-photo-fallback" aria-hidden="true">👤</div>'
            f'</div>'
        )
    else:
        photo_html = (
            '<div class="player-image-shell image-failed">'
            '<div class="player-photo-fallback" style="display:flex;" aria-hidden="true">👤</div>'
            '</div>'
        )

    logo_html = (
        f'<img class="club-logo" src="{html.escape(logo)}" alt="{team_name} club badge">'
        if logo
        else ""
    )

    fixtures = ui_text(player.get("next_opponents"), "Fixture data unavailable")
    fixture_preview = ", ".join(
        item.strip() for item in fixtures.split(",")[:3] if item.strip()
    ) or "N/A"

    render_html(
        f"""
        <article class="player-card" aria-label="{player_name} recommendation card">
            <div class="player-card-top">
                {photo_html}
                <div>
                    <div class="pick-rank">PICK #{rank}</div>
                    {logo_html}
                </div>
            </div>

            <h3>{player_name}</h3>
            <div class="player-meta">{team_name} · {position}</div>

            <div class="player-primary-stats">
                <div class="player-stat">
                    <div class="k">Form</div>
                    <div class="v">{safe_number(player.get('form_score')):.1f}</div>
                </div>
                <div class="player-stat">
                    <div class="k">Points</div>
                    <div class="v">{safe_number(player.get('total_points')):.0f}</div>
                </div>
                <div class="player-stat">
                    <div class="k">Owned</div>
                    <div class="v">{safe_number(player.get('selected_by_percent')):.1f}%</div>
                </div>
            </div>

            <div class="fixture-strip" aria-label="Upcoming fixtures">
                {fixture_strip_html(player.get('next_opponents', ''), safe_number(player.get('avg_fdr'), 3.0))}
            </div>

            <div class="score-row">
                <span class="score-pill" title="Recommendation score">
                    {safe_number(player.get('suggestion_score')):.1f}/100
                </span>
                <span class="price-pill">
                    £{safe_number(player.get('price')):.1f}m
                </span>
            </div>

            <div class="reason">
                <strong>Why:</strong> {explanation}
            </div>
        </article>
        """
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



# ==================== PHASE 4 GUI HELPERS ====================

def player_selector_labels(frame: pd.DataFrame) -> Dict[str, int]:
    """Build readable, unique labels for the 15-player squad selector."""
    labels: Dict[str, int] = {}
    for _, row in frame.sort_values(
        ["position", "suggestion_score"],
        ascending=[True, False],
    ).iterrows():
        label = (
            f"{row.get('web_name', 'Unknown')} · "
            f"{row.get('team_short', '')} · "
            f"{row.get('position', '')} · "
            f"£{float(row.get('price', 0)):.1f}m"
        )
        labels[label] = int(row["player_id"])
    return labels


def render_squad_score_cards(ratings: object) -> None:
    """Render eight squad ratings as football-green progress cards."""
    metrics = [
        ("Overall", float(ratings.overall)),
        ("Starting XI", float(ratings.starting_xi)),
        ("Bench", float(ratings.bench)),
        ("Captaincy", float(ratings.captaincy)),
        ("Fixtures", float(ratings.fixtures)),
        ("Availability", float(ratings.availability)),
        ("Value", float(ratings.value)),
        ("Risk", float(ratings.risk)),
    ]

    cards = []
    for label, value in metrics:
        bar_value = 100.0 - value if label == "Risk" else value
        cards.append(
            f"""
            <div class="squad-score-card">
                <div class="label">{html.escape(label)}</div>
                <div class="value">{value:.1f}</div>
                <div class="bar">
                    <div class="fill" style="width:{max(0, min(100, bar_value)):.1f}%"></div>
                </div>
            </div>
            """
        )

    render_html('<div class="squad-score-grid">' + "".join(cards) + "</div>")


def render_pitch(starting_xi: pd.DataFrame, formation: str) -> None:
    """Place the recommended XI on a CSS football pitch."""
    if starting_xi.empty:
        st.info("A legal starting XI is not available.")
        return

    rows = []
    for position in ["FWD", "MID", "DEF", "GK"]:
        player_cards = []
        for _, player_row in starting_xi[starting_xi["position"] == position].iterrows():
            photo = safe_image_url(player_row.get("player_photo"))
            image = (
                f'<img src="{html.escape(photo)}" alt="">'
                if photo
                else '<div style="font-size:2rem;">👤</div>'
            )
            player_cards.append(
                f"""
                <div class="pitch-player">
                    {image}
                    <div class="name">{html.escape(str(player_row.get('web_name', 'Unknown')))}</div>
                    <div class="meta">
                        {html.escape(str(player_row.get('team_short', '')))}
                        · {float(player_row.get('suggestion_score', 0)):.1f}
                    </div>
                </div>
                """
            )
        rows.append('<div class="pitch-row">' + "".join(player_cards) + "</div>")

    render_html(
        f"""
        <div style="margin:.4rem 0 .8rem;font-weight:850;color:#0b6f40;">
            Recommended formation: {html.escape(formation)}
        </div>
        <div class="pitch">{''.join(rows)}</div>
        """
    )


def render_bench(bench: pd.DataFrame) -> None:
    """Render substitutes as user-friendly themed cards."""
    if bench.empty:
        return

    cards = []
    for order, (_, player_row) in enumerate(bench.iterrows(), start=1):
        player_name = html.escape(str(player_row.get("web_name", "Unknown")))
        position = html.escape(str(player_row.get("position", "")))
        team = html.escape(str(player_row.get("team_short", "")))
        score = float(player_row.get("suggestion_score", 0) or 0)

        cards.append(
            f"""
            <div class="bench-card">
                <div class="bench-order">Bench option {order}</div>
                <div class="bench-name">{player_name}</div>
                <div class="bench-meta">
                    <span class="bench-chip">{position}</span>
                    <span class="bench-chip">{team}</span>
                    <span class="bench-chip score">Model score {score:.1f}</span>
                </div>
            </div>
            """
        )

    render_html('<div class="bench-strip">' + "".join(cards) + "</div>")


def render_chip_cards(readiness: Dict[str, Dict[str, object]]) -> None:
    """Render readiness cards for Wildcard, Free Hit, Bench Boost and Triple Captain."""
    cards = []
    for chip, details in readiness.items():
        cards.append(
            f"""
            <div class="chip-card">
                <div class="label">{html.escape(chip)}</div>
                <div class="value">
                    {html.escape(str(details.get('level', 'Low')))}
                    · {float(details.get('score', 0)):.0f}
                </div>
                <div style="margin-top:.45rem;color:#6c7570;font-size:.78rem;">
                    {html.escape(str(details.get('reason', '')))}
                </div>
            </div>
            """
        )
    render_html('<div class="chip-grid">' + "".join(cards) + "</div>")


st.markdown(
    """
    <div class="hero">
        <div class="hero-kicker">Explainable Fantasy Premier League intelligence</div>
        <h1>Make smarter FPL decisions</h1>
        <p>
            Rank players, compare transfer targets, optimize your squad and plan
            future gameweeks using live FPL data and a transparent scoring model.
        </p>
        <div class="hero-tags">
            <span class="hero-tag">Live player data</span>
            <span class="hero-tag">Sortable rankings</span>
            <span class="hero-tag">Transfer planning</span>
            <span class="hero-tag">Squad intelligence</span>
        </div>
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
        key="ui_lookback",
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
        key="ui_horizon",
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
        key="ui_weight_form",
        help="Rewards recent FPL points and expected goal involvement.",
    )
    st.caption("Recent points, attacking output and xGI.")

    weights["fixtures"] = st.slider(
        "Fixture quality",
        0,
        100,
        int(DEFAULT_WEIGHTS["fixtures"]),
        key="ui_weight_fixtures",
        help="Rewards players with easier upcoming opponents.",
    )
    st.caption("Upcoming difficulty and double-gameweek potential.")

    weights["minutes"] = st.slider(
        "Playing-time security",
        0,
        100,
        int(DEFAULT_WEIGHTS["minutes"]),
        key="ui_weight_minutes",
        help="Rewards regular starters and reduces rotation risk.",
    )
    st.caption("Recent minutes, starts and season involvement.")

    weights["availability"] = st.slider(
        "Fitness and availability",
        0,
        100,
        int(DEFAULT_WEIGHTS["availability"]),
        key="ui_weight_availability",
        help="Uses official chance-of-playing and injury news.",
    )
    st.caption("Injury status, suspension and chance of playing.")

    weights["value"] = st.slider(
        "Budget value",
        0,
        100,
        int(DEFAULT_WEIGHTS["value"]),
        key="ui_weight_value",
        help="Rewards players delivering more output for their price.",
    )
    st.caption("Points per £m, price movement and transfer momentum.")

    weights["team_impact"] = st.slider(
        "Team and player influence",
        0,
        100,
        int(DEFAULT_WEIGHTS["team_impact"]),
        key="ui_weight_team_impact",
        help="Measures team strength and the player's contribution.",
    )
    st.caption("Club quality plus the player's role within the team.")

    st.button(
        "Reset model settings",
        use_container_width=True,
        on_click=reset_model_controls,
        help="Restore the default analysis windows and ranking weights.",
    )

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


rank_tab, compare_tab, transfer_tab, ai_tab, team_tab, detail_tab, methodology_tab = st.tabs(
    [
        "Player rankings",
        "Compare players",
        "Transfer planner",
        "AI Help Center",
        "Team Center",
        "Player detail",
        "Methodology & data health",
    ]
)


with rank_tab:
    maximum_available_price = float(max(4.0, scored["price"].max()))
    team_options = ["All"] + sorted(
        scored["team_name"].dropna().unique().tolist()
    )

    st.markdown("### Find the right player")
    st.caption(
        "Choose a position first, then narrow the list by price or club. "
        "All filters update the cards and sortable rankings table."
    )

    position = st.radio(
        "Position",
        ["All", "GK", "DEF", "MID", "FWD"],
        horizontal=True,
        key="rank_position",
        help="GK = goalkeeper, DEF = defender, MID = midfielder, FWD = forward.",
    )

    filter_left, filter_middle, filter_right = st.columns([1, 1.35, .7])
    max_price = filter_left.slider(
        "Maximum price (£m)",
        3.5,
        maximum_available_price,
        maximum_available_price,
        0.1,
        key="rank_max_price",
    )
    team_filter = filter_middle.selectbox(
        "Club",
        team_options,
        key="rank_team",
    )
    filter_right.button(
        "Clear filters",
        use_container_width=True,
        on_click=reset_ranking_filters,
        args=(maximum_available_price,),
    )

    filtered = scored[scored["price"] <= max_price].copy()

    if position != "All":
        filtered = filtered[filtered["position"] == position]

    if team_filter != "All":
        filtered = filtered[filtered["team_name"] == team_filter]

    render_html(
        f"""
        <div class="filter-summary" aria-label="Active player filters">
            <span class="filter-chip">Position: {html.escape(position)}</span>
            <span class="filter-chip">Maximum price: £{max_price:.1f}m</span>
            <span class="filter-chip">Club: {html.escape(team_filter)}</span>
            <span class="filter-chip">{len(filtered)} players found</span>
        </div>
        """
    )

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
        render_html(
            """
            <div class="empty-state">
                <div class="empty-state-icon">🔎</div>
                <div class="empty-state-title">No players match these filters</div>
                <div class="empty-state-text">
                    Increase the maximum price, choose another club or clear the
                    position filter to see more recommendations.
                </div>
            </div>
            """
        )
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
        "selected_by_percent",
        "ownership_label",
        "transfers_in_event",
        "transfers_out_event",
        "net_transfers_event",
        "transfer_trend",
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
        "selected_by_percent": "Selected %",
        "ownership_label": "Ownership profile",
        "transfers_in_event": "Transfers in",
        "transfers_out_event": "Transfers out",
        "net_transfers_event": "Net transfers",
        "transfer_trend": "Transfer trend",
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
        "Selected %",
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

    display_limit = st.select_slider(
        "Rows shown",
        options=[25, 50, 100, 200],
        value=50,
        help="Use fewer rows for a faster table or increase the limit to browse more players.",
    )

    render_sticky_rankings_table(filtered.head(display_limit))

    st.caption(
        "Use the sortable table for quick decisions. The downloadable raw table "
        "below contains the full set of model columns."
    )

    with st.expander("Open downloadable raw rankings table"):
        render_pinned_player_table(
            table.rename(columns={"Pos": "Position"}),
            key="raw_rankings",
            progress_columns=("Score", "Form", "Fixtures", "Minutes", "Availability", "Value", "Team impact"),
            formats={"Price": "£{:.1f}m", "Selected %": "{:.1f}%", "Net transfers": "{:+,.0f}"},
            height=560,
        )
        st.download_button(
            "Download rankings as CSV",
            data=table.to_csv(index=False).encode("utf-8"),
            file_name="fpl_player_rankings.csv",
            mime="text/csv",
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
            ("Selected by managers (%)", "selected_by_percent", False),
            ("Transfers in this GW", "transfers_in_event", False),
            ("Transfers out this GW", "transfers_out_event", True),
            ("Net transfers this GW", "net_transfers_event", False),
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
                elif column_name == "avg_fdr":
                    formatted = (
                        f"{fixture_category_display(value)} "
                        f"({value:.1f}/5)"
                    )
                elif column_name == "selected_by_percent":
                    formatted = f"{value:.1f}%"
                elif column_name in {
                    "recent_points",
                    "recent_minutes",
                    "chance",
                    "transfers_in_event",
                    "transfers_out_event",
                    "net_transfers_event",
                }:
                    formatted = f"{value:+,.0f}" if column_name == "net_transfers_event" else f"{value:,.0f}"
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
            <h2>Transfer advisor</h2>
            <p>
                Select a player to sell, set your budget, and compare the best
                same-position replacements using form, fixtures, minutes,
                ownership, transfers, value and risk.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    control_left, control_right = st.columns([1.05, 1.95], gap="large")

    with control_left:
        st.markdown("### 1. Transfer setup")

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
        )
        outgoing_id = player_label_lookup[selected_out_label]
        outgoing = scored[scored["player_id"] == outgoing_id].iloc[0]

        bank = st.number_input(
            "Money available in the bank (£m)",
            min_value=0.0,
            max_value=20.0,
            value=0.0,
            step=0.1,
        )
        max_budget = float(outgoing["price"]) + float(bank)

        planner_priority = st.radio(
            "Transfer priority",
            [
                "Best overall",
                "Immediate returns",
                "Easy fixtures",
                "Secure starter",
                "Best value",
            ],
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
        )

        # ------------------------------------------------------------------
        # REQUIRED MODEL IMPROVEMENT FILTER
        # ------------------------------------------------------------------
        # This control compares every replacement candidate with the selected
        # outgoing player's overall recommendation score.
        #
        # Example:
        #   Current player score = 62
        #   Required improvement = +5
        #   Candidate must score at least 67 to appear.
        #
        # A very high requirement can legitimately return no players. A negative
        # value includes sideways or slightly lower-scoring moves, which can be
        # useful when the manager wants to save money for another transfer.
        # ------------------------------------------------------------------
        min_gain = st.select_slider(
            "How much better must the replacement be?",
            options=[-10.0, -5.0, 0.0, 2.0, 5.0, 10.0, 15.0, 20.0],
            value=0.0,
            format_func=lambda value: (
                f"Allow {abs(value):.0f}-point drop"
                if value < 0
                else "Any improvement"
                if value == 0
                else f"At least +{value:.0f} points"
            ),
            help=(
                "This compares the replacement's overall model score with the "
                "player you are selling. For example, if your current player "
                "scores 62 and you choose +5, only replacements scoring 67 or "
                "higher will be shown. This is a model-score difference, not a "
                "prediction of extra FPL points."
            ),
        )

        current_model_score = float(outgoing.get("suggestion_score", 0) or 0)
        required_candidate_score = current_model_score + float(min_gain)

        if min_gain < 0:
            filter_explanation = (
                f"Showing replacements scoring at least "
                f"{required_candidate_score:.1f}/100. This allows a model drop "
                f"of up to {abs(min_gain):.0f} points and may reveal cheaper "
                f"players who free money for another upgrade."
            )
        elif min_gain == 0:
            filter_explanation = (
                f"Showing only replacements that score higher than "
                f"{current_model_score:.1f}/100, the current player's model score."
            )
        else:
            filter_explanation = (
                f"Showing only replacements scoring at least "
                f"{required_candidate_score:.1f}/100 — {min_gain:.0f} model "
                f"points above the current player."
            )

        st.caption(filter_explanation)

        if required_candidate_score > 100:
            st.warning(
                "This setting requires a score above 100, so no replacement can "
                "match it. Lower the required improvement."
            )
        elif min_gain >= 15:
            st.warning(
                "This is a very strict filter and may return no players. Try "
                "+5 or +10 for a broader search."
            )

    with control_right:
        st.markdown("### Current player")

        out_photo = safe_image_url(outgoing.get("player_photo"))
        out_logo = safe_image_url(outgoing.get("team_logo"))
        out_name = html.escape(str(outgoing["web_name"]))
        out_team = html.escape(str(outgoing["team_name"]))

        render_html(
            f"""
            <div class="advisor-card">
                <div class="advisor-player-row">
                    {
                        f'<img class="advisor-photo" src="{html.escape(out_photo)}" alt="{out_name}">'
                        if out_photo else '<div class="player-placeholder">👤</div>'
                    }
                    {
                        f'<img class="advisor-logo" src="{html.escape(out_logo)}" alt="{out_team}">'
                        if out_logo else ''
                    }
                    <div>
                        <div class="advisor-rank">Transfer out</div>
                        <div class="advisor-name">{out_name}</div>
                        <div class="advisor-sub">
                            {out_team} · {html.escape(str(outgoing['position']))}
                        </div>
                    </div>
                </div>

                <div class="transfer-summary-grid">
                    <div class="transfer-summary-card">
                        <div class="label">Current score</div>
                        <div class="value">{float(outgoing['suggestion_score']):.1f}/100</div>
                    </div>
                    <div class="transfer-summary-card">
                        <div class="label">Selling price</div>
                        <div class="value">£{float(outgoing['price']):.1f}m</div>
                    </div>
                    <div class="transfer-summary-card">
                        <div class="label">Available budget</div>
                        <div class="value">£{max_budget:.1f}m</div>
                    </div>
                    <div class="transfer-summary-card">
                        <div class="label">Ownership</div>
                        <div class="value">{float(outgoing.get('selected_by_percent', 0)):.1f}%</div>
                    </div>
                </div>

                <div class="fixture-strip">
                    {fixture_strip_html(outgoing.get('next_opponents', ''), float(outgoing.get('avg_fdr', 3) or 3))}
                </div>
            </div>
            """
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
    candidates["confidence"] = candidates.apply(
        transfer_confidence,
        axis=1,
    )

    candidates = candidates[
        candidates["score_gain"] >= min_gain
    ].sort_values(
        [priority_column, "suggestion_score", "confidence"],
        ascending=False,
    )

    top_candidates = candidates.head(5)

    st.markdown("### Top replacement options")

    if top_candidates.empty:
        render_html(
            f"""
            <div class="empty-state">
                <div class="empty-state-icon">🔄</div>
                <div class="empty-state-title">No replacement meets every filter</div>
                <div class="empty-state-text">
                    The current player scores
                    {safe_number(outgoing.get('suggestion_score')):.1f}/100 and your
                    filters require at least
                    {safe_number(outgoing.get('suggestion_score')) + float(min_gain):.1f}/100.
                    Lower the improvement requirement, add money to the bank or
                    allow same-club options.
                </div>
            </div>
            """
        )
    else:
        first_row = st.columns(min(3, len(top_candidates)))
        for rank, (column, (_, candidate)) in enumerate(
            zip(first_row, top_candidates.head(3).iterrows()),
            start=1,
        ):
            with column:
                render_transfer_candidate_card(
                    candidate,
                    outgoing,
                    rank,
                    max_budget,
                )

        if len(top_candidates) > 3:
            second_row = st.columns(len(top_candidates) - 3)
            for rank, (column, (_, candidate)) in enumerate(
                zip(second_row, top_candidates.iloc[3:].iterrows()),
                start=4,
            ):
                with column:
                    render_transfer_candidate_card(
                        candidate,
                        outgoing,
                        rank,
                        max_budget,
                    )

        st.markdown("### Side-by-side comparison")

        comparison_candidates = pd.concat(
            [
                outgoing.to_frame().T.assign(
                    score_gain=0.0,
                    money_remaining=bank,
                    confidence=transfer_confidence(outgoing),
                ),
                top_candidates,
            ],
            ignore_index=True,
        )

        comparison_rows = {
            "Player": comparison_candidates["web_name"],
            "Price": comparison_candidates["price"],
            "Overall score": comparison_candidates["suggestion_score"],
            "Score gain": comparison_candidates["score_gain"],
            "Form": comparison_candidates["form_score"],
            "Fixtures": comparison_candidates["fixtures_score"],
            "Minutes": comparison_candidates["minutes_score"],
            "Availability": comparison_candidates["availability_score"],
            "Value": comparison_candidates["value_score"],
            "Team impact": comparison_candidates["team_impact_score"],
            "Ownership %": comparison_candidates["selected_by_percent"],
            "Net transfers": comparison_candidates["net_transfers_event"],
            "Fixture outlook": comparison_candidates["avg_fdr"].apply(
                fixture_category_display
            ),
            "Confidence %": comparison_candidates["confidence"],
            "Next 5": comparison_candidates["next_opponents"],
        }

        comparison_table = pd.DataFrame(comparison_rows)

        render_pinned_player_table(
            comparison_table.assign(Position=comparison_candidates["position"].astype(str).tolist()),
            key="transfer_comparison",
            pinned_columns=("Player", "Position", "Price"),
            progress_columns=("Overall score", "Form", "Fixtures", "Minutes", "Availability", "Value", "Team impact", "Confidence %"),
            formats={"Price": "£{:.1f}m", "Score gain": "{:+.1f}", "Ownership %": "{:.1f}%", "Net transfers": "{:+,.0f}"},
            height=470,
        )

        best = top_candidates.iloc[0]
        strengths = transfer_strengths(best, outgoing)
        risks = transfer_risks(best)

        st.markdown("### Transfer verdict")
        render_html(
            f"""
            <div class="decision-callout">
                <strong>Recommended move:</strong>
                {html.escape(str(outgoing['web_name']))}
                ➜
                {html.escape(str(best['web_name']))}
                <br><br>
                <strong>Why:</strong>
                {html.escape(', '.join(strengths) if strengths else 'stronger balanced profile')}.
                <br>
                <strong>Risks:</strong>
                {html.escape(', '.join(risks))}.
                <br>
                <strong>Projected model gain:</strong>
                {float(best['score_gain']):+.1f} points on the 0–100 recommendation scale.
                <br>
                <strong>Money remaining:</strong>
                £{float(best['money_remaining']):.1f}m.
            </div>
            """
        )

    st.caption(
        "This advisor uses the data already available in your app. "
        "Projected model gain is not the same as guaranteed FPL points."
    )





with ai_tab:
    render_html(
        """
        <div class="help-center-banner">
            <h2>🤖 AI Help Center</h2>
            <p>
                Get a detailed player verdict, captain options, low-owned targets,
                transfer momentum and fixture opportunities from the same
                explainable model used throughout FPL Scout.
            </p>
        </div>
        """
    )

    scout_tab, captain_tab, differential_tab, price_tab, swing_tab = st.tabs(
        [
            "Player analysis",
            "Captain picks",
            "Differential finder",
            "Price watch",
            "Fixture swings",
        ]
    )

    with scout_tab:
        # Use player ID behind the label so players with identical surnames do not
        # select the wrong row.
        help_player_lookup = {
            (
                f"{row['web_name']} · {row['team_short']} · "
                f"{row['position']} · £{float(row['price']):.1f}m"
            ): int(row["player_id"])
            for _, row in scored.sort_values(
                ["suggestion_score", "web_name"],
                ascending=[False, True],
            ).iterrows()
        }

        selected_help_label = st.selectbox(
            "Choose a player for detailed analysis",
            options=list(help_player_lookup.keys()),
            key="ai_help_player",
        )
        selected_help_id = help_player_lookup[selected_help_label]
        help_player = scored[
            scored["player_id"] == selected_help_id
        ].iloc[0]

        verdict = scout_verdict(help_player)
        photo = safe_image_url(help_player.get("player_photo"))
        logo = safe_image_url(help_player.get("team_logo"))
        name = html.escape(str(help_player.get("web_name", "Unknown")))
        team = html.escape(str(help_player.get("team_name", "Unknown")))
        position = html.escape(str(help_player.get("position", "")))

        overall_score = safe_number(help_player.get("suggestion_score"))
        confidence_score = safe_number(help_player.get("ai_confidence"))
        risk_score = safe_number(help_player.get("risk_score"))
        availability_score = safe_number(help_player.get("availability_score"))
        form_score = safe_number(help_player.get("form_score"))
        fixture_score = safe_number(help_player.get("fixtures_score"))
        minutes_score = safe_number(help_player.get("minutes_score"))
        value_score = safe_number(help_player.get("value_score"))
        ownership = safe_number(help_player.get("selected_by_percent"))
        net_transfers = safe_number(help_player.get("net_transfers_event"))

        photo_html = (
            f'<img class="ai-player-photo" src="{html.escape(photo)}" alt="{name}" '
            f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\';">'
            f'<div class="ai-player-fallback" style="display:none;" aria-hidden="true">👤</div>'
            if photo
            else '<div class="ai-player-fallback" aria-hidden="true">👤</div>'
        )
        logo_html = (
            f'<img class="ai-player-club" src="{html.escape(logo)}" '
            f'alt="{team} club badge">'
            if logo
            else ""
        )

        risk_context = (
            "Low risk"
            if risk_score < 30
            else "Moderate risk"
            if risk_score < 60
            else "High risk"
        )
        confidence_context = (
            "Strong data agreement"
            if confidence_score >= 75
            else "Moderate data agreement"
            if confidence_score >= 55
            else "Lower-confidence signal"
        )

        render_html(
            f"""
            <section class="ai-player-dashboard" aria-label="{name} AI analysis">
                <div class="ai-player-visual">
                    {photo_html}
                </div>

                <div class="ai-player-content">
                    <div class="ai-player-topline">
                        <div class="ai-player-identity">
                            {logo_html}
                            <div>
                                <span class="ai-verdict-badge">
                                    ⚽ {html.escape(verdict.action)}
                                </span>
                                <div class="ai-player-name">{name}</div>
                                <div class="ai-player-meta">
                                    {team} · {position} ·
                                    £{safe_number(help_player.get('price')):.1f}m
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="ai-key-score-grid">
                        <div class="ai-key-score">
                            <div class="label">Overall recommendation</div>
                            <div class="value">{overall_score:.1f}</div>
                            <div class="hint">Weighted 0–100 model score</div>
                            <div class="ai-meter">
                                <div class="ai-meter-fill"
                                     style="width:{max(0, min(100, overall_score)):.1f}%;">
                                </div>
                            </div>
                        </div>

                        <div class="ai-key-score confidence">
                            <div class="label">AI confidence</div>
                            <div class="value">{confidence_score:.0f}%</div>
                            <div class="hint">{html.escape(confidence_context)}</div>
                            <div class="ai-meter">
                                <div class="ai-meter-fill"
                                     style="width:{max(0, min(100, confidence_score)):.1f}%;">
                                </div>
                            </div>
                        </div>

                        <div class="ai-key-score risk">
                            <div class="label">Risk level</div>
                            <div class="value">{risk_score:.0f}/100</div>
                            <div class="hint">{html.escape(risk_context)} · lower is better</div>
                            <div class="ai-meter">
                                <div class="ai-meter-fill"
                                     style="width:{max(0, min(100, risk_score)):.1f}%;">
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="ai-support-grid">
                        <div class="ai-support-stat">
                            <div class="k">Form</div>
                            <div class="v">{form_score:.1f}</div>
                        </div>
                        <div class="ai-support-stat">
                            <div class="k">Fixtures</div>
                            <div class="v">{fixture_score:.1f}</div>
                        </div>
                        <div class="ai-support-stat">
                            <div class="k">Minutes</div>
                            <div class="v">{minutes_score:.1f}</div>
                        </div>
                        <div class="ai-support-stat">
                            <div class="k">Availability</div>
                            <div class="v">{availability_score:.1f}</div>
                        </div>
                        <div class="ai-support-stat">
                            <div class="k">Value</div>
                            <div class="v">{value_score:.1f}</div>
                        </div>
                        <div class="ai-support-stat">
                            <div class="k">Ownership</div>
                            <div class="v">{ownership:.1f}%</div>
                        </div>
                        <div class="ai-support-stat">
                            <div class="k">Total points</div>
                            <div class="v">{safe_number(help_player.get('total_points')):.0f}</div>
                        </div>
                        <div class="ai-support-stat">
                            <div class="k">Net transfers</div>
                            <div class="v">{net_transfers:+,.0f}</div>
                        </div>
                        <div class="ai-support-stat">
                            <div class="k">Captain score</div>
                            <div class="v">{safe_number(help_player.get('captain_score')):.1f}</div>
                        </div>
                        <div class="ai-support-stat">
                            <div class="k">Differential</div>
                            <div class="v">{safe_number(help_player.get('differential_score')):.1f}</div>
                        </div>
                    </div>

                    <div class="ai-fixture-row">
                        <div class="ai-fixture-label">Upcoming fixtures</div>
                        <div class="fixture-strip">
                            {fixture_strip_html(
                                help_player.get('next_opponents', ''),
                                safe_number(help_player.get('avg_fdr'), 3.0)
                            )}
                        </div>
                    </div>
                </div>
            </section>
            """
        )

        render_html(
            f"""
            <div class="decision-callout">
                <strong>{html.escape(verdict.headline)}</strong><br>
                {html.escape(verdict.summary)}
            </div>
            """
        )

        # Detailed analysis is split into clear football-management questions.
        attacking_text = (
            f"Season xG {float(help_player.get('expected_goals', 0)):.1f}, "
            f"xA {float(help_player.get('expected_assists', 0)):.1f}, and "
            f"xGI {float(help_player.get('expected_goal_involvements', 0)):.1f}. "
            f"Recent xGI: {float(help_player.get('recent_xgi', 0)):.2f}."
        )
        fixture_text = (
            f"Average FDR {float(help_player.get('avg_fdr', 0)):.2f}. "
            f"Next opponents: {str(help_player.get('next_opponents', 'No data')) or 'No data'}."
        )
        reliability_text = (
            f"Minutes score {float(help_player.get('minutes_score', 0)):.1f}/100, "
            f"availability {float(help_player.get('availability_score', 0)):.1f}/100, "
            f"official chance {float(help_player.get('chance', 100)):.0f}%."
        )

        render_html(
            f"""
            <div class="help-analysis-grid">
                <div class="help-analysis-card">
                    <strong>⚡ Attacking involvement</strong>
                    <p>{html.escape(attacking_text)}</p>
                </div>
                <div class="help-analysis-card">
                    <strong>📅 Fixture outlook</strong>
                    <p>{html.escape(fixture_text)}</p>
                </div>
                <div class="help-analysis-card">
                    <strong>⏱ Reliability</strong>
                    <p>{html.escape(reliability_text)}</p>
                </div>
                <div class="help-analysis-card">
                    <strong>✅ Main strengths</strong>
                    <p>{html.escape('; '.join(verdict.strengths))}</p>
                </div>
                <div class="help-analysis-card">
                    <strong>⚠️ Risks</strong>
                    <p>{html.escape('; '.join(verdict.risks))}</p>
                </div>
                <div class="help-analysis-card">
                    <strong>💷 Market context</strong>
                    <p>
                        {float(help_player.get('selected_by_percent', 0)):.1f}% owned,
                        {int(float(help_player.get('net_transfers_event', 0))):+,}
                        net transfers, value score
                        {float(help_player.get('value_score', 0)):.1f}/100.
                    </p>
                </div>
            </div>
            """
        )

        st.markdown("### Score breakdown")
        render_colored_breakdown(
            [
                ("Recent form", float(help_player.get("form_score", 0))),
                ("Upcoming fixtures", float(help_player.get("fixtures_score", 0))),
                ("Playing-time security", float(help_player.get("minutes_score", 0))),
                ("Availability", float(help_player.get("availability_score", 0))),
                ("Value", float(help_player.get("value_score", 0))),
                ("Team impact", float(help_player.get("team_impact_score", 0))),
            ]
        )

        if str(help_player.get("news", "")).strip():
            st.warning(f"Official FPL news: {help_player.get('news')}")

        st.caption(ai_scout_explanation(help_player))

    with captain_tab:
        st.markdown("### Best captain candidates")
        captain_limit = st.slider(
            "Number of captain options",
            3,
            12,
            6,
            key="captain_limit",
        )
        captains = captain_picks(scored, captain_limit)

        if captains.empty:
            st.info("No captain candidate is available with the current data.")
        else:
            captain_display = captains[
                [
                    "player_photo",
                    "web_name",
                    "team_short",
                    "position",
                    "price",
                    "captain_score",
                    "ai_confidence",
                    "form_score",
                    "fixtures_score",
                    "minutes_score",
                    "availability_score",
                    "selected_by_percent",
                    "next_opponents",
                ]
            ].rename(
                columns={
                    "player_photo": "Photo",
                    "web_name": "Player",
                    "team_short": "Team",
                    "position": "Pos",
                    "price": "Price",
                    "captain_score": "Captain score",
                    "ai_confidence": "Confidence",
                    "form_score": "Form",
                    "fixtures_score": "Fixtures",
                    "minutes_score": "Minutes",
                    "availability_score": "Availability",
                    "selected_by_percent": "Ownership %",
                    "next_opponents": "Next fixtures",
                }
            )
            render_pinned_player_table(
                captain_display.rename(columns={"Pos": "Position", "Team": "Club name"}),
                key="captain_picks",
                pinned_columns=("Photo", "Player", "Position", "Price"),
                progress_columns=("Captain score", "Confidence", "Form", "Fixtures", "Minutes", "Availability"),
                formats={"Price": "£{:.1f}m", "Ownership %": "{:.1f}%"},
                height=560,
            )

    with differential_tab:
        st.markdown("### Low-owned player finder")
        d1, d2 = st.columns(2)
        ownership_limit = d1.slider(
            "Maximum ownership",
            1.0,
            25.0,
            10.0,
            0.5,
            key="differential_ownership",
        )
        differential_limit = d2.slider(
            "Number of results",
            5,
            20,
            10,
            key="differential_limit",
        )

        differentials = differential_picks(
            scored,
            ownership_limit=ownership_limit,
            limit=differential_limit,
        )

        if differentials.empty:
            st.info(
                "No player is below the selected ownership limit. "
                "Increase the ownership slider."
            )
        else:
            differential_display = differentials[
                [
                    "player_photo",
                    "web_name",
                    "team_short",
                    "position",
                    "price",
                    "selected_by_percent",
                    "differential_score",
                    "suggestion_score",
                    "ai_confidence",
                    "form_score",
                    "fixtures_score",
                    "availability_score",
                    "net_transfers_event",
                    "next_opponents",
                ]
            ].rename(
                columns={
                    "player_photo": "Photo",
                    "web_name": "Player",
                    "team_short": "Team",
                    "position": "Pos",
                    "price": "Price",
                    "selected_by_percent": "Ownership %",
                    "differential_score": "Differential score",
                    "suggestion_score": "Overall",
                    "ai_confidence": "Confidence",
                    "form_score": "Form",
                    "fixtures_score": "Fixtures",
                    "availability_score": "Availability",
                    "net_transfers_event": "Net transfers",
                    "next_opponents": "Next fixtures",
                }
            )
            render_pinned_player_table(
                differential_display.rename(columns={"Pos": "Position", "Team": "Club name"}),
                key="differential_picks",
                pinned_columns=("Photo", "Player", "Position", "Price"),
                progress_columns=("Differential score", "Overall", "Confidence", "Form", "Fixtures", "Availability"),
                formats={"Price": "£{:.1f}m", "Ownership %": "{:.1f}%", "Net transfers": "{:+,.0f}"},
                height=580,
            )

    with price_tab:
        st.markdown("### Transfer and price pressure")
        st.caption(
            "This is a relative market-pressure indicator. It is not the "
            "unpublished official FPL price-change algorithm."
        )

        rising = price_watch(scored, 15)

        if rising.empty:
            st.info("No current transfer-momentum data is available.")
        else:
            price_display = rising[
                [
                    "player_photo",
                    "web_name",
                    "team_short",
                    "position",
                    "price",
                    "price_momentum_score",
                    "transfers_in_event",
                    "transfers_out_event",
                    "net_transfers_event",
                    "selected_by_percent",
                    "form_score",
                    "availability_score",
                ]
            ].rename(
                columns={
                    "player_photo": "Photo",
                    "web_name": "Player",
                    "team_short": "Team",
                    "position": "Position",
                    "price": "Price",
                    "price_momentum_score": "Momentum",
                    "transfers_in_event": "Transfers in",
                    "transfers_out_event": "Transfers out",
                    "net_transfers_event": "Net transfers",
                    "selected_by_percent": "Ownership %",
                    "form_score": "Form",
                    "availability_score": "Availability",
                }
            )
            render_pinned_player_table(
                price_display.rename(columns={"Team": "Club name"}),
                key="price_watch",
                pinned_columns=("Photo", "Player", "Position", "Price"),
                progress_columns=("Momentum", "Form", "Availability"),
                formats={"Price": "£{:.1f}m", "Ownership %": "{:.1f}%", "Net transfers": "{:+,.0f}"},
                height=570,
            )

    with swing_tab:
        st.markdown("### Future fixture swings")
        st.caption(
            "Ranks players whose fixture schedule, club strength and current "
            "form create a strong near-term opportunity."
        )

        swing_limit = st.slider(
            "Number of fixture opportunities",
            5,
            20,
            12,
            key="fixture_swing_limit",
        )
        swing = fixture_swing_picks(scored, swing_limit)

        if swing.empty:
            st.info("No upcoming fixture data is currently available.")
        else:
            swing_display = swing[
                [
                    "player_photo",
                    "web_name",
                    "team_short",
                    "position",
                    "price",
                    "fixture_swing_score",
                    "fixtures_score",
                    "avg_fdr",
                    "form_score",
                    "minutes_score",
                    "availability_score",
                    "team_impact_score",
                    "next_opponents",
                ]
            ].rename(
                columns={
                    "player_photo": "Photo",
                    "web_name": "Player",
                    "team_short": "Team",
                    "position": "Pos",
                    "price": "Price",
                    "fixture_swing_score": "Swing score",
                    "fixtures_score": "Fixtures",
                    "avg_fdr": "Avg FDR",
                    "form_score": "Form",
                    "minutes_score": "Minutes",
                    "availability_score": "Availability",
                    "team_impact_score": "Team impact",
                    "next_opponents": "Next fixtures",
                }
            )
            render_pinned_player_table(
                swing_display.rename(columns={"Pos": "Position", "Team": "Club name"}),
                key="fixture_swings",
                pinned_columns=("Photo", "Player", "Position", "Price"),
                progress_columns=("Swing score", "Fixtures", "Form", "Minutes", "Availability", "Team impact"),
                formats={"Price": "£{:.1f}m", "Avg FDR": "{:.2f}"},
                height=590,
            )


with team_tab:
    render_html(
        """
        <div class="team-center-banner">
            <h2>⚽ Phase 4 Team Center</h2>
            <p>
                Select a full squad, validate FPL rules, generate your best XI,
                build a wildcard and review coordinated transfer plans.
            </p>
        </div>
        """
    )

    squad_tab, xi_tab, wildcard_tab, pair_tab, calendar_tab, chip_tab = st.tabs(
        [
            "Squad analyzer",
            "Best XI",
            "Wildcard builder",
            "Two-transfer optimizer",
            "Fixture calendar",
            "Chip readiness",
        ]
    )

    selector_lookup = player_selector_labels(scored)
    selector_options = list(selector_lookup.keys())

    if "phase4_squad_ids" not in st.session_state:
        starter_squad, _ = build_wildcard_squad(
            scored,
            budget=100.0,
            strategy="Balanced",
        )
        st.session_state.phase4_squad_ids = (
            starter_squad["player_id"].astype(int).tolist()
            if len(starter_squad) == 15
            else []
        )

    default_squad_labels = [
        label
        for label, player_id in selector_lookup.items()
        if player_id in set(st.session_state.phase4_squad_ids)
    ]

    with squad_tab:
        st.markdown("### Build and validate your squad")

        squad_budget = st.number_input(
            "Squad budget (£m)",
            min_value=80.0,
            max_value=110.0,
            value=100.0,
            step=0.1,
            key="phase4_squad_budget",
        )

        selected_labels = st.multiselect(
            "Select 15 players",
            options=selector_options,
            default=default_squad_labels,
            max_selections=15,
            key="phase4_squad_selector",
            help="Select 2 GK, 5 DEF, 5 MID and 3 FWD.",
        )

        selected_ids = [selector_lookup[label] for label in selected_labels]
        st.session_state.phase4_squad_ids = selected_ids

        active_squad = scored[scored["player_id"].isin(selected_ids)].copy()

        position_counts = active_squad["position"].value_counts().to_dict()
        render_html(
            f"""
            <div class="squad-selection-summary" aria-label="Selected squad summary">
                <div class="selection-count-card">
                    <div class="k">Selected</div>
                    <div class="v">{len(active_squad)}/15</div>
                </div>
                <div class="selection-count-card">
                    <div class="k">Goalkeepers</div>
                    <div class="v">{int(position_counts.get('GK', 0))}/2</div>
                </div>
                <div class="selection-count-card">
                    <div class="k">Defenders</div>
                    <div class="v">{int(position_counts.get('DEF', 0))}/5</div>
                </div>
                <div class="selection-count-card">
                    <div class="k">Midfielders</div>
                    <div class="v">{int(position_counts.get('MID', 0))}/5</div>
                </div>
                <div class="selection-count-card">
                    <div class="k">Forwards</div>
                    <div class="v">{int(position_counts.get('FWD', 0))}/3</div>
                </div>
            </div>
            """
        )

        validation = validate_squad(
            active_squad,
            budget=float(squad_budget),
            require_complete_squad=True,
        )

        for message in validation.errors:
            st.error(message)
        for message in validation.warnings:
            st.warning(message)

        if validation.is_valid:
            st.success("This squad satisfies the main FPL squad rules.")

        if not active_squad.empty:
            ratings = rate_squad(active_squad)
            render_squad_score_cards(ratings)

            render_html(
                f"""
                <div class="team-note">
                    <strong>Squad verdict:</strong>
                    {html.escape(squad_summary(ratings))}
                </div>
                """
            )

            squad_display = active_squad[
                [
                    "web_name",
                    "team_short",
                    "position",
                    "price",
                    "suggestion_score",
                    "captain_score",
                    "fixtures_score",
                    "availability_score",
                    "risk_score",
                ]
            ].rename(
                columns={
                    "web_name": "Player",
                    "team_short": "Team",
                    "position": "Pos",
                    "price": "Price",
                    "suggestion_score": "Overall",
                    "captain_score": "Captain",
                    "fixtures_score": "Fixtures",
                    "availability_score": "Availability",
                    "risk_score": "Risk",
                }
            )

            render_pinned_player_table(
                squad_display.rename(columns={"Team": "Club name", "Pos": "Position"}),
                key="squad_analyzer",
                pinned_columns=("Player", "Position", "Price"),
                progress_columns=("Overall", "Captain", "Fixtures", "Availability", "Risk"),
                formats={"Price": "£{:.1f}m"},
                height=530,
            )

            st.markdown("### Budget allocation")
            budget_table = analyze_budget(active_squad, float(squad_budget))
            st.dataframe(
                budget_table,
                hide_index=True,
                use_container_width=True,
            )

            for warning in budget_warnings(budget_table):
                st.write(f"• {warning}")

    active_squad = scored[
        scored["player_id"].isin(st.session_state.phase4_squad_ids)
    ].copy()

    with xi_tab:
        st.markdown("### Best legal starting XI")

        if len(active_squad) != 15:
            st.info("Select a complete 15-player squad in Squad Analyzer first.")
        else:
            starters, bench, formation = select_best_starting_xi(active_squad)
            render_pitch(starters, formation)
            st.markdown("#### Recommended bench order")
            st.caption(
                "Bench option 1 is the first substitute. Goalkeepers still follow FPL automatic-substitution rules."
            )
            render_bench(bench)

            captain, vice = choose_captains(starters)
            if captain is not None:
                left, right = st.columns(2)
                left.metric(
                    "Captain",
                    str(captain.get("web_name", "Unknown")),
                    delta=f"{float(captain.get('captain_score', 0)):.1f} captain score",
                )
                right.metric(
                    "Vice-captain",
                    str(vice.get("web_name", "Unknown")) if vice is not None else "N/A",
                    delta=(
                        f"{float(vice.get('captain_score', 0)):.1f} captain score"
                        if vice is not None
                        else None
                    ),
                )

            render_html(
                f"""
                <div class="team-note">
                    {html.escape(starting_xi_summary(starters, bench, formation))}
                </div>
                """
            )

    with wildcard_tab:
        st.markdown("### Wildcard squad builder")

        wc1, wc2 = st.columns(2)
        wildcard_budget = wc1.number_input(
            "Wildcard budget (£m)",
            min_value=80.0,
            max_value=110.0,
            value=100.0,
            step=0.1,
            key="wildcard_budget",
        )
        wildcard_strategy = wc2.selectbox(
            "Strategy",
            ["Balanced", "Form", "Fixtures", "Value", "Safe"],
            key="wildcard_strategy",
        )

        if st.button(
            "Build wildcard squad",
            use_container_width=True,
            key="build_wildcard",
        ):
            generated, notes = build_wildcard_squad(
                scored,
                budget=float(wildcard_budget),
                strategy=wildcard_strategy,
            )
            st.session_state.phase4_wildcard = generated
            st.session_state.phase4_wildcard_notes = notes

        generated = st.session_state.get("phase4_wildcard", pd.DataFrame())
        notes = st.session_state.get("phase4_wildcard_notes", [])

        if not generated.empty:
            render_html(
                f"""
                <div class="team-note">
                    {html.escape(wildcard_summary(
                        generated,
                        notes,
                        float(wildcard_budget),
                    ))}
                </div>
                """
            )

            wc_starters, wc_bench, wc_formation = select_best_starting_xi(generated)
            render_pitch(wc_starters, wc_formation)
            render_bench(wc_bench)

            wildcard_table = generated[
                [
                    "web_name",
                    "team_short",
                    "position",
                    "price",
                    "suggestion_score",
                    "captain_score",
                    "value_score",
                ]
            ].rename(
                columns={
                    "web_name": "Player",
                    "team_short": "Club",
                    "position": "Position",
                    "price": "Price",
                    "suggestion_score": "Overall score",
                    "captain_score": "Captain potential",
                    "value_score": "Value rating",
                }
            )

            st.markdown("### Wildcard squad overview")
            st.caption(
                "Click a column heading to sort the squad. Scores use a 0–100 model scale."
            )

            render_pinned_player_table(
                wildcard_table,
                key="wildcard_squad",
                pinned_columns=("Player", "Position", "Price"),
                progress_columns=("Overall score", "Captain potential", "Value rating"),
                formats={"Price": "£{:.1f}m"},
                height=540,
            )

    with pair_tab:
        st.markdown("### Coordinated two-player transfers")
        st.write(
            "Find two moves that work together, including a downgrade that can "
            "fund a larger upgrade elsewhere."
        )

        if len(active_squad) != 15:
            st.info("Select a complete 15-player squad in Squad Analyzer first.")
        else:
            pair_left, pair_right = st.columns(2)

            with pair_left:
                transfer_bank = st.number_input(
                    "Money in bank (£m)",
                    min_value=0.0,
                    max_value=20.0,
                    value=0.0,
                    step=0.1,
                    key="phase4_pair_bank",
                    help="Money available in addition to the two outgoing prices.",
                )

            with pair_right:
                pair_search_size = st.select_slider(
                    "Search depth",
                    options=[6, 8, 10, 12],
                    value=8,
                    key="phase4_pair_search_size",
                    format_func=lambda value: {
                        6: "Fast",
                        8: "Recommended",
                        10: "Detailed",
                        12: "Deep",
                    }[value],
                    help=(
                        "Controls how many incoming candidates per position are "
                        "checked. Recommended is usually fast and thorough."
                    ),
                )

            st.caption(
                "The optimizer checks same-position replacements, total budget, "
                "the three-player club limit and combined model-score improvement."
            )

            run_pair_search = st.button(
                "Find coordinated transfers",
                key="run_pair_optimizer",
                use_container_width=True,
                type="primary",
            )

            if run_pair_search:
                # Clear the old result first so a stale plan is never shown while
                # a new search is running.
                st.session_state.phase4_pair_results = pd.DataFrame()
                st.session_state.phase4_pair_error = ""

                try:
                    with st.spinner(
                        "Searching the strongest legal two-transfer plans..."
                    ):
                        calculated_pairs = optimize_two_transfers(
                            active_squad,
                            scored,
                            bank=float(transfer_bank),
                            limit=12,
                            candidate_limit_per_position=int(pair_search_size),
                        )

                    st.session_state.phase4_pair_results = calculated_pairs
                    st.session_state.phase4_pair_signature = (
                        tuple(sorted(active_squad["player_id"].astype(int))),
                        float(transfer_bank),
                        int(pair_search_size),
                    )
                except Exception as exc:
                    st.session_state.phase4_pair_error = str(exc)

            pair_error = st.session_state.get("phase4_pair_error", "")
            pair_results = st.session_state.get(
                "phase4_pair_results",
                pd.DataFrame(),
            )

            if pair_error:
                st.error(
                    "The transfer search could not finish. Restart the app after "
                    f"installing the fixed optimizer. Technical detail: {pair_error}"
                )
            elif run_pair_search and pair_results.empty:
                st.warning(
                    "No positive legal two-transfer plan was found. Try adding "
                    "money to the bank, choosing a deeper search, or changing the "
                    "squad."
                )
            elif pair_results.empty:
                st.info(
                    "Choose your bank amount and press “Find coordinated "
                    "transfers.” Results normally appear within a few seconds."
                )
            else:
                best_gain = float(
                    pair_results.iloc[0].get("Combined score gain", 0) or 0
                )
                st.success(
                    f"Found {len(pair_results)} legal transfer plans. "
                    f"The best combined model improvement is +{best_gain:.1f}."
                )

                friendly_pairs = pair_results.copy()
                friendly_pairs.insert(
                    0,
                    "Plan",
                    [f"Option {index}" for index in range(1, len(friendly_pairs) + 1)],
                )

                st.dataframe(
                    friendly_pairs,
                    hide_index=True,
                    use_container_width=True,
                    height=480,
                    column_config={
                        "Plan": st.column_config.TextColumn(
                            "Plan",
                            width="small",
                        ),
                        "Transfer out 1": st.column_config.TextColumn(
                            "Sell",
                            width="medium",
                        ),
                        "Transfer out 2": st.column_config.TextColumn(
                            "Sell",
                            width="medium",
                        ),
                        "Transfer in 1": st.column_config.TextColumn(
                            "Buy",
                            width="medium",
                        ),
                        "Transfer in 2": st.column_config.TextColumn(
                            "Buy",
                            width="medium",
                        ),
                        "Position 1": st.column_config.TextColumn(
                            "Position",
                            width="small",
                        ),
                        "Position 2": st.column_config.TextColumn(
                            "Position",
                            width="small",
                        ),
                        "Outgoing cost": st.column_config.NumberColumn(
                            "Sold for",
                            format="£%.1fm",
                        ),
                        "Incoming cost": st.column_config.NumberColumn(
                            "Buy for",
                            format="£%.1fm",
                        ),
                        "Money remaining": st.column_config.NumberColumn(
                            "Bank left",
                            format="£%.1fm",
                        ),
                        "Combined score gain": st.column_config.NumberColumn(
                            "Model gain",
                            format="%+.1f",
                        ),
                        "Incoming average score": st.column_config.ProgressColumn(
                            "New pair quality",
                            min_value=0,
                            max_value=100,
                            format="%.1f",
                        ),
                    },
                )

                best_plan = pair_results.iloc[0]
                render_html(
                    f"""
                    <div class="decision-callout">
                        <strong>Best coordinated move</strong><br>
                        Sell {html.escape(str(best_plan['Transfer out 1']))} and
                        {html.escape(str(best_plan['Transfer out 2']))}.<br>
                        Buy {html.escape(str(best_plan['Transfer in 1']))} and
                        {html.escape(str(best_plan['Transfer in 2']))}.<br><br>
                        <strong>Combined model improvement:</strong>
                        {float(best_plan['Combined score gain']):+.1f}<br>
                        <strong>Money remaining:</strong>
                        £{float(best_plan['Money remaining']):.1f}m
                    </div>
                    """
                )

    with calendar_tab:
        st.markdown("### Squad fixture calendar")

        if active_squad.empty:
            st.info("Select a squad first.")
        else:
            st.dataframe(
                fixture_matrix(active_squad, horizon=horizon),
                hide_index=True,
                use_container_width=True,
            )

    with chip_tab:
        st.markdown("### Chip readiness")

        if len(active_squad) != 15:
            st.info("Select a complete squad first.")
        else:
            render_chip_cards(chip_readiness(active_squad))


with detail_tab:
    st.markdown(
        """
        <div class="section-heading">
            <h2>Player research center</h2>
            <p>
                Review price, ownership, form, fixtures, minutes, underlying
                statistics and risks before making an FPL decision.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    detail_lookup = {
        (
            f"{row['web_name']} · {row['team_short']} · "
            f"{row['position']} · £{safe_number(row.get('price')):.1f}m"
        ): int(row["player_id"])
        for _, row in scored.sort_values(
            ["suggestion_score", "web_name"],
            ascending=[False, True],
        ).iterrows()
    }

    selected_detail_label = st.selectbox(
        "Choose a player",
        options=list(detail_lookup.keys()),
        key="player_research_selector",
        help="Search by player name, then confirm the club, position and price.",
    )
    selected_detail_id = detail_lookup[selected_detail_label]
    player = scored[scored["player_id"] == selected_detail_id].iloc[0]

    player_name = html.escape(ui_text(player.get("web_name")))
    team_name = html.escape(ui_text(player.get("team_name")))
    position_name = html.escape(ui_text(player.get("position")))
    player_photo = safe_image_url(player.get("player_photo"))
    team_logo = safe_image_url(player.get("team_logo"))

    photo_html = (
        f'<img class="detail-player-photo" src="{html.escape(player_photo)}" '
        f'alt="{player_name}" '
        f'onerror="this.style.display=\'none\';">'
        if player_photo
        else '<div class="detail-player-photo" style="display:flex;align-items:center;justify-content:center;font-size:2.5rem;">👤</div>'
    )

    logo_html = (
        f'<img class="detail-club-logo" src="{html.escape(team_logo)}" '
        f'alt="{team_name} club badge">'
        if team_logo
        else ""
    )

    chance = safe_number(player.get("chance"), 100.0)
    status_class = (
        "status-available"
        if chance >= 90
        else "status-doubtful"
        if chance >= 50
        else "status-injured"
    )
    status_label = (
        "Available"
        if chance >= 90
        else "Doubtful"
        if chance >= 50
        else "Injury concern"
    )

    render_html(
        f"""
        <section class="player-profile-hero" aria-label="{player_name} profile">
            <div>{photo_html}</div>
            <div>
                <span class="status-chip {status_class}">
                    {status_label} · {chance:.0f}%
                </span>

                <div class="profile-identity">
                    {logo_html}
                    <div>
                        <div class="profile-kicker">{team_name} · {position_name}</div>
                        <div class="profile-name">{player_name}</div>
                        <div class="profile-sub">
                            {html.escape(ui_text(player.get('ownership_label')))}
                            · {html.escape(ui_text(player.get('transfer_trend')))}
                        </div>
                    </div>
                </div>

                <div class="profile-stat-grid">
                    <div class="profile-stat">
                        <div class="k">Recommendation</div>
                        <div class="v">{safe_number(player.get('suggestion_score')):.1f}/100</div>
                    </div>
                    <div class="profile-stat">
                        <div class="k">Price</div>
                        <div class="v">£{safe_number(player.get('price')):.1f}m</div>
                    </div>
                    <div class="profile-stat">
                        <div class="k">Form</div>
                        <div class="v">{safe_number(player.get('form_score')):.1f}</div>
                    </div>
                    <div class="profile-stat">
                        <div class="k">Total points</div>
                        <div class="v">{safe_number(player.get('total_points')):.0f}</div>
                    </div>
                    <div class="profile-stat">
                        <div class="k">Ownership</div>
                        <div class="v">{safe_number(player.get('selected_by_percent')):.1f}%</div>
                    </div>
                    <div class="profile-stat">
                        <div class="k">Net transfers</div>
                        <div class="v">{safe_number(player.get('net_transfers_event')):+,.0f}</div>
                    </div>
                </div>

                <div class="fixture-strip">
                    {fixture_strip_html(player.get('next_opponents', ''), safe_number(player.get('avg_fdr'), 3.0))}
                </div>
            </div>
        </section>
        """
    )

    render_html(
        f"""
        <div class="decision-callout">
            <strong>FPL summary:</strong>
            {html.escape(why_player(player))}
        </div>
        """
    )

    if player.get("news"):
        st.warning(f"Official FPL news: {player['news']}")

    if player.get("secondary_status"):
        st.info(
            f"Secondary source: {player['secondary_status']}"
        )

    overview_tab, fixtures_tab, history_tab = st.tabs(
        ["Overview", "Upcoming fixtures", "Match history"]
    )

    with overview_tab:
        st.markdown("### Key FPL indicators")
        st.caption(
            "The cards below mix three kinds of information: current-season totals, "
            "recent form, and forward-looking model scores."
        )

        render_html(
            """
            <div class="indicator-key">
                <div class="indicator-key-item">
                    <strong>📊 Season to date</strong>
                    Totals accumulated across the current FPL season.
                </div>
                <div class="indicator-key-item">
                    <strong>🔥 Recent / rolling</strong>
                    Short-term form that changes as new matches are played.
                </div>
                <div class="indicator-key-item">
                    <strong>🔮 Forward-looking</strong>
                    Upcoming fixtures and model-based scores.
                </div>
            </div>
            """
        )

        render_html(
            f"""
            <div class="indicator-section">
                <div class="indicator-section-title">📊 Current-season performance</div>
                <div class="indicator-section-subtitle">
                    These values are cumulative totals from the current FPL season.
                    They are not scores out of 100.
                </div>

                <div class="detail-insight-grid">
                    <div class="detail-insight-card season">
                        <div class="icon">⏱</div>
                        <div class="period-badge">Season total</div>
                        <div class="label">Minutes played</div>
                        <div class="value">{float(player.get('season_minutes', 0)):,.0f}</div>
                        <div class="note">
                            Total league minutes this season. Higher values usually
                            indicate a more secure starting role.
                        </div>
                    </div>

                    <div class="detail-insight-card season">
                        <div class="icon">🎯</div>
                        <div class="period-badge">Season total</div>
                        <div class="label">Expected goals (xG)</div>
                        <div class="value">{float(player.get('expected_goals', 0)):.1f}</div>
                        <div class="note">
                            Cumulative quality of the player's shooting chances
                            during the current season.
                        </div>
                    </div>

                    <div class="detail-insight-card season">
                        <div class="icon">🅰️</div>
                        <div class="period-badge">Season total</div>
                        <div class="label">Expected assists (xA)</div>
                        <div class="value">{float(player.get('expected_assists', 0)):.1f}</div>
                        <div class="note">
                            Cumulative quality of chances created for teammates
                            during the current season.
                        </div>
                    </div>

                    <div class="detail-insight-card season">
                        <div class="icon">⚡</div>
                        <div class="period-badge">Season total</div>
                        <div class="label">Expected goal involvement (xGI)</div>
                        <div class="value">{float(player.get('expected_goal_involvements', 0)):.1f}</div>
                        <div class="note">
                            Season xG plus season xA. It summarizes expected
                            attacking contribution.
                        </div>
                    </div>

                    <div class="detail-insight-card season">
                        <div class="icon">📈</div>
                        <div class="period-badge">Season total</div>
                        <div class="label">ICT index</div>
                        <div class="value">{float(player.get('ict_index', 0)):.1f}</div>
                        <div class="note">
                            Official cumulative Influence, Creativity and Threat
                            measure for this season.
                        </div>
                    </div>
                </div>
            </div>

            <div class="indicator-section">
                <div class="indicator-section-title">🔥 Recent and forward-looking indicators</div>
                <div class="indicator-section-subtitle">
                    These values help with short-term transfer decisions and upcoming
                    gameweek planning.
                </div>

                <div class="detail-insight-grid">
                    <div class="detail-insight-card recent">
                        <div class="icon">🔥</div>
                        <div class="period-badge">Rolling form</div>
                        <div class="label">Official form</div>
                        <div class="value">{float(player.get('form_api', 0)):.1f}</div>
                        <div class="note">
                            Official rolling FPL form based on recent returns.
                            This is not a score out of 100.
                        </div>
                    </div>

                    <div class="detail-insight-card fixture">
                        <div class="icon">📅</div>
                        <div class="period-badge">Next fixtures</div>
                        <div class="label">Fixture outlook</div>
                        <div class="value">{fixture_category_display(float(player.get('avg_fdr', 0)))}</div>
                        <div class="note">
                            Average upcoming difficulty is
                            {float(player.get('avg_fdr', 0)):.1f} out of 5.
                            Lower is easier.
                        </div>
                    </div>

                    <div class="detail-insight-card model">
                        <div class="icon">💷</div>
                        <div class="period-badge">Model score</div>
                        <div class="label">Price value</div>
                        <div class="value">{float(player.get('value_score', 0)):.1f} / 100</div>
                        <div class="note">
                            App-calculated value score. Higher means stronger
                            expected return for the player's price.
                        </div>
                    </div>

                    <div class="detail-insight-card model">
                        <div class="icon">⭐</div>
                        <div class="period-badge">Model score</div>
                        <div class="label">Overall recommendation</div>
                        <div class="value">{float(player.get('suggestion_score', 0)):.1f} / 100</div>
                        <div class="note">
                            Combined score using form, fixtures, minutes,
                            availability, value and team impact.
                        </div>
                    </div>
                </div>
            </div>
            """
        )

        st.markdown("### Model breakdown")
        st.caption(
            "Green means the player is strong in that area, yellow means "
            "average or worth monitoring, and red shows a weaker area."
        )

        render_colored_breakdown(
            [
                ("Recent form", float(player.get("form_score", 0))),
                ("Upcoming fixtures", float(player.get("fixtures_score", 0))),
                ("Playing-time security", float(player.get("minutes_score", 0))),
                ("Availability", float(player.get("availability_score", 0))),
                ("Value", float(player.get("value_score", 0))),
                ("Team impact", float(player.get("team_impact_score", 0))),
            ]
        )

        st.markdown("### What an FPL manager should check")
        checks = []
        if float(player.get("chance", 100)) < 100:
            checks.append("⚠️ Check the official availability update before the deadline.")
        else:
            checks.append("✅ No current official availability restriction.")
        if float(player.get("minutes_score", 0)) >= 75:
            checks.append("✅ Playing-time profile looks secure.")
        else:
            checks.append("⚠️ Review rotation and recent starts.")
        if float(player.get("avg_fdr", 3)) <= 2.5:
            checks.append("✅ Upcoming fixtures are favorable.")
        elif float(player.get("avg_fdr", 3)) >= 3.5:
            checks.append("⚠️ Upcoming fixture run is difficult.")
        if float(player.get("net_transfers_event", 0)) > 0:
            checks.append("📈 More managers are buying than selling this gameweek.")
        elif float(player.get("net_transfers_event", 0)) < 0:
            checks.append("📉 More managers are selling than buying this gameweek.")
        if float(player.get("selected_by_percent", 0)) < 10:
            checks.append("⭐ Low ownership offers differential potential.")
        elif float(player.get("selected_by_percent", 0)) >= 40:
            checks.append("🛡 High ownership may reduce rank damage if the player returns.")

        for check in checks:
            st.write(check)

    try:
        summary = get_element_summary(int(player["player_id"]))
        history = pd.DataFrame(summary.get("history", []))
        upcoming = pd.DataFrame(summary.get("fixtures", []))

        team_lookup = (
            teams.set_index("id")["short_name"].to_dict()
            if not teams.empty
            else {}
        )
        team_name_lookup = (
            teams.set_index("id")["name"].to_dict()
            if not teams.empty
            else {}
        )
        team_code_lookup = (
            teams.set_index("id")["code"].to_dict()
            if not teams.empty and "code" in teams.columns
            else {}
        )

        def team_badge_url(team_id: object) -> str:
            try:
                code = team_code_lookup.get(int(team_id))
                if pd.isna(code):
                    return ""
                return (
                    "https://resources.premierleague.com/"
                    f"premierleague/badges/70/t{int(code)}.png"
                )
            except (TypeError, ValueError):
                return ""

        with fixtures_tab:
            st.markdown("### Next fixtures")

            if upcoming.empty:
                st.info("No upcoming fixture records are currently available.")
            else:
                upcoming_display = upcoming.copy()
                upcoming_display["GW"] = pd.to_numeric(
                    upcoming_display.get("event"),
                    errors="coerce",
                ).astype("Int64")
                upcoming_display["Venue"] = upcoming_display.get(
                    "is_home",
                    False,
                ).map({True: "Home", False: "Away"})

                def opponent_id_for_row(row: pd.Series) -> object:
                    return (
                        row.get("team_a")
                        if bool(row.get("is_home"))
                        else row.get("team_h")
                    )

                def opponent_name(row: pd.Series) -> str:
                    opponent_id = opponent_id_for_row(row)
                    try:
                        return str(team_name_lookup.get(int(opponent_id), "TBD"))
                    except (TypeError, ValueError):
                        return "TBD"

                def opponent_short_name(row: pd.Series) -> str:
                    opponent_id = opponent_id_for_row(row)
                    try:
                        return str(team_lookup.get(int(opponent_id), "TBD"))
                    except (TypeError, ValueError):
                        return "TBD"

                def opponent_badge(row: pd.Series) -> str:
                    return team_badge_url(opponent_id_for_row(row))

                upcoming_display["Opponent"] = upcoming_display.apply(
                    opponent_name,
                    axis=1,
                )
                upcoming_display["Opponent short"] = upcoming_display.apply(
                    opponent_short_name,
                    axis=1,
                )
                upcoming_display["Badge"] = upcoming_display.apply(
                    opponent_badge,
                    axis=1,
                )
                upcoming_display["Difficulty score"] = pd.to_numeric(
                    upcoming_display.get("difficulty"),
                    errors="coerce",
                ).fillna(0).astype(int)
                upcoming_display["Difficulty"] = upcoming_display[
                    "Difficulty score"
                ].apply(fixture_category_display)
                upcoming_display["Kickoff"] = pd.to_datetime(
                    upcoming_display.get("kickoff_time"),
                    errors="coerce",
                    utc=True,
                ).dt.strftime("%b %d, %Y · %H:%M UTC")

                render_html(
                    """
                    <div class="fixture-difficulty-legend">
                        <div class="fixture-easy">🟢 Easy<br>Difficulty 1–2</div>
                        <div class="fixture-neutral">🟡 Medium<br>Difficulty 3</div>
                        <div class="fixture-hard">🔴 Hard<br>Difficulty 4–5</div>
                    </div>
                    """
                )

                fixture_cards = []
                for _, fixture in upcoming_display.head(8).iterrows():
                    difficulty_score = int(
                        fixture.get("Difficulty score", 0)
                    )
                    difficulty_category = fixture_difficulty_category(
                        difficulty_score
                    )
                    category_class = difficulty_category.lower()
                    opponent_logo = safe_image_url(fixture.get("Badge"))
                    opponent_logo_html = (
                        f'<img class="fixture-opponent-logo" '
                        f'src="{html.escape(opponent_logo)}" '
                        f'alt="{html.escape(str(fixture.get("Opponent", "Opponent")))} logo">'
                        if opponent_logo
                        else ""
                    )

                    fixture_cards.append(
                        f"""
                        <div class="fixture-card fdr-card-{difficulty_score}">
                            <div class="gw">Gameweek {fixture.get('GW', 'TBD')}</div>
                            <div class="fixture-opponent-row">
                                {opponent_logo_html}
                                <div>
                                    <div class="opponent">
                                        {html.escape(str(fixture.get('Opponent', 'TBD')))}
                                    </div>
                                    <div class="meta">
                                        {html.escape(str(fixture.get('Venue', '')))}
                                    </div>
                                </div>
                            </div>
                            <div class="meta">
                                {html.escape(str(fixture.get('Kickoff', 'TBD')))}
                            </div>
                            <span class="fixture-category category-{category_class}">
                                {html.escape(fixture_category_display(difficulty_score))}
                            </span>
                        </div>
                        """
                    )

                render_html(
                    '<div class="fixture-card-grid">'
                    + "".join(fixture_cards)
                    + "</div>"
                )

                st.caption(
                    "Difficulty is translated from the official 1–5 rating: "
                    "1–2 is Easy, 3 is Medium, and 4–5 is Hard."
                )

                fixture_table = upcoming_display[
                    [
                        "GW",
                        "Badge",
                        "Opponent",
                        "Venue",
                        "Difficulty",
                        "Kickoff",
                    ]
                ].head(12)

                st.dataframe(
                    fixture_table,
                    hide_index=True,
                    use_container_width=True,
                    height=500,
                    column_config={
                        "GW": st.column_config.NumberColumn(
                            "GW",
                            format="%d",
                            width="small",
                        ),
                        "Badge": st.column_config.ImageColumn(
                            "Club",
                            width="small",
                        ),
                        "Opponent": st.column_config.TextColumn(
                            "Opponent",
                            width="medium",
                        ),
                        "Venue": st.column_config.TextColumn(
                            "Venue",
                            width="small",
                        ),
                        "Difficulty": st.column_config.TextColumn(
                            "Difficulty",
                            width="medium",
                            help=(
                                "Easy = official difficulty 1–2, "
                                "Medium = 3, Hard = 4–5."
                            ),
                        ),
                        "Kickoff": st.column_config.TextColumn(
                            "Kickoff",
                            width="large",
                        ),
                    },
                )

        with history_tab:
            st.markdown("### Recent match history")

            if history.empty:
                st.info(
                    "No completed match history is available yet. "
                    "This is normal during preseason."
                )
            else:
                history_display = history.copy()
                history_display["GW"] = pd.to_numeric(
                    history_display.get("round"),
                    errors="coerce",
                ).astype("Int64")
                history_display["Opponent"] = history_display.get(
                    "opponent_team"
                ).map(team_lookup).fillna("TBD")
                history_display["Points"] = pd.to_numeric(
                    history_display.get("total_points"),
                    errors="coerce",
                ).fillna(0)
                history_display["Minutes"] = pd.to_numeric(
                    history_display.get("minutes"),
                    errors="coerce",
                ).fillna(0)
                history_display["Goals"] = pd.to_numeric(
                    history_display.get("goals_scored"),
                    errors="coerce",
                ).fillna(0)
                history_display["Assists"] = pd.to_numeric(
                    history_display.get("assists"),
                    errors="coerce",
                ).fillna(0)
                history_display["xG"] = pd.to_numeric(
                    history_display.get("expected_goals"),
                    errors="coerce",
                ).fillna(0)
                history_display["xA"] = pd.to_numeric(
                    history_display.get("expected_assists"),
                    errors="coerce",
                ).fillna(0)
                history_display["Bonus"] = pd.to_numeric(
                    history_display.get("bonus"),
                    errors="coerce",
                ).fillna(0)

                st.dataframe(
                    history_display[
                        [
                            "GW",
                            "Opponent",
                            "Points",
                            "Minutes",
                            "Goals",
                            "Assists",
                            "xG",
                            "xA",
                            "Bonus",
                        ]
                    ].tail(12),
                    hide_index=True,
                    use_container_width=True,
                    height=470,
                )

                h1, h2, h3, h4 = st.columns(4)
                recent_slice = history_display.tail(5)
                h1.metric(
                    "Last 5 points",
                    f"{recent_slice['Points'].sum():.0f}",
                )
                h2.metric(
                    "Last 5 minutes",
                    f"{recent_slice['Minutes'].sum():.0f}",
                )
                h3.metric(
                    "Last 5 xG",
                    f"{recent_slice['xG'].sum():.1f}",
                )
                h4.metric(
                    "Last 5 xA",
                    f"{recent_slice['xA'].sum():.1f}",
                )

    except FPLDataError as exc:
        with fixtures_tab:
            st.warning(str(exc))
        with history_tab:
            st.warning(str(exc))



with methodology_tab:
    st.markdown(
        """
        <div class="section-heading">
            <h2>How the recommendation score works</h2>
            <p>
                The app looks at six simple questions for every player, then
                combines the answers into one score out of 100.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_html(
        """
        <div class="formula-flow">
            <div class="formula-step">
                <strong>🔥 Form</strong>
                <span>Has the player been producing points recently?</span>
            </div>
            <div class="formula-step">
                <strong>📅 Fixtures</strong>
                <span>Are the next opponents easier or harder?</span>
            </div>
            <div class="formula-step">
                <strong>⏱ Minutes</strong>
                <span>Is the player likely to start and play regularly?</span>
            </div>
            <div class="formula-step">
                <strong>🩺 Availability</strong>
                <span>Is the player fit, available and free from warnings?</span>
            </div>
            <div class="formula-step">
                <strong>💷 Value</strong>
                <span>How much return does the player offer for the price?</span>
            </div>
            <div class="formula-step">
                <strong>🏟 Team impact</strong>
                <span>How strong is the club and how important is the player?</span>
            </div>
        </div>
        """
    )

    st.markdown("### What each part means")

    render_html(
        """
        <div class="method-grid">
            <div class="method-card">
                <div class="method-icon">🔥</div>
                <h3>Recent form</h3>
                <p>
                    Uses recent FPL points and attacking involvement.
                    A player scoring or assisting often will rate higher.
                </p>
            </div>

            <div class="method-card">
                <div class="method-icon">📅</div>
                <h3>Upcoming fixtures</h3>
                <p>
                    Easier opponents improve the score. Harder opponents
                    reduce it. Home and away matches are both considered.
                </p>
            </div>

            <div class="method-card">
                <div class="method-icon">⏱</div>
                <h3>Playing time</h3>
                <p>
                    Regular starters score better than rotation risks.
                    Recent minutes and starts are used here.
                </p>
            </div>

            <div class="method-card">
                <div class="method-icon">🩺</div>
                <h3>Fitness and availability</h3>
                <p>
                    Injuries, suspensions and official FPL warnings lower
                    the score. Fully available players score better.
                </p>
            </div>

            <div class="method-card">
                <div class="method-icon">💷</div>
                <h3>Value for money</h3>
                <p>
                    Looks at points for the player's price, plus transfer
                    activity and recent price movement.
                </p>
            </div>

            <div class="method-card">
                <div class="method-icon">🏟</div>
                <h3>Team and player impact</h3>
                <p>
                    Considers club strength and the player's contribution,
                    such as attacking involvement or defensive reliability.
                </p>
            </div>
        </div>
        """
    )

    st.markdown("### How to read the final score")

    render_html(
        """
        <div class="score-band">
            <div class="score-low">0–39<br>Weak option</div>
            <div class="score-watch">40–59<br>Worth monitoring</div>
            <div class="score-good">60–74<br>Good option</div>
            <div class="score-top">75–100<br>Strong recommendation</div>
        </div>
        """
    )

    st.caption(
        "The score is a decision-support tool, not a guarantee of future points."
    )

    st.markdown("### How the sliders affect the result")

    st.write(
        "The sliders in the sidebar tell the app what matters most to you. "
        "Moving a slider to the right gives that factor more influence."
    )

    render_html(
        """
        <div class="plain-example">
            <strong>Example:</strong> If you care most about short-term transfers,
            increase <strong>Recent performance</strong> and
            <strong>Fixture quality</strong>. If you want safer picks,
            increase <strong>Playing-time security</strong> and
            <strong>Fitness and availability</strong>.
        </div>
        """
    )

    st.markdown("### Popularity and transfer activity")

    pop1, pop2, pop3 = st.columns(3)
    pop1.metric(
        "Ownership %",
        "How many managers own the player",
    )
    pop2.metric(
        "Transfers in/out",
        "Whether managers are buying or selling",
    )
    pop3.metric(
        "Net transfers",
        "Transfers in minus transfers out",
    )

    st.write(
        "These popularity numbers help explain manager sentiment, but they do "
        "not automatically make a player good or bad. A highly owned player may "
        "be safer, while a low-owned player may offer differential potential."
    )

    st.markdown("### Where the information comes from")

    source1, source2, source3 = st.columns(3)

    with source1:
        st.info(
            "**Official FPL data**\n\n"
            "Player prices, ownership, transfers, availability, team data "
            "and most player statistics."
        )

    with source2:
        st.info(
            "**Official FPL fixtures**\n\n"
            "Upcoming opponents, home/away status and fixture difficulty."
        )

    with source3:
        st.info(
            "**Calculated by this app**\n\n"
            "Percentile scores, transfer trends, player comparisons and "
            "recommendation explanations."
        )

    if secondary.empty:
        st.caption(
            "Optional secondary injury checking is currently disabled. "
            "The app is using official FPL availability information."
        )
    else:
        st.success(
            f"Optional secondary injury records loaded: {len(secondary)}"
        )

    st.caption(
        "Official FPL endpoints are public but undocumented and may change. "
        "Cached information refreshes every 30 minutes."
    )
