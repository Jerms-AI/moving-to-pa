#!/usr/bin/env python3
"""Merge scraped RealScout matches (realscout_raw.json, written by
scrape_realscout.mjs) into listings.json — reusing parse_emails.py's geocoding,
school-district tagging, budget bucketing and address dedup. Idempotent: re-runs
keep existing geocodes and only add/refresh changed listings.

Usage: python3 ingest_realscout.py
"""
import json, re, sys, time
from parse_emails import HERE, geocode, district_for, budget, keyfor

RAW = f"{HERE}/realscout_raw.json"


def main():
    try:
        raw = json.load(open(RAW))
    except FileNotFoundError:
        print("no realscout_raw.json yet — run scrape_realscout.mjs first", file=sys.stderr)
        return
    if not isinstance(raw, list):
        print("realscout_raw.json is not a list", file=sys.stderr)
        return

    existing = json.load(open(f"{HERE}/listings.json"))
    by_addr = {keyfor(x): x for x in existing}
    feats = json.load(open(f"{HERE}/districts.geojson"))["features"]

    new_count = updated = 0
    for src in raw:
        L = dict(src)
        if not L.get("address"):
            continue
        if not L.get("priceNum"):
            L["priceNum"] = int(re.sub(r"[^\d]", "", str(L.get("price", "0"))) or 0)
        if not L.get("price") and L.get("priceNum"):
            L["price"] = "$" + format(L["priceNum"], ",")
        L["budget"] = budget(L.get("priceNum", 0))
        try:
            L["bathOK"] = float(L.get("baths") or 0) >= 2
        except (TypeError, ValueError):
            L["bathOK"] = False
        L["source"] = "realscout"

        k = keyfor(L)
        prev = by_addr.get(k)
        if prev:
            updated += 1
        else:
            new_count += 1
        # RealScout gives us exact lat/lng — use it directly (no geocoder needed);
        # only fall back to geocoding if a listing somehow lacks coordinates.
        if L.get("lat") is not None and L.get("lng") is not None:
            L["geoid"], L["district"] = district_for(L["lat"], L["lng"], feats)
        elif prev and prev.get("lat") is not None:
            for fld in ("lat", "lng", "geoid", "district"):
                L[fld] = prev.get(fld)
            if prev.get("approx"):
                L["approx"] = True
        else:
            lat, lng, approx = geocode(L["address"], L.get("city", ""), L.get("zip", ""))
            L["lat"], L["lng"] = lat, lng
            if approx:
                L["approx"] = True
            if lat is not None:
                L["geoid"], L["district"] = district_for(lat, lng, feats)
            else:
                L["geoid"] = L["district"] = None
                print(f"  !! could not geocode: {L.get('address')}, {L.get('city')}", file=sys.stderr)
            time.sleep(1)  # be polite to geocoders
        by_addr[k] = L

    final = sorted(by_addr.values(), key=lambda x: x.get("priceNum", 0))
    json.dump(final, open(f"{HERE}/listings.json", "w"), indent=2)
    print(f"RealScout ingest: {len(final)} listings total (+{new_count} new, {updated} refreshed)")


if __name__ == "__main__":
    main()
