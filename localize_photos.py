#!/usr/bin/env python3
"""Download remote listing photos and self-host them under photos/.

Realtor (RealScout) listings carry CloudFront photo URLs that are served with no
Content-Type and live on a marketing CDN — they get blocked by some browsers/ad
blockers and will eventually expire. This downloads each remote photo once to
photos/<hash>.jpg and rewrites listings.json to a relative path, so the images
render reliably and ship with the site. Idempotent — skips already-local photos.

Usage: python3 localize_photos.py
"""
import json, os, hashlib, urllib.request
from parse_emails import HERE

PHOTODIR = f"{HERE}/photos"


def main():
    os.makedirs(PHOTODIR, exist_ok=True)
    listings = json.load(open(f"{HERE}/listings.json"))
    got = skipped = failed = 0
    for L in listings:
        p = L.get("photo")
        if not p or not p.startswith("http"):
            skipped += 1
            continue
        name = hashlib.md5(p.encode()).hexdigest()[:12] + ".jpg"
        dest = f"{PHOTODIR}/{name}"
        rel = f"photos/{name}"
        if not os.path.exists(dest):
            try:
                req = urllib.request.Request(p, headers={"User-Agent": "Mozilla/5.0"})
                data = urllib.request.urlopen(req, timeout=30).read()
                open(dest, "wb").write(data)
                got += 1
            except Exception as e:
                print(f"  !! failed {L.get('address')}: {e}")
                failed += 1
                continue
        L["photo"] = rel
    json.dump(listings, open(f"{HERE}/listings.json", "w"), indent=2)
    print(f"Localized {got} photo(s), {skipped} had none/already local, {failed} failed.")


if __name__ == "__main__":
    main()
