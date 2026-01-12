# Agentic QA Engineer - LangGraph Agent

## Overview

The LangGraph Agent is an autonomous tool that:
- **Scans the codebase** - Analyzes project structure and files
- **Interacts with the frontend UI** - Submits URLs for scanning using Playwright
- **Analyzes results** - Processes and summarizes scan findings

The agent demonstrates how LangChain and LangGraph can be used to create intelligent agents that combine code analysis with UI automation.

## Architecture

### Core Components

#### 1. **scanCodebase()**
Recursively scans the project directory and returns file structure and metadata.

```javascript
const codebaseInfo = scanCodebase(directory, depth, maxDepth);
```

**Returns:**
- File hierarchy with types (file/directory)
- Line counts for each file
- File size information
- First 20 lines of code preview

#### 2. **submitURLToFrontend()**
Uses Playwright to interact with the frontend UI and submit a URL for scanning.

```javascript
const results = await submitURLToFrontend(url, baseURL);
```

**Process:**
1. Launches headless browser
2. Navigates to frontend UI
3. Fills URL input field
4. Clicks scan button
5. Waits for results
6. Extracts all result sections

**Returns:**
- Scan results
- Generated test cases
- Performance metrics
- Detected APIs
- Playwright example code
- Cypress example code

#### 3. **analyzeResults()**
Processes scan results and creates a structured summary.

```javascript
const analysis = analyzeResults(scanResults);
```

**Returns:**
- Summary statistics (issue count, test cases, APIs)
- Sample data from each section
- Code generation status

#### 4. **QAAgent Class**
Main orchestrator that coordinates all tools and maintains agent state.

```javascript
const agent = new QAAgent();
const state = await agent.run(urlToScan);
```

**Agent Workflow:**
1. **Step 1:** Scan codebase structure
2. **Step 2:** Submit URL to frontend for scanning
3. **Step 3:** Analyze and summarize results

## Usage

### Basic Usage

```bash
npm run agent "https://example.com"
```

### Running with Default URL

```bash
npm run agent
# Uses https://example.com as default
```

### Programmatic Usage

```javascript
const { QAAgent } = require("./agent.js");

const agent = new QAAgent();
const state = await agent.run("https://example.com");

console.log(state.codebaseInfo);  // Scanned codebase
console.log(state.scanResults);   // Frontend scan results
console.log(state.analysis);      // Analysis summary
```

## Requirements

### Dependencies
- `playwright` - Browser automation for frontend interaction
- `fs` - File system access for codebase scanning
- `path` - Path utilities

### Prerequisites
1. **Server must be running**
   ```bash
   npm start &
   ```

2. **URL must be accessible** - Agent requires a valid, scannable URL

## Example Output

```
╔════════════════════════════════════════╗
║  Agentic QA Engineer - LangGraph Agent ║
╚════════════════════════════════════════╝

📂 Step 1: Scanning codebase structure...
✅ Codebase scanned successfully

📋 Codebase Structure:
──────────────────────────────────────────────────
📄 server.js (234 lines, 10644 bytes)
📁 public/
  📄 app.js (91 lines, 3745 bytes)
  📄 index.html (44 lines, 1796 bytes)
📁 cypress/
  📁 e2e/
    📄 scan-ui.cy.js (51 lines, 2163 bytes)
...

🚀 Step 2: Submitting URL to frontend for scanning...

🌐 Navigating to http://localhost:3000...
📝 Filling URL input with: https://github.com
🔍 Clicking scan button...
⏳ Waiting for scan results...

✅ Scan completed successfully!
📊 Results obtained at: 2026-01-12T14:57:29.112Z

📊 Step 3: Analyzing scan results...
✅ Results analyzed

📊 Scan Summary:
──────────────────────────────────────────────────
Scan Time: 2026-01-12T14:57:29.112Z
Issues Found: 42
Test Cases Generated: 20
APIs Detected: 5
Performance Data: Yes

📝 Sample Results:
──────────────────────────────────────────────────
Issues (first 500 chars):
[Detailed issue list...]

🧪 Code Generation Status:
Playwright Example: ✅ Generated
Cypress Example: ✅ Generated
```

## Agent State

The agent maintains internal state throughout execution:

```javascript
{
  task: string,           // Current task being executed
  codebaseInfo: object,   // Scanned codebase structure
  scanResults: object,    // Frontend scan results
  analysis: object        // Analysis summary
}
```

## Error Handling

The agent includes comprehensive error handling:

```javascript
try {
  const result = await agent.run(urlToScan);
} catch (error) {
  // Network errors - URL unreachable
  // Timeout errors - Scan took too long
  // Browser errors - Playwright issues
  console.error("Agent failed:", error.message);
}
```

## Tools Summary

| Tool | Purpose | Input | Output |
|------|---------|-------|--------|
| **scanCodebase** | Analyze project structure | directory, depth, maxDepth | File hierarchy with metadata |
| **submitURLToFrontend** | UI automation | url, baseURL | Scan results from all sections |
| **analyzeResults** | Process findings | scanResults | Structured summary & statistics |
| **QAAgent.run** | Orchestrate workflow | urlToScan | Complete agent state |

## Future Enhancements

Potential extensions to the agent:

1. **Multi-Agent Coordination** - Multiple agents working on different URLs in parallel
2. **LLM Integration** - Use Claude/GPT to interpret findings and generate recommendations
3. **Persistent Storage** - Save results to database for historical tracking
4. **Scheduled Scans** - Automatically scan URLs on a schedule
5. **Slack Integration** - Post findings to Slack channels
6. **Custom Rules Engine** - Define custom scanning rules and policies
7. **Report Generation** - Create PDF/HTML reports of findings

## Related Documentation

- [LangChain Documentation](https://python.langchain.com/)
- [Playwright Documentation](https://playwright.dev/)
- [Main Project README](./README.md)
