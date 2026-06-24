/**
 * Scrape your RealScout "matches" into realscout_raw.json.
 *
 * Logs in headlessly with credentials from .realscout_creds.json (reusing a saved
 * session in .realscout_state.json when still valid), opens the matches page,
 * captures the JSON the app fetches, and writes a normalized listing array.
 * On anything unexpected it dumps realscout_dump.html + realscout_dump.png so the
 * selectors/endpoints can be pinned down.
 *
 * Run:  node scrape_realscout.mjs           (uses ../Work/dashboard Playwright)
 * Then: python3 ingest_realscout.py         (geocode + tag + merge to listings.json)
 */
import { chromium } from "/mnt/c/Users/Xliminal/Code/PersonalProjects/Work/dashboard/node_modules/playwright/index.mjs";
import fs from "node:fs";

const HERE = "/mnt/c/Users/Xliminal/Code/PersonalProjects/Moving to PA";
const CREDS = JSON.parse(fs.readFileSync(`${HERE}/.realscout_creds.json`, "utf8"));
const EMAIL = process.env.REALSCOUT_EMAIL || CREDS.email;
const PASSWORD = process.env.REALSCOUT_PASSWORD || CREDS.password;
const BOOTSTRAP_URL = process.env.REALSCOUT_LINK || CREDS.bootstrapUrl;   // passwordless "magic link"
const MATCHES_URL = CREDS.matchesUrl || "https://tabithaheit.realscout.com/homesearch/matches";
const STATE = `${HERE}/.realscout_state.json`;
const EXPLORE = process.argv.includes("--explore");

if (!BOOTSTRAP_URL && !(EMAIL && PASSWORD) && !fs.existsSync(STATE)) {
  console.error("Need a RealScout magic link (bootstrapUrl) or a saved session in .realscout_creds.json.");
  process.exit(2);
}

const log = (...a) => console.log("[realscout]", ...a);

// ── Heuristic field mapping from whatever JSON RealScout returns ──────────────
const pick = (o, keys) => { for (const k of keys) if (o && o[k] != null && o[k] !== "") return o[k]; return null; };
function looksLikeListing(o) {
  if (!o || typeof o !== "object") return false;
  const has = (...ks) => ks.some(k => k in o);
  return (has("list_price", "price", "listPrice", "asking_price") &&
          has("bedrooms", "beds", "num_bedrooms")) ||
         has("street_address", "full_address", "address_line", "display_address");
}
function normalize(o) {
  const addressRaw = pick(o, ["street_address", "address_line", "line", "full_address", "display_address", "address"]);
  const address = typeof addressRaw === "object" ? pick(addressRaw, ["line", "street_address", "full"]) : addressRaw;
  const priceNum = +(`${pick(o, ["list_price", "price", "listPrice", "asking_price"]) ?? ""}`.replace(/[^\d]/g, "")) || 0;
  let photo = pick(o, ["primary_photo", "photo", "photo_url", "thumbnail", "image"]);
  if (!photo) { const ph = pick(o, ["photos", "images", "media"]); if (Array.isArray(ph) && ph.length) photo = typeof ph[0] === "string" ? ph[0] : pick(ph[0], ["url", "href", "src"]); }
  return {
    address: address ? String(address).trim() : null,
    city: pick(o, ["city", "city_name", "locality"]),
    zip: `${pick(o, ["zip", "postal_code", "zip_code", "zipcode"]) ?? ""}`.slice(0, 5),
    price: priceNum ? "$" + priceNum.toLocaleString() : null,
    priceNum,
    beds: +(pick(o, ["bedrooms", "beds", "num_bedrooms"]) ?? 0) || null,
    baths: +(pick(o, ["bathrooms", "baths", "num_bathrooms", "total_baths"]) ?? 0) || null,
    sqft: +(`${pick(o, ["square_feet", "sqft", "living_area", "building_size"]) ?? ""}`.replace(/[^\d]/g, "")) || null,
    photo,
    url: pick(o, ["url", "permalink", "listing_url", "details_url", "share_url"]),
  };
}
// Walk arbitrary JSON and collect arrays of listing-like objects.
function harvest(node, out, depth = 0) {
  if (!node || depth > 8) return;
  if (Array.isArray(node)) {
    if (node.length && node.filter(looksLikeListing).length >= Math.max(1, node.length * 0.5)) out.push(node);
    node.forEach(n => harvest(n, out, depth + 1));
  } else if (typeof node === "object") {
    for (const k in node) harvest(node[k], out, depth + 1);
  }
}

async function autoScroll(page) {
  for (let i = 0; i < 25; i++) {
    await page.mouse.wheel(0, 4000).catch(() => {});
    await page.waitForTimeout(600);
    const more = await page.$('button:has-text("Load more"), button:has-text("Show more"), [data-testid*="load-more"]');
    if (more) { await more.click().catch(() => {}); await page.waitForTimeout(800); }
  }
}

