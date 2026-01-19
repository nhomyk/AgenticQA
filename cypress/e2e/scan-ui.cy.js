describe("orbitQA.ai Dashboard - UI Tests", () => {
  beforeEach(() => {
    cy.visit("/");
  });

  it("should load the homepage with correct title", () => {
    cy.get("h1").should("contain", "Enterprise-Grade");
    cy.get(".hero-description").should("contain", "orbitQA.ai");
  });

  it("should display all navigation tabs", () => {
    cy.contains(".tab-btn", "Overview").should("be.visible");
    cy.contains(".tab-btn", "Features").should("be.visible");
    cy.contains(".tab-btn", "Use Cases").should("be.visible");
    cy.contains(".tab-btn", "Technical").should("be.visible");
    cy.contains(".tab-btn", "Pricing").should("be.visible");
  });

  it("should have Overview tab active by default", () => {
    cy.get("#overview").should("have.class", "active");
  });

  it("should switch to Features tab when clicked", () => {
    cy.contains(".tab-btn", "Features").click();
    cy.get("#features").should("have.class", "active");
    cy.get("#overview").should("not.have.class", "active");
  });

  it("should switch to Use Cases tab and show content", () => {
    cy.contains(".tab-btn", "Use Cases").click();
    cy.get("#use-cases").should("have.class", "active");
    cy.contains("h2", "How AgenticQA Solves Real Problems").should("be.visible");
    cy.contains("h3", "Codebase Knowledge").should("be.visible");
    cy.contains("h3", "Code Generation").should("be.visible");
    cy.contains("h3", "Code Review").should("be.visible");
    cy.contains("h3", "Code Deployment").should("be.visible");
    cy.contains("h3", "Testing All Aspects of Code").should("be.visible");
    cy.contains("h3", "UI Functionality Testing").should("be.visible");
  });

  it("should switch to Technical tab and show architecture", () => {
    cy.contains(".tab-btn", "Technical").click();
    cy.get("#technical").should("have.class", "active");
    cy.contains("h2", "Technical Architecture").should("be.visible");
    cy.contains("h3", "Why AgenticQA is Technically Impressive").should("be.visible");
  });

  it("should switch to Pricing tab and display pricing cards", () => {
    cy.contains(".tab-btn", "Pricing").click();
    cy.get("#pricing").should("have.class", "active");
    cy.contains("h2", "Simple, Transparent Pricing").should("be.visible");
    cy.contains("h3", "Starter").should("be.visible");
    cy.contains("h3", "Professional").should("be.visible");
    cy.contains("h3", "Enterprise").should("be.visible");
  });

  it("should display CTA button in hero section", () => {
    cy.get(".cta-button").should("contain", "Start Free Trial");
  });

  it("should have proper responsive layout", () => {
    cy.get(".dashboard-container").should("be.visible");
    cy.get(".tabs").should("be.visible");
    cy.get(".content.active").should("be.visible");
  });

  it("should display use case cards with hover effects", () => {
    cy.contains(".tab-btn", "Use Cases").click();
    cy.get(".use-case-card").should("have.length", 6);
    cy.get(".use-case-card").first().should("be.visible");
  });

  it("should have correct feature descriptions", () => {
    cy.contains(".tab-btn", "Features").click();
    cy.contains("h3", "Standard Features").should("be.visible");
    cy.contains("h3", "Premium Features").should("be.visible");
  });
});
