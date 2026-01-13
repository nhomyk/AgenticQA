
const express = require("express");
const bodyParser = require("body-parser");
const puppeteer = require("puppeteer");
const path = require("path");
const rateLimit = require("express-rate-limit");

// Load environment variables
require("dotenv").config();

const app = express();

// Configuration from environment
const PORT = process.env.PORT || 3000;
const HOST = process.env.HOST || "localhost";
const NODE_ENV = process.env.NODE_ENV || "development";
const SCAN_TIMEOUT = parseInt(process.env.SCAN_TIMEOUT_MS || "30000");
const MAX_RESULTS = parseInt(process.env.MAX_RESULTS || "25");
const RATE_LIMIT_WINDOW = parseInt(process.env.RATE_LIMIT_WINDOW_MS || "15000");
const RATE_LIMIT_MAX = parseInt(process.env.RATE_LIMIT_MAX_REQUESTS || "100");

// Security middleware
const rateLimiter = rateLimit({
  windowMs: RATE_LIMIT_WINDOW,
  max: RATE_LIMIT_MAX,
  message: "Too many requests, please try again later.",
  standardHeaders: true,
  legacyHeaders: false,
});

// Middleware setup
app.use(bodyParser.json({ limit: "1mb" }));
app.use(express.static(path.join(__dirname, "public")));

