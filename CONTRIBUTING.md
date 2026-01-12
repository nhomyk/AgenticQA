# Contributing to AgenticQA

Thank you for your interest in contributing! We appreciate your help in making AgenticQA better.

## Code of Conduct

Please review our [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before contributing.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/AgenticQA.git
   cd AgenticQA
   ```

3. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

4. **Install dependencies**:
   ```bash
   npm install
   ```

## Development Workflow

### Code Style

We use ESLint for code formatting. Before committing, ensure your code passes linting:

```bash
npx eslint . --ext .js --fix
```

### Running Tests

Run all tests before submitting a pull request:

```bash
npm run test:vitest -- --run        # Unit tests
npm run test:playwright -- --ui      # Browser tests (visual)
npm run test:cypress -- --headless   # E2E tests
npx jest --coverage                  # Jest with coverage
```

### Security

- Never commit secrets or API keys
- Use environment variables (see `.env.example`)
- Run security checks:
  ```bash
  npm audit
  npm run security:check
  ```

## Commit Guidelines

Use conventional commits for clear history:

```
feat: add new feature
fix: fix a bug
docs: documentation changes
style: code style changes (ESLint)
test: add or update tests
chore: build process, dependencies
security: security improvements
```

Example:
```bash
git commit -m "feat: add oauth2 support to authentication"
```

## Pull Request Process

1. **Update documentation** if you're changing functionality
2. **Add tests** for new features or bug fixes
3. **Ensure all tests pass** locally
4. **Update CHANGELOG.md** with your changes
5. **Write a clear PR description** explaining:
   - What problem does this solve?
   - How does it work?
   - What tests cover this?

## Reporting Issues

### Security Issues

Please report security vulnerabilities privately to the maintainers. See [SECURITY.md](SECURITY.md).

### Bug Reports

Include:
- OS/Node.js version
- Steps to reproduce
- Expected vs actual behavior
- Error logs/screenshots

### Feature Requests

Describe:
- The use case
- The proposed solution
- Any alternatives you've considered

## Project Structure

```
├── public/              # Frontend files (HTML, CSS, JS)
├── cypress/             # E2E tests
├── unit-tests/          # Jest unit tests
├── playwright-tests/    # Playwright browser tests
├── vitest-tests/        # Vitest tests
├── .github/workflows/   # CI/CD configuration
├── server.js            # Main Express app
├── agentic_sre_engineer.js  # SRE automation agent
└── eslint.config.js     # ESLint rules
```

## Development Tips

- **Local testing**: Use `node server.js` to start the dev server
- **Debug mode**: Add `console.log()` statements and check browser console
- **Coverage**: Run `npm run test:jest -- --coverage` to see test coverage

## Becoming a Maintainer

Active contributors who consistently submit high-quality PRs may be invited to become maintainers.

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT).

Thank you for contributing to AgenticQA! 🚀
