/**
 * Dashboard UI Tests
 * Comprehensive testing suite for dashboard functionality
 */

const fs = require('fs');
const path = require('path');

// Test Results
const results = {
  passed: 0,
  failed: 0,
  tests: []
};

// Helper: Assert function
function assert(condition, message) {
  if (!condition) {
    throw new Error(`Assertion failed: ${message}`);
  }
}

// Helper: Test wrapper
async function test(name, fn) {
  try {
    await fn();
    results.passed++;
    results.tests.push({ name, status: 'PASS', error: null });
    console.log(`✅ ${name}`);
  } catch (error) {
    results.failed++;
    results.tests.push({ name, status: 'FAIL', error: error.message });
    console.error(`❌ ${name}: ${error.message}`);
  }
}

// ======================
// DASHBOARD HTML TESTS
// ======================

async function testDashboardHTML() {
  console.log('\n📋 DASHBOARD HTML STRUCTURE TESTS');
  console.log('═'.repeat(50));

  const dashboardPath = path.join(__dirname, 'public', 'dashboard.html');
  const html = fs.readFileSync(dashboardPath, 'utf8');

  await test('Dashboard file exists', () => {
    assert(fs.existsSync(dashboardPath), 'dashboard.html not found');
  });

  await test('HTML structure is valid', () => {
    assert(html.includes('<!DOCTYPE html>'), 'Missing DOCTYPE');
    assert(html.includes('<html lang="en">'), 'Missing html element');
    assert(html.includes('</body>'), 'Missing closing body tag');
  });

  await test('Page title is set', () => {
    assert(html.includes('<title>circleQA.ai Dashboard'), 'Missing or incorrect title');
  });

  await test('Navigation bar exists', () => {
    assert(html.includes('class="navbar"'), 'Missing navbar');
    assert(html.includes('circleQA.ai'), 'Missing logo');
    assert(html.includes('Dashboard'), 'Missing dashboard link');
  });

  await test('Main container exists', () => {
    assert(html.includes('class="container"'), 'Missing main container');
    assert(html.includes('class="page-header"'), 'Missing page header');
  });

  await test('Page header content', () => {
    assert(html.includes('Agent Control Center'), 'Missing header title');
    assert(html.includes('Monitor pipeline health'), 'Missing header description');
  });

  await test('Dashboard grid layout exists', () => {
    assert(html.includes('class="dashboard-grid"'), 'Missing dashboard grid');
  });

  await test('Pipeline Kickoff section', () => {
    assert(html.includes('kickoff-section'), 'Missing kickoff section');
    assert(html.includes('pipelineType'), 'Missing pipeline type selector');
    assert(html.includes('pipelineBranch'), 'Missing branch input');
    assert(html.includes('Launch Pipeline'), 'Missing launch button');
  });

  await test('Agent Interaction section', () => {
    assert(html.includes('Agent Interaction'), 'Missing agent section title');
    assert(html.includes('agentSelect'), 'Missing agent selector');
    assert(html.includes('agentQuery'), 'Missing query textarea');
    assert(html.includes('Send'), 'Missing send button');
  });

  await test('Agent options available', () => {
    assert(html.includes('SDET Agent'), 'Missing SDET agent');
    assert(html.includes('Fullstack Agent'), 'Missing Fullstack agent');
    assert(html.includes('Compliance Agent'), 'Missing Compliance agent');
    assert(html.includes('SRE Agent'), 'Missing SRE agent');
  });

  await test('Quick action buttons', () => {
    assert(html.includes('Health Check'), 'Missing health check button');
    assert(html.includes('Test Coverage'), 'Missing coverage button');
    assert(html.includes('Compliance'), 'Missing compliance button');
    assert(html.includes('Accessibility'), 'Missing accessibility button');
  });

  await test('Health Metrics card', () => {
    assert(html.includes('Health Metrics'), 'Missing metrics card');
    assert(html.includes('Pipeline Success'), 'Missing success metric');
    assert(html.includes('Avg. Duration'), 'Missing duration metric');
    assert(html.includes('Test Coverage'), 'Missing coverage metric');
  });

  await test('Compliance Status card', () => {
    assert(html.includes('Compliance Status'), 'Missing compliance card');
    assert(html.includes('WCAG 2.1'), 'Missing WCAG accessibility');
    assert(html.includes('Security Checks'), 'Missing security checks');
    assert(html.includes('Code Quality'), 'Missing code quality');
    assert(html.includes('Performance'), 'Missing performance');
  });

  await test('Recent Pipelines section', () => {
    assert(html.includes('Recent Pipelines'), 'Missing pipelines section');
    assert(html.includes('pipelinesList'), 'Missing pipelines list');
    assert(html.includes('Last 20'), 'Missing "Last 20" text');
  });

  await test('Response panel', () => {
    assert(html.includes('responsePanel'), 'Missing response panel');
    assert(html.includes('Agent Response'), 'Missing response title');
  });

  await test('Alert containers', () => {
    assert(html.includes('successAlert'), 'Missing success alert');
    assert(html.includes('errorAlert'), 'Missing error alert');
  });
}

