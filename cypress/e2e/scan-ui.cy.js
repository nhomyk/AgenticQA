describe("AgenticQA - UI Tests", () => {
  it("should load the homepage", () => {
    cy.get("h1").should("contain", "AgenticQA");
  });

  it("should have all result boxes visible", () => {
    // Click on scanner tab to view scanner section
    cy.contains(".tab-btn", "Scanner").click();
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
    cy.contains(".tab-btn", "Scanner").click();
    cy.get("#urlInput").should("be.visible").should("have.attr", "placeholder", "https://example.com");
    cy.get("#scanBtn").should("be.visible").should("contain", "Scan");
  });

  it("should display all headings", () => {
    cy.get("h1").should("contain", "AgenticQA");
    cy.contains("h2", "Scan Any Website").should("exist");
    cy.contains("h3", "Recommendations").should("exist");
    cy.contains("h3", "Scan Results").should("exist");
    cy.contains("h3", "Test Code Examples").should("exist");
  });

  it("should have correct placeholder text in textareas", () => {
    cy.contains(".tab-btn", "Scanner").click();
    cy.get("#results").should("have.attr", "placeholder").and("include", "will appear here");
    cy.get("#testcases").should("have.attr", "placeholder").and("include", "test cases");
    cy.get("#performance").should("have.attr", "placeholder").and("include", "Performance");
    cy.get("#apis").should("have.attr", "placeholder").and("include", "API");
    // Verify framework tabs exist as divs (they will be populated after scan)
    cy.get("#playwright").should("exist").and("have.class", "tab-pane");
    cy.get("#cypress").should("exist").and("have.class", "tab-pane");
    cy.get("#vitest").should("exist").and("have.class", "tab-pane");
  });

  it("should show error message if scanning without URL", () => {
    cy.contains(".tab-btn", "Scanner").click();
    cy.get("#scanBtn").click();
    cy.on("window:alert", (text) => {
      expect(text).to.include("URL");
    });
  });

  it("should have readonly textareas", () => {
    cy.contains(".tab-btn", "Scanner").click();
    cy.get("#results").should("have.attr", "readonly");
    cy.get("#testcases").should("have.attr", "readonly");
    cy.get("#performance").should("have.attr", "readonly");
    cy.get("#apis").should("have.attr", "readonly");
  });

  it("should display detected technologies after scanning a URL", () => {
    cy.contains(".tab-btn", "Scanner").click();
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

  it("should switch between test framework tabs", () => {
    cy.contains(".tab-btn", "Scanner").click();
    cy.get('[data-tab="playwright"]').should("have.class", "active");
    cy.get('[data-tab="cypress"]').click();
    cy.get('[data-tab="cypress"]').should("have.class", "active");
    cy.get('[data-tab="vitest"]').click();
    cy.get('[data-tab="vitest"]').should("have.class", "active");
  });

});
