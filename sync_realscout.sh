#!/usr/bin/env bash
# One-shot RealScout sync: scrape your matches -> merge into listings.json.
# Safe to run on a schedule (serve.py does) or by hand. Logs to realscout_sync.log.
cd "$(dirname "$0")" || exit 1
{
  echo "=== sync $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  node scrape_realscout.mjs && python3 ingest_realscout.py
  echo "exit: $?"
} >> realscout_sync.log 2>&1
