# SDET Quick Start Guide

## For Developers: Automatic Test Generation on Every Change

### TL;DR
- **Every UI change automatically gets tests**
- **Tests run before your commit**
- **High-priority gaps block commits** (use `--no-verify` to skip)
- **You focus on features, SDET handles testing**

---

## Normal Development Workflow

### 1. Make Your UI Changes
```bash
# Edit HTML/JS files as usual
# Make UI changes to public/settings.html
# Or add new components
```

### 2. Commit Your Changes
```bash
git add public/settings.html
git commit -m "fix: clear form fields on cancel"

# 🧪 SDET AUTOMATICALLY RUNS:
# ✓ Detects the UI change
# ✓ Extracts all UI elements
# ✓ Identifies test gaps
# ✓ Generates test suite
# ✓ Runs tests
# ✓ Reports coverage

# Output shows:
# ✅ Tests generated: ui-tests/settings.cy.js
# 🔴 High Priority gaps: 1
# 🟡 Medium Priority gaps: 1
```

### 3. Review Test Report
```bash
cat .sdet-test-report.json

# Shows:
# {
#   "timestamp": "2026-01-19T...",
#   "detectedChanges": 1,
#   "generatedTests": 1,
#   "testGaps": [
#     { "element": "Forms", "severity": "HIGH", "issue": "..." }
#   ]
# }
```

### 4. Optional: Review Generated Tests
```bash
# See what tests were generated
cat ui-tests/settings.cy.js

# The tests cover:
# ✓ Form field clearing
# ✓ Button clicks
# ✓ Modal show/hide
# ✓ Accessibility
# ✓ User workflows
```

---

## For Different Scenarios

### Scenario 1: Small Bug Fix (Like the Settings Form)
```bash
# Make your fix
# vim public/settings.html

git add public/settings.html
git commit -m "fix: clear form fields when canceling"

# ✅ Commit succeeds
# ✅ Tests generated for form behavior
# ✅ Tests automatically run
```

### Scenario 2: New Button or Form
```bash
# Add new element to settings.html
git add public/settings.html

git commit -m "feat: add export settings button"

# ⚠️ High priority gaps detected
# Tests needed for: Button click handler

# Two options:
# A) Add tests before committing:
#    cat ui-tests/settings.cy.js
#    # Review the generated tests
#    # Run: npm test
#    # Commit normally

# B) Force commit (use with caution):
#    git commit --no-verify
```

### Scenario 3: Complex Feature
```bash
# Building something with multiple elements
git add public/dashboard.html

# SDET detects:
# - Multiple buttons
# - New form
# - New modal
# - Event listeners

# Generates comprehensive test suite
# Review tests, add custom assertions if needed

git commit --allow-empty -m "tests: add comprehensive dashboard tests"
npm test  # Run tests
git push
```

---

## Commands at a Glance

```bash
# Auto-run via pre-commit hook (happens automatically)
git commit -m "your change"

# Manual: Run SDET now
npm run sdet

# Manual: Full test suite (SDET + all tests)
npm run test:all

# Manual: Continuous monitoring (great for TDD)
npm run sdet:monitor

# View last report
cat .sdet-test-report.json

# See generated tests for a page
cat ui-tests/settings.cy.js

# Run just the generated tests
npm run test:cypress -- ui-tests/settings.cy.js
```

---

## What Gets Tested Automatically

### For Each Button
```
✓ Is it visible?
✓ Is it enabled?
✓ What happens when clicked?
✓ Does it have accessibility labels?
```

### For Each Form
```
✓ Are all fields present?
✓ Can you type in inputs?
✓ Does submission work?
✓ Are errors displayed?
```

### For Each Modal
```
✓ Can you open it?
✓ Can you close it (via button)?
✓ Can you close it (via escape)?
✓ Does focus management work?
```

### For Every Page
```
✓ No accessibility violations (WCAG 2.1 AA)
✓ Proper heading structure
✓ All form labels present
✓ Keyboard navigation works
```

---

## Handling Test Gaps

### High Priority Gaps (🔴)
These are blocking - they represent important UI interactions not yet tested.

