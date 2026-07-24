# Phase 4 – Full Squad Intelligence

## Purpose

Phase 4 moves FPL Scout from player-level recommendations to complete squad
planning. It adds a Team Center while preserving all Phase 2 and Phase 3
features.

## New files

### `squad_engine.py`

Contains:

- complete squad validation
- official position-count checks
- three-player club-limit checks
- budget validation
- best legal starting XI selection
- formation selection
- captain and vice-captain selection
- squad ratings
- budget allocation analysis
- fixture matrix generation
- chip-readiness indicators

The file contains extensive comments explaining every major decision and formula.

### `optimizer.py`

Contains:

- wildcard squad builder
- strategy presets
- budget reservation logic
- club-limit enforcement
- local squad upgrade pass
- coordinated two-transfer optimizer

The wildcard builder is a transparent heuristic optimizer. It is designed for
speed and explainability rather than claiming a mathematically guaranteed global
optimum.

### `phase4_explanations.py`

Converts model results into readable squad, wildcard, budget and starting-XI
summaries.

## Updated `app.py`

A new top-level `Team Center` tab has been added with:

1. Squad Analyzer
2. Best XI
3. Wildcard Builder
4. Two-Transfer Optimizer
5. Fixture Calendar
6. Chip Readiness

## GUI improvements

The interface now has a stronger football identity:

- CSS-generated striped pitch hero
- pitch markings
- football field starting-XI view
- player cards placed by position
- substitute bench strip
- green analytics accents
- team rating cards
- football-themed Team Center banner
- responsive layouts for smaller screens

No external background image is required.

## Squad ratings

The dashboard includes:

- overall squad score
- starting XI
- bench
- captaincy
- fixtures
- availability
- value
- risk

The combined overall squad score gives the greatest influence to the starting XI,
then considers bench depth, captaincy, fixtures, availability and value.

## Wildcard strategies

- Balanced
- Form
- Fixtures
- Value
- Safe

All strategies still enforce:

- 2 goalkeepers
- 5 defenders
- 5 midfielders
- 3 forwards
- maximum 3 players per club
- selected budget

## Run

```bash
python -m streamlit run app.py
```

## Recommended test order

1. Confirm existing Player Rankings loads.
2. Confirm AI Center still works.
3. Open Team Center.
4. Verify the default squad is generated.
5. Change players in Squad Analyzer.
6. Verify rule errors appear for invalid squads.
7. Open Best XI and inspect the pitch.
8. Build wildcard squads with all five strategies.
9. Run the Two-Transfer Optimizer.
10. Review Fixture Calendar.
11. Review Chip Readiness.
12. Resize the browser to confirm responsive layout.

## Important limitations

- The wildcard algorithm is heuristic and does not claim to find the absolute
  global optimum.
- Chip readiness uses current fixture and player data only.
- Price and score indicators remain decision-support tools rather than guaranteed
  future FPL outcomes.
