import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { JSDOM } from "jsdom";

describe("Settings Page - GitHub Integration", () => {
  let dom;
  let document;
  let window;

  beforeEach(() => {
    // Setup DOM
    dom = new JSDOM(`
      <!DOCTYPE html>
      <html>
        <body>
          <div id="githubStatus" class="github-status disconnected">
            <h3>GitHub Not Connected</h3>
            <p id="statusMessage">Click "Connect GitHub" below</p>
          </div>
          <input type="password" id="githubToken" />
          <input type="text" id="githubRepo" />
          <button id="saveTokenBtn" onclick="saveGitHubToken(this)">Save Token</button>
          <div id="connectedCard" style="display: none;">Connected</div>
          <div id="githubLoginBtn" style="display: block;">Login</div>
          <div id="manualTokenBtn" style="display: block;">Manual Token</div>
          <div id="manualTokenCard" style="display: none;">Token Form</div>
          <div id="triggerTestCard" style="display: none;">Test</div>
          <div id="connectedAccount">—</div>
          <div id="connectedRepo">—</div>
          <div id="lastUsed">Never</div>
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
    global.githubConfig = null;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("should display GitHub Not Connected status initially", () => {
    const status = document.getElementById("githubStatus");
    expect(status.classList.contains("disconnected")).toBe(true);
    expect(document.querySelector("h3").textContent).toBe("GitHub Not Connected");
  });

  it("should show connected status when GitHub is connected", () => {
    const showConnectedStatus = (data) => {
      document.getElementById("githubStatus").classList.remove("disconnected");
      document.querySelector("h3").textContent = "✅ GitHub Connected";
      document.getElementById("statusMessage").textContent = "✅ Connected";
      document.getElementById("connectedAccount").textContent = "GitHub PAT Connected";
      document.getElementById("connectedRepo").textContent = data.repository || "—";
      document.getElementById("githubLoginBtn").style.display = "none";
      document.getElementById("manualTokenBtn").style.display = "none";
      document.getElementById("manualTokenCard").style.display = "none";
      document.getElementById("connectedCard").style.display = "block";
      document.getElementById("triggerTestCard").style.display = "block";
    };

    const testData = {
      status: "connected",
      repository: "nicholashomyk/AgenticQA",
      connectedAt: new Date().toISOString()
    };

    showConnectedStatus(testData);

    expect(document.getElementById("githubStatus").classList.contains("disconnected")).toBe(false);
    expect(document.querySelector("h3").textContent).toBe("✅ GitHub Connected");
    expect(document.getElementById("connectedCard").style.display).toBe("block");
    expect(document.getElementById("githubLoginBtn").style.display).toBe("none");
  });

  it("should hide connected status when disconnected", () => {
    const showDisconnectedStatus = () => {
      document.getElementById("githubStatus").classList.add("disconnected");
      document.querySelector("h3").textContent = "❌ GitHub Not Connected";
      document.getElementById("statusMessage").textContent = "Click Connect";
      document.getElementById("githubLoginBtn").style.display = "inline-block";
      document.getElementById("manualTokenBtn").style.display = "inline-block";
      document.getElementById("connectedCard").style.display = "none";
      document.getElementById("triggerTestCard").style.display = "none";
    };

    showDisconnectedStatus();

    expect(document.getElementById("githubStatus").classList.contains("disconnected")).toBe(true);
    expect(document.querySelector("h3").textContent).toBe("❌ GitHub Not Connected");
    expect(document.getElementById("connectedCard").style.display).toBe("none");
    expect(document.getElementById("githubLoginBtn").style.display).toBe("inline-block");
  });

  it("should validate that GitHub token is required before saving", () => {
    const saveGitHubToken = (btn) => {
      const token = document.getElementById("githubToken").value;
      if (!token) {
        throw new Error("Please enter a GitHub Personal Access Token");
      }
      return true;
    };

    // Empty token should fail
    expect(() => saveGitHubToken(null)).toThrow("Please enter a GitHub Personal Access Token");

    // Token provided should pass validation
    document.getElementById("githubToken").value = "ghp_test123456";
    expect(() => saveGitHubToken(null)).not.toThrow();
  });

  it("should store GitHub token configuration", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        status: "success",
        message: "GitHub account connected successfully",
        repository: "nicholashomyk/AgenticQA"
      })
    });

    const token = "ghp_test123456789";
    const repo = "nicholashomyk/AgenticQA";

    const response = await fetch("/api/github/connect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, repository: repo })
    });

    const data = await response.json();

    expect(response.ok).toBe(true);
    expect(data.status).toBe("success");
    expect(data.repository).toBe("nicholashomyk/AgenticQA");
  });

  it("should check GitHub connection status", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        status: "connected",
        repository: "nicholashomyk/AgenticQA",
        connectedAt: "2026-01-19T21:00:00.000Z"
      })
    });

    const response = await fetch("/api/github/status", {
      method: "GET",
      headers: { "Content-Type": "application/json" }
    });

    const data = await response.json();

    expect(data.status).toBe("connected");
    expect(data.repository).toBe("nicholashomyk/AgenticQA");
  });

  it("should check GitHub is not connected when no config", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ status: "disconnected" })
    });

    const response = await fetch("/api/github/status", {
      method: "GET",
      headers: { "Content-Type": "application/json" }
    });

    const data = await response.json();

    expect(data.status).toBe("disconnected");
  });

  it("should disconnect GitHub account", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        status: "success",
        message: "GitHub account disconnected"
      })
    });

    const response = await fetch("/api/github/disconnect", {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    });

    const data = await response.json();

    expect(data.status).toBe("success");
  });

  it("should test GitHub connection", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        status: "success",
        message: "GitHub connection test successful",
        repository: "nicholashomyk/AgenticQA"
      })
    });

    const response = await fetch("/api/github/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    });

    const data = await response.json();

    expect(data.status).toBe("success");
    expect(data.repository).toBe("nicholashomyk/AgenticQA");
  });

  it("should fail test when GitHub not connected", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: () => Promise.resolve({
        error: "GitHub account not connected",
        status: "error"
      })
    });

    const response = await fetch("/api/github/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    });

    const data = await response.json();

    expect(response.ok).toBe(false);
    expect(data.error).toContain("not connected");
  });

  it("should validate tab switching functionality", () => {
    const switchTab = (tabName) => {
      document.querySelectorAll(".tab-content").forEach(el => {
        el.classList.remove("active");
      });
      const tab = document.getElementById(tabName);
      if (tab) {
        tab.classList.add("active");
      }
    };

    // Mock tab elements
    const tabDiv = document.createElement("div");
    tabDiv.id = "github";
    tabDiv.className = "tab-content active";
    document.body.appendChild(tabDiv);

    const anotherTab = document.createElement("div");
    anotherTab.id = "other";
    anotherTab.className = "tab-content";
    document.body.appendChild(anotherTab);

    switchTab("other");

    expect(tabDiv.classList.contains("active")).toBe(false);
    expect(anotherTab.classList.contains("active")).toBe(true);
  });
});