// CORS configuration
if (process.env.ENABLE_CORS === "true") {
  app.use((req, res, next) => {
    res.header("Access-Control-Allow-Origin", process.env.CORS_ORIGIN || "*");
    res.header("Access-Control-Allow-Headers", "Origin, X-Requested-With, Content-Type, Accept");
    res.header("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    next();
  });
}

// Security headers
app.use((req, res, next) => {
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("X-Frame-Options", "DENY");
  res.setHeader("X-XSS-Protection", "1; mode=block");
  res.setHeader("Strict-Transport-Security", "max-age=31536000; includeSubDomains");
  res.setHeader("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'");
  next();
});

// Apply rate limiting to API endpoints
app.use("/scan", rateLimiter);
app.use("/api/", rateLimiter);

// Input validation helpers
function validateUrl(input) {
  if (!input || typeof input !== "string") {
    throw new Error("URL must be a non-empty string");
  }
  
  if (input.length > 2048) {
    throw new Error("URL must be less than 2048 characters");
  }
  
  try {
    const url = new URL(normalizeUrl(input));
    // Prevent scanning of local/internal IPs
    if (isLocalIP(url.hostname)) {
      throw new Error("Cannot scan local or internal IP addresses");
    }
    return url.toString();
  } catch (err) {
    throw new Error("Invalid URL format: " + err.message);
  }
}

function isLocalIP(hostname) {
  const localPatterns = [
    /^localhost$/i,
    /^127\./,
    /^192\.168\./,
    /^10\./,
    /^172\.(1[6-9]|2[0-9]|3[0-1])\./,
    /^::1$/,
    /^fc00:/,
    /^fe80:/,
  ];
  
  return localPatterns.some(pattern => pattern.test(hostname));
}

function sanitizeString(str) {
  if (typeof str !== "string") return "";
  return str
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;")
    .replace(/\//g, "&#x2F;");
}

// Health check endpoint
app.get("/health", (req, res) => {
  res.status(200).json({
    status: "ok",
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    environment: NODE_ENV,
  });
});

// Logging function
function log(level, message, data = {}) {
  const timestamp = new Date().toISOString();
  const logEntry = {
    timestamp,
    level,
    message,
    ...data,
  };
  
  if (NODE_ENV === "production") {
    console.log(JSON.stringify(logEntry));
  } else {
    console.log(`[${timestamp}] ${level}: ${message}`, data);
  }
}

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
  try {
    browser = await puppeteer.launch({ args: ["--no-sandbox", "--disable-setuid-sandbox"] });
    log("info", "Puppeteer browser launched successfully");
  } catch (err) {
    log("error", "Failed to launch Puppeteer browser", { error: err.message });
  }
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
  try {
    const { url } = req.body;
    
    // Input validation
    if (!url) {
      log("warn", "Scan requested without URL");
      return res.status(400).json({ error: "URL is required" });
    }
    
    // Validate and sanitize URL
    let target;
    try {
      target = validateUrl(url);
    } catch (err) {
      log("warn", "Invalid URL provided", { url: url.substring(0, 100), error: err.message });
      return res.status(400).json({ error: err.message });
    }
    
    log("info", "Scan started", { url: target });
    
    // Initialize browser if needed
    if (!browser) {
      log("warn", "Browser not initialized, launching new instance");
      browser = await puppeteer.launch({ args: ["--no-sandbox", "--disable-setuid-sandbox"] });
    }
    
    const page = await browser.newPage();
    
    // Set timeout
    page.setDefaultTimeout(SCAN_TIMEOUT);
    page.setDefaultNavigationTimeout(SCAN_TIMEOUT);
    
    // Navigate with error handling
    try {
      await page.goto(target, { waitUntil: "domcontentloaded" });
    } catch (navErr) {
      log("error", "Navigation failed", { url: target, error: navErr.message });
      throw new Error("Failed to load URL: " + navErr.message);
    }
    
    // Gather page data
    const technologies = await detectTechnologies(page);
    let technologiesArr = Array.isArray(technologies.techs) ? technologies.techs : [];
    let technologyUrls = Array.isArray(technologies.urls) ? technologies.urls : [];
    
    if (!Array.isArray(technologiesArr)) technologiesArr = [];
    if (!Array.isArray(technologyUrls)) technologyUrls = [];
    
    // Example test cases and recommendations
    const testCases = [
      "Verify page loads without errors",
      "Check accessibility compliance"
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
      "Regular security scanning recommended",
      "Update dependencies to latest versions",
      "Enable HTTPS if not already enabled"
    ];
    
    const responsePayload = {
      url: target,
      results: [],
      totalFound: 0,
      testCases,
      performanceResults,
      apis: [],
      recommendations,
      technologies: technologiesArr,
      technologyUrls: technologyUrls.map(u => sanitizeString(u))
    };
    
    await page.close();
    
    log("info", "Scan completed successfully", { url: target });
    res.json(responsePayload);
    
  } catch (err) {
    const errorMessage = err.message || String(err);
    log("error", "Scan failed", { error: errorMessage });
    
    res.status(500).json({
      error: NODE_ENV === "production" 
        ? "An error occurred during scanning" 
        : errorMessage,
      results: []
    });
  }
});

// 404 handler
app.use((req, res) => {
  log("warn", "404 Not Found", { path: req.path, method: req.method });
  res.status(404).json({ error: "Endpoint not found" });
});

// Error handler
app.use((err, req, res) => {
  log("error", "Unhandled error", { error: err.message, stack: err.stack });
  
  res.status(err.status || 500).json({
    error: NODE_ENV === "production" ? "Internal server error" : err.message
  });
});

// Graceful shutdown
process.on("SIGTERM", async () => {
  log("info", "SIGTERM received, shutting down gracefully");
  if (browser) {
    await browser.close();
    log("info", "Browser closed");
  }
  process.exit(0);
});

process.on("SIGINT", async () => {
  log("info", "SIGINT received, shutting down gracefully");
  if (browser) {
    await browser.close();
    log("info", "Browser closed");
  }
  process.exit(0);
});

if (require.main === module) {
  app.listen(PORT, HOST, () => {
    log("info", "Server started", {
      url: `http://${HOST}:${PORT}`,
      environment: NODE_ENV,
      maxResults: MAX_RESULTS,
      scanTimeout: SCAN_TIMEOUT
    });
  });
}

module.exports = { normalizeUrl, mapIssue, validateUrl, sanitizeString };

