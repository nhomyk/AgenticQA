# Compliance & Security Quick Reference

## 🚀 Quick Start

```bash
# Check accessibility
npm run test:pa11y

# Check security
npm run audit

# Run both
npm run test:compliance

# Run full compliance scanner with suggestions
node pa11y-security-scanner.js
```

## ♿ Common Accessibility Issues

| Issue | Command | Fix |
|-------|---------|-----|
| **Image alt text** | `grep -r '<img' public/ \| grep -v alt` | Add `alt="description"` |
| **Color contrast** | Use WebAIM tool | Adjust colors to 4.5:1 ratio |
| **Form labels** | Check HTML | Use `<label for="id">` |
| **Heading hierarchy** | `grep -E '^<h[1-6]' public/` | Use h1→h2→h3 order |
| **Focus indicators** | Test Tab key | Add CSS `:focus { outline: 2px solid; }` |
| **ARIA labels** | Screen reader test | Add `aria-label` or `aria-describedby` |

## 🔐 Security Fixes

```bash
# View vulnerabilities
npm audit

# Auto-fix dependencies
npm audit fix

# Audit report for review
npm audit --json > audit-report.json

# Update specific package
npm install package-name@latest
```

## 📋 Pre-Commit Checklist

```bash
# Run before git commit
npm run lint
npm run test
npm run test:pa11y
npm audit

# OR run all at once
npm run test:compliance
```

## 🔗 Links

- [Full Guide](./COMPLIANCE_SECURITY_GUIDE.md)
- [WCAG 2.1](https://www.w3.org/WAI/WCAG21/quickref/)
- [Pa11y Docs](https://www.pa11y.org/)
- [npm audit](https://docs.npmjs.com/cli/v8/commands/npm-audit)

## ⚠️ Rules

1. **Must pass**: Pa11y on main branch (will be enforced in v1.0)
2. **Must review**: Security vulnerabilities before merge
3. **Should fix**: Accessibility warnings (WCAG AA target)
4. **Should update**: Dependencies monthly

## 🆘 Help

- Check logs: `cat /tmp/server.log`
- Server running? `curl http://localhost:3000`
- More help: See [COMPLIANCE_SECURITY_GUIDE.md](./COMPLIANCE_SECURITY_GUIDE.md)