// ======================
// JAVASCRIPT TESTS
// ======================

async function testDashboardJavaScript() {
  console.log('\n🔧 DASHBOARD JAVASCRIPT FUNCTION TESTS');
  console.log('═'.repeat(50));

  const dashboardPath = path.join(__dirname, 'public', 'dashboard.html');
  const html = fs.readFileSync(dashboardPath, 'utf8');

  await test('loadRecentPipelines function exists', () => {
    assert(html.includes('async function loadRecentPipelines()'), 'Missing loadRecentPipelines function');
  });

  await test('queryAgent function exists', () => {
    assert(html.includes('async function queryAgent()'), 'Missing queryAgent function');
  });

  await test('quickQuery function exists', () => {
    assert(html.includes('function quickQuery(type)'), 'Missing quickQuery function');
  });

  await test('updateAgentInfo function exists', () => {
    assert(html.includes('function updateAgentInfo()'), 'Missing updateAgentInfo function');
  });

  await test('kickoffPipeline function exists', () => {
    assert(html.includes('async function kickoffPipeline()'), 'Missing kickoffPipeline function');
  });

  await test('showAlert function exists', () => {
    assert(html.includes('function showAlert(message, type)'), 'Missing showAlert function');
  });

  await test('getTimeAgo function exists', () => {
    assert(html.includes('function getTimeAgo(date)'), 'Missing getTimeAgo function');
  });

  await test('GitHub API integration exists', () => {
    assert(html.includes('api.github.com'), 'Missing GitHub API integration');
    assert(html.includes('actions/runs'), 'Missing workflow runs endpoint');
  });

  await test('Event listeners setup', () => {
    assert(html.includes('DOMContentLoaded'), 'Missing DOMContentLoaded listener');
    assert(html.includes('setInterval(loadRecentPipelines'), 'Missing auto-refresh setup');
  });

  await test('Pipeline kickoff API call', () => {
    assert(html.includes('fetch'), 'Missing fetch in kickoffPipeline');
  });

  await test('Response handlers', () => {
    assert(html.includes('.then('), 'Missing promise handlers');
    assert(html.includes('.catch('), 'Missing error handlers');
  });
}

// ======================
// CSS TESTS
// ======================

async function testDashboardCSS() {
  console.log('\n🎨 DASHBOARD CSS TESTS');
  console.log('═'.repeat(50));

  const dashboardPath = path.join(__dirname, 'public', 'dashboard.html');
  const html = fs.readFileSync(dashboardPath, 'utf8');

  await test('Responsive design media queries', () => {
    assert(html.includes('@media (max-width:'), 'Missing media queries');
  });

  await test('Dark theme styles', () => {
    assert(html.includes('#0f172a') || html.includes('0f172a'), 'Missing dark theme color');
    assert(html.includes('#e0e7ff') || html.includes('e0e7ff'), 'Missing light text color');
  });

  await test('Gradient definitions', () => {
    assert(html.includes('linear-gradient'), 'Missing gradient definitions');
    assert(html.includes('667eea') || html.includes('#667eea'), 'Missing primary gradient color');
    assert(html.includes('764ba2') || html.includes('#764ba2'), 'Missing secondary gradient color');
  });

  await test('Glassmorphism styles', () => {
    assert(html.includes('backdrop-filter'), 'Missing backdrop-filter');
    assert(html.includes('blur'), 'Missing blur effect');
  });

  await test('Card styles', () => {
    assert(html.includes('.card'), 'Missing card class');
    assert(html.includes('border-radius'), 'Missing border radius');
  });

  await test('Button styles', () => {
    assert(html.includes('.btn'), 'Missing button class');
    assert(html.includes('.btn-primary'), 'Missing primary button');
    assert(html.includes('.btn-secondary'), 'Missing secondary button');
  });

  await test('Animation keyframes', () => {
    assert(html.includes('@keyframes'), 'Missing animation keyframes');
    assert(html.includes('pulse'), 'Missing pulse animation');
  });

  await test('Grid layout', () => {
    assert(html.includes('display: grid'), 'Missing grid layout');
    assert(html.includes('grid-template-columns'), 'Missing grid columns');
  });

  await test('Flexbox layout', () => {
    assert(html.includes('display: flex'), 'Missing flexbox layout');
  });

  await test('Accessibility colors', () => {
    assert(html.includes('color:'), 'Missing color definitions');
    assert(html.includes('background:'), 'Missing background definitions');
  });
}

// ======================
// INTEGRATION TESTS
// ======================

