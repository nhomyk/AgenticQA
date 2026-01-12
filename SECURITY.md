# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in AgenticQA, please email the maintainers privately instead of using the public issue tracker.

**DO NOT** create public GitHub issues for suspected security vulnerabilities.

### Process

1. Email details to: nickhomyk@gmail.com with subject "AgenticQA Security Vulnerability"
2. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if available)

3. You will receive acknowledgment within 48 hours
4. We will work to fix and release a patch promptly
5. Public disclosure will be coordinated with you

## Security Best Practices

### For Users

- Keep Node.js and npm dependencies up to date
- Use environment variables for sensitive data (API keys, tokens)
- Enable HTTPS in production
- Use strong authentication credentials
- Monitor your instance for suspicious activity
- Review security logs regularly

### For Contributors

- Never commit secrets or credentials
- Use `.env.example` for configuration templates
- Validate and sanitize all user inputs
- Use parameterized queries to prevent injection attacks
- Keep dependencies updated
- Run security audits: `npm audit`
- Follow OWASP best practices

## Security Testing

Our CI/CD pipeline includes:

- **Dependency scanning** via `npm audit`
- **Secrets scanning** to detect exposed credentials
- **SAST analysis** for code vulnerabilities
- **ESLint security rules** for code quality
- **Unit test coverage** to catch logic errors

### Running Security Checks Locally

```bash
# Check for vulnerable dependencies
npm audit

# Run custom security check
npm run security:check

# Lint code for security issues
npx eslint . --ext .js
```

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | ✅ Yes (latest)   |
| < 1.0   | ❌ No              |

## Security Updates

Security patches are released as needed. Users are encouraged to update promptly.

## Third-Party Packages

We carefully vet all dependencies. If you find a vulnerability in a dependency, please report it to:
1. The package maintainers directly
2. npm Security: https://www.npmjs.com/advisories
3. Us, so we can assess and update

## Compliance

AgenticQA aims to follow:
- OWASP Top 10 guidelines
- CWE Top 25 prevention
- Best practices for secure coding

## Questions?

If you have security-related questions, please email us at nickhomyk@gmail.com.
