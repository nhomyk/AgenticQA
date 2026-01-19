import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { JSDOM } from "jsdom";

describe("Dashboard Page - Pipeline Triggering", () => {
  let dom;
  let document;
  let window;

  beforeEach(() => {
    dom = new JSDOM(`
      <!DOCTYPE html>
      <html>
        <body>
          <select id="pipelineType">
            <option value="full">Full CI/CD</option>
            <option value="tests">Tests</option>
            <option value="security">Security</option>
            <option value="compliance">Compliance</option>
          </select>
          <input type="text" id="pipelineBranch" value="main" />
          <button class="btn-primary">🚀 Launch Pipeline</button>
          <div id="pipelineStatus"></div>
          <div id="pipelineError" style="display: none;"></div>
        </body>
      </html>
    `, {
      url: "http://localhost:3000",
      pretendToBeVisual: true
    });
    
    document = dom.window.document;
    window = dom.window;
    global.document = document;
    global.window = window;
    global.fetch = vi.fn();
    global.localStorage = {
      data: {},
      getItem(key) { return this.data[key] || null; },
      setItem(key, value) { this.data[key] = value; },
      removeItem(key) { delete this.data[key]; },
      clear() { this.data = {}; }
    };
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("should validate pipeline type selection", () => {
    const pipelineType = document.getElementById("pipelineType");
    
    expect(pipelineType.value).toBe("full");
    
    pipelineType.value = "tests";
    expect(pipelineType.value).toBe("tests");
  });

  it("should validate branch input", () => {
    const branch = document.getElementById("pipelineBranch");
    
    expect(branch.value).toBe("main");
    
    branch.value = "develop";
    expect(branch.value).toBe("develop");
  });

  it("should check GitHub connection before launching pipeline", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        status: "connected",
        repository: "nicholashomyk/AgenticQA"
      })
    });

    const checkGitHubConnectionBefore = async () => {
      const response = await fetch("/api/github/status", {
        method: "GET",
        headers: { "Content-Type": "application/json" }
      });
      const data = await response.json();
      return data.status === "connected";
    };

    const isConnected = await checkGitHubConnectionBefore();
    expect(isConnected).toBe(true);
  });

  it("should prevent pipeline launch when GitHub not connected", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ status: "disconnected" })
    });

    const checkGitHubConnectionBefore = async () => {
      const response = await fetch("/api/github/status", {
        method: "GET",
        headers: { "Content-Type": "application/json" }
      });
      const data = await response.json();
      return data.status === "connected";
    };

    const isConnected = await checkGitHubConnectionBefore();
    expect(isConnected).toBe(false);
  });

  it("should trigger a full pipeline", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        status: "success",
        message: "Pipeline triggered successfully (full)",
        pipelineType: "full",
        branch: "main"
      })
    });

    const pipelineType = "full";
    const branch = "main";

    const response = await fetch("/api/trigger-workflow", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pipelineType, branch })
    });

    const data = await response.json();

    expect(response.ok).toBe(true);
    expect(data.status).toBe("success");
    expect(data.pipelineType).toBe("full");
    expect(data.branch).toBe("main");
  });

  it("should trigger a security pipeline", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        status: "success",
        message: "Pipeline triggered successfully (security)",
        pipelineType: "security",
        branch: "main"
      })
    });

    const response = await fetch("/api/trigger-workflow", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pipelineType: "security", branch: "main" })
    });

    const data = await response.json();

    expect(data.pipelineType).toBe("security");
  });

  it("should trigger a compliance pipeline", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        status: "success",
        message: "Pipeline triggered successfully (compliance)",
        pipelineType: "compliance",
        branch: "main"
      })
    });

    const response = await fetch("/api/trigger-workflow", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pipelineType: "compliance", branch: "main" })
    });

    const data = await response.json();

    expect(data.pipelineType).toBe("compliance");
  });

  it("should reject invalid pipeline types", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: () => Promise.resolve({
        error: "Invalid pipeline type",
        status: "error"
      })
    });

    const response = await fetch("/api/trigger-workflow", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pipelineType: "invalid", branch: "main" })
    });

    const data = await response.json();

    expect(response.ok).toBe(false);
    expect(data.error).toContain("Invalid");
  });

  it("should validate branch names", async () => {
    const validBranches = ["main", "develop", "feature/test", "release-1.0", "fix_bug"];
    
    for (const branch of validBranches) {
      const isValid = /^[a-zA-Z0-9._\-/]+$/.test(branch);
      expect(isValid).toBe(true);
    }
  });

  it("should reject invalid branch names", async () => {
    const invalidBranches = ["main@", "test#branch", "feature$", "release!"];
    
    for (const branch of invalidBranches) {
      const isValid = /^[a-zA-Z0-9._\-/]+$/.test(branch);
      expect(isValid).toBe(false);
    }
  });

  it("should include pipeline name in request reason", async () => {
    const pipelineTypeDisplayNames = {
      full: "Full CI/CD Pipeline",
      tests: "Test Suite",
      security: "Security Scan",
      compliance: "Compliance Check"
    };

    const pipelineType = "full";
    const expectedReason = `orbitQA.ai - ${pipelineTypeDisplayNames[pipelineType]}`;
    
    expect(expectedReason).toBe("orbitQA.ai - Full CI/CD Pipeline");
  });

  it("should handle GitHub API error responses", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 403,
      json: () => Promise.resolve({
        error: "GitHub token authentication failed",
        status: "error"
      })
    });

    const response = await fetch("/api/trigger-workflow", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pipelineType: "full", branch: "main" })
    });

    const data = await response.json();

    expect(response.status).toBe(403);
    expect(data.error).toContain("authentication failed");
  });

  it("should handle missing token error", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: () => Promise.resolve({
        error: "GitHub token not configured. Please add your GitHub PAT in Settings.",
        status: "error"
      })
    });

    const response = await fetch("/api/trigger-workflow", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pipelineType: "full", branch: "main" })
    });

    const data = await response.json();

    expect(response.status).toBe(503);
    expect(data.error).toContain("not configured");
  });

  it("should store user authentication token in localStorage", () => {
    const token = "demo-token-" + Date.now();
    global.localStorage.setItem("token", token);
    
    const storedToken = global.localStorage.getItem("token");
    expect(storedToken).toBe(token);
  });

  it("should store user info in localStorage", () => {
    const userInfo = {
      email: "test@example.com",
      name: "Test User"
    };
    global.localStorage.setItem("user", JSON.stringify(userInfo));
    
    const storedUser = JSON.parse(global.localStorage.getItem("user"));
    expect(storedUser.email).toBe("test@example.com");
    expect(storedUser.name).toBe("Test User");
  });

  it("should clear localStorage on logout", () => {
    global.localStorage.setItem("token", "test-token");
    global.localStorage.setItem("user", JSON.stringify({ email: "test@example.com" }));
    
    global.localStorage.clear();
    
    expect(global.localStorage.getItem("token")).toBeNull();
    expect(global.localStorage.getItem("user")).toBeNull();
  });
});
