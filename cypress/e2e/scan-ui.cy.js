describe("orbitQA.ai Dashboard - UI Tests", () => {
  beforeEach(() => {
    cy.visit("/");
  });

  it("should load the homepage with correct title", () => {
    cy.get("h1").should("contain", "Enterprise-Grade");
    cy.get(".hero-description").should("contain", "orbitQA.ai");
  });

  it("should display all navigation tabs", () => {
    cy.contains(".tab-button", "Overview").should("be.visible");
    cy.contains(".tab-button", "Who We Are").should("be.visible");
    cy.contains(".tab-button", "Architecture").should("be.visible");
    cy.contains(".tab-button", "Compliance").should("be.visible");
    cy.contains(".tab-button", "Testing").should("be.visible");
  });

  it("should have Overview tab active by default", () => {
    cy.get("#overview").should("have.class", "active");
  });

  it("should switch to Features tab when clicked", () => {
    cy.contains(".tab-button", "Who We Are").click();
    cy.get("#who-we-are").should("have.class", "active");
    cy.get("#overview").should("not.have.class", "active");
  });

  it("should switch to Use Cases tab and show content", () => {
    cy.contains(".tab-button", "Architecture").click();
    cy.get("#architecture").should("have.class", "active");
  });

  it("should switch to Technical tab and show architecture", () => {
    cy.contains(".tab-button", "Compliance").click();
    cy.get("#compliance").should("have.class", "active");
  });

  it("should switch to Pricing tab and display pricing cards", () => {
    cy.contains(".tab-button", "Testing").click();
    cy.get("#testing").should("have.class", "active");
  });

  it("should display CTA button in hero section", () => {
    cy.get(".cta-buttons .btn-primary").first().should("be.visible");
  });

  it("should have proper responsive layout", () => {
    cy.get(".hero").should("be.visible");
    cy.get(".tabs-section").should("be.visible");
    cy.get(".tab-content.active").should("be.visible");
  });

  it("should display use case cards with hover effects", () => {
    cy.get(".feature-card").should("have.length.at.least", 3);
    cy.get(".feature-card").first().should("be.visible");
  });

  it("should have correct feature descriptions", () => {
    cy.contains(".tab-button", "Who We Are").click();
    cy.contains("h3").should("have.length.at.least", 1);
  });
});