**What to do:**
```bash
# Option 1: Review and accept the generated tests
cat ui-tests/settings.cy.js
# If tests look good, commit anyway

# Option 2: Add custom tests
# Edit ui-tests/settings.cy.js
# Add domain-specific test cases
# Run: npm run test:cypress

# Option 3: Force commit (last resort)
git commit --no-verify
# But then manually run tests:
npm run test:cypress
```

### Medium Priority Gaps (🟡)
These are nice-to-have test coverage improvements.

**What to do:**
```bash
# Address them when convenient:
# - During code review
# - At end of sprint
# - Or skip if time-constrained
```

### Low Priority Gaps (🟢)
These are minor and can be addressed anytime.

**What to do:**
```bash
# Usually skip unless you're in a testing mood
# Or add incrementally as part of other work
```

---

## Real Example: Settings Form Fix

### Step 1: Make the fix
```javascript
// In public/settings.html
function hideManualTokenTab() {
  // Clear form fields when hiding
  document.getElementById('githubToken').value = '';
  document.getElementById('githubRepo').value = '';
  document.getElementById('manualTokenCard').style.display = 'none';
}
```

### Step 2: Commit
```bash
git add public/settings.html
git commit -m "fix: clear form fields when canceling GitHub token setup"
```

### Step 3: SDET Runs
```
📍 PHASE 1: Detecting Changed UI Files
   ✅ Found 1 HTML file(s)
      → public/settings.html

📍 Extracting UI elements from: public/settings.html
   ✅ Buttons: 2 (Save Token, Cancel)
   ✅ Inputs: 2 (Token, Repository)

📍 Identifying test gaps for: public/settings.html
   🔴 Forms (1 items)
      Issue: Form submission, validation

📍 Generating test suite for: public/settings.html
   ✅ Generated: ui-tests/settings.cy.js

✅ Tests Generated: 1
✅ Test Gaps Identified: 1 high-priority
```

### Step 4: Push Confidently
```bash
git push

# All tests have run, form fields are tested
# You know the fix works correctly
# Team can see exactly what was tested
```

---

## Troubleshooting

### "Tests failed after SDET generation"
```bash
# Check what failed
npm run test:cypress

# Two cases:
# 1. Your code has a bug - fix it
# 2. The generated test is wrong - update it
#    Edit ui-tests/page-name.cy.js
#    Change assertions to match your implementation
#    Run: npm run test:cypress
#    Commit when fixed
```

### "Pre-commit hook not running"
```bash
# Make hook executable
chmod +x .git/hooks/pre-commit

# Test it manually
bash .git/hooks/pre-commit

# Then try commit again
git commit -m "your message"
```

### "I want to skip SDET for this commit"
```bash
# Use --no-verify flag
git commit --no-verify -m "WIP: testing something"

# But still run tests manually after
npm run test:all
```

---

## Key Principles

1. **Every UI change gets tested**
   - You don't have to remember to write tests
   - They're generated automatically

2. **Tests run before commit**
   - No broken tests reach the repository
   - High confidence in code quality

3. **Focus on features, not testing**
   - SDET handles the test automation
   - You focus on great UI/UX

4. **Incrementally improve coverage**
   - Start with generated tests
   - Customize them for your needs
   - Add domain-specific tests over time

---

## Common Questions

**Q: Do I have to use the generated tests?**
A: No! They're suggestions. Feel free to customize, replace, or ignore them. But high-priority gaps block commits for a reason.

**Q: Can I disable SDET?**
A: Yes, use `git commit --no-verify`, but you lose automatic test generation.

**Q: How often should I run tests?**
A: Every commit (automatic via hook). For active development, use `npm run sdet:monitor` for continuous testing.

**Q: What if the generated test doesn't match my code?**
A: Update either the test (if your code is correct) or the code (if the test reveals a bug).

**Q: Is SDET perfect?**
A: No. It generates smart baseline tests, but you should customize them for your specific use cases.

---

## Next Steps

1. **Try it:** Make a small UI change and commit
2. **Review:** Check the generated tests in `ui-tests/`
3. **Customize:** Add your own test cases as needed
4. **Commit:** Push with confidence knowing tests run automatically

**That's it! Your UI is now tested on every change. 🎉**
