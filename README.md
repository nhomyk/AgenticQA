
# Agentic QA Engineer


Agentic QA Engineer is a lightweight Node.js service and web UI that scans webpages for:

- Console errors and page exceptions
- Failed network requests
- Common DOM and accessibility issues (missing image alts, broken images, missing form labels, bad anchors, heading order problems)
- Automatically generated recommended test cases (positive and negative)
- Simulated performance results (JMeter-like summary)
- **APIs Used:** Displays up to 10 API calls (fetch/XHR) detected on the scanned page
- **Playwright Example:** Shows a Playwright test code snippet for the first recommended test case
- **Cypress Example:** Shows a Cypress test code snippet for the first recommended test case

## Setup

1. **Install dependencies:**
	 ```bash
	 npm install
	 ```

2. **Run the server:**
	 ```bash
	 npm start
	 ```

3. **Open the web UI:**
	 Go to [http://localhost:3000](http://localhost:3000) in your browser. Enter a URL to scan.


## Features

- **Scan Results:**
	- Console errors, page exceptions, failed requests, and DOM/accessibility issues (max 25 items per scan)
- **Recommended Test Cases:**
	- 10 positive and 10 negative test cases are generated for the scanned page
- **Performance Results:**
	- Simulated JMeter-like summary: total/failed requests, resource count, average response time, page load time, throughput, and top resources
- **APIs Used:**
	- Displays up to 10 API calls (fetch/XHR) detected on the scanned page
- **Playwright Example:**
	- Shows a Playwright test code snippet for the first recommended test case
- **Cypress Example:**
	- Shows a Cypress test code snippet for the first recommended test case

## API

- `POST /scan` — Accepts `{ url: "https://example.com" }` and returns scan results, test cases, and performance summary as JSON

## Development & Testing

### Comprehensive Test Coverage

The Agentic QA Engineer project maintains **59+ tests** across 5 testing frameworks to ensure reliability, maintainability, and code quality. Every language and component is thoroughly tested.

#### Test Suite Overview

| Framework | Tests | Purpose | Coverage |
|-----------|-------|---------|----------|
| **ESLint** | Continuous | Static code analysis and linting | All `.js` files |
| **Jest** | 5 | Unit tests for Node.js code | Server functions, utilities |
| **Vitest** | 18 | Fast unit tests with coverage | Server, browser, HTML/CSS, integration |
| **Playwright** | 7+ | Modern E2E browser automation | UI interactions, cross-browser |
| **Cypress** | 22 | Comprehensive E2E testing | UI validation, accessibility, integration |

**Total: 59+ automated tests ensuring no errors are missed**

### Thorough Unit Testing Across All Languages

Each programming language in the project is validated with dedicated unit tests:

#### JavaScript (Node.js) - Backend
- **Functions Tested:** `normalizeUrl()`, `mapIssue()`, API scanning logic
- **Frameworks:** Jest, Vitest
- **Tests:** 8 dedicated tests
- **Focus:** URL normalization, issue mapping, error handling

#### JavaScript (Browser) - Frontend
- **Functions Tested:** `renderResults()`, `generatePlaywrightExample()`, `generateCypressExample()`
- **Frameworks:** Jest, Vitest
- **Tests:** 6 dedicated tests
- **Focus:** Code generation, result rendering, template logic

#### HTML/CSS Structure
- **Validation:** Semantic HTML structure, CSS styling rules, responsive design
- **Frameworks:** Vitest, Cypress
- **Tests:** 19+ dedicated tests
- **Focus:** DOM structure, layout consistency, accessibility compliance

#### Integration Testing
- **Coverage:** Full scan workflow, URL handling, test case generation, API detection, performance metrics
- **Frameworks:** Vitest
- **Tests:** 6 dedicated tests
- **Focus:** End-to-end logic flow and data transformations

### Thorough UI Testing with Multiple Tools

The project uses **3 complementary E2E testing frameworks** to catch UI issues from different angles:

#### Playwright Tests (`playwright-tests/`)
- **Focus:** Modern browser automation and cross-browser compatibility
- **Tests:** 7+ UI validation tests
- **Coverage:** Element visibility, placeholder text, readonly attributes, form validation
- **Advantage:** Lightweight, fast, good for rapid UI validation

#### Cypress Tests (`cypress/e2e/scan-ui.cy.js`)
- **Focus:** User-centric testing and interactive flows
- **Tests:** 7 comprehensive UI tests
- **Coverage:** Homepage loading, result boxes, input validation, readonly states, error handling
- **Advantage:** Great developer experience, interactive debugging

#### Accessibility & Integration Tests (`cypress/e2e/accessibility.cy.js`)
- **Focus:** Accessibility compliance and full workflow integration
- **Tests:** 15 comprehensive tests including:
  - Heading hierarchy and semantic structure
  - Form element labels and placeholders
  - Keyboard navigation support
  - Responsive viewport testing (mobile, tablet, desktop)
  - Color contrast validation
  - Complete scan flow integration
  - UI state consistency across interactions
- **Advantage:** Ensures usability for all users, catches real-world issues

**Why Multiple Frameworks?**
- **Playwright** catches structural issues fast
- **Cypress (UI)** validates user interactions thoroughly
- **Cypress (Accessibility)** ensures compliance and real-world workflows
- Combined approach ensures no UI bugs, accessibility issues, or user experience problems

### Code Quality & Maintainability

#### Linting
```bash
npx eslint . --ext .js
```
- **Status:** 0 errors, 6 warnings
- **Coverage:** All JavaScript files including server, browser, tests
- **Standard:** ESLint v9+ with flat config

#### Unit Testing with Coverage
```bash
npx jest --coverage
```
- **Test Count:** 5 comprehensive unit tests
- **Coverage:** Server functions, utilities, browser logic
- **Metrics:** Statement, branch, function, and line coverage

#### Fast Unit Testing
```bash
npm run test:vitest
```
- **Test Count:** 18 tests (4 test files)
- **Speed:** <300ms execution
- **Coverage:** Includes HTML/CSS validation and integration tests

#### Modern E2E Testing
```bash
npx playwright test
```
- **Test Count:** 7+ tests
- **Execution:** <2 seconds
- **Coverage:** UI element validation, form interactions

#### Comprehensive E2E Testing
```bash
npm run test:cypress
```
- **Test Count:** 22 tests (2 spec files)
- **Execution:** <15 seconds
- **Coverage:** UI validation, accessibility, integration flows

### Automated CI/CD Pipeline

GitHub Actions runs **5 parallel jobs** on every push and pull request:

```yaml
jobs:
  1. lint - ESLint validation
  2. unit-test - Jest with coverage
  3. test-vitest - Vitest with coverage
  4. test-playwright - Playwright E2E tests
  5. test-cypress - Cypress E2E + accessibility tests
```

**All jobs must pass** before code can be merged, ensuring:
- ✅ No style violations
- ✅ No broken unit tests
- ✅ No UI regressions
- ✅ No accessibility issues
- ✅ No integration failures

### Running All Tests

```bash
# Run all tests at once
npm run test:vitest -- --run && \
npx jest && \
npx playwright test && \
npm run test:cypress && \
npx eslint . --ext .js
```

### Test Maintenance & Usability

The test suite is designed for **ease of maintenance** and **maximum usability**:

1. **Clear Test Organization**
   - Unit tests in `unit-tests/` and `vitest-tests/`
   - E2E tests in `playwright-tests/` and `cypress/e2e/`
   - Each test file focuses on a specific component

2. **Descriptive Test Names**
   - Tests clearly state what is being validated
   - Easy to identify failing tests and their purpose
   - Self-documenting test code

3. **Comprehensive Error Messages**
   - Test failures include expected vs actual values
   - Line numbers and stack traces for debugging
   - Coverage reports for identifying gaps

4. **Low Maintenance Overhead**
   - Minimal configuration required
   - Tests run in parallel for speed
   - Clear separation of concerns

### Linting

```bash
npx eslint . --ext .js
```

### Unit Tests (Jest)
```bash
npx jest --coverage
```

### Unit Tests (Vitest)
```bash
npm run test:vitest -- --run --coverage
```

### Playwright Tests
```bash
npx playwright test
```

### Cypress Tests
```bash
npm run test:cypress
```

## Notes & Limitations

- Results are limited to 25 items per scan
- Puppeteer downloads a Chromium binary on first install (requires network access)
- Some advanced accessibility or performance issues may not be detected
- For troubleshooting Puppeteer launch issues, ensure Chrome/Chromium is available and accessible

## License

MIT