async function tryLogin(page) {
  const pw = await page.$('input[type="password"]');
  if (!pw) return false;
  log("login form detected — signing in");
  const emailSel = await page.$('input[type="email"], input[name*="email" i], input[autocomplete="username"], input[name="user[email]"]');
  if (emailSel) await emailSel.fill(EMAIL);
  await pw.fill(PASSWORD);
  const btn = await page.$('button[type="submit"], input[type="submit"], button:has-text("Sign in"), button:has-text("Log in"), button:has-text("Login")');
  if (btn) await btn.click(); else await pw.press("Enter");
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(2500);
  return true;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext(
    fs.existsSync(STATE) ? { storageState: STATE } : {}
  );
  const page = await ctx.newPage();

  // Capture every JSON response — the matches almost certainly arrive this way.
  const jsons = [];
  page.on("response", async (res) => {
    const ct = (res.headers()["content-type"] || "");
    if (!ct.includes("json")) return;
    try { jsons.push({ url: res.url(), body: await res.json() }); } catch {}
  });

  const arraysIn = () => { const a = []; for (const { body } of jsons) harvest(body, a); return a; };
  async function loadMatches() {
    await page.goto(MATCHES_URL, { waitUntil: "networkidle", timeout: 60000 }).catch(e => log("goto:", e.message));
    await page.waitForTimeout(2500);
    await autoScroll(page);
  }

  log("opening matches:", MATCHES_URL);
  await loadMatches();

  // Not authenticated (no listing data)? Bootstrap a session via the magic link,
  // then via password as a fallback.
  if (!arraysIn().length && BOOTSTRAP_URL) {
    log("no data on saved session — following magic link to authenticate");
    await page.goto(BOOTSTRAP_URL, { waitUntil: "networkidle", timeout: 60000 }).catch(e => log("bootstrap:", e.message));
    await page.waitForTimeout(3000);
    log("landed on:", page.url());
    await loadMatches();
  }
  if (!arraysIn().length && await tryLogin(page)) {
    await loadMatches();
  }

  // Save session for next time.
  await ctx.storageState({ path: STATE }).catch(() => {});

  // Always dump for debugging / selector work.
  fs.writeFileSync(`${HERE}/realscout_dump.html`, await page.content());
  await page.screenshot({ path: `${HERE}/realscout_dump.png`, fullPage: true }).catch(() => {});

  if (EXPLORE) {
    fs.writeFileSync(`${HERE}/realscout_api.json`,
      JSON.stringify(jsons.map(j => ({ url: j.url, sample: Array.isArray(j.body) ? j.body.slice(0, 1) : j.body })), null, 2));
    log("explore mode: wrote realscout_api.json (response catalog)");
  }

  // RealScout serves your matches at data.current_user.searcher.listings via the
  // /graphql-homebuyer endpoint. Each item already has lat/lng, price, beds/baths,
  // a thumbnail, a slug for the detail URL, and verdict.prose ("saved" = favorited).
  const origin = new URL(MATCHES_URL).origin;
  const rsListings = [];
  for (const { body } of jsons) {
    const arr = body?.data?.current_user?.searcher?.listings;
    if (Array.isArray(arr)) rsListings.push(...arr);
  }
  const seen = new Set();
  let listings = [];
  for (const it of rsListings) {
    if (!it || !it.address) continue;
    const k = it.encoded_id || (it.address + "|" + (it.postal_code || ""));
    if (seen.has(k)) continue;
    seen.add(k);
    const priceNum = +(`${it.display_price ?? ""}`.replace(/[^\d]/g, "")) || 0;
    // RealScout hides coordinates (0/0 or null) for undisclosed addresses — treat
    // those as missing so ingest geocodes the ZIP/town centroid instead.
    const lat = Number.isFinite(it.latitude) && it.latitude !== 0 ? it.latitude : null;
    const lng = Number.isFinite(it.longitude) && it.longitude !== 0 ? it.longitude : null;
    listings.push({
      address: String(it.address).trim(),
      city: it.city || "",
      zip: `${it.postal_code ?? ""}`.slice(0, 5),
      price: priceNum ? "$" + priceNum.toLocaleString() : null,
      priceNum,
      beds: it.beds_total ?? null,
      baths: it.baths_total ?? null,
      sqft: it.structure_sqft ?? null,
      lat, lng,
      photo: it.thumbnail_image_url || null,
      url: it.slug ? `${origin}/homesearch/listings/${it.slug}` : MATCHES_URL,
      status: it.display_status || null,
      favorite: !!(it.verdict && /saved|favorite|liked/i.test(it.verdict.prose || "")),
      source: "realscout",
    });
  }

  // Fallback: if RealScout changes their schema, try the generic harvester.
  if (!listings.length) {
    const arrays = [];
    for (const { body } of jsons) harvest(body, arrays);
    arrays.sort((a, b) => b.length - a.length);
    if (arrays.length) {
      for (const o of arrays[0].map(normalize)) {
        if (!o.address || !o.priceNum) continue;
        const k = (o.address + "|" + (o.zip || "")).toLowerCase();
        if (seen.has(k)) continue;
        seen.add(k); o.source = "realscout"; listings.push(o);
      }
    }
  }

  fs.writeFileSync(`${HERE}/realscout_raw.json`, JSON.stringify(listings, null, 2));
  const favs = listings.filter(l => l.favorite).length;
  log(`wrote realscout_raw.json with ${listings.length} listings (${favs} favorited)`);
  if (!listings.length) log("0 extracted — inspect realscout_dump.html / realscout_dump.png / realscout_api.json");

  await browser.close();
})();
