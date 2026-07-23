# Phase 3 – AI Integration

## Overview

Phase 3 adds an explainable AI-style decision layer to the existing FPL Scout
application. It does **not** require a paid AI API. Every verdict is generated
from visible official FPL data and from the existing model scores.

This design was chosen so that:

1. Recommendations remain transparent.
2. The project can run locally and on Streamlit Cloud without an API key.
3. Every result can be traced to a formula.
4. A real language model can be added later without rewriting the scoring system.

## Files changed

### `ai_engine.py` — new

This is the core Phase 3 file.

It adds:

- `captain_score`
- `differential_score`
- `risk_score`
- `ai_confidence`
- `price_momentum_score`
- `fixture_swing_score`

It also contains helper functions that return:

- structured Buy/Hold/Watch/Avoid verdicts
- captain recommendations
- differential recommendations
- price pressure candidates
- fixture swing candidates

### `scoring.py` — updated

The existing Phase 2 score remains unchanged.

At the end of `build_scores()`, the scored DataFrame is passed to:

```python
df = add_phase3_scores(df)
```

This means Phase 3 builds on top of Phase 2 rather than replacing it.

### `explanations.py` — updated

A new function was added:

```python
ai_scout_explanation(row)
```

The AI engine makes the decision, and `explanations.py` converts that structured
decision into readable text. Keeping those responsibilities separate makes the
code easier to maintain.

### `app.py` — updated

A new top-level tab was added:

```text
AI Center
```

It contains five sub-tabs:

1. AI Scout
2. Captain picks
3. Differential finder
4. Price watch
5. Fixture swings

## Score formulas

### Captain score

Captaincy favors immediate upside and reliability:

- 32% recent form
- 25% fixtures
- 18% playing-time security
- 15% team impact
- 10% availability

A small position adjustment gives midfielders and forwards more captaincy upside,
while still allowing defenders and goalkeepers to appear when their data is strong.

### Differential score

Differential recommendations combine:

- 30% overall recommendation score
- 25% form
- 20% fixtures
- 15% value
- 10% low-ownership opportunity

The ownership filter in the UI can be changed by the user.

### Risk score

Higher risk is worse. It is based on:

- 40% availability risk
- 30% minutes/rotation risk
- 20% fixture risk
- 10% negative transfer sentiment

### AI confidence

Confidence is higher when:

- the overall recommendation score is strong
- the model factors agree with each other
- the player's risk score is low

This prevents a player with one excellent statistic and several poor statistics
from receiving unjustifiably high confidence.

### Price momentum score

This is not an official price-rise prediction. It combines:

- relative net-transfer momentum
- recent form
- value score

The transfer component is converted to a percentile so it automatically adapts
to the size of the current gameweek transfer market.

### Fixture swing score

This identifies players with attractive upcoming schedules using:

- 70% fixture quality
- 20% team impact
- 10% current form

## Running the project

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## Testing checklist

- Open Player Rankings and confirm Phase 2 rankings still load.
- Open Compare Players and compare two or three players.
- Open Transfer Planner and verify replacement options.
- Open AI Center.
- Test one player in AI Scout.
- Verify captain picks show progress scores.
- Change differential ownership from 10% to another value.
- Confirm Price Watch shows transfer momentum.
- Confirm Fixture Swings shows upcoming opponents.
- Open Player Detail to ensure existing research views still work.

## Important interpretation note

All Phase 3 scores are decision-support indicators on a 0–100 scale. They are not
guaranteed FPL points, betting odds or official FPL predictions.
