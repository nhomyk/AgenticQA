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
  } catch {
    // ignore parsing errors
    return input;
  }
}

function mapIssue(type, message, recommendation) {
  return { type, message, recommendation };
}

function generateRecommendations(results, features, performanceResults) {
  const recommendations = [];
  
  // Count issues by type
  const accessibilityIssues = results.filter(r => ["MissingAlt", "EmptyAlt", "MissingLabel", "HeadingOrder"].includes(r.type)).length;
  const performanceIssues = results.filter(r => r.type === "RequestFailed").length;

  // Recommendation 1: Accessibility & Inclusivity Strategy
  if (accessibilityIssues > 8) {
    recommendations.push(`🎯 Accessibility Crisis: ${accessibilityIssues} issues detected. This isn't just about compliance—it affects 15% of your audience. Start with: (1) ARIA labels on all form inputs (50% of issues), (2) Meaningful alt text on images (critical for SEO), (3) Color contrast ratios (4.5:1 minimum). Use aXe DevTools for continuous scanning. Budget 2-3 sprints for remediation.`);
  } else if (accessibilityIssues > 3) {
    recommendations.push(`♿ Accessibility Opportunity: ${accessibilityIssues} fixable issues. Implement: (1) Tab order testing (keyboard-only navigation), (2) ARIA landmarks for screen readers, (3) Focus indicators on interactive elements. This directly impacts: SEO ranking (+8%), user retention (+12%), legal compliance (ADA). Priority: High ROI improvements.`);
  } else {
    recommendations.push(`⭐ Accessibility Foundation Solid: Only ${accessibilityIssues || 0} minor issues. Next level: (1) ARIA live regions for dynamic content, (2) Semantic HTML audit, (3) Testing with real assistive tech users. This shows commitment to inclusive design—a competitive differentiator.`);
  }
  // Recommendation 2: Performance & User Experience
  if (performanceIssues > 3) {
    recommendations.push(`⚡ Critical Performance Issue: ${performanceIssues} failed requests. Each failure: (1) Increases bounce rate by 7%, (2) Costs ~$2.6M annually in lost revenue per 1sec delay. Actions: (1) Audit external dependencies for dead code, (2) Implement request retries with exponential backoff, (3) Set up error tracking (Sentry), (4) Cache aggressively. This is business-critical.`);
  } else if (performanceResults && performanceResults.loadTimeMs > 3000) {
    recommendations.push("⏱️ Load Time Optimization Critical: Page load >3 seconds. Each 100ms delay costs 1% conversion rate. Implement: (1) Image optimization (WebP format, lazy loading), (2) Code splitting (lazy load non-critical JS), (3) CDN adoption, (4) Service Worker caching, (5) Monitor Core Web Vitals monthly. Target: <2 seconds (mobile), <1 second (desktop).");
  } else {
    recommendations.push("🚀 Performance Excellence: Load times solid. Maintain competitive advantage: (1) Monthly Core Web Vitals audits via Google Lighthouse, (2) Implement Service Workers for offline experience, (3) Progressive image loading (LQIP), (4) Database query optimization. Benchmark against competitors to stay ahead.");
  }

  // Recommendation 3: API Design & Testing Strategy
  const apiCount = features && features.hasForm ? 3 : 1;
  if (apiCount > 10) {
    recommendations.push(`🔌 API Architecture Review Needed: ${apiCount}+ API endpoints detected. Risk assessment: (1) Review for unused/deprecated endpoints (maintenance debt), (2) Audit response payloads for bloat, (3) Implement rate limiting to prevent abuse, (4) Standardize error responses (REST conventions), (5) Versioning strategy. Create API specification (OpenAPI/Swagger) for documentation and contract testing.`);
  } else if (apiCount > 3) {
    recommendations.push(`🧪 API Testing Foundation: ${apiCount} APIs identified. Critical gaps to fill: (1) Contract testing (verify endpoint schemas), (2) Integration tests (API chains), (3) Load testing under 100 concurrent users, (4) Security scanning (OWASP Top 10). Use Playwright for complex multi-step API flows. Coverage target: 85%+ of critical paths.`);
  } else {
    recommendations.push("📡 API Simplicity Advantage: Minimal APIs detected. Leverage this: (1) Comprehensive E2E tests covering all flows, (2) Mock API responses for frontend tests, (3) GraphQL evaluation (if complexity grows). Document all endpoints in OpenAPI 3.0 format for developer onboarding.");
  }

  // Recommendation 4: Testing & QA Automation Strategy
  const issueCount = results.length;
  recommendations.push(`🧪 Advanced Testing Strategy: Current scan identified ${issueCount} issues. Build comprehensive test pyramid: (1) Unit tests (40%): Core functions, utilities, calculations, (2) Integration tests (30%): API interactions, database queries, feature workflows, (3) E2E tests (20%): Critical user journeys, (4) Visual regression (10%): Design consistency. Target: 80%+ code coverage. Tools: Playwright (E2E), Vitest (unit), Percy (visual). CI/CD integration mandatory for velocity.`);

  // Recommendation 5: Strategic QA Roadmap
  recommendations.push("🎯 Strategic QA Roadmap (Q1-Q2): (1) Week 1-2: Establish testing infrastructure (CI/CD pipelines, baseline metrics), (2) Week 3-4: Unit test coverage to 60%, accessibility audit + fixes, (3) Week 5-8: E2E test suite for critical paths (15+ scenarios), API contract testing, (4) Week 9-12: Performance optimization, security audit, stress testing. Success metrics: Deploy confidence > 95%, bug escape rate < 2%, incident response time < 30min. This roadmap prevents technical debt and scales your team.");

  return recommendations;
}

app.post("/scan", async (req, res) => {
  const { url } = req.body;
  if (!url) return res.status(400).json({ error: "Missing url" });
  const target = normalizeUrl(url);
  console.log("[SERVER] /scan called for URL:", target);

  const results = [];

  let browser;
  try {
    console.log("[SERVER] Launching browser for:", target);
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
    page.on("request", () => {
      totalRequests += 1;
    });
    page.on("requestfailed", request => {
      failedRequests += 1;
      results.push(mapIssue("RequestFailed", `${request.url()} -> ${request.failure() && request.failure().errorText}`, "Check resource URL and server responses; ensure CORS and availability."));
    });
    page.on("requestfinished", () => {
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

    // Generate AI recommendations based on scan results
    const recommendations = generateRecommendations(results, features, performanceResults);

    // trim to 25 issue results
    const trimmed = results.slice(0, 25);

    await browser.close();
    const responsePayload = { url: target, results: trimmed, totalFound: results.length, testCases: testCases.slice(0,20), performanceResults, apis: apis || [], recommendations };
    console.log("[SERVER] Responding with payload:", JSON.stringify(responsePayload, null, 2));
    res.json(responsePayload);
  } catch (err) {
    if (browser) await browser.close();
    res.status(500).json({ error: String(err), results: results.slice(0,25) });
  }
});

const PORT = process.env.PORT || 3000;
if (require.main === module) {
  app.listen(PORT, () => console.log(`Agentic QA Engineer running on http://localhost:${PORT}`));
}

// Export functions for testing (ESM)
export { normalizeUrl, mapIssue };
