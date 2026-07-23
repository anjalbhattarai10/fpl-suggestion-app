from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://fantasy.premierleague.com/api"
REQUEST_TIMEOUT = 20
CACHE_TTL_SECONDS = 1800


class FPLDataError(RuntimeError):
    """Raised when an FPL endpoint cannot be read safely."""


@dataclass(frozen=True)
class SeasonState:
    current_gw: int
    next_gw: int
    finished_gws: List[int]


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {
            "User-Agent": "FPL-Suggestion-App/1.0 (+Streamlit; personal analytics)",
            "Accept": "application/json,text/plain,*/*",
        }
    )
    return session


def _get_json(endpoint: str) -> Any:
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    try:
        response = _session().get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise FPLDataError(f"Could not load {url}: {exc}") from exc
    except ValueError as exc:
        raise FPLDataError(f"The FPL API returned invalid JSON for {url}.") from exc


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_bootstrap() -> Dict[str, Any]:
    data = _get_json("bootstrap-static/")
    required = {"elements", "teams", "element_types", "events"}
    if not isinstance(data, dict) or not required.issubset(data):
        missing = sorted(required - set(data if isinstance(data, dict) else {}))
        raise FPLDataError(f"bootstrap-static/ changed shape. Missing: {missing}")
    return data


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_fixtures() -> List[Dict[str, Any]]:
    data = _get_json("fixtures/")
    if not isinstance(data, list):
        raise FPLDataError("fixtures/ changed shape; expected a list.")
    return data


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_event_live(gameweek: int) -> Dict[str, Any]:
    data = _get_json(f"event/{int(gameweek)}/live/")
    if not isinstance(data, dict) or "elements" not in data:
        raise FPLDataError(f"event/{gameweek}/live/ changed shape.")
    return data


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_element_summary(player_id: int) -> Dict[str, Any]:
    data = _get_json(f"element-summary/{int(player_id)}/")
    if not isinstance(data, dict):
        raise FPLDataError(f"element-summary/{player_id}/ changed shape.")
    data.setdefault("fixtures", [])
    data.setdefault("history", [])
    data.setdefault("history_past", [])
    return data


def season_state(events: Iterable[Dict[str, Any]]) -> SeasonState:
    events = list(events)
    finished = [int(e["id"]) for e in events if e.get("finished")]
    current = next((int(e["id"]) for e in events if e.get("is_current")), 0)
    nxt = next((int(e["id"]) for e in events if e.get("is_next")), 0)
    if current == 0 and finished:
        current = max(finished)
    if nxt == 0:
        future = [int(e["id"]) for e in events if not e.get("finished")]
        nxt = min(future) if future else min(current + 1, 38)
    return SeasonState(current_gw=current, next_gw=nxt, finished_gws=finished)


