
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

// Enhanced detectTechnologies with multiple detection methods
async function detectTechnologies(page) {
  const detectedTechs = new Set();
  const urls = [];

  try {
    // 1. Detect from script tags (src attributes)
    const scriptData = await page.$$eval("script[src]", scripts => {
      return {
        techs: scripts
          .map(s => {
            const src = s.src;
            // Extract tech name from URL
            const patterns = [
              /([a-z-]+)@[\d.]+/i,  // @version format (e.g., react@17)
              /\/([a-z-]+)\/[\d.]+/i, // /tech/version format
              /([a-z-]+)\.min\.js/i, // tech.min.js format
              /([a-z-]+)\/[\d.]+\//i, // tech/version/ format
              /([\w-]+)(?:[-.](?:min|latest|stable))?\.js/i  // generic tech.js
            ];
            
            for (const pattern of patterns) {
              const match = src.match(pattern);
              if (match && match[1]) return match[1];
            }
            return null;
          })
          .filter(Boolean),
        urls: scripts.map(s => s.src)
      };
    });
    
    scriptData.techs.forEach(t => detectedTechs.add(t));
    urls.push(...scriptData.urls);

    // 2. Detect from meta tags
    const metaTags = await page.$$eval("meta", metas => {
      const results = [];
      metas.forEach(meta => {
        const name = meta.getAttribute("name") || meta.getAttribute("property") || "";
        const content = meta.getAttribute("content") || "";
        
        if (name.includes("generator") && content) {
          results.push(content);
        }
        if (name.includes("framework") && content) {
          results.push(content);
        }
      });
      return results;
    });
    
    metaTags.forEach(t => {
      if (t) {
        const tech = t.split(/[\s,;/]/)[0];
        if (tech.length > 1) detectedTechs.add(tech);
      }
    });

    // 3. Detect from link tags (stylesheets, frameworks)
    const linkData = await page.$$eval("link[rel='stylesheet']", links => {
      return links.map(l => l.href).filter(href => href && href.length > 0);
    });
    
    linkData.forEach(href => {
      const patterns = [
        /\/([a-z-]+)\/[\d.]+\/.*\.css/i,
        /([a-z-]+)\.min\.css/i,
        /(bootstrap|materialize|tailwind|foundation|bulma|semantic)/i
      ];
      
      for (const pattern of patterns) {
        const match = href.match(pattern);
        if (match && match[1]) {
          detectedTechs.add(match[1]);
          break;
        }
      }
    });

    // 4. Detect from HTTP headers
    const responseHeaders = await page.evaluate(() => {
      return {
        server: document.head?.querySelector("meta[http-equiv=\"Server\"]")?.content || "",
        powered: document.head?.querySelector("meta[http-equiv=\"X-UA-Compatible\"]")?.content || ""
      };
    });
    
    if (responseHeaders.server) detectedTechs.add(responseHeaders.server.split("/")[0]);

    // 5. Detect common patterns in page content
    const pageContent = await page.evaluate(() => {
      const html = document.documentElement.outerHTML;
      const techs = [];
      
      // Look for framework signatures in HTML
      const patterns = {
        "Next.js": /__NEXT_DATA__|next\.js|next\/page/i,
        "Vue.js": /v-|Vue\.|__VUE__|nuxt/i,
        "Angular": /ng-|angular|ng-app/i,
        "Ember.js": /ember|EMBER|ember\.js/i,
        "Backbone.js": /Backbone|backbone/i,
        "Svelte": /svelte|sveltekit/i,
        "Astro": /astro/i,
        "Gatsby": /gatsby/i,
        "Remix": /remix/i,
        "SvelteKit": /sveltekit/i
      };
      
      for (const [name, regex] of Object.entries(patterns)) {
        if (regex.test(html)) {
          techs.push(name);
        }
      }
      
      return techs;
    });
    
    pageContent.forEach(t => detectedTechs.add(t));

    // 6. Detect from favicon and common library patterns
    const commonLibraries = {
      "jQuery": /jquery/i,
      "Lodash": /lodash/i,
      "Axios": /axios/i,
      "Fetch API": /fetch/i,
      "Moment.js": /moment/i,
      "D3.js": /d3/i,
      "Three.js": /three/i,
      "Chart.js": /chart/i,
      "DataTables": /datatables/i,
      "Slick": /slick/i,
      "Owl Carousel": /owl/i,
      "Bootstrap": /bootstrap/i,
      "Font Awesome": /font-?awesome/i,
      "Animate.css": /animate/i,
      "AOS": /aos|animate-on-scroll/i,
      "Popper.js": /popper/i,
      "Tooltip": /tooltip/i
    };
    
    for (const [name, pattern] of Object.entries(commonLibraries)) {
      if (urls.some(url => pattern.test(url))) {
        detectedTechs.add(name);
      }
    }

  } catch (err) {
    console.error("Error detecting technologies:", err.message);
  }

  // Clean up and normalize tech names
  const finalTechs = Array.from(detectedTechs)
    .map(t => {
      // Normalize: capitalize, remove special chars
      return t
        .replace(/[-_]/g, " ")
        .replace(/\b\w/g, char => char.toUpperCase())
        .trim();
    })
    .filter(t => t.length > 1 && !["Js", "Css", "Min", "Latest", "Stable"].includes(t))
    .sort();

  return { 
    techs: [...new Set(finalTechs)],  // Deduplicate
    urls 
  };
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


