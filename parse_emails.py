#!/usr/bin/env python3
"""Parse RealScout listing emails (*.eml) into listings.json.

Reads every *.eml in this folder, extracts each listing (price, beds/baths/sqft,
address, photo, View Details link, days-on-site), dedupes by address against the
existing listings.json (newest email wins), geocodes new addresses (US Census
geocoder, Nominatim fallback), tags each to its school district by
point-in-polygon, and writes listings.json. Idempotent — safe to re-run.

Usage: python3 parse_emails.py
"""
import email, re, html, json, glob, sys, time, urllib.parse, urllib.request
from email import policy

HERE = __file__.rsplit("/", 1)[0] if "/" in __file__ else "."

# Price/beds/baths/sqft + days-on-site come from the flattened visible text.
METRICS_RE = re.compile(
    r"\$([\d,]+)\s+(\d+)\s+Beds?\s*\|\s*([\d.]+)\s+Baths?\s*\|\s*([\d,]+)\s+Sqft"
    r"\s+.+?\s+(New on site|\d+\s+days?\s+on\s+site)"
)
# Street + city/state/zip come from the HTML, where they're split by <br/>.
ADDR_RE = re.compile(r"([^<>]+?)<br\s*/?>\s*([A-Za-z .]+),\s*PA,\s*(\d{5})")


def email_date(msg):
    return msg.get("Date", "")


def parse_email(path):
    msg = email.message_from_file(open(path, encoding="utf-8", errors="replace"), policy=policy.default)
    body = next((p.get_content() for p in msg.walk() if p.get_content_type() == "text/html"), None)
    if not body:
        return []
    text = re.sub(r"\s+", " ", html.unescape(re.sub("<[^>]+>", " ", body)))
    photos = re.findall(r'src="([^"]*property_photos[^"]*)"', body)
    links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*View Details\s*</a>', body)
    metrics = METRICS_RE.findall(text)
    addrs = ADDR_RE.findall(body)
    if len(metrics) != len(addrs):
        print(f"  !! {path}: {len(metrics)} metrics vs {len(addrs)} addresses", file=sys.stderr)
    out = []
    for i, (mt, ad) in enumerate(zip(metrics, addrs)):
        price, beds, baths, sqft, days = mt
        addr, city, zc = ad
        addr = html.unescape(addr).strip().rstrip("#").strip()
        dnum = None if days.startswith("New") else int(re.search(r"\d+", days).group())
        out.append({
            "address": addr, "city": city.strip(), "zip": zc,
            "price": "$" + price, "priceNum": int(price.replace(",", "")),
            "beds": int(beds), "baths": float(baths), "sqft": int(sqft.replace(",", "")),
            "days": dnum,
            "photo": photos[i] if i < len(photos) else None,
            "url": links[i] if i < len(links) else None,
            "_emailDate": email_date(msg),
        })
    return out


def budget(p):
    return "under" if p < 3000 else "ceiling" if p <= 3500 else "over"


def _nominatim(q):
    u = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "json", "limit": 1})
    req = urllib.request.Request(u, headers={"User-Agent": "moving-to-pa/1.0"})
    r = json.load(urllib.request.urlopen(req, timeout=20))
    return (float(r[0]["lat"]), float(r[0]["lon"])) if r else None


def geocode(addr, city, zc):
    """Return (lat, lng, approx). approx=True means we only resolved to the
    ZIP/town centroid (street address undisclosed/unmatched)."""
    has_street = bool(re.match(r"\s*\d", addr))
    if has_street:
        one = f"{addr}, {city}, PA, {zc}"
        # 1) US Census (exact)
        try:
            u = ("https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?"
                 + urllib.parse.urlencode({"address": one, "benchmark": "Public_AR_Current", "format": "json"}))
            m = json.load(urllib.request.urlopen(u, timeout=20))["result"]["addressMatches"]
            if m:
                c = m[0]["coordinates"]
                return c["y"], c["x"], False
        except Exception as e:
            print(f"  census fail: {e}", file=sys.stderr)
        # 2) Nominatim full address (exact)
        try:
            p = _nominatim(f"{addr}, {city}, PA {zc}")
            if p:
                return p[0], p[1], False
        except Exception as e:
            print(f"  nominatim fail: {e}", file=sys.stderr)
    # 3) ZIP/town centroid (approximate) — for undisclosed or unmatched addresses
    for q in (f"{zc}, PA", f"{city}, PA"):
        try:
            p = _nominatim(q)
            if p:
                return p[0], p[1], True
        except Exception as e:
            print(f"  centroid fail ({q}): {e}", file=sys.stderr)
    return None, None, False


def point_in_ring(x, y, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def point_in_feature(x, y, geom):
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    for poly in polys:
        if point_in_ring(x, y, poly[0]) and not any(point_in_ring(x, y, h) for h in poly[1:]):
            return True
    return False


def district_for(lat, lng, feats):
    for f in feats:
        if point_in_feature(lng, lat, f["geometry"]):
            return f["properties"]["GEOID"], f["properties"]["NAME"].replace(" School District", "").strip()
    return None, None


def keyfor(x):
    a = re.sub(r"[^a-z0-9]", "", x["address"].lower())
    # undisclosed/non-numeric addresses aren't unique — qualify with city + price
    if not re.match(r"\s*\d", x["address"]):
        a += re.sub(r"[^a-z0-9]", "", x.get("city", "").lower()) + str(x.get("priceNum", ""))
    return a


def main():
    existing = json.load(open(f"{HERE}/listings.json"))
    by_addr = {keyfor(x): x for x in existing}

    # gather parsed listings, newest email last so it overwrites
    parsed = []
    for f in sorted(glob.glob(f"{HERE}/*.eml")):
        parsed.extend(parse_email(f))
    parsed.sort(key=lambda x: x["_emailDate"])

    new_count = updated = 0
    feats = json.load(open(f"{HERE}/districts.geojson"))["features"]
    for L in parsed:
        k = keyfor(L)
        L["budget"] = budget(L["priceNum"])
        L["bathOK"] = L["baths"] >= 2
        prev = by_addr.get(k)
        if prev and prev.get("lat") is not None:
            # keep geocode/district from existing; refresh listing facts
            for fld in ("lat", "lng", "geoid", "district"):
                L[fld] = prev.get(fld)
            if prev.get("approx"):
                L["approx"] = True
            updated += 1
        else:
            # new listing, or a previously-ungeocoded one worth retrying
            lat, lng, approx = geocode(L["address"], L["city"], L["zip"])
            L["lat"], L["lng"] = lat, lng
            if approx:
                L["approx"] = True
            if lat is not None:
                L["geoid"], L["district"] = district_for(lat, lng, feats)
                if approx:
                    print(f"  ~ approx (ZIP centroid): {L['address']}, {L['city']} {L['zip']}", file=sys.stderr)
            else:
                L["geoid"] = L["district"] = None
                print(f"  !! could not geocode: {L['address']}, {L['city']}", file=sys.stderr)
            new_count += (0 if prev else 1)
            time.sleep(1)  # be polite to geocoders
        L.pop("_emailDate", None)
        by_addr[k] = L

    final = sorted(by_addr.values(), key=lambda x: x["priceNum"])
    json.dump(final, open(f"{HERE}/listings.json", "w"), indent=2)
    print(f"Total: {len(final)} listings  (+{new_count} new, {updated} refreshed)")


if __name__ == "__main__":
    main()
