# Design: School-District Quality Map (first view)

**Date:** 2026-06-15
**Status:** Approved (design); ready for implementation plan
**Scope:** The map only. Rent, basketball detail, and the realtor brief are later layers.

## Goal

A single, keepable, self-contained page that shows the school districts around Lansdale, PA as
**real outlined boundaries**, color-coded by their **1–10 national quality score**, so we can see
which colored area any prospective address falls inside. Borders matter: a top-tier district and a
weak one can sit across the same street, and school assignment follows the district line.

## Approach

A self-contained **`index.html`** — Leaflet + OpenStreetMap tiles loaded from CDN. No build step,
no server, no database. Opened directly in a browser. This mirrors the proven map pattern from the
`Work` dashboard but drops all the lead-card / list / SQLite machinery.

### Why boundaries, not pins

Pins are centered points; they say nothing about where a district's edge is. We render each
district as a **filled, outlined polygon (choropleth)** so the borders — the thing that actually
decides which school a child attends — are visible.

## Data

### District scores (1–10 national; 10 = best in the country)

Synthesized from U.S. News (2025–26 national HS rank, ~17,600 ranked schools, used as the primary
national signal), cross-checked against Niche grades, GreatSchools 1–10, and Public School Review.

| # | District / Area | Score | Drive to Lansdale | Rationale |
|---|---|---|---|---|
| 1 | Wissahickon (Ambler / Lower Gwynedd) | 9.0 | ~18 min | A+, U.S. News #21 PA / #701 nat; best blend of score + commute. Trend: slipping slightly. |
| 2 | Colonial (Plymouth Meeting) | 8.5 | ~25 min | Top 5% PA, U.S. News #24 PA / #872 nat. |
| 3 | Central Bucks (Doylestown) | 8.5 | ~25 min | CB East elite (#14 PA / #600 nat); West/South pull the average down. |
| 4 | Upper Dublin (Maple Glen) | 8.0 | ~22 min | A+, #39 PA / #1,391 nat. Trend: down from #27 PA in 2024. |
| 5 | Spring-Ford (Royersford) | 8.0 | ~28 min | Strong, often more house for the money; longest regular drive. |
| 6 | North Penn (Lansdale) | 7.5 | 0 min | Default — shortest commute, most rentals, in-district hoops. #79 PA / #2,059 nat. |
| 7 | Methacton (Eagleville) | 7.5 | ~22 min | Strong, quieter backup. ~#76 PA. |
| 8 | Souderton Area | 7.0 | ~14 min | Good, more affordable, close-in. ~#69 PA. |
| 9 | Hatboro-Horsham (Horsham) | 5.5 | ~22 min | Weakest of the suburban set. #200 PA / #4,982 nat. |
| 10 | School District of Philadelphia (avg) | 3.0 | ~45 min | Bimodal; neighborhood average well below median. |
| — | Chestnut Hill / Mt. Airy catchment | 2 (catchment) / 9.5 (magnet) | ~35 min | Neighborhood schools weak; magnets elite but lottery/test-in — hard for a mid-year 6th-grade landing. |

**Honest read:** realistic targets cluster **7.5–9.0**, which is unusually strong for one
commute radius. North Penn lands at 7.5 (not the 8 an earlier rough pass guessed) once anchored on
U.S. News national rank.

Uncertain numbers to flag in the data file: exact national ranks for Souderton and Methacton; CB
East GreatSchools number; Spring-Ford district Niche grade (A vs A+). Trend-down notes for
Wissahickon and Upper Dublin should be surfaced in their popups.

### District boundaries

- Source: **U.S. Census Bureau TIGER/Line — Unified School Districts (Pennsylvania)**, the
  authoritative boundaries used for school assignment, via NCES/EDGE.
- Filtered to the districts above, converted to **GeoJSON**, and **simplified** (e.g. Douglas-
  Peucker / mapshaper) to keep the file small while preserving border shape.
- Philadelphia: the district polygon is the citywide boundary; the Chestnut Hill / Mt. Airy
  bimodal note lives in the popup, not as a separate polygon (catchments are a later layer).

### Point markers (on top of polygons)

- **Lansdale (work anchor)** — distinct navy star.
- **Basketball:** CAL Sports Academy (Lansdale) and North Penn YMCA (Lansdale) — a distinct
  marker shape/color, name + type only for now.

## Rendering

- **Choropleth fill** by score band:
  - Green: 8.0–10
  - Amber: 6.0–7.9
  - Red: below 6.0
- Each polygon labeled with its **score number** near its centroid.
- **Hover** highlights the polygon border; **click** opens a popup with district name, score,
  drive time to Lansdale, rationale, and any trend note.
- A small **legend** explains the color bands and the score scale (10 = best nationally).

## Editability

All scores, coordinates, marker data, and the district↔score mapping live in **one data block at
the top of `index.html`** (or one adjacent `data.js`), so updating a score or dropping in a real
realtor address later is a one-line edit.

## Out of scope (future layers)

- Within-district elementary attendance zones.
- Rent filters (3BR / 2 full bath / under $3.5k) per area.
- Realtor addresses as droppable points with "which district am I in" readout.
- One-page realtor brief.

## Success criteria

- Opening `index.html` shows an interactive street map centered on the Lansdale area.
- Each target district appears as a correctly-placed, outlined, color-coded shape with its score
  number visible.
- Clicking a district shows its details; Lansdale and the two basketball spots appear as markers.
- No API key, no server, no build step required to view it.
