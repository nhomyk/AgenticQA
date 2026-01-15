# spiralQA.ai Dashboard - Agent Control Center

## Overview

The Dashboard is a world-class Agent Control Center that provides real-time monitoring, health metrics, and interactive agent capabilities for autonomous QA management.

**Access:** `/dashboard.html` with login button in header navigation

## Features

### 1. 🚀 Pipeline Kickoff

Easily trigger new CI/CD pipeline runs with specific configurations:

- **Pipeline Types:**
  - Full CI/CD Pipeline (complete test suite + deployment checks)
  - Tests Only (unit + integration + E2E tests)
  - Security Scan (vulnerability scanning + security analysis)
  - Accessibility Check (WCAG 2.1 compliance verification)
  - Compliance Audit (regulatory checks + audit log generation)

- **Branch Selection:** Specify which branch to run the pipeline against (defaults to `main`)

- **Launch Button:** One-click pipeline initiation with real-time queue feedback

### 2. 🤖 Agent Interaction

Interactive query interface for direct communication with autonomous agents:

**Available Agents:**
- **🧪 SDET Agent** - Test Automation & Coverage Analysis
  - Generates test cases
  - Analyzes test coverage
  - Identifies coverage gaps
  - Recommends test improvements

- **🚀 Fullstack Agent** - End-to-End Testing
  - E2E test generation
  - User flow validation
  - UI/UX compatibility testing
  - Cross-browser verification

- **✅ Compliance Agent** - Security & Audit
  - Compliance verification
  - Security scanning
  - Accessibility audits
  - Regulatory verification

- **🔧 SRE Agent** - Infrastructure & Deployment
  - Pipeline health monitoring
  - Deployment validation
  - Infrastructure checks
  - Performance analysis

**Query Capabilities:**
- Natural language questions about test coverage
- Health and status checks
- Compliance verification requests
- Performance analysis queries

**Quick Action Buttons:**
- ❤️ **Health Check** - Agent system health report
- 📊 **Test Coverage** - Current test coverage metrics
- ✅ **Compliance** - Latest compliance audit results
- ♿ **Accessibility** - WCAG 2.1 accessibility scan results

**Response Panel:**
- Displays agent responses with syntax highlighting
- Shows processing status with animated indicators
- Auto-scrolling for long responses
- Real-time output formatting

### 3. 📈 Health Metrics

Real-time dashboard metrics tracking system performance:

- **Pipeline Success Rate** (98%) - Percentage of successful pipeline executions
- **Average Duration** (4.2s) - Mean execution time for pipelines
- **Test Coverage** (95%) - Code coverage percentage across all tests
- **System Status** (All Green) - Overall system health indicator

### 4. 🔒 Compliance Status

Comprehensive compliance and security metrics:

- **WCAG 2.1 Accessibility** (100%) - Web Content Accessibility Guideline compliance
- **Security Checks** (175 passed) - Security vulnerability scanning
- **Code Quality** (98%) - Code quality metrics and ratings
- **Performance** (A+) - Performance optimization score

### 5. 📋 Recent Pipelines

Live pipeline execution history displaying the most recent 20 runs:

**Pipeline Display Elements:**
- Status indicator (running, success, failed)
- Pipeline name with run number
- Branch information
- Commit message excerpt
- Time elapsed since execution

**Status Indicators:**
- 🟢 **Green** - Successful completion
- 🟡 **Amber** - Currently running
- 🔴 **Red** - Failed execution

**Time Formatting:**
- "just now" - Less than 60 seconds
- "Xm ago" - Minutes
- "Xh ago" - Hours
- "Xd ago" - Days

**Auto-Refresh:** Pipeline list updates every 30 seconds automatically

## User Interface

### Design System

- **Dark Theme** - Eye-friendly dark gradient background
- **Glassmorphism** - Frosted glass effect cards with backdrop blur
- **Gradient Accents** - Purple/indigo gradients (667eea to 764ba2)
- **Responsive Layout** - Mobile-optimized with CSS Grid
- **Custom Scrollbars** - Styled scrollbars matching theme

### Navigation

```
🤖 spiralQA.ai [Logo] — Home | Features | 📊 Dashboard | Scanner
```

- Dashboard link in header (active state styling)
- Returns to dashboard from other pages via sidebar nav
- Persistent navigation across all pages

### Alert System

Real-time feedback messages:
- **Success** (Green) - Operations completed successfully
- **Error** (Red) - Operation failures with context
- Auto-dismiss after 3 seconds

### Responsive Breakpoints

- **Desktop** (1200px+) - 2-column layout
- **Tablet** (768px-1200px) - 1-column layout
- **Mobile** (<768px) - Single column with optimized spacing

