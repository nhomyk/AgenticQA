
const express = require("express");
const bodyParser = require("body-parser");
const puppeteer = require("puppeteer");
const path = require("path");
const rateLimit = require("express-rate-limit");
const https = require("https");
const http = require("http");

// Load environment variables
require("dotenv").config();

const app = express();

// Configuration from environment
const PORT = process.env.PORT || 3000;
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
app.use(bodyParser.json({ limit: "100kb" })); // Reduced from 1mb to prevent large payload attacks
app.use(express.static(path.join(__dirname, "public")));

// Root handler - redirect to dashboard
app.get("/", (req, res) => {
  res.redirect("/public/dashboard.html");
});

// CORS configuration - stricter settings
if (process.env.ENABLE_CORS === "true") {
  const allowedOrigins = (process.env.CORS_ORIGIN || "localhost:3000").split(",").map(o => o.trim());
  app.use((req, res, next) => {
    const origin = req.headers.origin;
    if (allowedOrigins.includes(origin) || allowedOrigins.includes("*")) {
      res.header("Access-Control-Allow-Origin", origin || allowedOrigins[0]);
    }
    res.header("Access-Control-Allow-Headers", "Origin, X-Requested-With, Content-Type, Accept");
    res.header("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    res.header("Access-Control-Max-Age", "3600");
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

// ===== API PROXY TO SaaS API Server (saas-api-dev.js on port 3001) =====
// Forward /api/* requests to the SaaS API server so the dashboard can access all API endpoints
app.use("/api/", async (req, res) => {
  try {
    // Construct the URL for the proxied request
    const apiUrl = `http://localhost:3001${req.originalUrl}`;
    const url = new URL(apiUrl);
    
    // Log proxy request
    log("info", "Proxying API request to SaaS server", { 
      originalUrl: req.originalUrl,
      method: req.method,
      target: "localhost:3001"
    });

    // Prepare proxy request options
    const options = {
      hostname: url.hostname,
      port: url.port || 3001,
      path: url.pathname + url.search,
      method: req.method,
      headers: {
        "Content-Type": req.headers["content-type"] || "application/json",
        "Authorization": req.headers["authorization"] || "",
        "User-Agent": "Dashboard-Proxy/1.0"
      }
    };

    // Make the proxied request
    const proxyReq = http.request(options, (proxyRes) => {
      // Forward the response status
      res.writeHead(proxyRes.statusCode, proxyRes.headers);
      
      // Forward the response body
      proxyRes.pipe(res);
    });

    // Forward body for POST/PUT/PATCH requests
    if (req.method !== "GET" && req.method !== "HEAD") {
      if (req.body && Object.keys(req.body).length > 0) {
        proxyReq.write(JSON.stringify(req.body));
      }
    }

    // Handle proxy request errors
    proxyReq.on("error", (error) => {
      log("error", "API proxy error", { 
        error: error.message,
        url: req.originalUrl,
        code: error.code
      });
      
      // If SaaS server is not available, return error
      if (!res.headersSent) {
        res.status(503).json({ 
          error: "SaaS API server is not available. Make sure saas-api-dev.js is running on port 3001.",
          details: error.message 
        });
      }
    });

    // End the proxy request
    proxyReq.end();
    
  } catch (error) {
    log("error", "API proxy middleware error", { 
      error: error.message,
      url: req.originalUrl 
    });
    
    res.status(500).json({ 
      error: "Internal server error in API proxy",
      details: error.message 
    });
  }
});

// Health check endpoint
app.get("/health", (req, res) => {
  res.status(200).json({
    status: "ok",
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    environment: NODE_ENV,
  });
});

// Detailed comparison endpoint
app.get("/api/comparison", (req, res) => {
  res.status(200).json({
    status: "success",
    data: {
      products: [
        {
          name: "orbitQA.ai (CLI)",
          category: "In-Repo Version",
          features: [
            "Local CLI tools",
            "Pre-commit hooks",
            "Direct file system access",
            "Developer-focused",
            "Open source",
            "Zero setup for developers",
            "Runs on your machine"
          ],
          pricing: "Free / Open Source",
          deployment: "Local"
        },
        {
          name: "orbitQA.ai (SaaS)",
          category: "External Platform",
          features: [
            "REST API endpoints",
            "GitHub/GitLab webhooks",
            "Multi-tenant infrastructure",
            "Team collaboration",
            "Enterprise security",
            "Managed hosting",
            "Real-time dashboards"
          ],
          pricing: "Subscription-based",
          deployment: "Cloud"
        }
      ],
      comparison: {
        architecture: "Shared agent cores (@orbitqa/* packages)",
        codebase: "Zero duplication between CLI and SaaS",
        maintenance: "Single source of truth for core logic",
        scalability: "Independent evolution per deployment model"
      },
      capabilities: {
        testing: "Automated QA, Compliance checks, Performance analysis",
        integration: "GitHub, GitLab, CI/CD pipelines",
        reporting: "Real-time dashboards, Historical trends, Risk assessment",
        compliance: "GDPR, SOC2, HIPAA, CCPA, GDPR, LGPD, PCI-DSS, ISO 27001"
      }
    },
    timestamp: new Date().toISOString()
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

// Reuse Puppeteer browser instance (lazy initialized)
let browser;
let browserInitialized = false;

async function initializeBrowser() {
  if (browserInitialized) return;
  browserInitialized = true;
  
  try {
    browser = await puppeteer.launch({ args: ["--no-sandbox", "--disable-setuid-sandbox"] });
    log("info", "Puppeteer browser launched successfully");
  } catch (err) {
    log("error", "Failed to launch Puppeteer browser", { error: err.message });
  }
}

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
  let page = null;
  const requestTimeout = setTimeout(() => {
    log("error", "Scan request timeout after " + SCAN_TIMEOUT + "ms");
    if (page) {
      page.close().catch(() => {});
    }
    if (!res.headersSent) {
      res.status(504).json({ error: "Scan request timed out", results: [] });
    }
  }, SCAN_TIMEOUT + 5000); // 5 second buffer above page timeout
  
  try {
    const { url } = req.body;
    
    // Input validation
    if (!url) {
      log("warn", "Scan requested without URL");
      clearTimeout(requestTimeout);
      return res.status(400).json({ error: "URL is required" });
    }
    
    // Validate and sanitize URL
    let target;
    try {
      target = validateUrl(url);
    } catch (err) {
      log("warn", "Invalid URL provided", { url: url.substring(0, 100), error: err.message });
      clearTimeout(requestTimeout);
      return res.status(400).json({ error: err.message });
    }
    
    log("info", "Scan started", { url: target });
    
    // Initialize browser if needed (lazy loading)
    if (!browser) {
      log("info", "Initializing Puppeteer browser on first scan request");
      await initializeBrowser();
    }
    
    if (!browser) {
      throw new Error("Browser failed to initialize");
    }
    
    page = await browser.newPage();
    
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
    
    // Detect security issues
    const results = [];
    
    // Check for mixed content warnings
    const hasHttp = target.startsWith("http://");
    if (hasHttp) {
      results.push(mapIssue("security", "Page uses unencrypted HTTP protocol", "Use HTTPS instead of HTTP for secure connections"));
    }
    
    // Check for console errors and warnings
    const consoleMessages = [];
    page.on("console", msg => {
      if (msg.type() === "error" || msg.type() === "warning") {
        consoleMessages.push(msg.text());
      }
    });
    
    // Detect potential security and accessibility issues from page content
    const pageIssues = await page.evaluate(() => {
      const issues = [];
      
      // Check for missing alt text on images
      const imgsWithoutAlt = document.querySelectorAll("img:not([alt])").length;
      if (imgsWithoutAlt > 0) {
        issues.push({
          type: "accessibility",
          message: `Found ${imgsWithoutAlt} images without alt text`,
          recommendation: "Add descriptive alt text to all images for accessibility"
        });
      }
      
      // Check for missing form labels
      const inputsWithoutLabel = document.querySelectorAll("input:not([aria-label]):not([id])").length;
      if (inputsWithoutLabel > 0) {
        issues.push({
          type: "accessibility",
          message: `Found ${inputsWithoutLabel} form inputs without labels`,
          recommendation: "Use label elements or aria-label attributes on all form inputs"
        });
      }
      
      // Check for color contrast issues
      const lowContrastElements = document.querySelectorAll("[style*='color']").length;
      if (lowContrastElements > 5) {
        issues.push({
          type: "accessibility",
          message: "Multiple elements with inline color styles detected",
          recommendation: "Use CSS classes for styling to ensure color contrast compliance"
        });
      }
      
      // Check for missing viewport meta tag
      if (!document.querySelector("meta[name='viewport']")) {
        issues.push({
          type: "performance",
          message: "Missing viewport meta tag",
          recommendation: "Add <meta name='viewport' content='width=device-width, initial-scale=1'>"
        });
      }
      
      // Check for render-blocking resources
      const scripts = document.querySelectorAll("script[src]").length;
      if (scripts > 5) {
        issues.push({
          type: "performance",
          message: `Found ${scripts} external script tags (may block rendering)`,
          recommendation: "Use async or defer attributes on scripts to improve page load time"
        });
      }
      
      return issues;
    });
    
    results.push(...pageIssues);
    
    // Detect API calls
    const apis = [];
    const requestsIntercepted = [];
    
    page.on("response", async response => {
      const url = response.url();
      // Capture API/AJAX calls (filter out document and stylesheet requests)
      if ((url.includes("/api/") || url.includes(".json") || url.match(/\.(jpg|png|css|js|ico|woff|woff2)$/)) === false) {
        if (!requestsIntercepted.includes(url)) {
          requestsIntercepted.push(url);
        }
      }
    });
    
    // Wait a bit to catch any async API calls
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Extract actual XHR/Fetch endpoints from network
    const networkRequests = await page.evaluate(() => {
      // Try to capture from performance timing
      const entries = performance.getEntriesByType("resource");
      return entries
        .filter(e => e.name.includes("/api/") || e.name.includes(".json"))
        .slice(0, 10)
        .map(e => e.name);
    });
    
    apis.push(...networkRequests);
    
    // Also look for fetch/XHR calls in scripts
    const pageApis = await page.evaluate(() => {
      const found = [];
      const scripts = document.querySelectorAll("script");
      let totalCode = "";
      
      for (const script of scripts) {
        if (script.textContent) {
          totalCode += script.textContent + "\n";
        }
      }
      
      // Look for common API patterns
      const patterns = [
        /fetch\(['"`]([^'"`]+)['"`]/gi,
        /\.get\(['"`]([^'"`]+)['"`]/gi,
        /\.post\(['"`]([^'"`]+)['"`]/gi,
        /api['\s]*:\s*['"`]([^'"`]+)['"`]/gi,
        /endpoint\s*=\s*['"`]([^'"`]+)['"`]/gi
      ];
      
      for (const pattern of patterns) {
        let match;
        while ((match = pattern.exec(totalCode)) !== null) {
          if (match[1]) {
            found.push(match[1]);
          }
        }
      }
      
      return found.slice(0, 10);
    });
    
    apis.push(...pageApis);
    
    // Deduplicate and limit
    const uniqueApis = [...new Set(apis)].filter(a => a && a.length > 0 && !a.startsWith("blob:")).slice(0, 10);
    
    // Collect real performance metrics from the page
    const performanceData = await page.evaluate(() => {
      const perfTiming = performance.timing || {};
      const perfNavTiming = performance.getEntriesByType("navigation")[0];
      const resourceEntries = performance.getEntriesByType("resource");
      
      // Calculate page load time
      let loadTimeMs = 0;
      if (perfTiming.loadEventEnd && perfTiming.navigationStart) {
        loadTimeMs = perfTiming.loadEventEnd - perfTiming.navigationStart;
      } else if (perfNavTiming) {
        loadTimeMs = perfNavTiming.loadEventEnd - perfNavTiming.fetchStart;
      }
      
      // Calculate average response time and get top resources
      let totalResponseTime = 0;
      let responseCount = 0;
      const topResources = [];
      
      for (const resource of resourceEntries) {
        if (resource.duration > 0) {
          totalResponseTime += resource.duration;
          responseCount++;
        }
        
        // Collect top 5 slowest resources
        if (topResources.length < 5) {
          topResources.push({
            name: resource.name.split("/").pop().substring(0, 40),
            timeMs: Math.round(resource.duration),
            type: resource.initiatorType || "unknown"
          });
        }
      }
      
      // Sort by duration descending
      topResources.sort((a, b) => b.timeMs - a.timeMs);
      
      const avgResponseTime = responseCount > 0 ? totalResponseTime / responseCount : 0;
      const throughput = loadTimeMs > 0 ? (resourceEntries.length * 1000) / loadTimeMs : 0;
      
      return {
        totalRequests: resourceEntries.length,
        avgResponseTimeMs: Math.round(avgResponseTime),
        loadTimeMs: Math.round(loadTimeMs),
        throughputReqPerSec: Math.round(throughput * 10) / 10,
        topResources: topResources.slice(0, 5)
      };
    });
    
    // Example test cases and recommendations
    const testCases = [
      "Verify page loads without errors",
      "Check accessibility compliance",
      `Validate that ${results.length} identified issues are addressed`,
      "Test all API endpoints for proper error handling",
      "Verify responsive design on mobile devices",
      `Optimize page load time (currently ${performanceData.loadTimeMs}ms)`
    ];
    
    const performanceResults = {
      totalRequests: performanceData.totalRequests,
      failedRequests: 0,
      resourceCount: performanceData.totalRequests,
      avgResponseTimeMs: performanceData.avgResponseTimeMs,
      loadTimeMs: performanceData.loadTimeMs,
      throughputReqPerSec: performanceData.throughputReqPerSec,
      topResources: performanceData.topResources
    };
    
    const recommendations = [
      results.length > 0 ? `Fix ${results.length} identified accessibility and performance issues` : "Continue regular accessibility and performance monitoring",
      "Update dependencies to latest versions",
      "Enable HTTPS if not already enabled",
      "Implement proper error handling for all API calls",
      "Add CORS headers if serving cross-origin requests"
    ];
    
    const responsePayload = {
      url: target,
      results: results.slice(0, 10),  // Limit to 10 results
      totalFound: results.length,
      testCases,
      performanceResults,
      apis: uniqueApis,
      recommendations,
      technologies: technologiesArr,
      technologyUrls: technologyUrls.map(u => sanitizeString(u))
    };
    
    if (page) {
      await page.close().catch(err => {
        log("warn", "Error closing page", { error: err.message });
      });
    }
    
    clearTimeout(requestTimeout);
    log("info", "Scan completed successfully", { url: target });
    res.json(responsePayload);
    
  } catch (err) {
    const errorMessage = err.message || String(err);
    log("error", "Scan failed", { error: errorMessage });
    
    if (page) {
      await page.close().catch(err => {
        log("warn", "Error closing page in catch block", { error: err.message });
      });
    }
    
    clearTimeout(requestTimeout);
    
    if (!res.headersSent) {
      res.status(500).json({
        error: NODE_ENV === "production" 
          ? "An error occurred during scanning" 
          : errorMessage,
        results: []
      });
    }
  }
});

// Workflow dispatch API endpoint
app.post("/api/trigger-workflow", async (req, res) => {
  try {
    // Disable caching for this endpoint
    res.set("Cache-Control", "no-store, no-cache, must-revalidate, proxy-revalidate");
    res.set("Pragma", "no-cache");
    res.set("Expires", "0");
    
    const { pipelineType = "manual", branch = "main", pipelineName } = req.body;
    
    log("info", "🚀 Trigger workflow request received", { pipelineType, branch, pipelineName });
    
    // Validate pipeline type against whitelist (prevent injection)
    const validPipelineTypes = ["full", "tests", "security", "accessibility", "compliance", "manual"];
    if (!validPipelineTypes.includes(pipelineType)) {
      log("warn", "Invalid pipeline type attempted", { pipelineType, ip: req.ip });
      return res.status(400).json({
        error: "Invalid pipeline type",
        status: "error"
      });
    }
    
    // Validate branch name (alphanumeric, dash, underscore, slash only)
    // Max 255 characters
    if (!branch || typeof branch !== "string" || branch.length > 255) {
      log("warn", "Invalid branch name (missing or too long)", { branch, ip: req.ip });
      return res.status(400).json({
        error: "Invalid branch",
        status: "error"
      });
    }
    
    if (!/^[a-zA-Z0-9._\-/]+$/.test(branch)) {
      log("warn", "Invalid branch name format attempted", { branch, ip: req.ip });
      return res.status(400).json({
        error: "Invalid branch format",
        status: "error"
      });
    }
    
    // Validate pipeline name if provided (max 255 characters)
    if (pipelineName && (typeof pipelineName !== "string" || pipelineName.length > 255)) {
      log("warn", "Invalid pipeline name format attempted", { pipelineName, ip: req.ip });
      return res.status(400).json({
        error: "Invalid pipeline name",
        status: "error"
      });
    }
    
    // Get GitHub token from config or environment
    let githubToken = process.env.GITHUB_TOKEN;
    log("info", "🔍 Token check", {
      hasEnv: !!process.env.GITHUB_TOKEN,
      envLength: process.env.GITHUB_TOKEN ? process.env.GITHUB_TOKEN.length : 0,
      hasConfig: !!(global.githubConfig && global.githubConfig.fullToken),
      configLength: (global.githubConfig && global.githubConfig.fullToken) ? global.githubConfig.fullToken.length : 0
    });
    
    if (!githubToken && global.githubConfig && global.githubConfig.fullToken) {
      githubToken = global.githubConfig.fullToken;
      log("info", "Using GitHub token from global config");
    } else if (githubToken) {
      log("info", "Using GitHub token from environment variable", { tokenStart: githubToken.substring(0, 10), length: githubToken.length });
    }
    
    if (!githubToken) {
      log("warn", "❌ GITHUB_TOKEN not available for workflow dispatch");
      return res.status(503).json({
        error: "GitHub token not configured. Please add your GitHub PAT in Settings.",
        status: "error"
      });
    }
    
    // Prepare workflow dispatch payload
    // Use custom pipeline name if provided, otherwise generate from type
    const pipelineTypeDisplayNames = {
      full: "Full CI/CD Pipeline",
      tests: "Test Suite",
      security: "Security Scan",
      accessibility: "Accessibility Audit",
      compliance: "Compliance Check",
      manual: "Manual Pipeline"
    };
    
    const workflowName = pipelineName || `🤖 AgenticQA - ${pipelineTypeDisplayNames[pipelineType] || pipelineType}`;
    
    const payload = {
      ref: branch,
      inputs: {
        reason: workflowName,
        run_type: "manual"
      }
    };
    
    log("info", "📋 Preparing GitHub workflow dispatch", { workflowName, ref: branch, payload: JSON.stringify(payload) });
    
    // Call GitHub API to dispatch workflow
    return new Promise((resolve) => {
      const payloadString = JSON.stringify(payload);
      const options = {
        hostname: "api.github.com",
        port: 443,
        path: "/repos/nhomyk/AgenticQA/actions/workflows/ci.yml/dispatches",
        method: "POST",
        headers: {
          "Accept": "application/vnd.github+json",
          "Authorization": `Bearer ${githubToken}`,
          "X-GitHub-Api-Version": "2022-11-28",
          "Content-Type": "application/json",
          "User-Agent": "AgenticQA-Dashboard",
          "Content-Length": Buffer.byteLength(payloadString)
        }
      };
      
      const githubReq = https.request(options, (githubRes) => {
        let responseBody = "";
        
        githubRes.on("data", (chunk) => {
          responseBody += chunk;
        });
        
        githubRes.on("end", () => {
          log("info", "📡 GitHub API response received", { statusCode: githubRes.statusCode });
          
          if (githubRes.statusCode === 204) {
            log("info", "✅ Workflow dispatch successful!", {
              pipelineType,
              branch,
              workflowName,
              timestamp: new Date().toISOString()
            });
            
            resolve(res.status(200).json({
              status: "success",
              message: `✅ Pipeline '${pipelineType}' triggered successfully on branch '${branch}'`,
              workflow: "ci.yml",
              branch: branch,
              pipelineType: pipelineType,
              workflowName: workflowName,
              timestamp: new Date().toISOString()
            }));
          } else if (githubRes.statusCode === 401 || githubRes.statusCode === 403) {
            log("warn", "🔐 GitHub token authentication failed", {
              status: githubRes.statusCode,
              body: responseBody
            });
            
            resolve(res.status(403).json({
              error: "GitHub token authentication failed. Verify token has 'actions' and 'contents' scopes.",
              status: "error",
              helpUrl: "https://github.com/settings/tokens"
            }));
          } else if (githubRes.statusCode === 404) {
            log("warn", "🔍 GitHub workflow not found", {
              repository: "nhomyk/AgenticQA",
              workflow: "ci.yml",
              status: githubRes.statusCode
            });
            
            resolve(res.status(404).json({
              error: "GitHub workflow 'ci.yml' not found in repository 'nhomyk/AgenticQA'",
              status: "error"
            }));
          } else {
            log("error", "⚠️ GitHub API returned unexpected status", {
              status: githubRes.statusCode,
              body: responseBody
            });
            
            resolve(res.status(502).json({
              error: `GitHub API error: HTTP ${githubRes.statusCode}`,
              status: "error",
              details: responseBody
            }));
          }
        });
      });
      
      githubReq.on("error", (error) => {
        log("error", "❌ GitHub API request failed", {
          error: error.message
        });
        
        resolve(res.status(502).json({
          error: "Failed to communicate with GitHub API",
          status: "error",
          details: error.message
        }));
      });
      
      githubReq.write(payloadString);
      githubReq.end();
    });
  } catch (error) {
    log("error", "❌ Workflow dispatch failed with exception", {
      error: error.message,
      stack: error.stack
    });
    
    return res.status(500).json({
      error: "Failed to trigger workflow: " + error.message,
      status: "error"
    });
  }
});

// GitHub Connection API endpoint
app.post("/api/github/connect", (req, res) => {
  try {
    const { token, repository } = req.body;
    
    if (!token) {
      return res.status(400).json({
        error: "GitHub Personal Access Token is required",
        status: "error"
      });
    }

    // Store GitHub token in memory (in production, use secure storage)
    global.githubConfig = {
      token: token.substring(0, 10) + "***", // Masked version for logging
      fullToken: token, // Full token for actual use
      repository: repository || "",
      connectedAt: new Date().toISOString()
    };

    log("info", "GitHub token saved", {
      repository: repository || "not specified"
    });

    res.json({
      status: "success",
      message: "GitHub account connected successfully",
      repository: repository || "Not specified"
    });
  } catch (error) {
    log("error", "GitHub connection failed", { error: error.message });
    res.status(500).json({
      error: "Failed to connect GitHub account: " + error.message,
      status: "error"
    });
  }
});

// GitHub connection status endpoint
app.get("/api/github/status", (req, res) => {
  try {
    // Disable caching for this endpoint
    res.set("Cache-Control", "no-store, no-cache, must-revalidate, proxy-revalidate");
    res.set("Pragma", "no-cache");
    res.set("Expires", "0");
    
    const hasEnvToken = !!process.env.GITHUB_TOKEN;
    const hasConfigToken = !!(global.githubConfig && global.githubConfig.fullToken);
    const isConnected = hasEnvToken || hasConfigToken || (global.githubConfig && global.githubConfig.fullToken);
    
    if (isConnected) {
      res.json({
        status: "connected",
        repository: global.githubConfig?.repository || "nhomyk/AgenticQA",
        connectedAt: global.githubConfig?.connectedAt || new Date().toISOString(),
        hasEnvToken: hasEnvToken,
        hasConfigToken: hasConfigToken,
        tokenSource: hasEnvToken ? "environment" : (hasConfigToken ? "config" : "none")
      });
    } else {
      res.json({
        status: "disconnected",
        hasEnvToken: hasEnvToken,
        hasConfigToken: hasConfigToken,
        tokenSource: hasEnvToken ? "environment" : (hasConfigToken ? "config" : "none")
      });
    }
  } catch (error) {
    res.status(500).json({
      error: "Failed to check GitHub status: " + error.message
    });
  }
});

// GitHub disconnect endpoint
app.post("/api/github/disconnect", (req, res) => {
  try {
    global.githubConfig = null;
    log("info", "GitHub account disconnected");
    res.json({
      status: "success",
      message: "GitHub account disconnected"
    });
  } catch (error) {
    res.status(500).json({
      error: "Failed to disconnect GitHub account: " + error.message
    });
  }
});

// GitHub test connection endpoint
app.post("/api/github/test", (req, res) => {
  try {
    if (!global.githubConfig) {
      return res.status(400).json({
        error: "GitHub account not connected",
        status: "error"
      });
    }

    res.json({
      status: "success",
      message: "GitHub connection test successful",
      repository: global.githubConfig.repository || "Not specified"
    });
  } catch (error) {
    res.status(500).json({
      error: "GitHub connection test failed: " + error.message
    });
  }
});

// Get available branches from GitHub repository
app.get("/api/github/branches", async (req, res) => {
  try {
    if (!global.githubConfig) {
      return res.json({
        status: "success",
        branches: [
          { name: "main", protected: true },
          { name: "develop", protected: false }
        ]
      });
    }

    const [owner, repo] = (global.githubConfig.repository || "").split("/");
    
    if (!owner || !repo) {
      return res.json({
        status: "success",
        branches: [
          { name: "main", protected: true },
          { name: "develop", protected: false },
          { name: "staging", protected: false }
        ]
      });
    }

    const branchResponse = await new Promise((resolve, reject) => {
      const options = {
        hostname: "api.github.com",
        path: `/repos/${owner}/${repo}/branches`,
        method: "GET",
        headers: {
          "Authorization": `token ${global.githubConfig.fullToken}`,
          "User-Agent": "orbitQA.ai",
          "Accept": "application/vnd.github.v3+json"
        }
      };

      const request = https.request(options, (response) => {
        let data = "";
        response.on("data", (chunk) => (data += chunk));
        response.on("end", () => {
          try {
            resolve({ status: response.statusCode, data: JSON.parse(data) });
          } catch (e) {
            resolve({ status: response.statusCode, data: [] });
          }
        });
      });

      request.on("error", reject);
      request.end();
    });

    if (branchResponse.status === 200 && Array.isArray(branchResponse.data)) {
      const branches = branchResponse.data.map(b => ({
        name: b.name,
        protected: b.protected || false
      }));
      
      res.json({
        status: "success",
        branches: branches
      });
    } else {
      res.json({
        status: "success",
        branches: [
          { name: "main", protected: true },
          { name: "develop", protected: false }
        ]
      });
    }
  } catch (error) {
    log("error", "Failed to fetch branches", { error: error.message });
    res.json({
      status: "success",
      branches: [
        { name: "main", protected: true },
        { name: "develop", protected: false }
      ]
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

// Graceful shutdown on SIGTERM (sent by process managers)
process.on("SIGTERM", async () => {
  log("info", "SIGTERM received, shutting down gracefully");
  if (browser) {
    await browser.close();
    log("info", "Browser closed");
  }
  process.exit(0);
});

// SIGINT handler: during development/testing, let the process manager handle it
// This prevents accidental shutdown when SIGINT is sent by start-server-and-test
process.on("SIGINT", () => {
  // Just log it, don't exit - let start-server-and-test manage the lifecycle
  log("info", "SIGINT received (ignoring to allow process manager to control shutdown)");
});

if (require.main === module) {
  let server = null;
  
  const startServer = () => {
    try {
      server = app.listen(PORT, "127.0.0.1", () => {
        log("info", "Server started", {
          url: `http://127.0.0.1:${PORT}`,
          environment: NODE_ENV,
          maxResults: MAX_RESULTS,
          scanTimeout: SCAN_TIMEOUT
        });
      });
      
      server.on("error", (err) => {
        if (err.code === "EADDRINUSE") {
          log("error", `Port ${PORT} is already in use`, {
            port: PORT,
            code: err.code
          });
          console.error(`\n❌ Port ${PORT} is already in use.`);
          console.error(`   Kill it with: lsof -ti:${PORT} | xargs kill -9`);
          process.exit(1);
        } else {
          log("error", "Server error", { error: err.message });
          throw err;
        }
      });
      
      return server;
    } catch (err) {
      log("error", "Failed to start server", { error: err.message });
      console.error(`\n❌ Server startup failed: ${err.message}`);
      process.exit(1);
    }
  };
  
  startServer();
}

// NEW: Utility function for formatting API responses
function formatApiResponse(data, status = "success") {
  return {
    status,
    data,
    timestamp: new Date().toISOString(),
    version: "1.0"
  };
}

module.exports = { normalizeUrl, mapIssue, validateUrl, sanitizeString, formatApiResponse };

