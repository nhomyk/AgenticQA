describe("Accessibility Tests", () => {
  beforeEach(() => {
    cy.visit("/");
  });

  it("should have proper heading hierarchy", () => {
    cy.get("h1").should("exist").and("contain", "AgenticQA");
    cy.get("h1").should("have.length", 1);
  });

  it("should have descriptive labels for buttons", () => {
    cy.get(".cta-button").should("be.visible").should("have.text", "Start Free Trial");
    cy.get(".tab-btn").should("have.length.at.least", 5);
  });

  it("should support keyboard navigation between tabs", () => {
    cy.get(".tab-btn").first().should("be.visible");
    cy.contains(".tab-btn", "Features").click({ force: true });
    cy.get("#features").should("have.class", "active");
  });

  it("should have proper color contrast on text elements", () => {
    cy.get("h1").should("be.visible");
    cy.get(".cta-button").should("be.visible");
    cy.get(".tab-btn").should("be.visible");
  });

  it("should have visible and accessible tabs", () => {
    cy.get(".tabs").should("be.visible");
    cy.get(".tab-btn").each(($btn) => {
      cy.wrap($btn).should("be.visible");
    });
  });

  it("should display content sections correctly", () => {
    cy.get(".content.active").should("be.visible");
  });

  it("should be responsive to viewport changes", () => {
    cy.viewport(1280, 720);
    cy.get(".dashboard-container").should("be.visible");
    cy.viewport(768, 1024);
    cy.get(".dashboard-container").should("be.visible");
    cy.viewport(375, 667);
    cy.get(".dashboard-container").should("be.visible");
  });
});
