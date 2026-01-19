# SDET UI Change Detection & Automated Testing System

## Overview

The SDET (Software Development Engineer in Test) UI Change Detection system automatically detects UI changes, identifies test gaps, and generates comprehensive test suites. This ensures that **every piece of new code is tested** before deployment.

**Key Principle:** No UI change should ever reach production without corresponding test coverage.

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────┐
│  Pre-Commit Hook (.git/hooks/pre-commit)                │
│  Triggered automatically before git commit              │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  SDET UI Change Detector (sdet-ui-change-detector.js)   │
│                                                           │
│  1. Detect Changed UI Files                              │
│  2. Extract UI Elements & Properties                     │
│  3. Identify Test Gaps                                   │
│  4. Generate Test Suites                                 │
│  5. Run Tests                                            │
│  6. Generate Coverage Report                             │
└──────────────────┬──────────────────────────────────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   ┌────────┐ ┌────────┐ ┌─────────┐
   │ HTML   │ │   JS   │ │ Reports │
   │ Tests  │ │ Tests  │ │ & Logs  │
   └────────┘ └────────┘ └─────────┘
```

---

## How It Works

### Phase 1: Detect Changed UI Files
- Monitors `git diff` for UI file changes (`.html`, `.js` in public)
- Identifies which files were modified or staged

### Phase 2: Extract UI Elements
For each changed HTML file, extracts:
- **Buttons** with click handlers, labels, accessibility attributes
- **Form inputs** with types, placeholders, validation
- **Modals/dialogs** for user interaction testing
- **Alerts** for display and dismissal testing
- **Event listeners** for keyboard, focus, and custom events
- **Conditional rendering** for state-driven UI

### Phase 3: Identify Test Gaps
For each extracted element, identifies:
- ✗ Missing E2E tests for interactions
- ✗ Missing unit tests for logic
- ✗ Missing accessibility tests
- ✗ Missing error handling tests
- ✗ Missing keyboard navigation tests

### Phase 4: Generate Test Suites
Automatically creates Cypress E2E tests for:
- Element visibility and presence
- Click handlers and button interactions
- Form submission and validation
- Modal open/close and escape key handling
- Alert display and dismissal
- Conditional rendering and state changes
- Event listener functionality
- Keyboard navigation and focus management
- Accessibility compliance (WCAG 2.1 AA)

### Phase 5: Run Tests
Executes:
- Jest unit tests
- Vitest tests
- Cypress E2E tests
- Accessibility audits

### Phase 6: Generate Report
Creates `.sdet-test-report.json` with:
- Files detected
- Tests generated
- Test gaps identified (by severity)
- Coverage summary

---

## Quick Start

### 1. Automatic Detection (Pre-Commit)

When you attempt to commit UI changes, SDET runs automatically:

```bash
git add public/settings.html
git commit -m "fix: UI issue"

# This triggers:
# ✓ SDET detection
# ✓ Test generation
# ✓ Test execution
# ✓ Coverage report
```

### 2. Manual Detection

Run SDET at any time:

```bash
npm run sdet
```

**Output:**
```
🧪 SDET UI CHANGE DETECTOR - AUTO TEST GENERATION

📍 PHASE 1: Detecting Changed UI Files
   ✅ Found 1 HTML file(s)
      → public/settings.html

📍 Extracting UI elements from: public/settings.html
   ✅ Buttons: 5
   ✅ Inputs: 3
   ✅ Forms: 2
   ✅ Modals: 1
   ✅ Alerts: 2
   ✅ Event Listeners: 8
   ✅ Conditional Rendering: 3

📍 Identifying test gaps for: public/settings.html
   🔴 Buttons (5 items)
      Issue: Click handlers need E2E testing
   🟡 Forms (2 items)
      Issue: Form submission, validation, and error handling
   🟢 Alerts (2 items)
      Issue: Alert display, auto-dismiss, close buttons

📍 Generating test suite for: public/settings.html
   ✅ Generated: ui-tests/settings.cy.js

📍 PHASE 6: Running Generated Tests
   🧪 Running Cypress E2E tests...
   🧪 Running Jest unit tests...

📍 PHASE 7: Generating Test Coverage Report
   ✅ Test Coverage Report:
      Detected Changes: 1
      Generated Tests: 1
      Test Gaps: 3
      High Priority: 1
      Medium Priority: 1
      Low Priority: 1
```

### 3. Full Test Suite

Run complete testing including compliance:

```bash
npm run test:all

