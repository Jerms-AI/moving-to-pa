# Moving to PA

A self-contained interactive map for relocating the family to the Pennsylvania suburbs near
Lansdale — school districts, individual schools, attendance zones, apartment listings, and
demographics, all in one page.

**Live:** https://cybercanvascollective.art/movepa/

## Why this exists

We're renting (likely ~2 years) and school quality is decided by **district boundaries**, not by
being "near" a good district. The map shows the real boundary lines, scores them, and lets us see
exactly which district (and school catchment) any prospective rental falls in.

## The constraints driving the search

- **Three kids** entering **K, 3rd, and 6th** → elementary + middle matter most over a 2-year stay
  (high school never comes into play).
- **Work in Lansdale + Merck (West Point).** Commute matters; shorter is better.
- **Rent under $3k** ideal, **$3.5k ceiling**. Cheaper is better.
- **3 bedroom / 2 full bathroom** — hard requirement.
- **Basketball for the 6th grader** — training/teams/AAU. Flagged important.
- Open to Philadelphia too.

## What the map does

- **37 school districts** (within ~20 mi of Lansdale) as Census boundary polygons, color-coded by a
  Pennsylvania-relative 1–10 score (10 = best in PA).
- **Grade-band buttons** (Elementary / Middle / High) — multi-select; recolor districts by the
  average of the selected bands *and* show/hide the matching school dots.
- **Individual school dots**, colored by each school's own 1–10 score, with score-band toggles
  (6–10). District fill greys out unless it contains a currently-visible school.
- **School attendance zones** — hover a school to isolate its catchment (the other districts fade).
- **Apartment listings** from the realtor's emails — geocoded pins colored by budget, with photo,
  beds/baths/sqft, days-on-site, the district + its scores, and a real "View Details" link. A
  left-rail card browser with hover-to-locate.
- **Right-rail district cards** — every district's aggregate rating, E/M/H breakdown, and a
  population-weighted race/ethnicity line; the **top-5 best-fit** districts are starred
  (weighted 70% schools · 20% Black % · 10% closeness).
- **Demographics overlay** — shade tracts by % White / Black / Asian / Hispanic.
- **★ Ideal** toggle — isolate the top-5 districts (and their schools) while keeping all apartments.
- **Basketball** pins (CAL Sports, North Penn YMCA); **work** pins (Lansdale, Merck).
- Two-way linking: hover a district card → district highlights; click a district → its card highlights.

## Data (all keyless — the Census API now needs a key, so we avoid it)

- **Boundaries** — US Census TIGER (districts + tracts) and **NCES SABS 2015-16** (attendance zones).
- **School locations** — NCES EDGE geocode file.
- **School/district scores** — PA state proficiency (2018 EDFacts) via the Urban Institute
  Education Data API, ranked across PA schools → 1–10.
- **Demographics** — CDC SVI 2022 (Census ACS 2018-22), aggregated tracts → districts.
- **Listing locations** — US Census geocoder (+ Nominatim fallback), tagged to districts by
  point-in-polygon.

Honest caveats: proficiency is 2018, attendance zones are 2015-16, district demographics are
tract-aggregated (approximate at edges).

## Listings workflow

The realtor (Tabitha Heit, BHHS Fox & Roach) sends RealScout match emails. Save the `.eml`/`.htm`
into this folder; the listings are parsed from the email HTML by code (price, beds/baths, sqft,
address, photo, View Details link, days-on-site), deduped by address across emails, geocoded, and
written to `listings.json`. **Do not hand-transcribe** — parse the file. Email files are gitignored.

## Files

- `index.html` — the whole app (Leaflet via CDN, no build step).
- `districts.geojson`, `districts_scores.json` — boundaries + per-band scores, distance, demographics.
- `schools.json`, `school_boundaries.geojson` — school dots + attendance zones.
- `tracts.geojson` — demographic choropleth.
- `listings.json` — apartments.

## Dev

- Preview: `python3 -m http.server 5050` in this folder, open `http://localhost:5050`.
  The page has a localhost-only auto-reloader (inert over HTTPS).
- Verify changes headlessly with the Playwright install in `PersonalProjects/Work/dashboard`.
- **Deploy is manual** (FTP to `cybercanvascollective.art/movepa/`); pushing to git does not deploy.
