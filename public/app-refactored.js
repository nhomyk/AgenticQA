/**
 * Refactored Public App Code - Reduced DOM Complexity
 * Extracted testable functions, dependency injection, reduced coupling
 */

// ============================================
// SECTION 1: UTILITY & HELPER FUNCTIONS
// ============================================

/**
 * Safely validates and formats a URL
 * @param {string} url - URL to validate
 * @returns {string} - Validated URL
 * @throws {Error} - If URL is invalid
 */
function validateAndFormatUrl(url) {
  if (!url || typeof url !== "string") {
    throw new Error("URL must be a non-empty string");
  }
  
  if (url.length > 2048) {
    throw new Error("URL exceeds maximum length (2048 characters)");
  }
  
  try {
    const parsed = new URL(url.startsWith("http") ? url : `http://${url}`);
    
    // Reject internal IPs
    const internalHosts = ["localhost", "127.0.0.1", "0.0.0.0", "::1"];
    if (internalHosts.includes(parsed.hostname)) {
      throw new Error("Local hosts not allowed");
    }
    
    return parsed.toString();
  } catch (err) {
    throw new Error(`Invalid URL: ${err.message}`);
  }
}

/**
 * Sanitizes user input to prevent XSS
 * @param {string} input - User input
 * @returns {string} - Sanitized string
 */
