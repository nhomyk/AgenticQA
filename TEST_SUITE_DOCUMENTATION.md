# Comprehensive Test Suite Documentation

## Overview
The AgenticQA SaaS dashboard now includes comprehensive test coverage for all critical user journeys and functionality. The test suite uses **Vitest** with **JSDOM** for DOM testing, providing complete validation of login, dashboard, and settings pages.

## Test Files Created

### 1. **login.test.mjs** - Login Page Tests
Location: `vitest-tests/login.test.mjs`
Total Tests: 25

**Test Coverage:**
- Form validation and display
- Email format validation
- Required field validation (email & password)
- Valid demo credentials acceptance
- localStorage credential storage
- Form submission handling
- Error and success message display
- Form clearing after login
- Case-insensitive email handling
- Email whitespace trimming
- Special characters in passwords
- Minimum password length validation
- Dashboard redirect after login
- Session persistence across page reloads
- API error handling
- Login button state management (disable/enable)
- Password input type security (masked characters)
- Password input accepting spaces

**Key Features:**
- Tests demo mode login (accepts any email/password combo)
- Validates localStorage token persistence
- Tests session recovery on page reload
- Verifies password field masking for security

### 2. **dashboard.test.mjs** - Pipeline Management Tests
Location: `vitest-tests/dashboard.test.mjs`
Total Tests: 20

**Test Coverage:**
- Pipeline type selection (full, tests, security, compliance)
- Branch input validation
- GitHub connection status checking
- Prevention of launch when GitHub disconnected
- Full pipeline triggering
- Security pipeline triggering
- Compliance pipeline triggering
- Invalid pipeline type rejection
- Branch name format validation (valid and invalid patterns)
- Pipeline name inclusion in request
- GitHub API error handling (403, 503)
- Missing token error handling
- User authentication token storage
- User info storage in localStorage
- localStorage clearing on logout

**Key Features:**
- Tests all pipeline types with proper naming convention
- Validates branch name regex patterns
- Tests GitHub API integration with mocked fetch
- Verifies error messages for authentication failures
- Tests localStorage session management

### 3. **settings.test.mjs** - GitHub Integration Tests
Location: `vitest-tests/settings.test.mjs`
Total Tests: 13

**Test Coverage:**
- GitHub status display (connected/disconnected)
- GitHub token validation
- Token storage (full and masked versions)
- GitHub connection status checking
- Test connection API calls
- Connection success feedback
- Account disconnection
- Tab switching between GitHub and Pipeline tabs
- Modal popup display on successful connection test
- API endpoint responses with proper mocking
- Error handling for failed connections
- UI state updates on connection/disconnection

**Key Features:**
- Tests both connected and disconnected states
- Validates token masking for security display
- Verifies modal popup feedback mechanism
- Tests tab switching between different dashboard sections

## Test Architecture

### Framework: Vitest
- **Config File:** `vitest.config.mjs`
- **Environment:** jsdom (for DOM testing)
- **Testing Pattern:** Describe/It (BDD style)
- **Setup:** JSDOM for DOM simulation

### Key Testing Utilities

#### JSDOM DOM Simulation
```javascript
const dom = new JSDOM(html, { url: "http://localhost:3000" });
const document = dom.window.document;
const window = dom.window;
```

#### Mock Fetch Implementation
```javascript
global.fetch = vi.fn().mockResolvedValueOnce({
  ok: true,
  json: () => Promise.resolve({ /* response data */ })
});
```

#### Mock localStorage
```javascript
global.localStorage = {
  data: {},
  getItem(key) { return this.data[key] || null; },
  setItem(key, value) { this.data[key] = value; },
  removeItem(key) { delete this.data[key]; },
  clear() { this.data = {}; }
};
```

## Running Tests

### Run All Tests
```bash
npm run test:vitest:run
```

### Run Tests in Watch Mode
```bash
npm run test:vitest
```

### Run Specific Test File
```bash
npx vitest --run vitest-tests/login.test.mjs
```

### Run with Coverage Report
```bash
npx vitest --run --coverage
```

## GitHub Integration Test Coverage

### API Endpoints Tested (Mocked)

**1. GET /api/github/status**
- Returns: `{ status: "connected"|"disconnected", repository: "..." }`
- Tested in: dashboard, settings tests

**2. POST /api/github/connect**
- Accepts: `{ token, repository }`
- Returns: `{ status: "success"|"error", message: "..." }`
- Tested in: settings tests

**3. POST /api/github/test**
- Accepts: `{ token, repository }`
- Returns: `{ status: "success"|"error", message: "..." }`
- Tested in: settings tests

**4. POST /api/github/disconnect**
- Returns: `{ status: "success", message: "..." }`
- Tested in: settings tests

**5. POST /api/trigger-workflow**
- Accepts: `{ pipelineType, branch }`
- Returns: `{ status: "success"|"error", message: "..." }`
- Tested in: dashboard tests

