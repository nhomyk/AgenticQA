# Compliance & Security Integration Guide

## Overview

This guide explains how AgenticQA integrates accessibility compliance (Pa11y) and security vulnerability scanning (npm audit) into the development workflow.

## 🎯 Compliance Checks

### 1. Accessibility Compliance (Pa11y)

**What is Pa11y?**
- Automated accessibility testing tool
- Tests against WCAG 2.1 Level AA standards
- Identifies issues preventing access for users with disabilities

**Configuration**: [.pa11yci.json](.pa11yci.json)

#### Running Accessibility Tests

```bash
# Run Pa11y accessibility scan
npm run test:pa11y

# Run with detailed output
npm run test:pa11y -- --reporter json

# Test specific pages
npm run test:pa11y -- --urls http://localhost:3000,http://localhost:3000/scan
```

#### Common Accessibility Issues & Fixes

| Issue | WCAG Criterion | Fix |
|-------|---|---|
| Missing image alt text | 1.1.1 Non-text Content | Add meaningful `alt` attribute to all images |
| Poor color contrast | 1.4.3 Contrast (Minimum) | Ensure text-to-background ratio ≥ 4.5:1 |
| Form labels not associated | 1.3.1 Info and Relationships | Use `<label for="id">` or wrap input |
| Missing heading hierarchy | 1.3.1 Info and Relationships | Use h1 → h2 → h3 in order |
| Keyboard not usable | 2.1.1 Keyboard | Test Tab navigation, ensure focus visible |
| Missing ARIA labels | 4.1.2 Name, Role, Value | Add `aria-label` or `aria-describedby` |
| No focus indicator | 2.4.7 Focus Visible | CSS: `outline: 2px solid blue;` |

#### Remediation Examples

**Missing Alt Text**
```html
<!-- ❌ Bad -->
<img src="logo.png" />

<!-- ✅ Good -->
<img src="logo.png" alt="AgenticQA Logo" />
```

**Color Contrast**
```css
/* ❌ Bad - Contrast ratio 2.1:1 */
color: #777;
background: #fff;

/* ✅ Good - Contrast ratio 4.5:1 */
color: #333;
background: #fff;
```

**Form Labels**
```html
<!-- ❌ Bad -->
<label>Email</label>
<input type="email" />

<!-- ✅ Good -->
<label for="email">Email</label>
<input id="email" type="email" />
```

**Focus Indicators**
```css
/* ✅ Good - Always include visible focus */
button:focus {
  outline: 2px solid #0066cc;
  outline-offset: 2px;
}
```

### 2. Security Compliance (npm audit)

**What is npm audit?**
- Scans dependencies for known security vulnerabilities
- Checks against CVE database
- Identifies severity levels: low, moderate, high, critical

**Configuration**: [.auditrc.json](.auditrc.json)

#### Running Security Tests

```bash
# Run npm audit
npm run audit

# Generate JSON report
npm run audit:report

# Attempt automatic fixes
npm run audit:fix

# Check specific audit level
npm audit --audit-level=moderate
```

#### Interpreting npm audit Results

```json
{
  "metadata": {
    "vulnerabilities": 5,
    "packages": 820,
    "severity": "moderate"
  },
  "vulnerabilities": {
    "package-name": {
      "severity": "moderate",
      "range": "^1.0.0",
      "recommendation": "Update to 1.2.3"
    }
  }
}
```

#### Security Remediation Steps

1. **Review Vulnerabilities**
   ```bash
   npm audit --json | jq '.vulnerabilities'
   ```

2. **Attempt Auto-Fix**
   ```bash
   npm audit fix
   ```

3. **Manual Update**
   ```bash
   npm install package-name@latest
   ```

4. **Review Changelog**
   ```bash
   npm view package-name changelog
   ```

5. **Test After Updates**
   ```bash
   npm test
   ```

## 🔧 Running Full Compliance Scans

### Manual Scan

```bash
# Run combined compliance & security scan
npm run test:compliance

# Run Pa11y + security scanner
npm run scan:compliance

# Run Pa11y security scanner (with remediation suggestions)
node pa11y-security-scanner.js
```

### Automated Scanning

GitHub Actions automatically runs compliance checks on:
- Every push to `main` or `develop`
- Every pull request
- Daily schedule (2 AM UTC)
- Manual workflow dispatch

