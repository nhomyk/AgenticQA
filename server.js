
const express = require("express");
const bodyParser = require("body-parser");
const puppeteer = require("puppeteer");
const path = require("path");

const app = express();
app.use(bodyParser.json({ limit: "1mb" }));
app.use(express.static(path.join(__dirname, "public")));

function mapIssue(type, message, recommendation) {
  return { type, message, recommendation };
}

function normalizeUrl(input) {
  if (!/^https?:\/\//i.test(input)) return "http://" + input;
  return input;
}

// Reuse Puppeteer browser instance
let browser;
(async () => {
  browser = await puppeteer.launch({ args: ["--no-sandbox", "--disable-setuid-sandbox"] });
})();

// Dummy detectTechnologies for now (replace with real logic if needed)
async function detectTechnologies(page) {
  // Example: look for script tags and try to infer tech
  const techs = await page.$$eval('script[src]', scripts =>
    scripts.map(s => s.src.match(/([\w-]+)(?:[./@-])/i)).filter(Boolean).map(m => m[1])
  );
  const urls = await page.$$eval('script[src]', scripts => scripts.map(s => s.src));
  return { techs, urls };
}

app.post("/scan", async (req, res) => {
  const { url } = req.body;
  if (!url) return res.status(400).json({ error: "Missing url" });
  const target = normalizeUrl(url);
  try {
    if (!browser) {
      browser = await puppeteer.launch({ args: ["--no-sandbox", "--disable-setuid-sandbox"] });
    }
    const page = await browser.newPage();
    await page.goto(target, { waitUntil: "domcontentloaded", timeout: 10000 });
    // Add your scanning logic here (DOM checks, performance, etc.)
    // For now, just return a dummy response
    const testCases = [
      "Positive: Example test case",
      "Negative: Example negative test case"
    ];
    const performanceResults = {
      totalRequests: 0,
      failedRequests: 0,
      resourceCount: 0,
      avgResponseTimeMs: 0,
      loadTimeMs: 0,
      throughputReqPerSec: 0,
      topResources: []
    };
    const recommendations = [
      "Add real recommendations here."
    ];
    const technologies = await detectTechnologies(page);
    let technologiesArr = Array.isArray(technologies.techs) ? technologies.techs : [];
    let technologyUrls = Array.isArray(technologies.urls) ? technologies.urls : [];
    // Always ensure both are arrays, even if empty
    if (!Array.isArray(technologiesArr)) technologiesArr = [];
    if (!Array.isArray(technologyUrls)) technologyUrls = [];
    await page.close();
    const responsePayload = {
      url: target,
      results: [],
      totalFound: 0,
      testCases,
      performanceResults,
      apis: [],
      recommendations,
      technologies: technologiesArr,
      technologyUrls
    };
    res.json(responsePayload);
  } catch (err) {
    res.status(500).json({ error: String(err), results: [] });
  }
});

const PORT = process.env.PORT || 3000;
if (require.main === module) {
  app.listen(PORT, () => console.log(`Agentic QA Engineer running on http://localhost:${PORT}`));
}

module.exports = { normalizeUrl, mapIssue };


