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
    cy.contains("h3", "AI Generated Test Cases for your site").should("exist");
  });

  it("should have correct placeholder text in textareas", () => {
    cy.get("#results").should("have.attr", "placeholder").and("include", "Results will appear here");
    cy.get("#testcases").should("have.attr", "placeholder").and("include", "test cases");
    cy.get("#performance").should("have.attr", "placeholder").and("include", "JMeter-like performance");
    cy.get("#apis").should("have.attr", "placeholder").and("include", "APIs");
    // Verify framework tabs exist as divs (they will be populated after scan)
    cy.get("#playwright").should("exist").and("have.class", "tab-pane");
    cy.get("#cypress").should("exist").and("have.class", "tab-pane");
    cy.get("#vitest").should("exist").and("have.class", "tab-pane");
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
  });

  it("should display detected technologies after scanning a URL", () => {
    cy.get("#urlInput").clear().type("https://example.com");
    cy.get("#scanBtn").click();
    cy.get("#technologies", { timeout: 30000 })
      .should("be.visible")
      .should($el => {
        const val = $el.val();
        console.log('Technologies box value:', val);
        expect(val.trim().length).to.be.greaterThan(0);
      });
  });

});