function sanitizeInput(input) {
  if (typeof input !== "string") return "";
  
  const htmlEscapeMap = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  };
  
  return input.replace(/[&<>"']/g, (char) => htmlEscapeMap[char]);
}

/**
 * Detects potential security issues in page content
 * @returns {Object} - Security and accessibility issues found
 */
function detectPageIssues() {
  const issues = [];
  
  // Check for missing alt text on images
  const imgsWithoutAlt = document.querySelectorAll("img:not([alt])").length;
  if (imgsWithoutAlt > 0) {
    issues.push({
      type: "accessibility",
      severity: "medium",
      message: `Found ${imgsWithoutAlt} images without alt text`,
      count: imgsWithoutAlt,
    });
  }
  
  // Check for missing form labels
  const inputsWithoutLabel = document.querySelectorAll(
    "input:not([aria-label]):not([id])"
  ).length;
  if (inputsWithoutLabel > 0) {
    issues.push({
      type: "accessibility",
      severity: "medium",
      message: `Found ${inputsWithoutLabel} form inputs without labels`,
      count: inputsWithoutLabel,
    });
  }
  
  // Check for potential security issues
  const scriptsFromExternalOrigins = document.querySelectorAll(
    "script[src]:not([src*='" + window.location.hostname + "'])"
  ).length;
  if (scriptsFromExternalOrigins > 0) {
    issues.push({
      type: "security",
      severity: "high",
      message: `Found ${scriptsFromExternalOrigins} external scripts`,
      count: scriptsFromExternalOrigins,
    });
  }
  
  return issues;
}

// ============================================
// SECTION 2: RESULT RENDERING (Extracted & Refactored)
// ============================================

/**
 * Formats security detection results for display
 * @param {Object} response - API response with security data
 * @returns {Object} - Formatted results
 */
function formatSecurityResults(response) {
  const results = {
    technologies: response.technologies || [],
    securityIssues: response.securityIssues || [],
    performanceMetrics: response.performanceMetrics || {},
  };
  
  return {
    hasTech: results.technologies.length > 0,
    techCount: results.technologies.length,
    hasIssues: results.securityIssues.length > 0,
    issueCount: results.securityIssues.length,
    ...results,
  };
}

/**
 * Formats API endpoints for display
 * @param {Array<string>} apis - Array of API endpoints
 * @returns {string} - Formatted output
 */
function formatApiList(apis) {
  if (!apis || !Array.isArray(apis) || apis.length === 0) {
    return "No API calls detected during scan.";
  }
  
  const header = "APIs used on this page (first 10 calls)\n\n";
  const lines = apis.slice(0, 10).map((api, index) => `${index + 1}. ${api}`);
  return header + lines.join("\n");
}

/**
 * Generates test case examples for a framework
 * @param {string} framework - Framework name ('playwright' | 'cypress' | 'vitest')
 * @param {Array} testCases - Test case data
 * @returns {string} - Formatted test cases
 */
function generateTestCaseExamples(framework, testCases) {
  if (!testCases || !Array.isArray(testCases) || testCases.length === 0) {
    return `No test cases generated for ${framework}.`;
  }
  
  const limit = 5;
  const cases = testCases.slice(0, limit);
  
  if (framework === "playwright") {
    return generatePlaywrightTests(cases);
  } else if (framework === "cypress") {
    return generateCypressTests(cases);
  } else if (framework === "vitest") {
    return generateVitestTests(cases);
  }
  
  return "";
}

/**
 * Generates Playwright test examples
 * @param {Array} testCases - Test cases
 * @returns {string} - Playwright test code
 */
function generatePlaywrightTests(testCases) {
  const header = "Playwright Test Cases (First 5)\n\n";
  const tests = testCases.map((tc, i) => {
    return `test('Test ${i + 1}: ${sanitizeInput(tc)}', async () => {
  await page.goto('${sanitizeInput(tc)}');
  await expect(page).toHaveTitle(/.*/)
});`;
  });
  
  return header + tests.join("\n\n");
}

/**
 * Generates Cypress test examples
 * @param {Array} testCases - Test cases
 * @returns {string} - Cypress test code
 */
function generateCypressTests(testCases) {
  const header = "Cypress Test Cases (First 5)\n\n";
  const tests = testCases.map((tc, i) => {
    return `it('Test ${i + 1}: ${sanitizeInput(tc)}', () => {
  cy.visit('${sanitizeInput(tc)}');
  cy.get('body').should('be.visible');
});`;
  });
  
  return header + tests.join("\n\n");
}

/**
 * Generates Vitest test examples
 * @param {Array} testCases - Test cases
 * @returns {string} - Vitest test code
 */
function generateVitestTests(testCases) {
  const header = "Vitest Test Cases (First 5)\n\n";
  const tests = testCases.map((tc, i) => {
    return `test('Test ${i + 1}: ${sanitizeInput(tc)}', () => {
  expect('${sanitizeInput(tc)}').toBeTruthy();
});`;
  });
  
  return header + tests.join("\n\n");
}

// ============================================
// SECTION 3: DOM MANIPULATION (Extracted & Batch-Optimized)
// ============================================

/**
 * Batch DOM updates to minimize reflows
 */
const DOMBatcher = (() => {
  let pending = [];
  let scheduled = false;
  
  return {
    schedule: (updateFn) => {
      pending.push(updateFn);
      
      if (!scheduled) {
        scheduled = true;
        requestAnimationFrame(() => {
          pending.forEach((fn) => fn());
          pending = [];
          scheduled = false;
        });
      }
    },
    getPending: () => pending.length,
  };
})();

/**
 * Safely updates DOM element text content
 * @param {Element} element - DOM element
 * @param {string} text - Text content to set
 */
function setElementText(element, text) {
  if (!element) return;
  
  DOMBatcher.schedule(() => {
    element.textContent = sanitizeInput(text);
  });
}

/**
 * Safely sets element value
 * @param {Element} element - Input/textarea element
 * @param {string} value - Value to set
 */
function setElementValue(element, value) {
  if (!element || !value) return;
  
  DOMBatcher.schedule(() => {
    if (element.tagName === "TEXTAREA" || element.tagName === "INPUT") {
      element.value = value;
    }
  });
}

/**
 * Updates multiple DOM elements in one batch
 * @param {Object} updates - Mapping of element selectors to content
 */
function batchUpdateElements(updates) {
  DOMBatcher.schedule(() => {
    Object.entries(updates).forEach(([selector, content]) => {
      const element = document.querySelector(selector);
      if (element) {
        element.textContent = sanitizeInput(content);
      }
    });
  });
}

// ============================================
// SECTION 4: EVENT HANDLING (Extracted & Refactored)
// ============================================

/**
 * Tab switching handler
 */
const TabManager = (() => {
  const hiddenClass = "hidden";
  const activeClass = "active";
  
  return {
    switchTab: (tabName) => {
      // Hide all tabs
      const allTabs = document.querySelectorAll(".tab-pane");
      allTabs.forEach((tab) => {
        tab.classList.add(hiddenClass);
        tab.classList.remove(activeClass);
      });
      
      // Show selected tab
      const selectedTab = document.getElementById(tabName);
      if (selectedTab) {
        selectedTab.classList.remove(hiddenClass);
        selectedTab.classList.add(activeClass);
      }
    },
    
    init: () => {
      const tabButtons = document.querySelectorAll("[data-tab]");
      tabButtons.forEach((btn) => {
        btn.addEventListener("click", (e) => {
          e.preventDefault();
          const tabName = btn.getAttribute("data-tab");
          TabManager.switchTab(tabName);
          TabManager.updateTabUI(tabName);
        });
      });
    },
    
    updateTabUI: (activeTab) => {
      const buttons = document.querySelectorAll("[data-tab]");
      buttons.forEach((btn) => {
        const isActive = btn.getAttribute("data-tab") === activeTab;
        if (isActive) {
          btn.classList.add(activeClass);
        } else {
          btn.classList.remove(activeClass);
        }
      });
    },
  };
})();

// ============================================
// SECTION 5: SCAN SUBMISSION & API CALLS
// ============================================

/**
 * HTTP client with error handling and timeouts
 */
const HttpClient = (() => {
  const DEFAULT_TIMEOUT = 30000;
  
  return {
    post: async (url, data, timeout = DEFAULT_TIMEOUT) => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);
      
      try {
        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
          signal: controller.signal,
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
      } catch (err) {
        clearTimeout(timeoutId);
        throw err;
      }
    },
  };
})();

