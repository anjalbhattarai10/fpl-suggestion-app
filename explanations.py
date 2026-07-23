from __future__ import annotations

from typing import List

import pandas as pd


def why_player(row: pd.Series) -> str:
    reasons: List[str] = []
    components = {
        "strong recent form": float(row.get("form_score", 0)),
        "favorable upcoming fixtures": float(row.get("fixtures_score", 0)),
        "secure recent minutes": float(row.get("minutes_score", 0)),
        "good price value": float(row.get("value_score", 0)),
        "strong team context": float(row.get("team_impact_score", 0)),
    }
    for label, _ in sorted(components.items(), key=lambda item: item[1], reverse=True)[:2]:
        reasons.append(label)

    chance = float(row.get("chance", 100))
    news = str(row.get("news", "")).strip()
    if chance < 100:
        reasons.append(f"only {chance:.0f}% official availability")
    elif news:
        reasons.append("has an official availability note")
    else:
        reasons.append("no current official injury warning")

    opponents = str(row.get("next_opponents", "")).strip()
    fixture_text = f" Next: {opponents}." if opponents else ""
    return f"Recommended because of {', '.join(reasons)}.{fixture_text}"