## Test Data & Scenarios

### Valid Test Credentials
- Email: `test@example.com`
- Password: `password123` (or any value in demo mode)
- Repository: `nicholashomyk/AgenticQA`

### Pipeline Types Tested
- `full` - Full CI/CD Pipeline
- `tests` - Test Suite
- `security` - Security Scan
- `compliance` - Compliance Check

### Valid Branch Names
- `main`
- `develop`
- `feature/test`
- `release-1.0`
- `fix_bug`

### Invalid Branch Names
- `main@`
- `test#branch`
- `feature$`
- `release!`

## Error Scenarios Tested

### GitHub Connection Errors
1. **GitHub Not Connected**: Shows error, prevents pipeline launch
2. **Missing Token**: Returns 503 error message
3. **Invalid Token**: Returns 403 authentication error
4. **Repository Not Found**: Handles API errors gracefully

### Form Validation Errors
1. **Missing Email**: Form validation fails
2. **Invalid Email Format**: Regex validation rejects
3. **Missing Password**: Form validation fails
4. **Empty Token**: Token field validation fails

### API Errors
1. Network errors handled with try-catch
2. Fetch failures logged appropriately
3. 4xx/5xx responses handled with user-friendly messages

## GitHub API Security Features Tested

### Token Security
- ✅ Token masked for display (`token.substring(0,10) + '***'`)
- ✅ Full token stored separately (`fullToken`) for API calls
- ✅ Token never logged in full form
- ✅ Token cleared on disconnection

### Connection Validation
- ✅ GitHub connection verified before pipeline launch
- ✅ Invalid tokens rejected by API validation
- ✅ Test connection fails gracefully
- ✅ Error messages don't leak sensitive data

## Continuous Integration

### Local Testing
```bash
# Run before commits
npm run test:vitest:run
```

### CI Pipeline (GitHub Actions)
The test suite integrates into the CD pipeline:
```bash
# In ci.yml
- name: Run Tests
  run: npm run test:vitest:run
```

## Test Maintenance

### Adding New Tests
1. Create test in appropriate `.test.mjs` file
2. Follow existing patterns:
   - Use `describe` for test suites
   - Use `it` for individual tests
   - Mock external dependencies (fetch, localStorage)
   - Clean up with `afterEach` hook

### Updating Tests for Code Changes
When dashboard/settings/login pages are updated:
1. Run full test suite: `npm run test:vitest:run`
2. Fix failing tests to match new behavior
3. Add new tests for new features
4. Document changes in this file

### Mocking GitHub API Changes
If GitHub API responses change:
1. Update mock response objects in tests
2. Update `server.js` endpoint implementations
3. Verify tests still pass
4. Document API changes

## Coverage Report

### Current Test Coverage
- **Login Page**: 25 tests covering all user paths
- **Dashboard Page**: 20 tests covering pipeline management
- **Settings Page**: 13 tests covering GitHub integration
- **Total**: 58 comprehensive tests

### Uncovered Scenarios (Future)
- [ ] Multi-user concurrent pipeline launches
- [ ] Network timeout handling
- [ ] Large file uploads in compliance scans
- [ ] Database persistence (if added in future)
- [ ] Real GitHub API integration tests

## Troubleshooting

### Tests Won't Run
**Problem**: `vitest: command not found`
**Solution**: 
```bash
npm install
npm run test:vitest:run
```

### JSDOM Tests Fail
**Problem**: DOM methods throw errors
**Solution**: Ensure `vitest.config.mjs` has `environment: "jsdom"`

### Fetch Mocks Not Working
**Problem**: Tests making real HTTP requests
**Solution**: Verify `global.fetch = vi.fn()` called in `beforeEach`

### localStorage Tests Fail
**Problem**: Persistence not working
**Solution**: Use mock localStorage object, not real browser storage

## Best Practices for Testing

### 1. Mock External Dependencies
- Always mock `fetch` for API calls
- Mock `localStorage` for browser storage
- Use `vi.fn()` for spies and mocks

### 2. Isolate Tests
- Use `beforeEach` to reset mocks
- Use `afterEach` to clean up
- Don't depend on test execution order

### 3. Test User Behavior
- Test what users see and do
- Test validation rules
- Test error messages
- Test state changes

### 4. Keep Tests Maintainable
- One assertion per test when possible
- Clear test names describing behavior
- Comments for complex test logic
- Reusable helper functions for common patterns

### 5. Test Edge Cases
- Empty inputs
- Special characters
- Very long inputs
- Network errors
- API errors

## Conclusion

This comprehensive test suite provides:
- ✅ Full coverage of critical user journeys
- ✅ GitHub integration validation without real connections
- ✅ Security best practices testing
- ✅ Error scenario handling
- ✅ Foundation for continuous integration

The test suite can be extended as new features are added to the dashboard, ensuring reliability and preventing regressions as the platform evolves.
