import { describe, it, expect } from "vitest";
import { mapIssue } from "../debug_scan.js";

describe("debug_scan.js", () => {
  it("should export mapIssue function", () => {
    expect(typeof mapIssue).toBe("function");
  });

  it("should map issues correctly in debug context", () => {
    const warning = mapIssue("warning", "Console warning", "warning-recommendation");
    expect(warning.type).toBe("warning");
    expect(warning.message).toBe("Console warning");
    expect(warning.recommendation).toBe("warning-recommendation");
  });

  it("should handle different issue types", () => {
    const errorIssue = mapIssue("error", "Error message", "error-rec");
    const warningIssue = mapIssue("warning", "Warning message", "warning-rec");
    const logIssue = mapIssue("log", "Log message", "log-rec");

    expect(errorIssue.type).toBe("error");
    expect(warningIssue.type).toBe("warning");
    expect(logIssue.type).toBe("log");
  });
});
