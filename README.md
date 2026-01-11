# Agentic QA Engineer

Lightweight service that scans a webpage for console errors and common DOM/accessibility issues using Puppeteer.

Setup

1. Install dependencies:

```bash
npm install
```

2. Run the server:

```bash
npm start
```

3. Open http://localhost:3000 and enter a URL to scan.

Notes

- Results are limited to 25 items. The scanner reports console errors, page exceptions, failed requests, missing image alts, broken images, missing form labels, bad anchors, and basic heading order issues.
- Puppeteer will download a Chromium binary on first install; ensure network access.
