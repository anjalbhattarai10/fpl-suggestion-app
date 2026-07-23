# FPL Player Suggestion App

A Streamlit app that ranks Fantasy Premier League players using recent form, fixtures, minutes, availability, value, and team context.

## Run

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Optional secondary injury source:

```bash
# Windows PowerShell
$env:SECONDARY_INJURY_URL="https://example.com/injuries"

# macOS/Linux
export SECONDARY_INJURY_URL="https://example.com/injuries"
```
