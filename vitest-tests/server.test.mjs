import { describe, it, expect } from "vitest";
import { normalizeUrl, mapIssue } from "../server.js";

describe("server.js", () => {
  it("should normalize URLs by adding http protocol if missing", () => {
    expect(normalizeUrl("example.com")).toBe("http://example.com");
    expect(normalizeUrl("https://example.com")).toBe("https://example.com");
    expect(normalizeUrl("http://example.com")).toBe("http://example.com");
  });

  it("should map issues with type, message, and recommendation", () => {
    const issue = mapIssue("error", "Test error message", "test-recommendation");
    expect(issue.type).toBe("error");
    expect(issue.message).toBe("Test error message");
    expect(issue.recommendation).toBe("test-recommendation");
  });
});