# Runs:
# ✓ SDET detection and generation
# ✓ Unit tests (Jest + Vitest)
# ✓ E2E tests (Cypress)
# ✓ Compliance checks (Pa11y + npm audit)
```

### 4. Watch Mode

Monitor UI changes continuously:

```bash
npm run sdet:monitor

# Runs SDET every 3 seconds when files in public/ or unit-tests/ change
# Perfect for TDD workflow
```

---

## Test Coverage Details

### Buttons & Click Handlers
```javascript
// Generated test covers:
✓ Button visibility and enabled state
✓ Click functionality
✓ Event handler execution
✓ State changes after click
✓ Accessibility (aria-label, type attribute)
✓ Disabled state handling
```

### Forms & Validation
```javascript
// Generated test covers:
✓ Form rendering with all inputs
✓ Input field presence and types
✓ Form submission
✓ Validation error display
✓ Error message content
✓ Field-level error handling
```

### Modals & Dialogs
```javascript
// Generated test covers:
✓ Modal visibility and rendering
✓ Close button functionality
✓ Escape key handling
✓ Backdrop click handling
✓ Focus management
✓ Keyboard navigation
```

### Alerts & Notifications
```javascript
// Generated test covers:
✓ Alert display and visibility
✓ Close button presence
✓ Alert dismissal
✓ Auto-dismiss if applicable
✓ Multiple alert handling
```

### Event Listeners
```javascript
// Generated test covers:
✓ Click events
✓ Keyboard events (typing, arrows, enter)
✓ Focus and blur events
✓ Change events on inputs
✓ Custom events
```

### Accessibility
```javascript
// Generated test covers:
✓ WCAG 2.1 AA violations (via Axe)
✓ Heading hierarchy
✓ Form label associations
✓ Keyboard navigation (Tab key)
✓ Focus indicators
✓ ARIA attributes
✓ Color contrast
```

---

## Integration with Development Workflow

### Before Making Changes
```bash
# Check current test status
npm run test:all
```

### While Developing
```bash
# Run SDET monitor in one terminal
npm run sdet:monitor

# Develop in another terminal
# Tests regenerate automatically on file changes
```

### Before Committing
```bash
# SDET runs automatically via pre-commit hook
git add public/settings.html
git commit -m "feature: new UI element"

# If high-priority gaps exist, review and add tests:
# - Tests are generated in ui-tests/
# - Run cypress to verify: npm run test:cypress
# - Force commit if necessary: git commit --no-verify
```

### Before Pushing
```bash
# Run full test suite
npm run test:all

# Review coverage report
cat .sdet-test-report.json
```

---

## Understanding Test Reports

### `.sdet-test-report.json`

```json
{
  "timestamp": "2026-01-19T...",
  "detectedChanges": 3,
  "generatedTests": 4,
  "testGaps": 7,
  "summary": {
    "highPriority": 2,
    "mediumPriority": 3,
    "lowPriority": 2
  }
}
```

**Interpretation:**
- **High Priority (🔴):** Critical user interactions not tested
  - Action: Add tests before committing
- **Medium Priority (🟡):** Important features with partial coverage
  - Action: Add tests if time permits
- **Low Priority (🟢):** Nice-to-have test coverage
  - Action: Can be addressed later

---

## Generated Test Files

### E2E Tests (ui-tests/)
Location: `ui-tests/{page-name}.cy.js`

**Example:** `ui-tests/settings.cy.js`

```javascript
describe('settings - UI Components', () => {
  beforeEach(() => {
    cy.visit('/settings.html');
  });

  describe('Button Interactions', () => {
    it('should handle button click for "Save Token"', () => {
      cy.contains('button', 'Save Token').should('be.visible');
      cy.contains('button', 'Save Token').should('be.enabled');
      cy.contains('button', 'Save Token').click();
    });
  });

  describe('Form Interactions', () => {
    it('should render form "tokenForm" with all inputs', () => {
      cy.get('form#tokenForm').should('exist').and('be.visible');
    });
  });

  describe('Accessibility', () => {
    it('should not have any detectable accessibility violations', () => {
      cy.injectAxe();
      cy.checkA11y();
    });
  });
});
```

### Unit Tests (unit-tests/)
Location: `unit-tests/{module-name}.test.js`

```javascript
describe('settingsModule', () => {
  describe('saveGitHubToken()', () => {
    it('should exist and be callable', () => {
      expect(typeof saveGitHubToken).toBe('function');
    });

    it('should handle normal inputs', () => {
      // Test with valid token
    });

    it('should handle edge cases', () => {
      // Test with empty/invalid inputs
    });

    it('should handle errors gracefully', () => {
      // Test error scenarios
    });
  });
});
```

---

## Best Practices

### 1. Commit Messages Matter
```bash
# ❌ Bad
git commit -m "fix stuff"

