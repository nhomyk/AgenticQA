  it("should display detected technologies after scanning a URL", () => {
    cy.get("#urlInput").clear().type("https://example.com");
    cy.get("#scanBtn").click();
    cy.get("#technologies", { timeout: 15000 }).should("be.visible");
    cy.get("#technologies").invoke("val").then(val => {
      // Should always show the header
      expect(val).to.include("Technologies Detected");
      // Should show either a technology or 'None detected'
      expect(val.trim().length).to.be.greaterThan(0);
    });
  });
describe("Agentic QA Engineer - UI Tests", () => {
  it("should load the homepage", () => {
    cy.get("h1").should("contain", "Agentic QA Engineer");
  });

  it("should have all result boxes visible", () => {
    cy.get("#results").should("be.visible");
    cy.get("#testcases").should("be.visible");
    cy.get("#performance").should("be.visible");
    cy.get("#apis").should("be.visible");
    // Test example tabs exist (Playwright is active by default)
    cy.get("#playwright").should("exist").and("have.class", "active");
    cy.get("#cypress").should("exist");
    cy.get("#vitest").should("exist");
  });

  it("should have proper input and button", () => {
    cy.get("#urlInput").should("be.visible").should("have.attr", "placeholder", "https://example.com");
    cy.get("#scanBtn").should("be.visible").should("contain", "Scan");
  });

  it("should display all headings", () => {
    cy.get("h1").should("contain", "Agentic QA Engineer");
    cy.get("h3").should("have.length.at.least", 6);
    // First h3 is now "AgenticQA Engineer's Recommendations"
    cy.get("h3").first().should("contain", "AgenticQA Engineer's Recommendations");
    // Verify other key sections exist
    cy.contains("h3", "Scan Results").should("exist");
    cy.contains("h3", "Test Framework Examples").should("exist");
  });

  it("should have correct placeholder text in textareas", () => {
    cy.get("#results").should("have.attr", "placeholder").and("include", "Results will appear here");
    cy.get("#testcases").should("have.attr", "placeholder").and("include", "test cases");
    cy.get("#performance").should("have.attr", "placeholder").and("include", "JMeter-like performance");
    cy.get("#apis").should("have.attr", "placeholder").and("include", "APIs");
    cy.get("#playwright").should("have.attr", "placeholder").and("include", "Playwright");
    cy.get("#cypress").should("have.attr", "placeholder").and("include", "Cypress");
    cy.get("#vitest").should("have.attr", "placeholder").and("include", "Vitest");
  });

  it("should show error message if scanning without URL", () => {
    cy.get("#scanBtn").click();
    cy.on("window:alert", (text) => {
      expect(text).to.include("URL");
    });
  });

  it("should have readonly textareas", () => {
    cy.get("#results").should("have.attr", "readonly");
    cy.get("#testcases").should("have.attr", "readonly");
    cy.get("#performance").should("have.attr", "readonly");
    cy.get("#apis").should("have.attr", "readonly");
    cy.get("#playwright").should("have.attr", "readonly");
    cy.get("#cypress").should("have.attr", "readonly");
  });

});
