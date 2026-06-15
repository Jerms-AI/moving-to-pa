# Moving to PA

A keepable, self-contained map for relocating the family to the Pennsylvania suburbs near
Lansdale. The first view color-codes the local **school districts by their national quality
(1–10)** as real, outlined boundary shapes — so we can see exactly which side of a district
line any prospective rental falls on.

## Why this exists

We're moving the family (~3–4 month window) and renting, most likely for ~2 years. The search
has hard constraints, and school quality is decided by **district boundaries**, not by being
"near" a good district. A centered pin can't show that; a colored boundary map can.

## The constraints driving the search

- **Three kids**, entering **Kindergarten, 3rd grade, and 6th grade**. Top-tier schools for all
  three. Same school is a nice-to-have, not required.
- **Wife works in Lansdale.** A commute is fine; shorter is better.
- **Rent under $3k** if possible, **$3.5k ceiling**. Cheaper is better.
- **3 bedroom / 2 full bathroom** — hard requirement.
- **Basketball for the 6th grader** — training, teams, AAU. Flagged as important.
- Renting, likely **~2 years**. A realtor is helping find homes.
- Neighborhoods with kids are a big plus. Open to Philadelphia proper too.

## What's in here now

- **`index.html`** *(to be built)* — self-contained interactive map:
  Leaflet + OpenStreetMap tiles, U.S. Census school-district boundary polygons color-coded
  green→red by national score, with Lansdale and basketball locations as point markers on top.
- **`docs/superpowers/specs/`** — design spec for the map.

## Tech

- **Leaflet + OpenStreetMap** for the map (free, no API key — same engine as the Work dashboard's
  map; that one only used Google's API behind the scenes for business search, not for display).
- **U.S. Census Bureau / NCES** school-district boundaries (the authoritative lines used for
  actual school assignment), rendered as a GeoJSON choropleth.
- No build step, no server — `index.html` is opened directly.

## Later layers (not in the first view)

- Within-district **elementary attendance zones** (decides which school, and elementary-vs-middle
  for the 6th grader).
- **Rent reality** filters (3BR / 2 full bath / under $3.5k) per area.
- Real **realtor addresses** dropped as points to see which district they land in.
- A one-page **realtor brief**.
