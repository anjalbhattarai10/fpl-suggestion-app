"""Global visual design system for the FPL Scout Streamlit app."""

from __future__ import annotations

import streamlit as st


APP_CSS = r"""
<style>
:root {
    --fpl-purple-950: #16001f;
    --fpl-purple-900: #25002d;
    --fpl-purple-800: #37003c;
    --fpl-purple-700: #52065d;
    --fpl-green-500: #00c96b;
    --fpl-green-400: #00e676;
    --fpl-green-300: #00ff87;
    --fpl-cyan-400: #05d9f5;
    --fpl-yellow-400: #f6c744;
    --fpl-red-500: #e5485d;
    --fpl-orange-500: #ef8f00;
    --ink-950: #211128;
    --ink-800: #3d3042;
    --ink-650: #655b6a;
    --ink-500: #817687;
    --surface-0: #ffffff;
    --surface-1: #f8faf9;
    --surface-2: #eef4f0;
    --border: rgba(55, 0, 60, 0.11);
    --shadow-sm: 0 8px 22px rgba(31, 16, 40, 0.06);
    --shadow-md: 0 14px 36px rgba(31, 16, 40, 0.10);
    --radius-sm: 10px;
    --radius-md: 16px;
    --radius-lg: 22px;
}

/* ---------- Global foundation ---------- */
html {
    scroll-behavior: smooth;
}

body,
.stApp {
    color: var(--ink-950);
    background:
        radial-gradient(circle at 8% 2%, rgba(0,255,135,.12), transparent 19rem),
        radial-gradient(circle at 94% 0%, rgba(5,217,245,.09), transparent 22rem),
        repeating-linear-gradient(
            90deg,
            rgba(15,117,64,.022) 0,
            rgba(15,117,64,.022) 90px,
            rgba(255,255,255,.02) 90px,
            rgba(255,255,255,.02) 180px
        ),
        linear-gradient(180deg, #f9fbfa 0%, #eef4f0 100%) !important;
}

.stApp,
.stApp p,
.stApp label,
.stApp input,
.stApp button,
.stApp textarea {
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
}

.stApp h1,
.stApp h2,
.stApp h3,
.stApp h4,
.stApp h5,
.stApp h6 {
    color: var(--ink-950);
    letter-spacing: -.025em;
}

.stApp h1 { font-size: clamp(2rem, 4vw, 3.25rem); }
.stApp h2 { font-size: clamp(1.5rem, 2.4vw, 2.1rem); }
.stApp h3 { font-size: clamp(1.15rem, 1.6vw, 1.4rem); }

.block-container {
    max-width: 1540px;
    padding-top: 1rem;
    padding-bottom: 3.5rem;
}

*:focus-visible {
    outline: 3px solid rgba(5,217,245,.72) !important;
    outline-offset: 2px !important;
    border-radius: 8px;
}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {
    background:
        radial-gradient(circle at 30% 5%, rgba(0,255,135,.10), transparent 16rem),
        linear-gradient(180deg, var(--fpl-purple-950), var(--fpl-purple-800) 62%, #4a0052);
    border-right: 1px solid rgba(255,255,255,.08);
}

section[data-testid="stSidebar"] * {
    color: #fff;
}

section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] div[data-testid="stCaptionContainer"] p {
    color: rgba(255,255,255,.74) !important;
}

section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: var(--fpl-green-300);
}

.sidebar-guide {
    margin: .5rem 0 1rem;
    padding: .95rem;
    border: 1px solid rgba(255,255,255,.15);
    border-radius: var(--radius-md);
    background: rgba(255,255,255,.075);
    box-shadow: inset 0 1px 0 rgba(255,255,255,.04);
}

.sidebar-guide-title {
    margin-bottom: .35rem;
    color: var(--fpl-green-300);
    font-size: .84rem;
    font-weight: 850;
}

.sidebar-guide-text {
    color: rgba(255,255,255,.78);
    font-size: .78rem;
    line-height: 1.5;
}

/* ---------- Hero and page banners ---------- */
.hero {
    position: relative;
    isolation: isolate;
    min-height: 210px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    overflow: hidden;
    padding: 2rem 2.25rem;
    margin-bottom: 1.15rem;
    border: 1px solid rgba(255,255,255,.26);
    border-radius: 26px;
    color: #fff;
    background:
        radial-gradient(circle at 86% 18%, rgba(0,255,135,.28), transparent 18rem),
        linear-gradient(rgba(10,20,16,.15), rgba(10,20,16,.26)),
        repeating-linear-gradient(
            90deg,
            #0a7b45 0,
            #0a7b45 100px,
            #08713f 100px,
            #08713f 200px
        );
    box-shadow: 0 22px 55px rgba(6,68,37,.24);
}

.hero::before {
    content: "";
    position: absolute;
    inset: 16px;
    z-index: -1;
    border: 2px solid rgba(255,255,255,.34);
    border-radius: 18px;
}

.hero::after {
    content: "";
    position: absolute;
    width: 170px;
    height: 170px;
    right: 7%;
    top: calc(50% - 85px);
    z-index: -1;
    border: 2px solid rgba(255,255,255,.24);
    border-radius: 50%;
}

.hero-kicker {
    margin-bottom: .35rem;
    color: var(--fpl-green-300);
    font-size: .76rem;
    font-weight: 900;
    letter-spacing: .14em;
    text-transform: uppercase;
}

.hero h1 {
    margin: 0;
    color: #fff;
    line-height: 1.04;
}

.hero p {
    max-width: 740px;
    margin: .8rem 0 0;
    color: rgba(255,255,255,.86);
    font-size: 1rem;
    line-height: 1.55;
}

.hero-tags {
    display: flex;
    flex-wrap: wrap;
    gap: .45rem;
    margin-top: 1rem;
}

.hero-tag {
    padding: .28rem .62rem;
    border: 1px solid rgba(255,255,255,.18);
    border-radius: 999px;
    color: #fff;
    background: rgba(22,0,31,.25);
    font-size: .72rem;
    font-weight: 800;
}

.team-center-banner,
.help-center-banner {
    position: relative;
    overflow: hidden;
    padding: 1.35rem 1.5rem;
    margin: .45rem 0 1rem;
    border-radius: 21px;
    color: #fff;
    box-shadow: var(--shadow-md);
}

.team-center-banner {
    background: linear-gradient(115deg, #102f22, #0b6f40 65%, #00a85a);
}

.help-center-banner {
    background:
        radial-gradient(circle at 90% 20%, rgba(0,255,135,.22), transparent 25%),
        linear-gradient(120deg, #25002d, #4a0052 58%, #09663d);
}

.team-center-banner h2,
.help-center-banner h2 {
    margin: 0;
    color: #fff;
}

.team-center-banner p,
.help-center-banner p {
    margin: .45rem 0 0;
    color: rgba(255,255,255,.84);
}

/* ---------- Tabs and navigation ---------- */
div[data-baseweb="tab-list"] {
    gap: .28rem;
    padding: .28rem;
    overflow-x: auto;
    overflow-y: hidden;
    white-space: nowrap;
    border: 1px solid rgba(55,0,60,.07);
    border-radius: 14px 14px 0 0;
    background: rgba(255,255,255,.72);
    scrollbar-width: thin;
}

button[data-baseweb="tab"] {
    flex: 0 0 auto;
    min-width: max-content;
    height: 2.85rem;
    padding: 0 .9rem;
    border-radius: 10px 10px 4px 4px;
    color: var(--ink-650);
    font-weight: 760;
}

button[data-baseweb="tab"]:hover {
    color: var(--fpl-purple-800);
    background: rgba(55,0,60,.055);
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: #fff !important;
    background: linear-gradient(135deg, var(--fpl-purple-800), var(--fpl-purple-700));
    border-bottom-color: var(--fpl-green-300) !important;
    box-shadow: 0 7px 18px rgba(55,0,60,.19);
}

/* ---------- Controls ---------- */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
div[data-testid="stNumberInput"] input,
div[data-testid="stTextInput"] input,
div[data-testid="stMultiSelect"] > div,
textarea {
    min-height: 44px;
    border-color: rgba(55,0,60,.17) !important;
    border-radius: 12px !important;
    color: var(--ink-950) !important;
    background: rgba(255,255,255,.97) !important;
    box-shadow: 0 3px 10px rgba(31,16,40,.025);
}

div[data-baseweb="select"] > div:hover,
div[data-baseweb="input"] > div:hover,
div[data-testid="stMultiSelect"] > div:hover {
    border-color: rgba(0,201,107,.68) !important;
}

div[data-testid="stWidgetLabel"] p,
.stApp label {
    color: var(--ink-950) !important;
    font-weight: 760 !important;
}

section[data-testid="stSidebar"] div[data-testid="stWidgetLabel"] p,
section[data-testid="stSidebar"] label {
    color: #fff !important;
}

/* Multiselect selected tokens */
span[data-baseweb="tag"] {
    color: #fff !important;
    background: linear-gradient(135deg, var(--fpl-purple-800), var(--fpl-purple-700)) !important;
    border-radius: 999px !important;
}

/* Sliders */
div[data-baseweb="slider"] {
    padding-top: .25rem;
    padding-bottom: .45rem;
}

div[data-baseweb="slider"] > div > div {
    border-radius: 999px;
    background: linear-gradient(90deg, rgba(0,255,135,.30), rgba(5,217,245,.22));
}

div[data-baseweb="slider"] [role="slider"] {
    width: 21px !important;
    height: 21px !important;
    border: 3px solid #fff !important;
    background: linear-gradient(145deg, var(--fpl-green-300), var(--fpl-cyan-400)) !important;
    box-shadow:
        0 0 0 3px rgba(55,0,60,.12),
        0 5px 13px rgba(0,201,107,.34) !important;
    transition: transform .18s ease, box-shadow .18s ease;
}

div[data-baseweb="slider"] [role="slider"]:hover {
    transform: scale(1.12);
    box-shadow:
        0 0 0 4px rgba(0,255,135,.20),
        0 8px 18px rgba(0,201,107,.38) !important;
}

/* Buttons */
.stButton > button,
.stDownloadButton > button {
    min-height: 44px;
    border: 0 !important;
    border-radius: 12px !important;
    color: #fff !important;
    background: linear-gradient(135deg, var(--fpl-purple-800), var(--fpl-purple-700)) !important;
    font-weight: 800 !important;
    box-shadow: 0 7px 18px rgba(55,0,60,.18);
    transition: transform .17s ease, box-shadow .17s ease, background .17s ease;
}

.stButton > button:hover,
.stDownloadButton > button:hover {
    transform: translateY(-1px);
    color: var(--fpl-purple-800) !important;
    background: linear-gradient(135deg, var(--fpl-green-300), var(--fpl-cyan-400)) !important;
    box-shadow: 0 11px 24px rgba(0,201,107,.25);
}

.stButton > button:disabled,
.stDownloadButton > button:disabled {
    transform: none;
    opacity: .55;
    color: #746a79 !important;
    background: #e7e3e9 !important;
    box-shadow: none;
    cursor: not-allowed;
}

/* ---------- Metrics, captions and alerts ---------- */
div[data-testid="stMetric"] {
    min-height: 108px;
    padding: 1rem 1.1rem;
    border: 1px solid var(--border);
    border-radius: 18px;
    background: rgba(255,255,255,.94);
    box-shadow: var(--shadow-sm);
}

div[data-testid="stMetricLabel"] {
    color: var(--ink-500);
    font-weight: 700;
}

div[data-testid="stMetricValue"] {
    color: var(--fpl-purple-800);
    font-weight: 900;
}

div[data-testid="stCaptionContainer"] {
    margin-top: .12rem;
    padding: .38rem .58rem;
    border-left: 4px solid var(--fpl-green-500);
    border-radius: 8px;
    background: linear-gradient(90deg, rgba(0,255,135,.09), transparent);
}

div[data-testid="stCaptionContainer"] p {
    color: #514557 !important;
    line-height: 1.45;
}

section[data-testid="stSidebar"] div[data-testid="stCaptionContainer"] {
    border-left-color: var(--fpl-green-300);
    background: rgba(255,255,255,.06);
}

div[data-testid="stAlert"] {
    border: 1px solid rgba(55,0,60,.10);
    border-radius: 14px;
    box-shadow: var(--shadow-sm);
}

/* ---------- Section headings and reusable panels ---------- */
.section-heading {
    margin: .75rem 0 1rem;
}

.section-heading h2 {
    margin-bottom: .15rem;
}

.section-heading p {
    max-width: 920px;
    margin-top: 0;
    color: var(--ink-500);
    line-height: 1.55;
}

.filter-panel,
.selection-panel,
.indicator-section {
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: rgba(255,255,255,.78);
    box-shadow: var(--shadow-sm);
}

.filter-summary {
    display: flex;
    flex-wrap: wrap;
    gap: .4rem;
    margin: .7rem 0 .9rem;
}

.filter-chip,
.status-chip,
.info-chip {
    display: inline-flex;
    align-items: center;
    gap: .25rem;
    padding: .28rem .6rem;
    border-radius: 999px;
    font-size: .72rem;
    font-weight: 800;
}

.filter-chip {
    color: var(--fpl-purple-800);
    background: #efe9f2;
}

.status-available { color: #075c34; background: #d9f8e7; }
.status-doubtful { color: #765500; background: #fff0bf; }
.status-injured { color: #862436; background: #ffe1e6; }
.status-suspended { color: #6b2b78; background: #f2dcf5; }

.empty-state {
    padding: 1.6rem;
    border: 1px dashed rgba(55,0,60,.22);
    border-radius: var(--radius-lg);
    text-align: center;
    background: rgba(255,255,255,.65);
}

.empty-state-icon { font-size: 2rem; }
.empty-state-title {
    margin-top: .4rem;
    color: var(--ink-950);
    font-size: 1rem;
    font-weight: 850;
}
.empty-state-text {
    max-width: 620px;
    margin: .3rem auto 0;
    color: var(--ink-500);
    font-size: .84rem;
}

/* ---------- Player cards ---------- */
.player-card {
    min-height: 360px;
    overflow: hidden;
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 20px;
    background: rgba(255,255,255,.97);
    box-shadow: var(--shadow-md);
    transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease;
}

.player-card:hover {
    transform: translateY(-3px);
    border-color: rgba(0,201,107,.40);
    box-shadow: 0 18px 42px rgba(31,16,40,.14);
}

.player-card.is-selected {
    border: 2px solid var(--fpl-green-500);
    background: linear-gradient(180deg, #fff, #f1fff7);
}

.player-card-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: .75rem;
}

.player-image-shell {
    position: relative;
    width: 94px;
    height: 116px;
    overflow: hidden;
    border-radius: 16px;
    background:
        radial-gradient(circle at 50% 88%, rgba(0,255,135,.24), transparent 46%),
        linear-gradient(145deg, #eee8f1, #e8fff2);
}

.player-photo {
    width: 100%;
    height: 100%;
    object-fit: contain;
    object-position: bottom;
}

.player-photo-fallback {
    position: absolute;
    inset: 0;
    display: none;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
}

.player-image-shell.image-failed .player-photo-fallback {
    display: flex;
}

.club-logo {
    width: 44px;
    height: 44px;
    object-fit: contain;
}

.pick-rank {
    color: var(--ink-500);
    font-size: .67rem;
    font-weight: 900;
    letter-spacing: .1em;
    text-align: right;
}

.player-card h3 {
    margin: .75rem 0 .08rem;
    color: var(--ink-950);
    font-size: 1.15rem;
}

.player-meta {
    color: var(--ink-500);
    font-size: .82rem;
}

.player-primary-stats {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: .42rem;
    margin-top: .8rem;
}

.player-stat {
    padding: .48rem;
    border-radius: 10px;
    background: #f3f1f5;
}

.player-stat .k {
    color: var(--ink-500);
    font-size: .58rem;
    font-weight: 850;
    letter-spacing: .04em;
    text-transform: uppercase;
}

.player-stat .v {
    margin-top: .12rem;
    color: var(--ink-950);
    font-size: .86rem;
    font-weight: 900;
}

.score-row {
    display: flex;
    justify-content: space-between;
    gap: .5rem;
    margin-top: .75rem;
    padding-top: .7rem;
    border-top: 1px solid #ece7ef;
}

.score-pill,
.price-pill {
    padding: .34rem .7rem;
    border-radius: 999px;
    font-weight: 900;
}

.score-pill {
    color: #063f25;
    background: var(--fpl-green-300);
}

.price-pill {
    color: #fff;
    background: var(--fpl-purple-800);
}

.reason {
    margin-top: .72rem;
    padding: .68rem .72rem;
    border-left: 4px solid var(--fpl-green-500);
    border-radius: 9px;
    color: #5e5363;
    background: #f7fbf8;
    font-size: .76rem;
    line-height: 1.45;
}

/* ---------- Player research hero ---------- */
.player-profile-hero {
    display: grid;
    grid-template-columns: 160px minmax(0, 1fr);
    gap: 1.15rem;
    align-items: center;
    padding: 1.1rem;
    margin: .8rem 0 1rem;
    border: 1px solid var(--border);
    border-radius: 22px;
    background:
        radial-gradient(circle at 92% 12%, rgba(0,255,135,.18), transparent 18rem),
        linear-gradient(145deg, #fff, #f4fff8);
    box-shadow: var(--shadow-md);
}

.detail-player-photo {
    width: 150px;
    height: 175px;
    object-fit: contain;
    object-position: bottom;
    border-radius: 18px;
    background: linear-gradient(145deg, #eee8f1, #e8fff2);
}

.detail-club-logo {
    width: 55px;
    height: 55px;
    object-fit: contain;
}

.profile-identity {
    display: flex;
    align-items: center;
    gap: .7rem;
}

.profile-kicker {
    color: var(--ink-500);
    font-size: .75rem;
    font-weight: 850;
    letter-spacing: .08em;
    text-transform: uppercase;
}

.profile-name {
    margin-top: .08rem;
    color: var(--ink-950);
    font-size: clamp(1.65rem, 3vw, 2.35rem);
    font-weight: 950;
    line-height: 1.08;
}

.profile-sub {
    margin-top: .24rem;
    color: var(--ink-500);
    font-size: .86rem;
}

.profile-stat-grid {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: .55rem;
    margin-top: .85rem;
}

.profile-stat {
    padding: .62rem;
    border: 1px solid rgba(55,0,60,.06);
    border-radius: 12px;
    background: rgba(255,255,255,.85);
}

.profile-stat .k {
    color: var(--ink-500);
    font-size: .58rem;
    font-weight: 850;
    text-transform: uppercase;
}

.profile-stat .v {
    margin-top: .15rem;
    color: var(--ink-950);
    font-size: .95rem;
    font-weight: 900;
}

/* ---------- Recommendations, details and analysis ---------- */
.decision-callout,
.team-note,
.plain-example,
.viz-callout {
    padding: 1rem 1.05rem;
    margin: .8rem 0 1rem;
    border-left: 5px solid var(--fpl-green-500);
    border-radius: 14px;
    color: #37283c;
    background: linear-gradient(135deg, rgba(0,255,135,.08), #fff);
    box-shadow: var(--shadow-sm);
    line-height: 1.55;
}

.detail-insight-grid,
.fixture-card-grid,
.method-grid,
.help-analysis-grid,
.squad-score-grid,
.chip-grid,
.bench-strip {
    display: grid;
    gap: .8rem;
}

.detail-insight-grid { grid-template-columns: repeat(4, minmax(0,1fr)); }
.fixture-card-grid { grid-template-columns: repeat(4, minmax(0,1fr)); }
.method-grid { grid-template-columns: repeat(3, minmax(0,1fr)); }
.help-analysis-grid { grid-template-columns: repeat(3, minmax(0,1fr)); }
.squad-score-grid,
.chip-grid,
.bench-strip { grid-template-columns: repeat(4, minmax(0,1fr)); }

.detail-insight-card,
.fixture-card,
.method-card,
.help-analysis-card,
.squad-score-card,
.chip-card,
.bench-card,
.advisor-card,
.transfer-summary-card {
    border: 1px solid var(--border);
    border-radius: 16px;
    background: rgba(255,255,255,.97);
    box-shadow: var(--shadow-sm);
}

.detail-insight-card,
.fixture-card,
.method-card,
.help-analysis-card,
.squad-score-card,
.chip-card,
.bench-card,
.transfer-summary-card {
    padding: .9rem;
}

.detail-insight-card {
    position: relative;
    overflow: hidden;
    min-height: 138px;
}

.detail-insight-card::before {
    content: "";
    position: absolute;
    inset: 0 auto 0 0;
    width: 5px;
    background: var(--fpl-purple-800);
}

.detail-insight-card.season::before { background: #6f42c1; }
.detail-insight-card.recent::before { background: var(--fpl-orange-500); }
.detail-insight-card.fixture::before { background: #2b9f67; }
.detail-insight-card.model::before { background: var(--fpl-green-500); }

.detail-insight-card .label,
.squad-score-card .label,
.chip-card .label {
    color: var(--ink-500);
    font-size: .66rem;
    font-weight: 850;
    letter-spacing: .05em;
    text-transform: uppercase;
}

.detail-insight-card .value,
.squad-score-card .value,
.chip-card .value {
    margin-top: .2rem;
    color: var(--ink-950);
    font-size: 1.25rem;
    font-weight: 900;
}

.detail-insight-card .note,
.help-analysis-card p,
.method-card p {
    color: var(--ink-500);
    font-size: .78rem;
    line-height: 1.45;
}

.help-analysis-card {
    border-top: 4px solid var(--fpl-green-500);
}

.help-analysis-card:nth-child(2) { border-top-color: var(--fpl-cyan-400); }
.help-analysis-card:nth-child(3) { border-top-color: var(--fpl-yellow-400); }
.help-analysis-card:nth-child(5) { border-top-color: var(--fpl-red-500); }

.help-analysis-card strong {
    display: block;
    margin-bottom: .28rem;
    color: var(--fpl-purple-800);
}

.indicator-key {
    display: grid;
    grid-template-columns: repeat(3, minmax(0,1fr));
    gap: .7rem;
    margin: .75rem 0 1rem;
}

.indicator-key-item {
    padding: .72rem;
    border: 1px solid var(--border);
    border-radius: 13px;
    color: var(--ink-650);
    background: #fff;
    font-size: .76rem;
    line-height: 1.4;
}

.indicator-key-item strong {
    display: block;
    margin-bottom: .2rem;
    color: var(--ink-950);
}

/* ---------- Fixtures and status ---------- */
.fixture-strip {
    display: flex;
    flex-wrap: wrap;
    gap: .32rem;
    margin-top: .52rem;
}

.fixture-pill,
.fixture-category,
.fdr-chip {
    display: inline-flex;
    align-items: center;
    padding: .25rem .5rem;
    border-radius: 999px;
    font-size: .68rem;
    font-weight: 850;
}

.fixture-pill.easy,
.fixture-easy,
.category-easy,
.fdr-1,
.fdr-2 {
    color: #075c34;
    background: #d9f8e7;
}

.fixture-pill.medium,
.fixture-neutral,
.category-medium,
.fdr-3 {
    color: #765500;
    background: #fff0bf;
}

.fixture-pill.hard,
.fixture-hard,
.category-hard,
.fdr-4,
.fdr-5 {
    color: #862436;
    background: #ffe1e6;
}

.fixture-pill.unknown,
.fdr-0 {
    color: #5f5663;
    background: #ece8ef;
}

.fixture-card.fdr-card-1,
.fixture-card.fdr-card-2 {
    border-color: #8bd7ae;
    background: linear-gradient(180deg, #effcf5, #dff7e9);
}

.fixture-card.fdr-card-3 {
    border-color: #e4cb79;
    background: linear-gradient(180deg, #fffaf0, #fff0c7);
}

.fixture-card.fdr-card-4,
.fixture-card.fdr-card-5 {
    border-color: #e8a0aa;
    background: linear-gradient(180deg, #fff5f6, #ffe0e5);
}

/* ---------- Score bars ---------- */
.score-legend,
.score-band,
.fixture-difficulty-legend {
    display: grid;
    overflow: hidden;
    margin: .75rem 0 1rem;
    border: 1px solid var(--border);
    border-radius: 13px;
}

.score-legend,
.score-band { grid-template-columns: repeat(4, minmax(0,1fr)); }
.fixture-difficulty-legend { grid-template-columns: repeat(3, minmax(0,1fr)); }

.score-legend div,
.score-band div,
.fixture-difficulty-legend div {
    padding: .7rem;
    text-align: center;
    font-size: .76rem;
    font-weight: 850;
}

.score-weak,
.score-low { color:#862436; background:#ffe1e6; }
.score-watch { color:#765500; background:#fff0bf; }
.score-good { color:#12613b; background:#ddf5e8; }
.score-strong,
.score-top { color:#075c34; background:#c9f9df; }

.breakdown-grid {
    display: grid;
    gap: .65rem;
}

.breakdown-row {
    display: grid;
    grid-template-columns: 180px minmax(0,1fr) 64px;
    align-items: center;
    gap: .7rem;
    padding: .7rem .8rem;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: #fff;
}

.breakdown-label {
    color: var(--ink-950);
    font-size: .82rem;
    font-weight: 800;
}

.breakdown-track {
    height: 13px;
    overflow: hidden;
    border-radius: 999px;
    background: #ebe7ee;
}

.breakdown-fill { height:100%; border-radius:999px; }
.fill-weak { background:linear-gradient(90deg,#ff9aa6,#ef4458); }
.fill-watch { background:linear-gradient(90deg,#ffe082,#f6b800); }
.fill-good { background:linear-gradient(90deg,#94e2b8,#2eb872); }
.fill-strong { background:linear-gradient(90deg,#4ee39a,#00a85a); }

.breakdown-value {
    text-align: right;
    font-size: .86rem;
    font-weight: 900;
}

.value-weak { color:#b42335; }
.value-watch { color:#8a6800; }
.value-good { color:#167246; }
.value-strong { color:#007c42; }

/* ---------- Transfer and comparison cards ---------- */
.transfer-summary-grid,
.advisor-metrics,
.ai-score-grid {
    display: grid;
    gap: .55rem;
}

.transfer-summary-grid { grid-template-columns: repeat(4,minmax(0,1fr)); }
.advisor-metrics { grid-template-columns: repeat(2,minmax(0,1fr)); }
.ai-score-grid { grid-template-columns: repeat(3,minmax(0,1fr)); }

.advisor-card {
    min-height: 320px;
    padding: 1rem;
}

.advisor-card.best {
    border: 2px solid var(--fpl-green-500);
    background: linear-gradient(180deg,#fff,#f2fff8);
}

.advisor-player-row {
    display:flex;
    align-items:center;
    gap:.65rem;
}

.advisor-photo {
    width:68px;
    height:82px;
    object-fit:contain;
    border-radius:12px;
    background:#eef8f3;
}

.advisor-logo {
    width:35px;
    height:35px;
    object-fit:contain;
}

.advisor-rank {
    color:var(--ink-500);
    font-size:.68rem;
    font-weight:850;
    text-transform:uppercase;
}

.advisor-name {
    color:var(--ink-950);
    font-size:1.08rem;
    font-weight:900;
}

.advisor-sub {
    color:var(--ink-500);
    font-size:.76rem;
}

.advisor-metric,
.ai-mini-score {
    padding:.52rem;
    border-radius:10px;
    background:#f4f2f5;
}

.advisor-metric .k,
.ai-mini-score .label,
.transfer-summary-card .label {
    color:var(--ink-500);
    font-size:.62rem;
    font-weight:850;
    text-transform:uppercase;
}

.advisor-metric .v,
.ai-mini-score .value,
.transfer-summary-card .value {
    margin-top:.12rem;
    color:var(--ink-950);
    font-weight:900;
}

.pros-cons {
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:.65rem;
    margin-top:.8rem;
}

.pros,
.cons {
    padding:.68rem;
    border-radius:11px;
    font-size:.76rem;
    line-height:1.45;
}

.pros { color:#12613b; background:#e7f8ef; }
.cons { color:#842331; background:#fff0f2; }

/* ---------- Team center ---------- */
.pitch {
    position:relative;
    min-height:620px;
    padding:1.6rem .8rem;
    overflow:hidden;
    border:5px solid #f7fff9;
    border-radius:24px;
    background:
        repeating-linear-gradient(
            90deg,
            #0b854b 0,
            #0b854b 100px,
            #087744 100px,
            #087744 200px
        );
    box-shadow:
        inset 0 0 0 2px rgba(255,255,255,.60),
        0 18px 42px rgba(5,78,42,.20);
}

.pitch::before {
    content:"";
    position:absolute;
    left:50%;
    top:0;
    bottom:0;
    width:2px;
    background:rgba(255,255,255,.55);
}

.pitch::after {
    content:"";
    position:absolute;
    left:calc(50% - 70px);
    top:calc(50% - 70px);
    width:140px;
    height:140px;
    border:2px solid rgba(255,255,255,.55);
    border-radius:50%;
}

.pitch-row {
    position:relative;
    z-index:2;
    display:flex;
    justify-content:center;
    flex-wrap:wrap;
    gap:.85rem;
    margin:1rem 0;
}

.pitch-player {
    width:120px;
    padding:.68rem .5rem;
    border:1px solid rgba(255,255,255,.42);
    border-radius:15px;
    text-align:center;
    color:#fff;
    background:rgba(18,0,31,.84);
    box-shadow:0 10px 24px rgba(0,0,0,.18);
}

.pitch-player img {
    width:56px;
    height:66px;
    object-fit:contain;
}

.pitch-player .name {
    font-size:.76rem;
    font-weight:900;
}

.pitch-player .meta {
    color:#bfffd8;
    font-size:.64rem;
}

.squad-score-card .value,
.chip-card .value {
    color:#0b6f40;
}

.squad-score-card .bar {
    height:7px;
    margin-top:.6rem;
    overflow:hidden;
    border-radius:999px;
    background:#e4ece7;
}

.squad-score-card .fill {
    height:100%;
    border-radius:999px;
    background:linear-gradient(90deg,#00b864,#00ff87);
}

.bench-card {
    position:relative;
    overflow:hidden;
    padding-left:1.1rem;
}

.bench-card::before {
    content:"";
    position:absolute;
    inset:0 auto 0 0;
    width:6px;
    background:linear-gradient(180deg,var(--fpl-purple-800),var(--fpl-green-300));
}

.bench-order {
    display:inline-flex;
    margin-bottom:.45rem;
    padding:.2rem .5rem;
    border-radius:999px;
    color:#fff;
    background:linear-gradient(135deg,var(--fpl-purple-800),var(--fpl-purple-700));
    font-size:.65rem;
    font-weight:900;
    text-transform:uppercase;
}

.bench-name {
    color:var(--ink-950);
    font-weight:900;
}

.bench-meta {
    display:flex;
    flex-wrap:wrap;
    gap:.3rem;
    margin-top:.42rem;
}

.bench-chip {
    padding:.2rem .45rem;
    border-radius:999px;
    color:#425047;
    background:#eef7f1;
    font-size:.65rem;
    font-weight:800;
}

.bench-chip.score {
    color:#0b5d36;
    background:#d9f8e7;
}

.squad-selection-summary {
    display:grid;
    grid-template-columns:repeat(5,minmax(0,1fr));
    gap:.55rem;
    margin:.75rem 0 1rem;
}

.selection-count-card {
    padding:.65rem;
    border:1px solid var(--border);
    border-radius:12px;
    background:#fff;
}

.selection-count-card .k {
    color:var(--ink-500);
    font-size:.6rem;
    font-weight:850;
    text-transform:uppercase;
}

.selection-count-card .v {
    margin-top:.14rem;
    color:var(--ink-950);
    font-size:1rem;
    font-weight:900;
}

/* ---------- Tables ---------- */
div[data-testid="stDataFrame"],
div[data-testid="stTable"] {
    max-width:100%;
    overflow:hidden;
    border:1px solid var(--border);
    border-radius:16px;
    background:#fff;
    box-shadow:var(--shadow-sm);
}

div[data-testid="stDataFrame"] [role="columnheader"] {
    color:var(--ink-950);
    font-weight:850;
    background:#f0edf3;
}

div[data-testid="stDataFrame"] [role="row"]:hover {
    background:rgba(0,255,135,.055);
}

/* ---------- Loading ---------- */
div[data-testid="stSpinner"] {
    padding:.75rem;
    border:1px solid var(--border);
    border-radius:13px;
    background:rgba(255,255,255,.86);
    box-shadow:var(--shadow-sm);
}

/* ---------- Responsive ---------- */
@media (max-width: 1100px) {
    .profile-stat-grid { grid-template-columns:repeat(3,minmax(0,1fr)); }
    .detail-insight-grid,
    .fixture-card-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
    .method-grid,
    .help-analysis-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
    .squad-score-grid,
    .chip-grid,
    .bench-strip { grid-template-columns:repeat(2,minmax(0,1fr)); }
    .transfer-summary-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
}

@media (max-width: 768px) {
    html,
    body,
    [data-testid="stAppViewContainer"],
    .stApp {
        max-width:100%;
        overflow-x:hidden;
    }

    .block-container {
        max-width:100%;
        padding:.55rem .55rem 2.5rem !important;
    }

    .hero {
        min-height:160px;
        padding:1.15rem 1rem;
        border-radius:18px;
    }

    .hero::before { inset:9px; }
    .hero::after { display:none; }
    .hero h1 { font-size:1.95rem; }
    .hero p { font-size:.84rem; }

    div[data-testid="stHorizontalBlock"] {
        flex-direction:column !important;
        gap:.6rem !important;
    }

    div[data-testid="column"] {
        width:100% !important;
        min-width:100% !important;
        flex:1 1 100% !important;
    }

    .player-card {
        min-height:auto;
    }

    .player-profile-hero {
        grid-template-columns:1fr;
        text-align:center;
    }

    .detail-player-photo {
        width:120px;
        height:145px;
        margin:0 auto;
    }

    .profile-identity {
        justify-content:center;
    }

    .profile-stat-grid {
        grid-template-columns:repeat(2,minmax(0,1fr));
    }

    .detail-insight-grid,
    .fixture-card-grid,
    .method-grid,
    .help-analysis-grid,
    .squad-score-grid,
    .chip-grid,
    .bench-strip,
    .pros-cons {
        grid-template-columns:1fr;
    }

    .indicator-key {
        grid-template-columns:1fr;
    }

    .score-legend,
    .score-band,
    .fixture-difficulty-legend {
        grid-template-columns:repeat(2,minmax(0,1fr));
    }

    .breakdown-row {
        grid-template-columns:100px minmax(0,1fr) 45px;
        gap:.42rem;
    }

    .pitch {
        min-height:500px;
        padding:1rem .3rem;
    }

    .pitch-row { gap:.35rem; }

    .pitch-player {
        width:82px;
        padding:.4rem .25rem;
    }

    .pitch-player img {
        width:40px;
        height:48px;
    }

    .pitch-player .name { font-size:.62rem; }
    .pitch-player .meta { font-size:.53rem; }

    .squad-selection-summary {
        grid-template-columns:repeat(2,minmax(0,1fr));
    }

    section[data-testid="stSidebar"] {
        width:min(88vw,340px) !important;
    }

    .stButton > button,
    .stDownloadButton > button {
        width:100%;
    }

    div[data-testid="stDataFrame"],
    div[data-testid="stTable"] {
        overflow-x:auto;
        -webkit-overflow-scrolling:touch;
    }
}

@media (max-width: 420px) {
    .block-container {
        padding-left:.4rem !important;
        padding-right:.4rem !important;
    }

    .hero h1 { font-size:1.7rem; }

    .player-primary-stats,
    .profile-stat-grid,
    .score-legend,
    .score-band,
    .fixture-difficulty-legend {
        grid-template-columns:1fr;
    }

    .breakdown-row {
        grid-template-columns:82px minmax(0,1fr) 38px;
    }
}

/* ---------- AI player analysis ---------- */
.ai-player-dashboard {
    display: grid;
    grid-template-columns: 230px minmax(0, 1fr);
    gap: 1.25rem;
    align-items: stretch;
    margin: .85rem 0 1rem;
    padding: 1.15rem;
    border: 1px solid var(--border);
    border-radius: 24px;
    background:
        radial-gradient(circle at 95% 8%, rgba(0,255,135,.16), transparent 20rem),
        linear-gradient(145deg, #ffffff 0%, #f4fff8 100%);
    box-shadow: var(--shadow-md);
}

.ai-player-visual {
    position: relative;
    min-height: 310px;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    overflow: hidden;
    border-radius: 20px;
    background:
        radial-gradient(circle at 50% 85%, rgba(0,255,135,.28), transparent 42%),
        linear-gradient(160deg, #eee8f1 0%, #e7fff1 100%);
}

.ai-player-visual::after {
    content: "";
    position: absolute;
    width: 160px;
    height: 160px;
    left: calc(50% - 80px);
    bottom: -85px;
    border: 2px solid rgba(55,0,60,.10);
    border-radius: 50%;
}

.ai-player-photo {
    position: relative;
    z-index: 2;
    width: 100%;
    height: 300px;
    object-fit: contain;
    object-position: center bottom;
}

.ai-player-fallback {
    position: relative;
    z-index: 2;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 300px;
    font-size: 4rem;
}

.ai-player-content {
    min-width: 0;
}

.ai-player-topline {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: .8rem;
}

.ai-player-identity {
    display: flex;
    align-items: center;
    gap: .72rem;
}

.ai-player-club {
    width: 58px;
    height: 58px;
    object-fit: contain;
}

.ai-verdict-badge {
    display: inline-flex;
    align-items: center;
    gap: .35rem;
    padding: .34rem .68rem;
    border-radius: 999px;
    color: #fff;
    background: linear-gradient(135deg, var(--fpl-purple-800), var(--fpl-purple-700));
    font-size: .72rem;
    font-weight: 900;
    letter-spacing: .035em;
    text-transform: uppercase;
}

.ai-player-name {
    margin-top: .32rem;
    color: var(--ink-950);
    font-size: clamp(1.8rem, 3vw, 2.45rem);
    font-weight: 950;
    line-height: 1.05;
}

.ai-player-meta {
    margin-top: .3rem;
    color: var(--ink-500);
    font-size: .88rem;
}

.ai-key-score-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: .7rem;
    margin-top: 1rem;
}

.ai-key-score {
    position: relative;
    overflow: hidden;
    min-height: 125px;
    padding: .85rem;
    border: 1px solid var(--border);
    border-radius: 16px;
    background: rgba(255,255,255,.92);
}

.ai-key-score::before {
    content: "";
    position: absolute;
    inset: 0 0 auto 0;
    height: 5px;
    background: var(--fpl-green-500);
}

.ai-key-score.confidence::before {
    background: var(--fpl-cyan-400);
}

.ai-key-score.risk::before {
    background: var(--fpl-red-500);
}

.ai-key-score .label {
    color: var(--ink-500);
    font-size: .64rem;
    font-weight: 850;
    letter-spacing: .06em;
    text-transform: uppercase;
}

.ai-key-score .value {
    margin-top: .28rem;
    color: var(--ink-950);
    font-size: 1.65rem;
    font-weight: 950;
    line-height: 1;
}

.ai-key-score .hint {
    margin-top: .28rem;
    color: var(--ink-500);
    font-size: .7rem;
}

.ai-meter {
    height: 8px;
    overflow: hidden;
    margin-top: .7rem;
    border-radius: 999px;
    background: #e8e4ea;
}

.ai-meter-fill {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--fpl-green-500), var(--fpl-green-300));
}

.ai-key-score.confidence .ai-meter-fill {
    background: linear-gradient(90deg, #078da0, var(--fpl-cyan-400));
}

.ai-key-score.risk .ai-meter-fill {
    background: linear-gradient(90deg, #ff9aa6, var(--fpl-red-500));
}

.ai-support-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: .55rem;
    margin-top: .7rem;
}

.ai-support-stat {
    padding: .65rem;
    border: 1px solid rgba(55,0,60,.07);
    border-radius: 12px;
    background: #f4f2f5;
}

.ai-support-stat .k {
    color: var(--ink-500);
    font-size: .58rem;
    font-weight: 850;
    text-transform: uppercase;
}

.ai-support-stat .v {
    margin-top: .14rem;
    color: var(--ink-950);
    font-size: .95rem;
    font-weight: 900;
}

.ai-fixture-row {
    margin-top: .75rem;
    padding: .7rem .75rem;
    border: 1px solid rgba(55,0,60,.07);
    border-radius: 13px;
    background: rgba(255,255,255,.72);
}

.ai-fixture-label {
    margin-bottom: .35rem;
    color: var(--ink-500);
    font-size: .62rem;
    font-weight: 850;
    text-transform: uppercase;
}

/* Make the sidebar reset action blend into the dark navigation instead of
   creating a large white slab. */
section[data-testid="stSidebar"] .stButton > button {
    color: #fff !important;
    background: rgba(255,255,255,.08) !important;
    border: 1px solid rgba(255,255,255,.16) !important;
    box-shadow: none !important;
}

section[data-testid="stSidebar"] .stButton > button:hover {
    color: var(--fpl-purple-800) !important;
    background: var(--fpl-green-300) !important;
}

@media (max-width: 1050px) {
    .ai-player-dashboard {
        grid-template-columns: 190px minmax(0, 1fr);
    }

    .ai-support-grid {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }
}

@media (max-width: 768px) {
    .ai-player-dashboard {
        grid-template-columns: 1fr;
        padding: .8rem;
    }

    .ai-player-visual {
        min-height: 230px;
    }

    .ai-player-photo,
    .ai-player-fallback {
        height: 230px;
    }

    .ai-player-topline {
        flex-direction: column;
    }

    .ai-key-score-grid {
        grid-template-columns: 1fr;
    }

    .ai-support-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}

@media (max-width: 420px) {
    .ai-support-grid {
        grid-template-columns: 1fr;
    }
}


/* ---------- Pinned player tables ---------- */
.pinned-table-wrap {
    position: relative;
    max-width: 100%;
    max-height: 620px;
    overflow: auto;
    margin: .55rem 0 1rem;
    border: 1px solid var(--border);
    border-radius: 16px;
    background: #ffffff;
    box-shadow: var(--shadow-sm);
    scrollbar-color: rgba(55,0,60,.35) rgba(55,0,60,.07);
    -webkit-overflow-scrolling: touch;
}

.pinned-player-table {
    width: max-content;
    min-width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    color: var(--ink-950);
    background: #ffffff;
    font-size: .78rem;
}

.pinned-player-table th,
.pinned-player-table td {
    padding: .62rem .68rem;
    border-right: 1px solid #e7e3e9;
    border-bottom: 1px solid #e7e3e9;
    vertical-align: middle;
    white-space: nowrap;
    background: #ffffff;
}

.pinned-player-table th {
    position: sticky;
    top: 0;
    z-index: 50;
    color: #493a4f;
    background: #f0edf3;
    font-size: .68rem;
    font-weight: 900;
    letter-spacing: .03em;
    text-align: left;
    text-transform: uppercase;
}

.pinned-player-table tbody tr:hover td {
    background: #f4fff8;
}

.pinned-player-table .pinned-column {
    position: sticky;
    z-index: 30;
    box-shadow: 1px 0 0 #ded8e2;
}

.pinned-player-table th.pinned-column {
    z-index: 70;
    background: #e9e4ed;
}

.pinned-player-table tbody tr:hover .pinned-column {
    background: #ebfbf2;
}

.pinned-player-table .cell-image {
    width: 34px;
    height: 34px;
    object-fit: contain;
    display: block;
    margin: 0 auto;
}

.pinned-player-table .player-cell {
    color: var(--ink-950);
    font-weight: 900;
}

.pinned-player-table .position-chip {
    display: inline-flex;
    min-width: 42px;
    justify-content: center;
    padding: .22rem .42rem;
    border-radius: 999px;
    color: #ffffff;
    background: linear-gradient(135deg, var(--fpl-purple-800), var(--fpl-purple-700));
    font-size: .66rem;
    font-weight: 900;
}

.pinned-player-table .price-cell {
    color: #075c34;
    font-weight: 900;
}

.pinned-player-table .positive-value {
    color: #087744;
    font-weight: 850;
}

.pinned-player-table .negative-value {
    color: #b42335;
    font-weight: 850;
}

.pinned-player-table .table-progress {
    display: grid;
    grid-template-columns: 94px 42px;
    gap: .42rem;
    align-items: center;
}

.pinned-player-table .table-progress-track {
    height: 8px;
    overflow: hidden;
    border-radius: 999px;
    background: #ece8ef;
}

.pinned-player-table .table-progress-fill {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--fpl-green-500), var(--fpl-green-300));
}

.pinned-player-table .table-progress-value {
    color: #493a4f;
    font-size: .7rem;
    font-weight: 850;
    text-align: right;
}

@media (max-width: 768px) {
    .pinned-player-table {
        font-size: .72rem;
    }

    .pinned-player-table th,
    .pinned-player-table td {
        padding: .54rem .58rem;
    }

    .pinned-player-table .table-progress {
        grid-template-columns: 76px 38px;
    }
}

</style>
"""


def apply_global_styles() -> None:
    """Inject the application-wide design system."""
    st.markdown(APP_CSS, unsafe_allow_html=True)
