#!/usr/bin/env python3
"""Local dev server: serves the static site AND persists listing notes/ratings to
notes.json on disk, so they survive browser cache clears (and aren't stuck in one
browser). The page auto-saves via PUT /api/notes and loads via GET /api/notes; if
this endpoint is absent (e.g. a plain static host) the page falls back to
localStorage. Run instead of `python3 -m http.server`:

    python3 serve.py            # http://localhost:5050
"""
import json, os, subprocess, threading, time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
NOTES = os.path.join(HERE, "notes.json")
PORT = 5050

# RealScout auto-sync: scrape your matches into listings.json on startup and every
# few hours while the server runs. No-ops cleanly if creds aren't set up.
SYNC_SCRIPT = os.path.join(HERE, "sync_realscout.sh")
CREDS = os.path.join(HERE, ".realscout_creds.json")
SYNC_INTERVAL = 6 * 3600          # every 6 hours
_sync_lock = threading.Lock()


def run_sync():
    """Run the scrape+ingest once. Guarded so two never overlap."""
    if not os.path.exists(CREDS):
        return
    if not _sync_lock.acquire(blocking=False):
        return  # a sync is already running
    try:
        subprocess.run(["bash", SYNC_SCRIPT], cwd=HERE, timeout=300)
    except Exception as e:
        print(f"realscout sync error: {e}")
    finally:
        _sync_lock.release()


def sync_scheduler():
    time.sleep(8)                 # let the server come up first
    while True:
        run_sync()
        time.sleep(SYNC_INTERVAL)


class Handler(SimpleHTTPRequestHandler):
    def _send(self, code, body=b"", ctype="application/json"):
        self.send_response(code)
        if body:
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/") == "/api/notes":
            data = open(NOTES, "rb").read() if os.path.exists(NOTES) else b"{}"
            return self._send(200, data)
        return super().do_GET()

    def do_POST(self):
        if self.path.rstrip("/") == "/api/refresh":
            threading.Thread(target=run_sync, daemon=True).start()
            return self._send(202, b'{"status":"syncing"}')
        return self._send(405)

    def do_PUT(self):
        if self.path.rstrip("/") == "/api/notes":
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            try:
                json.loads(body)            # validate before writing
            except Exception:
                return self._send(400, b'{"error":"invalid json"}')
            with open(NOTES, "wb") as f:
                f.write(body)
            return self._send(204)
        return self._send(405)

    def log_message(self, *a):              # quiet
        pass


if __name__ == "__main__":
    os.chdir(HERE)
    print(f"Serving {HERE} on http://localhost:{PORT}  (notes -> {NOTES})")
    if os.path.exists(CREDS):
        threading.Thread(target=sync_scheduler, daemon=True).start()
        print(f"RealScout auto-sync on (every {SYNC_INTERVAL // 3600}h; logs -> realscout_sync.log)")
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()