**Workflow**: [.github/workflows/compliance.yml](.github/workflows/compliance.yml)

## 📊 Compliance Reports

### Report Locations

- **Pa11y Reports**: Generated in workspace root, timestamped
- **Audit Reports**: `audit-report.json`
- **GitHub Artifacts**: Available in Actions run artifacts

### Report Contents

**Pa11y Report** (`pa11y-report.json`)
```json
{
  "documentTitle": "Page Title",
  "url": "http://localhost:3000",
  "issues": [
    {
      "code": "WCAG2AA.Principle1.Guideline1_1_1.H37",
      "type": "error",
      "typeCode": 1,
      "message": "Img element missing an alt attribute",
      "selector": "img.logo"
    }
  ]
}
```

**Audit Report** (`audit-report.json`)
```json
{
  "metadata": {
    "vulnerabilities": 2,
    "packages": 820,
    "severity": "moderate"
  },
  "vulnerabilities": {
    "lodash": {
      "severity": "high",
      "range": "^4.17.0",
      "recommendation": "Update to 4.17.21"
    }
  }
}
```

## 🤖 SRE Agent Integration

The SRE agent can automatically detect and help remediate compliance violations:

```bash
# Run SRE agent with compliance focus
node agentic_sre_engineer.js
```

### Agent Capabilities

- **Scan Detection**: Identifies accessibility and security issues
- **Remediation Suggestions**: Provides specific fixes
- **Code Generation**: Creates accessibility-compliant code samples
- **Package Management**: Recommends security updates
- **Report Analysis**: Explains compliance violations

## 📋 Compliance Checklist

### Before Deployment

- [ ] Pa11y accessibility scan passes (no critical violations)
- [ ] npm audit shows no critical vulnerabilities
- [ ] Color contrast meets WCAG AA (4.5:1 minimum)
- [ ] All images have alt text
- [ ] Form labels properly associated
- [ ] Keyboard navigation works
- [ ] Focus indicators visible
- [ ] No console errors

### For Production Release

- [ ] Full compliance scan passed
- [ ] Security audit reviewed and approved
- [ ] Accessibility issues documented or resolved
- [ ] Third-party dependencies vetted
- [ ] Security update plan in place

## 🔐 Security Best Practices

1. **Regular Updates**
   - Run `npm audit` weekly
   - Update dependencies monthly
   - Monitor security advisories

2. **Dependency Management**
   - Minimize dependencies
   - Use minimal versions
   - Audit before installing

3. **Supply Chain Security**
   - Verify package authenticity
   - Check maintainer reputation
   - Review package source code

## ♿ Accessibility Best Practices

1. **Semantic HTML**
   - Use proper heading levels
   - Use semantic elements (nav, main, aside)
   - Avoid div/span for structure

2. **Color & Contrast**
   - Never rely on color alone
   - Maintain 4.5:1 contrast ratio
   - Test with color blindness simulator

3. **Keyboard Navigation**
   - Support full keyboard access
   - Visible focus indicators
   - No keyboard traps

4. **Assistive Technology**
   - Screen reader compatible
   - Proper ARIA labels
   - Text alternatives for media

## 🆘 Troubleshooting

### Pa11y Issues

**Server Connection Failed**
```bash
# Ensure server is running on port 3000
npm start &
sleep 3
npm run test:pa11y
```

**Timeout Errors**
- Increase timeout in `.pa11yci.json`
- Check server logs: `tail -f /tmp/server.log`

**Reporting Issues**
```bash
# Run with verbose output
pa11y-ci --config .pa11yci.json --reporter cli
```

### npm audit Issues

**Too Many Vulnerabilities**
```bash
# Review by severity
npm audit --audit-level=critical

# Check specific package
npm audit ls package-name
```

**Cannot Fix Automatically**
- Update package manually
- Check for breaking changes
- Run full test suite

## 📚 Resources

- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [Pa11y Documentation](https://www.pa11y.org/)
- [npm Security](https://docs.npmjs.com/cli/v8/commands/npm-audit)
- [WebAIM Accessibility Resources](https://webaim.org/)
- [OWASP Security Guidelines](https://owasp.org/)

## 📞 Support

For compliance and security questions:
1. Review this guide
2. Check GitHub Issues
3. Review WCAG/CVE documentation
4. Contact the development team

---

**Last Updated**: 2024
**Compliance Framework**: WCAG 2.1 Level AA + npm Security Audit