/**
 * Handles scan form submission
 */
async function submitScan(url) {
  try {
    // Validate URL
    const validatedUrl = validateAndFormatUrl(url);
    
    // Show loading state
    setElementText(document.querySelector(".scan-status"), "Scanning...");
    
    // Submit scan
    const result = await HttpClient.post("/scan", { url: validatedUrl });
    
    // Process results
    renderResults(result);
    
  } catch (err) {
    console.error("Scan error:", err);
    setElementText(
      document.querySelector(".scan-status"),
      `Error: ${sanitizeInput(err.message)}`
    );
  }
}

/**
 * Renders all results to the page
 * @param {Object} response - API response
 */
function renderResults(response) {
  const formatted = formatSecurityResults(response);
  
  // Batch update multiple elements
  batchUpdateElements({
    ".results-tech": formatted.hasT tech ? `${formatted.techCount} technologies detected` : "No technologies detected",
    ".results-security": formatted.hasIssues ? `${formatted.issueCount} issues found` : "No issues detected",
    ".results-apis": formatApiList(response.apis),
    ".results-playwright": generateTestCaseExamples("playwright", response.testCases),
    ".results-cypress": generateTestCaseExamples("cypress", response.testCases),
    ".results-vitest": generateTestCaseExamples("vitest", response.testCases),
  });
}

// ============================================
// SECTION 6: INITIALIZATION & EXPORTS
// ============================================

// Auto-initialize when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    TabManager.init();
  });
} else {
  TabManager.init();
}

// Expose public API for testing
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    validateAndFormatUrl,
    sanitizeInput,
    detectPageIssues,
    formatSecurityResults,
    formatApiList,
    generateTestCaseExamples,
    setElementText,
    setElementValue,
    batchUpdateElements,
    submitScan,
    TabManager,
    HttpClient,
  };
}