async function testDashboardIntegration() {
  console.log('\n🔗 DASHBOARD INTEGRATION TESTS');
  console.log('═'.repeat(50));

  const dashboardPath = path.join(__dirname, 'public', 'dashboard.html');
  const html = fs.readFileSync(dashboardPath, 'utf8');

  await test('Navigation links to dashboard', () => {
    const indexPath = path.join(__dirname, 'public', 'index.html');
    const indexHtml = fs.readFileSync(indexPath, 'utf8');
    assert(indexHtml.includes('/dashboard.html'), 'Dashboard link missing from index.html');
    assert(indexHtml.includes('Dashboard'), 'Dashboard button missing from navigation');
  });

  await test('Dashboard has back to home link', () => {
    assert(html.includes('/index.html'), 'Missing link back to home');
  });

  await test('All form inputs have IDs', () => {
    assert(html.includes('id="pipelineType"'), 'pipelineType missing ID');
    assert(html.includes('id="pipelineBranch"'), 'pipelineBranch missing ID');
    assert(html.includes('id="agentSelect"'), 'agentSelect missing ID');
    assert(html.includes('id="agentQuery"'), 'agentQuery missing ID');
  });

  await test('All event handlers connected', () => {
    assert(html.includes('onclick="kickoffPipeline()"'), 'Launch button not connected');
    assert(html.includes('onclick="queryAgent()"'), 'Send button not connected');
    assert(html.includes('onclick="quickQuery'), 'Quick actions not connected');
    assert(html.includes('onchange="updateAgentInfo()"'), 'Agent selector not connected');
  });

  await test('GitHub API endpoints configured', () => {
    assert(html.includes('nhomyk/AgenticQA'), 'Missing repo path');
    assert(html.includes('per_page='), 'Missing pagination parameter');
  });

  await test('Error handling callbacks', () => {
    assert(html.includes('.catch('), 'Missing catch handlers');
  });

  await test('DOM manipulation targets', () => {
    assert(html.includes('getElementById'), 'Missing getElementById calls');
    assert(html.includes('innerHTML'), 'Missing innerHTML assignments');
    assert(html.includes('appendChild'), 'Missing appendChild calls');
  });
}

// ======================
// ACCESSIBILITY TESTS
// ======================

async function testDashboardAccessibility() {
  console.log('\n♿ DASHBOARD ACCESSIBILITY TESTS');
  console.log('═'.repeat(50));

  const dashboardPath = path.join(__dirname, 'public', 'dashboard.html');
  const html = fs.readFileSync(dashboardPath, 'utf8');

  await test('Semantic HTML headings', () => {
    assert(html.includes('<h1>'), 'Missing H1 heading');
    // Check for h2 or h3 with class or without
    const hasSubheading = html.includes('<h2') || html.includes('<h3') || html.includes('h2>') || html.includes('h3>');
    assert(hasSubheading, 'Missing subheadings');
  });

  await test('Form labels present', () => {
    // Check for labels with or without for attribute
    const hasLabels = html.includes('<label') && (html.match(/<label/g) || []).length >= 3;
    assert(hasLabels, 'Missing form labels - need at least 3');
  });

  await test('Alt text structure', () => {
    assert(html.includes('aria-') || html.includes('title='), 'Missing ARIA labels');
  });

  await test('Focus indicators', () => {
    assert(html.includes(':focus'), 'Missing focus styles');
    assert(html.includes('outline') || html.includes('box-shadow'), 'Missing focus indicators');
  });

  await test('Button accessibility', () => {
    assert(html.includes('<button'), 'Missing button elements');
    assert(html.includes('type='), 'Missing button types');
  });

  await test('Color contrast setup', () => {
    assert(html.includes('color:'), 'Missing text color');
    assert(html.includes('background:'), 'Missing background color');
  });

  await test('Keyboard navigation support', () => {
    assert(html.includes('tabindex'), 'Missing tab order');
  });

  await test('Responsive text sizes', () => {
    assert(html.includes('font-size'), 'Missing font size definitions');
    assert(html.includes('rem') || html.includes('em'), 'Using scalable units');
  });
}

// ======================
// RUN ALL TESTS
// ======================

async function runAllTests() {
  console.log('\n╔════════════════════════════════════════════╗');
  console.log('║   DASHBOARD UI COMPREHENSIVE TEST SUITE    ║');
  console.log('╚════════════════════════════════════════════╝\n');

  await testDashboardHTML();
  await testDashboardJavaScript();
  await testDashboardCSS();
  await testDashboardIntegration();
  await testDashboardAccessibility();

  // Print summary
  console.log('\n╔════════════════════════════════════════════╗');
  console.log('║          TEST RESULTS SUMMARY              ║');
  console.log('╚════════════════════════════════════════════╝\n');

  console.log(`✅ PASSED: ${results.passed}`);
  console.log(`❌ FAILED: ${results.failed}`);
  console.log(`📊 TOTAL:  ${results.passed + results.failed}`);
  console.log(`📈 SUCCESS RATE: ${((results.passed / (results.passed + results.failed)) * 100).toFixed(2)}%\n`);

  if (results.failed > 0) {
    console.log('❌ FAILED TESTS:');
    results.tests
      .filter(t => t.status === 'FAIL')
      .forEach(t => {
        console.log(`   • ${t.name}: ${t.error}`);
      });
  }

  process.exit(results.failed > 0 ? 1 : 0);
}

// Execute tests
runAllTests().catch(error => {
  console.error('Test suite error:', error);
  process.exit(1);
});
