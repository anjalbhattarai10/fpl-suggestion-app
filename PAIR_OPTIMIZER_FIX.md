# Two-Transfer Optimizer Fix

## Root cause

The old optimizer repeatedly:

- generated large player-pair combinations,
- created a complete proposed squad DataFrame for each pair,
- concatenated DataFrames inside the deepest loop,
- counted clubs from the complete proposed DataFrame.

That repeated pandas work made the Streamlit request appear stuck.

## Fix

- Uses small position-specific candidate pools.
- Uses dictionaries for club-limit checks.
- Performs price and score checks before creating result rows.
- Creates the result DataFrame once, after the search.
- Adds Fast, Recommended, Detailed and Deep search modes.
- Adds visible success, no-result and error messages.
- Displays user-friendly sortable results.
- Shows the best transfer plan in a highlighted verdict.

## Replace

1. Rename `optimizer_fast.py` to `optimizer.py`.
2. Rename `app_pair_optimizer_fixed.py` to `app.py`.
3. Replace those two files in the current project.

## Test

```bash
python -m py_compile optimizer.py app.py
python -m streamlit run app.py
```

Start with Search depth = Recommended.
