# Quick Start - Running Tests

## One-Liner Test Commands

### Run All Tests Once
```bash
npm run test:vitest:run
```

### Watch Mode (Auto-rerun on changes)
```bash
npm run test:vitest
```

### Run Specific Test File
```bash
npx vitest --run vitest-tests/login.test.mjs
npx vitest --run vitest-tests/dashboard.test.mjs
npx vitest --run vitest-tests/settings.test.mjs
```

### Generate Coverage Report
```bash
npx vitest --run --coverage
```

## Test Files Summary

| File | Tests | Focus |
|------|-------|-------|
| `login.test.mjs` | 25 | Form validation, credentials, session persistence |
| `dashboard.test.mjs` | 20 | Pipeline selection, triggering, GitHub checks |
| `settings.test.mjs` | 13 | GitHub PAT connection, token storage, test connection |

**Total: 58 Comprehensive Tests**

## What Gets Tested

### Login Page ✅
- Email and password validation
- Demo mode credentials (any email/password accepted)
- Token storage in localStorage
- Session persistence
- Redirect to dashboard
- Error handling

### Dashboard Page ✅
- Pipeline type selection (full, tests, security, compliance)
- Branch validation
- GitHub connection verification before launch
- Pipeline triggering with proper naming
- localStorage session management
- API error handling

### Settings Page ✅
- GitHub PAT connection
- Token validation and storage (full + masked versions)
- Connection status checking
- Test connection with modal feedback
- Account disconnection
- Tab switching

## Expected Test Output

When all tests pass, you'll see:

```
✓ vitest-tests/login.test.mjs (25)
✓ vitest-tests/dashboard.test.mjs (20)
✓ vitest-tests/settings.test.mjs (13)

Test Files  3 passed (3)
     Tests  58 passed (58)
```

## Troubleshooting

### Error: vitest not found
```bash
npm install
```

### Error: JSDOM environment not available
Update `vitest.config.mjs` to have:
```javascript
environment: "jsdom",
```

### Tests hanging or timeout
Kill any running servers:
```bash
pkill node
npm run test:vitest:run
```

## Integration with Development

### Before Committing Code
```bash
npm run test:vitest:run
```

### During Development (watch mode)
```bash
npm run test:vitest
```

### In CI/CD Pipeline
Tests run automatically when you push to GitHub via GitHub Actions.

## Adding New Tests

1. Create new test in appropriate file under `vitest-tests/`
2. Follow existing test patterns
3. Use mocked fetch and localStorage
4. Run tests: `npm run test:vitest:run`

## Key Testing Features

✅ **No Real GitHub Connections**: All GitHub API calls are mocked  
✅ **No Backend Required**: Tests run with JSDOM simulation  
✅ **Isolated Tests**: Each test is independent  
✅ **Fast Execution**: Full test suite runs in seconds  
✅ **Clear Failures**: Specific error messages for debugging  

## Next Steps

- [ ] Run: `npm run test:vitest:run` to verify all tests pass
- [ ] Review coverage: `npx vitest --run --coverage`
- [ ] Commit: `git add . && git commit -m "Add comprehensive test suite"`
- [ ] Push: `git push origin main`