def _safe_numeric(series: pd.Series, default: float = 0.0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(default)


def bootstrap_frames() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, SeasonState]:
    bootstrap = get_bootstrap()
    players = pd.DataFrame(bootstrap["elements"])
    teams = pd.DataFrame(bootstrap["teams"])
    positions = pd.DataFrame(bootstrap["element_types"])
    state = season_state(bootstrap["events"])

    team_names = teams.set_index("id")["name"].to_dict() if not teams.empty else {}
    team_short = teams.set_index("id")["short_name"].to_dict() if not teams.empty else {}
    position_names = positions.set_index("id")["singular_name_short"].to_dict() if not positions.empty else {}

    players["player_id"] = players["id"]
    players["player_name"] = (
        players.get("first_name", "").fillna("").str.strip()
        + " "
        + players.get("second_name", "").fillna("").str.strip()
    ).str.strip()
    players["web_name"] = players.get("web_name", players["player_name"])
    players["team_name"] = players["team"].map(team_names).fillna("Unknown")
    players["team_short"] = players["team"].map(team_short).fillna("UNK")
    players["position"] = players["element_type"].map(position_names).fillna("UNK").replace({"GKP": "GK"})

    # Get the Premier League team code from the FPL teams data.
    # This code is used to build each club badge URL.
    team_codes = (
        teams.set_index("id")["code"].to_dict()
        if not teams.empty and "code" in teams.columns
        else {}
    )

    players["team_code"] = players["team"].map(team_codes)

    # Build a public Premier League club badge URL.
    players["team_logo"] = players["team_code"].apply(
        lambda code: (
            "https://resources.premierleague.com/"
            f"premierleague/badges/70/t{int(code)}.png"
            if pd.notna(code)
            else ""
        )
    )

    # Build a public Premier League player photo URL.
    # The FPL API usually provides a photo value such as "123456.jpg".
    players["player_photo"] = players.get(
        "photo",
        pd.Series("", index=players.index),
    ).fillna("").astype(str).apply(
        lambda photo: (
            "https://resources.premierleague.com/"
            "premierleague/photos/players/110x140/"
            f"p{photo.rsplit('.', 1)[0]}.png"
            if photo and photo.rsplit(".", 1)[0].isdigit()
            else ""
        )
    )

    players["price"] = _safe_numeric(
        players.get(
            "now_cost",
            pd.Series(index=players.index),
        )
    ) / 10.0

    players["total_points"] = _safe_numeric(players.get("total_points", pd.Series(index=players.index)))
    players["season_minutes"] = _safe_numeric(players.get("minutes", pd.Series(index=players.index)))
    players["form_api"] = _safe_numeric(players.get("form", pd.Series(index=players.index)))
    players["selected_by_percent"] = _safe_numeric(
        players.get("selected_by_percent", pd.Series(index=players.index))
    )
    players["transfers_in_event"] = _safe_numeric(
        players.get("transfers_in_event", pd.Series(index=players.index))
    )
    players["transfers_out_event"] = _safe_numeric(
        players.get("transfers_out_event", pd.Series(index=players.index))
    )
    players["transfers_in"] = _safe_numeric(
        players.get("transfers_in", pd.Series(index=players.index))
    )
    players["transfers_out"] = _safe_numeric(
        players.get("transfers_out", pd.Series(index=players.index))
    )
    players["net_transfers_event"] = (
        players["transfers_in_event"] - players["transfers_out_event"]
    )
    players["net_transfers_season"] = (
        players["transfers_in"] - players["transfers_out"]
    )

    players["ownership_label"] = pd.cut(
        players["selected_by_percent"],
        bins=[-0.01, 5, 10, 25, 40, float("inf")],
        labels=[
            "Ultra differential",
            "Differential",
            "Moderately owned",
            "Popular pick",
            "Highly owned",
        ],
        include_lowest=True,
        right=False,
    ).astype(str)

    players["transfer_trend"] = players["net_transfers_event"].apply(
        lambda value: (
            "Rapidly rising"
            if value >= 100_000
            else "Rising"
            if value > 0
            else "Rapidly falling"
            if value <= -100_000
            else "Falling"
            if value < 0
            else "Stable"
        )
    )

    players["cost_change_event"] = _safe_numeric(players.get("cost_change_event", pd.Series(index=players.index))) / 10.0
    players["cost_change_start"] = _safe_numeric(players.get("cost_change_start", pd.Series(index=players.index))) / 10.0
    players["chance"] = _safe_numeric(
        players.get("chance_of_playing_next_round", players.get("chance_of_playing_this_round", pd.Series(index=players.index))),
        default=100.0,
    )
    # FPL returns null for healthy players; treat null as 100% available.
    chance_raw = players.get("chance_of_playing_next_round", players.get("chance_of_playing_this_round"))
    if chance_raw is not None:
        players.loc[chance_raw.isna(), "chance"] = 100.0
    players["news"] = players.get("news", "").fillna("").astype(str)
    players["status"] = players.get("status", "a").fillna("a").astype(str)

    for col in ["expected_goals", "expected_assists", "expected_goal_involvements", "expected_goals_conceded", "influence", "creativity", "threat", "ict_index"]:
        players[col] = _safe_numeric(players.get(col, pd.Series(index=players.index)))

    return players, teams, positions, state


