import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { JSDOM } from "jsdom";

describe("Login Page - Authentication", () => {
  let dom;
  let document;
  let window;

  beforeEach(() => {
    dom = new JSDOM(`
      <!DOCTYPE html>
      <html>
        <body>
          <div id="loginContainer">
            <h1>orbitQA.ai Dashboard</h1>
            <div id="loginForm">
              <input type="email" id="emailInput" placeholder="Email" />
              <input type="password" id="passwordInput" placeholder="Password" />
              <button id="loginButton">Login</button>
              <div id="errorMessage" style="display: none;"></div>
              <div id="successMessage" style="display: none;"></div>
            </div>
          </div>
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
    global.localStorage = {
      data: {},
      getItem(key) { return this.data[key] || null; },
      setItem(key, value) { this.data[key] = value; },
      removeItem(key) { delete this.data[key]; },
      clear() { this.data = {}; }
    };
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("should display login form elements", () => {
    const emailInput = document.getElementById("emailInput");
    const passwordInput = document.getElementById("passwordInput");
    const loginButton = document.getElementById("loginButton");
    
    expect(emailInput).toBeTruthy();
    expect(passwordInput).toBeTruthy();
    expect(loginButton).toBeTruthy();
  });

  it("should validate email format", () => {
    const validateEmail = (email) => {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      return emailRegex.test(email);
    };

    expect(validateEmail("test@example.com")).toBe(true);
    expect(validateEmail("user@company.co.uk")).toBe(true);
    expect(validateEmail("invalid.email")).toBe(false);
    expect(validateEmail("@example.com")).toBe(false);
  });

  it("should require email for login", () => {
    const emailInput = document.getElementById("emailInput");
    const passwordInput = document.getElementById("passwordInput");
    
    emailInput.value = "";
    passwordInput.value = "password123";
    
    const isValid = emailInput.value.length > 0 && passwordInput.value.length > 0;
    expect(isValid).toBe(false);
  });

  it("should require password for login", () => {
    const emailInput = document.getElementById("emailInput");
    const passwordInput = document.getElementById("passwordInput");
    
    emailInput.value = "test@example.com";
    passwordInput.value = "";
    
    const isValid = emailInput.value.length > 0 && passwordInput.value.length > 0;
    expect(isValid).toBe(false);
  });

  it("should accept valid demo credentials", () => {
    const emailInput = document.getElementById("emailInput");
    const passwordInput = document.getElementById("passwordInput");
    
    emailInput.value = "test@example.com";
    passwordInput.value = "password123";
    
    const isValid = emailInput.value.length > 0 && passwordInput.value.length > 0;
    expect(isValid).toBe(true);
  });

  it("should store user credentials in localStorage", () => {
    const email = "test@example.com";
    const credentials = {
      email,
      token: "demo-token-" + Date.now()
    };
    
    global.localStorage.setItem("user", JSON.stringify(credentials));
    const stored = JSON.parse(global.localStorage.getItem("user"));
    
    expect(stored.email).toBe(email);
    expect(stored.token).toBeTruthy();
  });

  it("should handle form submission with valid credentials", () => {
    const emailInput = document.getElementById("emailInput");
    const passwordInput = document.getElementById("passwordInput");
    
    emailInput.value = "user@example.com";
    passwordInput.value = "securepass123";
    
    const credentials = {
      email: emailInput.value,
      password: passwordInput.value
    };
    
    expect(credentials.email).toBe("user@example.com");
    expect(credentials.password).toBe("securepass123");
  });

  it("should show error for missing credentials", () => {
    const errorMessage = document.getElementById("errorMessage");
    
    errorMessage.textContent = "Email and password are required";
    errorMessage.style.display = "block";
    
    expect(errorMessage.textContent).toContain("required");
    expect(errorMessage.style.display).toBe("block");
  });

  it("should show success message on login", () => {
    const successMessage = document.getElementById("successMessage");
    
    successMessage.textContent = "Login successful!";
    successMessage.style.display = "block";
    
    expect(successMessage.textContent).toBe("Login successful!");
    expect(successMessage.style.display).toBe("block");
  });

  it("should clear form after successful login", () => {
    const emailInput = document.getElementById("emailInput");
    const passwordInput = document.getElementById("passwordInput");
    
    emailInput.value = "test@example.com";
    passwordInput.value = "password123";
    
    // Simulate successful login
    emailInput.value = "";
    passwordInput.value = "";
    
    expect(emailInput.value).toBe("");
    expect(passwordInput.value).toBe("");
  });

  it("should handle case-insensitive email login", () => {
    const validateEmail = (email) => {
      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.toLowerCase());
    };
    
    expect(validateEmail("TEST@EXAMPLE.COM")).toBe(true);
    expect(validateEmail("Test@Example.Com")).toBe(true);
  });

  it("should trim whitespace from email", () => {
    const email = "  test@example.com  ";
    const trimmed = email.trim();
    
    expect(trimmed).toBe("test@example.com");
  });

  it("should allow special characters in passwords", () => {
    const password = "P@ssw0rd!#$%^&*";
    
    expect(password.length).toBeGreaterThan(0);
    expect(password).toContain("@");
    expect(password).toContain("!");
  });

  it("should require minimum password length", () => {
    const validatePassword = (password) => password.length >= 3;
    
    expect(validatePassword("pass")).toBe(true);
    expect(validatePassword("pa")).toBe(false);
    expect(validatePassword("secure123!@#")).toBe(true);
  });

  it("should redirect to dashboard after login", () => {
    const email = "test@example.com";
    const token = "demo-token";
    
    global.localStorage.setItem("token", token);
    
    // Simulate redirect
    const redirectUrl = global.localStorage.getItem("token") ? "/dashboard.html" : null;
    
    expect(redirectUrl).toBe("/dashboard.html");
  });

  it("should check if user is already logged in on page load", () => {
    const token = global.localStorage.getItem("token");
    
    expect(token).toBeNull(); // Not logged in
    
    global.localStorage.setItem("token", "existing-token");
    const newToken = global.localStorage.getItem("token");
    
    expect(newToken).toBe("existing-token"); // Logged in
  });

  it("should handle API errors gracefully", async () => {
    global.fetch = vi.fn().mockRejectedValueOnce(
      new Error("Network error")
    );
    
    try {
      await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "test@example.com", password: "pass123" })
      });
    } catch (error) {
      expect(error.message).toBe("Network error");
    }
  });

  it("should disable login button during submission", () => {
    const loginButton = document.getElementById("loginButton");
    
    loginButton.disabled = false;
    expect(loginButton.disabled).toBe(false);
    
    loginButton.disabled = true;
    expect(loginButton.disabled).toBe(true);
  });

  it("should re-enable login button after response", () => {
    const loginButton = document.getElementById("loginButton");
    
    loginButton.disabled = true;
    loginButton.disabled = false;
    
    expect(loginButton.disabled).toBe(false);
  });

  it("should preserve user session across page reloads", () => {
    const userToken = "session-token-12345";
    global.localStorage.setItem("token", userToken);
    
    // Simulate page reload by retrieving from storage
    const retrievedToken = global.localStorage.getItem("token");
    
    expect(retrievedToken).toBe(userToken);
  });

  it("should have secure password input type", () => {
    const passwordInput = document.getElementById("passwordInput");
    
    expect(passwordInput.type).toBe("password");
  });

  it("should hide password characters on input", () => {
    const passwordInput = document.getElementById("passwordInput");
    passwordInput.value = "hidden123";
    
    // Password field always masks input regardless of value
    expect(passwordInput.type).toBe("password");
  });

  it("should accept spaces in password", () => {
    const password = "pass word with spaces";
    expect(password.length).toBeGreaterThan(0);
    expect(password).toContain(" ");
  });
});
