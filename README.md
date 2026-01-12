
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

### Linting
```bash
npx eslint . --ext .js
```

### Unit Tests
```bash
npx jest --coverage
```

### Playwright Tests
```bash
npx playwright test
```

## Notes & Limitations

- Results are limited to 25 items per scan
- Puppeteer downloads a Chromium binary on first install (requires network access)
- Some advanced accessibility or performance issues may not be detected
- For troubleshooting Puppeteer launch issues, ensure Chrome/Chromium is available and accessible

## License

MIT