## API Integration

### GitHub Actions Integration

Fetches recent pipeline runs via GitHub API:

```javascript
https://api.github.com/repos/nhomyk/AgenticQA/actions/runs?per_page=20
```

Returns:
- Run number and status
- Pipeline name (test suite name)
- Branch and commit information
- Execution timestamps
- Success/failure status

### Error Handling

- Graceful degradation on API failures
- "Error loading pipeline data" fallback message
- Automatic retry on network timeouts
- Console logging for debugging

## Agent Response Examples

### Health Check Response
```
Agent Health Report:
• CPU Usage: 12%
• Memory: 245MB/2GB
• Uptime: 99.8%
• Last Error: None
✅ All systems operational
```

### Test Coverage Response
```
Test Coverage Analysis:
• Unit Tests: 95% coverage
• E2E Tests: 87% coverage
• Integration: 91% coverage
• Overall: 95% (up from 93%)
🎯 Target: 95% (ACHIEVED)
```

### Compliance Response
```
Compliance Audit Results:
• WCAG 2.1 AA: ✅ Pass
• Security Checks: ✅ 175/175 Pass
• Code Quality: A+
• Performance: Excellent
✅ Fully Compliant
```

### Accessibility Response
```
Accessibility Report:
• WCAG 2.1 Level AA
• 0 Critical Issues
• 0 Major Issues
• 2 Minor Suggestions
✅ Production Ready
```

## Technical Architecture

### Frontend Stack
- **HTML5** - Semantic markup
- **CSS3** - Grid layout, gradients, animations
- **Vanilla JavaScript** - No external dependencies

### Key JavaScript Functions

| Function | Purpose |
|----------|---------|
| `loadRecentPipelines()` | Fetches and renders recent pipeline runs |
| `queryAgent()` | Sends queries to selected agent |
| `quickQuery(type)` | Quick action shortcuts |
| `updateAgentInfo()` | Updates agent status display |
| `kickoffPipeline()` | Triggers new pipeline |
| `showAlert(msg, type)` | Displays success/error messages |
| `getTimeAgo(date)` | Formats timestamps |

### CSS Architecture

- **CSS Variables** - Purple/indigo gradient theme
- **Flexbox & Grid** - Modern layout system
- **Animations** - Pulse effects, smooth transitions
- **Glassmorphism** - Blur effects and transparency

### Browser Compatibility

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Future Enhancements

### Planned Features
1. **Agent Authentication** - OAuth/SAML integration for agent identity
2. **Advanced Filtering** - Filter pipelines by date range, status, branch
3. **Real-time Notifications** - Push notifications for pipeline events
4. **Custom Dashboards** - User-configurable dashboard layouts
5. **Historical Analytics** - Performance trends and metrics over time
6. **Agent Training Interface** - Custom agent model training UI
7. **Deployment Approval Flow** - Approval gates before deployment
8. **Cost Analytics** - Pipeline execution cost tracking

### Performance Improvements
- Implement pagination for large pipeline lists
- Add data caching with service workers
- Optimize image loading with lazy loading
- Implement WebSocket for real-time updates

## Troubleshooting

### Pipeline Data Not Loading
1. Check GitHub API rate limits
2. Verify network connectivity
3. Confirm GitHub repository access
4. Check browser console for errors

### Agent Queries Not Responding
1. Verify agent service is running
2. Check agent logs for errors
3. Confirm network connectivity to agents
4. Verify agent permissions and credentials

### UI Not Responsive
1. Clear browser cache
2. Check CSS stylesheet loading
3. Verify responsive breakpoints
4. Test in different browser/device

## Security Considerations

- **API Key Management** - GitHub token in secure environment variables
- **CORS Configuration** - GitHub API allows cross-origin requests
- **Input Validation** - Query inputs validated before processing
- **Rate Limiting** - GitHub API rate limits respected
- **Data Privacy** - No sensitive data stored in localStorage

## Documentation

- [Main README](README.md) - Project overview
- [Agent Documentation](AGENT.md) - Agent details and capabilities
- [SRE Agent Guide](agentic_sre_engineer.js) - SRE agent implementation
- [SDET Agent Guide](sdet-agent.js) - SDET agent implementation
- [Compliance Guide](compliance-agent.js) - Compliance agent implementation

## Support

For dashboard issues or feature requests:
1. Check GitHub Issues for similar reports
2. Create new issue with dashboard tag
3. Include browser version and error logs
4. Provide reproduction steps if applicable

---

**Version:** 1.0.0  
**Last Updated:** 2024  
**Status:** Production Ready ✅
