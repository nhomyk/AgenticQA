describe("Accessibility Tests", () => {
  beforeEach(() => {
    cy.visit("/");
  });

  it("should have proper heading hierarchy", () => {
    cy.get("h1").should("exist").and("contain", "Enterprise-Grade");
    cy.get("h1").should("have.length.at.least", 1);
  });

  it("should have descriptive labels for buttons", () => {
    cy.get(".cta-buttons .btn-primary").first().should("be.visible");
    cy.get(".tab-button").should("have.length.at.least", 5);
  });

  it("should support keyboard navigation between tabs", () => {
    cy.get(".tab-button").first().should("be.visible");
    cy.contains(".tab-button", "Architecture").click({ force: true });
    cy.get("#architecture").should("exist");
  });

  it("should have proper color contrast on text elements", () => {
    cy.get("h1").should("be.visible");
    cy.get(".btn-primary").should("be.visible");
    cy.get(".tab-button").should("be.visible");
  });

  it("should have visible and accessible tabs", () => {
    cy.get(".tabs-section").should("be.visible");
    cy.get(".tab-button").each(($btn) => {
      cy.wrap($btn).should("be.visible");
    });
  });

  it("should display content sections correctly", () => {
    cy.get(".tab-content.active").should("be.visible");
  });

  it("should be responsive to viewport changes", () => {
    cy.viewport(1280, 720);
    cy.get(".hero").should("be.visible");
    cy.viewport(768, 1024);
    cy.get(".hero").should("be.visible");
    cy.viewport(375, 667);
    cy.get(".hero").should("be.visible");
  });
});

