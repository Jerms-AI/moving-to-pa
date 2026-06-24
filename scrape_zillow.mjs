/**
 * Scrape your Zillow saved homes by reusing a logged-in session.
 *
 * You export your zillow.com cookies (Cookie-Editor extension -> Export as JSON)
 * into .zillow_cookies.json. This loads them into a headless browser, opens your
 * saved-homes page, captures the JSON Zillow's app fetches, and writes
 * zillow_raw.json. Dumps zillow_dump.html / .png so we can pin down the data.
 *
 * Run:  node scrape_zillow.mjs "<your saved-homes URL>"
 *       (URL optional; defaults below. Add --explore for the response catalog.)
 */
import { chromium } from "/mnt/c/Users/Xliminal/Code/PersonalProjects/Work/dashboard/node_modules/playwright/index.mjs";
import fs from "node:fs";

const HERE = "/mnt/c/Users/Xliminal/Code/PersonalProjects/Moving to PA";
const COOKIES_FILE = `${HERE}/.zillow_cookies.json`;
const EXPLORE = process.argv.includes("--explore");
const SAVED_URL = process.argv.find(a => a.startsWith("http")) || "https://www.zillow.com/myzillow/";
const log = (...a) => console.log("[zillow]", ...a);

if (!fs.existsSync(COOKIES_FILE)) {
  console.error("Missing .zillow_cookies.json — export your zillow.com cookies first.");
  process.exit(2);
}

// Cookie-Editor exports an array of cookie objects; map them to Playwright's shape.
const SS = { no_restriction: "None", lax: "Lax", strict: "Strict", unspecified: "Lax" };
function toPlaywrightCookies(raw) {
  return raw.map(c => {
    const ck = {
      name: c.name, value: c.value,
      domain: c.domain || (c.host && "." + c.host) || ".zillow.com",
      path: c.path || "/",
      httpOnly: !!c.httpOnly,
      secure: !!c.secure,
      sameSite: SS[String(c.sameSite).toLowerCase()] || "Lax",
    };
    if (c.expirationDate) ck.expires = Math.floor(c.expirationDate);
    return ck;
  }).filter(c => c.name && c.value);
}

(async () => {
  let raw;
  try { raw = JSON.parse(fs.readFileSync(COOKIES_FILE, "utf8")); }
  catch (e) { console.error("Couldn't parse .zillow_cookies.json:", e.message); process.exit(2); }
  const cookies = toPlaywrightCookies(Array.isArray(raw) ? raw : raw.cookies || []);
  log(`loaded ${cookies.length} cookies`);

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    viewport: { width: 1366, height: 900 },
  });
  await ctx.addCookies(cookies);
  const page = await ctx.newPage();

  const jsons = [];
  page.on("response", async (res) => {
    const ct = res.headers()["content-type"] || "";
    if (!ct.includes("json")) return;
    try { jsons.push({ url: res.url(), body: await res.json() }); } catch {}
  });

  log("opening saved homes:", SAVED_URL);
  await page.goto(SAVED_URL, { waitUntil: "domcontentloaded", timeout: 60000 }).catch(e => log("goto:", e.message));
  await page.waitForTimeout(4000);
  for (let i = 0; i < 20; i++) { await page.mouse.wheel(0, 4000).catch(() => {}); await page.waitForTimeout(500); }

  fs.writeFileSync(`${HERE}/zillow_dump.html`, await page.content());
  await page.screenshot({ path: `${HERE}/zillow_dump.png`, fullPage: true }).catch(() => {});

  // Bot-wall detection
  const html = (await page.content()).toLowerCase();
  const blocked = /press.{0,4}hold|captcha|are you a human|px-captcha|perimeterx|unusual traffic/.test(html);
  if (blocked) log("⚠ looks like Zillow served a bot challenge — cookie route may not work; we'll use the Network-tab fallback.");

  if (EXPLORE) {
    fs.writeFileSync(`${HERE}/zillow_api.json`,
      JSON.stringify(jsons.map(j => ({ url: j.url, sample: Array.isArray(j.body) ? j.body.slice(0, 1) : j.body })), null, 2));
    log(`explore: wrote zillow_api.json (${jsons.length} JSON responses)`);
  }
  log(`captured ${jsons.length} JSON responses. Inspect zillow_dump.html / zillow_dump.png / zillow_api.json`);
  await browser.close();
})();