def recent_live_stats(finished_gws: List[int], lookback: int = 5) -> pd.DataFrame:
    selected = sorted(finished_gws)[-max(1, int(lookback)) :]
    records: List[Dict[str, Any]] = []
    for gw in selected:
        try:
            payload = get_event_live(gw)
        except FPLDataError:
            continue
        for item in payload.get("elements", []):
            stats = item.get("stats", {}) or {}
            records.append(
                {
                    "player_id": item.get("id"),
                    "gw": gw,
                    "points": stats.get("total_points", 0),
                    "minutes": stats.get("minutes", 0),
                    "starts": stats.get("starts", 0),
                    "goals": stats.get("goals_scored", 0),
                    "assists": stats.get("assists", 0),
                    "clean_sheets": stats.get("clean_sheets", 0),
                    "xg": stats.get("expected_goals", 0),
                    "xa": stats.get("expected_assists", 0),
                    "xgi": stats.get("expected_goal_involvements", 0),
                    "xgc": stats.get("expected_goals_conceded", 0),
                    "bonus": stats.get("bonus", 0),
                }
            )

    if not records:
        return pd.DataFrame(columns=["player_id", "recent_points", "recent_minutes", "recent_starts", "recent_goals", "recent_assists", "recent_xg", "recent_xa", "recent_xgi", "matches_seen"])

    df = pd.DataFrame(records)
    numeric_cols = [c for c in df.columns if c not in {"player_id", "gw"}]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    agg = df.groupby("player_id", as_index=False).agg(
        recent_points=("points", "sum"),
        recent_minutes=("minutes", "sum"),
        recent_starts=("starts", "sum"),
        recent_goals=("goals", "sum"),
        recent_assists=("assists", "sum"),
        recent_xg=("xg", "sum"),
        recent_xa=("xa", "sum"),
        recent_xgi=("xgi", "sum"),
        recent_clean_sheets=("clean_sheets", "sum"),
        recent_bonus=("bonus", "sum"),
        matches_seen=("gw", "count"),
    )
    return agg


def upcoming_fixture_features(fixtures: List[Dict[str, Any]], teams: pd.DataFrame, next_gw: int, horizon: int = 5) -> pd.DataFrame:
    fixtures_df = pd.DataFrame(fixtures)
    if fixtures_df.empty:
        return pd.DataFrame(columns=["team", "fixture_count", "avg_fdr", "fixture_score_raw", "next_opponents"])

    team_short = teams.set_index("id")["short_name"].to_dict() if not teams.empty else {}
    rows: List[Dict[str, Any]] = []
    max_event = next_gw + max(1, int(horizon)) - 1
    future = fixtures_df[
        fixtures_df.get("event", pd.Series(index=fixtures_df.index)).notna()
        & (pd.to_numeric(fixtures_df["event"], errors="coerce") >= next_gw)
        & (pd.to_numeric(fixtures_df["event"], errors="coerce") <= max_event)
        & (~fixtures_df.get("finished", False).fillna(False))
    ]

    for _, fixture in future.iterrows():
        home = int(fixture["team_h"])
        away = int(fixture["team_a"])
        event = int(fixture["event"])
        rows.append({"team": home, "event": event, "difficulty": float(fixture.get("team_h_difficulty", 3)), "opponent": f"{team_short.get(away, 'UNK')} (H)"})
        rows.append({"team": away, "event": event, "difficulty": float(fixture.get("team_a_difficulty", 3)), "opponent": f"{team_short.get(home, 'UNK')} (A)"})

    if not rows:
        return pd.DataFrame(columns=["team", "fixture_count", "avg_fdr", "fixture_score_raw", "next_opponents"])

    team_fx = pd.DataFrame(rows).sort_values(["team", "event"])
    result = team_fx.groupby("team", as_index=False).agg(
        fixture_count=("difficulty", "count"),
        avg_fdr=("difficulty", "mean"),
        next_opponents=("opponent", lambda values: ", ".join(values)),
    )
    # FDR 1 is easiest and 5 hardest. Convert to a higher-is-better 0..100 raw score.
    result["fixture_score_raw"] = ((5.0 - result["avg_fdr"]) / 4.0 * 100.0).clip(0, 100)
    # Double gameweeks gain a modest bonus; blank gameweeks receive zero fixtures.
    result["fixture_score_raw"] = (result["fixture_score_raw"] + (result["fixture_count"] - horizon).clip(lower=0) * 5).clip(0, 100)
    return result