# ✅ Good - Tests will be more targeted
git commit -m "fix: clear form fields when canceling GitHub token setup"
```

### 2. Review Generated Tests
```bash
# After SDET generates tests, review them:
cat ui-tests/settings.cy.js

# Customize for your specific use cases
# Add domain-specific assertions
```

### 3. Run Tests Frequently
```bash
# During development
npm run sdet:monitor

# Before committing
npm run test:all

# Before pushing
npm run test:cypress
```

### 4. Fix Accessibility Issues Early
```bash
# SDET automatically checks accessibility
# Review accessibility violations in test output
# Fix in your HTML/CSS immediately

# Example accessibility violations:
# - Missing alt text for images
# - Poor color contrast
# - Missing form labels
# - Improper heading hierarchy
```

### 5. Handle Test Gaps

When SDET identifies gaps:

```javascript
// ❌ Don't ignore high-priority gaps
// ✅ Do address them:

// 1. Review the generated test
cat ui-tests/new-feature.cy.js

// 2. Run the test to see what's missing
npm run test:cypress -- ui-tests/new-feature.cy.js

// 3. Update your code or the test assertions
// 4. Verify tests pass
npm test

// 5. Commit with confidence
git commit -m "feature: new feature with full test coverage"
```

---

## Troubleshooting

### SDET Not Detecting Changes
```bash
# Ensure you're in a git repository
git status

# Check if files are actually modified
git diff --name-only

# Run SDET manually to debug
npm run sdet
```

### Tests Failing After Generation
```bash
# Review the generated test
cat ui-tests/page-name.cy.js

# Run just that test to see the error
npm run test:cypress -- ui-tests/page-name.cy.js

# Fix either:
# 1. The test expectations (if your implementation is correct)
# 2. Your implementation (if the test expectations are correct)
```

### Missing Test Coverage
```bash
# Generate a coverage report
npm run coverage

# Review areas with <80% coverage
# Add tests for uncovered lines in ui-tests/ or unit-tests/
```

### Pre-Commit Hook Not Running
```bash
# Make hook executable
chmod +x .git/hooks/pre-commit

# Verify it works
bash .git/hooks/pre-commit

# Or force commit to skip
git commit --no-verify
```

---

## Key Metrics

### Coverage Targets
- **Overall:** ≥85% code coverage
- **UI Components:** ≥90% coverage
- **Critical Functions:** 100% coverage
- **Accessibility:** 0 WCAG violations

### Performance Targets
- **SDET Detection:** <5 seconds
- **Test Generation:** <10 seconds
- **Full Test Suite:** <2 minutes
- **Accessibility Scan:** <10 seconds

---

## Advanced Usage

### Custom Test Configuration
```javascript
// In sdet-ui-change-detector.js
// Modify generateButtonTests() for custom button testing logic
// Add domain-specific assertions
// Customize element selectors
```

### Integration with CI/CD
```yaml
# .github/workflows/test.yml
name: Tests

on: [pull_request, push]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm install
      - run: npm run test:all
      - run: npm run sdet
```

### Slack Notifications
```javascript
// Add to sdet-ui-change-detector.js to notify team
const notifySlack = (report) => {
  const message = `
    🧪 SDET Report:
    • Changes: ${report.detectedChanges}
    • Tests: ${report.generatedTests}
    • Gaps: ${report.testGaps.length}
    • High Priority: ${report.summary.highPriority}
  `;
  // Send to Slack webhook
};
```

---

## Support & Maintenance

### Updating Test Generation
Edit `sdet-ui-change-detector.js` to:
- Add new element types to detect
- Customize test templates
- Add framework-specific tests (React, Vue, etc.)

### Reporting Issues
```bash
# Check logs
tail -f .sdet-test-report.json

# Debug SDET
npm run sdet -- --debug

# Review git hooks
cat .git/hooks/pre-commit
```

---

## Summary

The SDET UI Change Detection system ensures:

✅ **Every UI change is detected**
✅ **Every change gets test coverage**
✅ **Every test is executed before commit**
✅ **Every deployment is tested**
✅ **No untested code reaches production**

This reinforces quality, speeds up development, and catches bugs early.

**Remember:** Tests that don't exist can't catch bugs. This system makes sure tests always exist.
