
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



// Dummy detectTechnologies for now (replace with real logic if needed)
async function detectTechnologies() {
  return { techs: [], urls: [] };
}

app.post("/scan", async (req, res) => {
  const { url } = req.body;
  if (!url) return res.status(400).json({ error: "Missing url" });
  const target = normalizeUrl(url);
  let browser;
  try {
    browser = await puppeteer.launch({ headless: true });
    const page = await browser.newPage();
    await page.goto(target, { waitUntil: "networkidle2", timeout: 20000 });
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
    let technologiesArr = [];
    let technologyUrls = [];
    if (technologies && Array.isArray(technologies.techs)) {
      technologiesArr = Array.isArray(technologies.techs) ? technologies.techs : [];
      technologyUrls = Array.isArray(technologies.urls) ? technologies.urls : [];
    } else if (Array.isArray(technologies)) {
      technologiesArr = technologies;
    }
    // Always ensure both are arrays, even if empty
    if (!Array.isArray(technologiesArr)) technologiesArr = [];
    if (!Array.isArray(technologyUrls)) technologyUrls = [];
    await browser.close();
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
    if (browser) await browser.close();
    res.status(500).json({ error: String(err), results: [] });
  }

});

const PORT = process.env.PORT || 3000;
if (require.main === module) {
  app.listen(PORT, () => console.log(`Agentic QA Engineer running on http://localhost:${PORT}`));
}

module.exports = { normalizeUrl, mapIssue };