def team_strength_features(teams: pd.DataFrame) -> pd.DataFrame:
    if teams.empty:
        return pd.DataFrame(columns=["team", "team_attack_raw", "team_defence_raw"])
    result = teams.copy()
    attack_cols = [c for c in ["strength_attack_home", "strength_attack_away"] if c in result.columns]
    defence_cols = [c for c in ["strength_defence_home", "strength_defence_away"] if c in result.columns]
    result["team_attack_raw"] = result[attack_cols].apply(pd.to_numeric, errors="coerce").mean(axis=1) if attack_cols else 0
    # FPL's defence strength uses higher-is-stronger values.
    result["team_defence_raw"] = result[defence_cols].apply(pd.to_numeric, errors="coerce").mean(axis=1) if defence_cols else 0
    return result[["id", "team_attack_raw", "team_defence_raw"]].rename(columns={"id": "team"})


def optional_secondary_injury_rows() -> pd.DataFrame:
    """Best-effort generic scraper.

    Set SECONDARY_INJURY_URL in the environment or Streamlit secrets. The function
    extracts table rows containing availability terms. It intentionally does not
    depend on one specific commercial website's HTML structure.
    """
    url = os.getenv("SECONDARY_INJURY_URL", "").strip()
    if not url:
        try:
            url = str(st.secrets.get("SECONDARY_INJURY_URL", "")).strip()
        except Exception:
            url = ""
    if not url:
        return pd.DataFrame(columns=["secondary_name", "secondary_status", "secondary_source"])

    try:
        response = _session().get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.RequestException:
        return pd.DataFrame(columns=["secondary_name", "secondary_status", "secondary_source"])

    keywords = re.compile(r"injur|doubt|suspend|unavailable|fitness|return|knock|illness", re.I)
    rows = []
    for tr in soup.select("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.select("th,td")]
        text = " | ".join(cells)
        if len(cells) >= 2 and keywords.search(text):
            rows.append({"secondary_name": cells[0], "secondary_status": " | ".join(cells[1:]), "secondary_source": url})
    return pd.DataFrame(rows).drop_duplicates() if rows else pd.DataFrame(columns=["secondary_name", "secondary_status", "secondary_source"])


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def attach_secondary_injuries(players: pd.DataFrame, secondary: pd.DataFrame) -> pd.DataFrame:
    result = players.copy()
    result["secondary_status"] = ""
    result["injury_source_disagreement"] = False
    if secondary.empty:
        return result

    lookup: Dict[str, str] = {}
    for _, row in secondary.iterrows():
        key = normalize_name(row.get("secondary_name", ""))
        if key:
            lookup[key] = str(row.get("secondary_status", ""))

    for idx, player in result.iterrows():
        candidates = [normalize_name(player.get("player_name", "")), normalize_name(player.get("web_name", ""))]
        status = next((lookup[k] for k in candidates if k in lookup), "")
        result.at[idx, "secondary_status"] = status
        official_concern = player.get("chance", 100) < 100 or bool(str(player.get("news", "")).strip()) or player.get("status") != "a"
        secondary_concern = bool(status)
        result.at[idx, "injury_source_disagreement"] = official_concern != secondary_concern if status else False
    return result
