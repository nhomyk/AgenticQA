const express = require("express");
const bodyParser = require("body-parser");
const puppeteer = require("puppeteer");
const path = require("path");

const app = express();
app.use(bodyParser.json({ limit: "1mb" }));
app.use(express.static(path.join(__dirname, "public")));

function normalizeUrl(input) {
  try {
    // add protocol if missing
    if (!/^https?:\/\//i.test(input)) return "http://" + input;
    return input;
  } catch (e) {
     
    return input;
  }
}

function mapIssue(type, message, recommendation) {
  return { type, message, recommendation };
}

app.post("/scan", async (req, res) => {
  const { url } = req.body;
  if (!url) return res.status(400).json({ error: "Missing url" });
  const target = normalizeUrl(url);

  const results = [];

  let browser;
  try {
    browser = await puppeteer.launch({ args: ["--no-sandbox", "--disable-setuid-sandbox"] });
    const page = await browser.newPage();

    // collect console errors
    page.on("console", msg => {
      try {
        if (msg.type() === "error") {
          results.push(mapIssue("ConsoleError", msg.text(), "Check the stack trace and source; fix the script error or wrap calls in try/catch."));
        }
      } catch (e) {
         
        void e;
      }
    });

    // uncaught page errors
    page.on("pageerror", err => {
      results.push(mapIssue("PageError", String(err), "Fix the exception in page scripts; guard against undefined values."));
    });

    // request tracking for basic performance metrics
    let totalRequests = 0;
    let failedRequests = 0;
    page.on("request", request => {
       
      totalRequests += 1;
    });
    page.on("requestfailed", request => {
      failedRequests += 1;
      results.push(mapIssue("RequestFailed", `${request.url()} -> ${request.failure() && request.failure().errorText}`, "Check resource URL and server responses; ensure CORS and availability."));
    });
    page.on("requestfinished", _request => {
       
      // finished requests counted via `request` event; keep hooks for future metrics
    });

    await page.setViewport({ width: 1280, height: 900 });
    await page.goto(target, { waitUntil: "load", timeout: 30000 }).catch((e) => {
      results.push(mapIssue("NavigationError", String(e), "Verify the URL and network; consider increasing timeout."));
    });


    // DOM checks, feature detection, and API usage detection
    const domResult = await page.evaluate(() => {
      const issues = [];

      const features = {
        hasForm: !!document.querySelector("form"),
        hasSearch: !!document.querySelector("input[type=\"search\"], input[name*=\"search\" i], form[action*=\"search\" i]"),
        hasLogin: !!document.querySelector("input[type=\"password\"], form[action*=\"/login\" i]"),
        hasImages: !!document.querySelector("img"),
        hasLinks: !!document.querySelector("a[href]"),
        hasButtons: !!document.querySelector("button, [role=\"button\"]"),
        hasNav: !!document.querySelector("nav"),
        hasTables: !!document.querySelector("table"),
        hasModal: !!document.querySelector("[role=\"dialog\"], .modal"),
        headingCount: document.querySelectorAll("h1,h2,h3").length
      };

      // images missing alt or empty alt
      document.querySelectorAll("img").forEach(img => {
        if (!img.hasAttribute("alt")) {
          issues.push({ type: "MissingAlt", message: `img src=${img.currentSrc || img.src} missing alt`, recommendation: "Add meaningful alt text describing the image." });
        } else if (img.getAttribute("alt").trim() === "") {
          issues.push({ type: "EmptyAlt", message: `img src=${img.currentSrc || img.src} has empty alt`, recommendation: "Provide descriptive alt text or mark as decorative with alt=\"\" and role=\"presentation\"." });
        }
        if (img.naturalWidth === 0) {
          issues.push({ type: "BrokenImage", message: `img src=${img.currentSrc || img.src} appears broken (naturalWidth=0)`, recommendation: "Ensure the image URL is correct and the resource is served." });
        }
      });

      // inputs without labels or aria-label
      document.querySelectorAll("input, textarea, select").forEach(el => {
        const id = el.id;
        const hasLabel = id && document.querySelector(`label[for="${id}"]`);
        const aria = el.getAttribute("aria-label") || el.getAttribute("aria-labelledby");
        if (!hasLabel && !aria && el.type !== "hidden") {
          issues.push({ type: "MissingLabel", message: `Form control (${el.tagName.toLowerCase()} type=${el.type || "n/a"}) missing label or aria-label`, recommendation: "Add a <label> or aria-label to improve accessibility." });
        }
      });

      // anchors with empty or javascript href
      document.querySelectorAll("a").forEach(a => {
        const href = a.getAttribute("href");
        if (!href || href.trim() === "" || href === "#") {
          issues.push({ type: "BadHref", message: `anchor text="${(a.textContent||"").trim().slice(0,30)}" has href="${href}"`, recommendation: "Use meaningful hrefs or use button elements for actions." });
        }
      });

      // headings order issues (simple check)
      const headings = Array.from(document.querySelectorAll("h1,h2,h3,h4,h5,h6")).map(h => parseInt(h.tagName.slice(1)));
      for (let i = 1; i < headings.length; i++) {
        if (headings[i] > headings[i-1] + 1) {
          issues.push({ type: "HeadingOrder", message: `Possible heading order issue: ...${headings[i-1]} -> ${headings[i]}`, recommendation: "Ensure heading levels follow a logical sequence for accessibility and structure." });
          break;
        }
      }

      // API usage detection (fetch/XHR)
      const origFetch = window.fetch;
      window.__apiCalls = [];
      window.fetch = function(...args) {
        window.__apiCalls.push(args[0]);
        return origFetch.apply(this, args);
      };
      const origXhrOpen = window.XMLHttpRequest && window.XMLHttpRequest.prototype.open;
      if (origXhrOpen) {
        window.XMLHttpRequest.prototype.open = function(method, url, ...rest) {
          window.__apiCalls.push(url);
          return origXhrOpen.call(this, method, url, ...rest);
        };
      }

      // Wait a bit to collect API calls (simulate page activity)
      return new Promise(resolve => {
        setTimeout(() => {
          const apis = (window.__apiCalls || []).slice(0, 10);
          resolve({ issues, features, apis });
        }, 2000);
      });
    });


    // domResult is now a Promise result
    const { issues: domIssues, features, apis } = domResult;
    domIssues.forEach(i => results.push(mapIssue(i.type, i.message, i.recommendation)));

    // Performance / JMeter-like summary using resource timings
    const perf = await page.evaluate(() => {
      const resources = performance.getEntriesByType("resource").map(r => ({ name: r.name, duration: r.duration, initiatorType: r.initiatorType }));
      const nav = performance.getEntriesByType("navigation")[0] || {};
      const loadTime = nav.loadEventEnd || (performance.timing ? (performance.timing.loadEventEnd - performance.timing.fetchStart) : 0);
      return { resources, loadTime };
    });

    const resourceCount = perf.resources.length;
    const avgResponseTimeMs = resourceCount ? Math.round(perf.resources.reduce((s, r) => s + (r.duration || 0), 0) / resourceCount) : 0;
    const loadTimeMs = Math.round(perf.loadTime || 0);
    const throughputReqPerSec = loadTimeMs > 0 ? Math.round((totalRequests / (loadTimeMs / 1000)) * 100) / 100 : 0;

    const topResources = perf.resources.sort((a,b) => (b.duration||0) - (a.duration||0)).slice(0,10).map(r => ({ name: r.name, timeMs: Math.round(r.duration || 0), type: r.initiatorType }));

    const performanceResults = {
      totalRequests,
      failedRequests,
      resourceCount,
      avgResponseTimeMs,
      loadTimeMs,
      throughputReqPerSec,
      topResources
    };

    // generate recommended test cases (10 positive, 10 negative) based on features
    const testCases = [];
    const f = features;
    // helper to push up to 20
    const pushIf = (title) => { if (testCases.length < 20) testCases.push(title); };

    // Positive tests
    if (f.headingCount > 0) pushIf("Positive: Verify main headings render properly");
    if (f.hasNav) pushIf("Positive: Navigation menu loads and links are clickable");
    if (f.hasSearch) pushIf("Positive: Search returns results for valid query");
    if (f.hasForm) pushIf("Positive: Submitting form with valid data succeeds");
    if (f.hasLogin) pushIf("Positive: Login form accepts valid credentials and redirects");
    if (f.hasImages) pushIf("Positive: Important images display with non-empty alt text");
    if (f.hasButtons) pushIf("Positive: Primary CTA button is visible and triggers action");
    if (f.hasLinks) pushIf("Positive: All main links navigate to expected destinations");
    if (f.hasTables) pushIf("Positive: Data tables render rows and pagination works");
    if (f.hasModal) pushIf("Positive: Modal/dialog opens and closes correctly");

    // Negative tests
    if (f.hasSearch) pushIf("Negative: Searching with gibberish returns no results handled gracefully");
    if (f.hasForm) pushIf("Negative: Submitting form with invalid data shows validation errors");
    if (f.hasLogin) pushIf("Negative: Login with wrong credentials shows proper error");
    if (f.hasImages) pushIf("Negative: Broken image placeholders are shown or replaced");
    if (f.hasButtons) pushIf("Negative: Disabled buttons are not clickable and show correct state");
    if (f.hasLinks) pushIf("Negative: Broken links return 4xx/5xx and are reported");
    pushIf("Negative: Page handles slow network (resources time out)");
    pushIf("Negative: Layout does not break under long text or large images");
    pushIf("Negative: Accessibility: focus order works for keyboard navigation");
    pushIf("Negative: Heading structure regressions cause screen-reader confusion");

    // trim to 25 issue results
    const trimmed = results.slice(0, 25);

    await browser.close();
    res.json({ url: target, results: trimmed, totalFound: results.length, testCases: testCases.slice(0,20), performanceResults, apis: apis || [] });
  } catch (err) {
    if (browser) await browser.close();
    res.status(500).json({ error: String(err), results: results.slice(0,25) });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Agentic QA Engineer running on http://localhost:${PORT}`));

// Export functions for testing
module.exports = { normalizeUrl, mapIssue };
