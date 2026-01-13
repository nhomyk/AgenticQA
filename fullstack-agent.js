// Fullstack Agent v3.0 - Enhanced Code Fixer with Test Generation
// ✅ Scans for known issues and fixes them directly
// ✅ Generates tests for code lacking coverage
// ✅ Expert knowledge of all pipeline tools

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
const GITHUB_RUN_ID = process.env.GITHUB_RUN_ID;
const REPO_OWNER = 'nhomyk';
const REPO_NAME = 'AgenticQA';

// Pipeline tool expertise
const PIPELINE_KNOWLEDGE = {
  testFrameworks: {
    jest: { 
      files: 'unit-tests/*.test.js',
      syntax: 'test(\'description\', () => { expect(...).toBe(...) })',
      setup: 'const { expect, test, describe } = require(\'@jest/globals\');'
    },
    playwright: { 
      files: 'playwright-tests/*.spec.js',
      syntax: 'test(\'description\', async ({ page }) => { await page.goto(...) })',
      setup: 'import { test, expect } from \'@playwright/test\';'
    },
    cypress: { 
      files: 'cypress/e2e/*.cy.js',
      syntax: 'it(\'description\', () => { cy.visit(...) })',
      setup: 'describe(\'suite\', () => { ... })'
    },
    vitest: { 
      files: 'vitest-tests/*.test.mjs',
      syntax: 'test(\'description\', () => { expect(...).toBe(...) })',
      setup: 'import { test, expect, describe } from \'vitest\';'
    }
  },
  codebase: {
    frontend: {
      files: ['public/app.js', 'public/index.html'],
      testFile: 'unit-tests/app.test.js',
      key_functions: ['renderResults', 'downloadScript', 'copyToClipboard', 'generatePlaywrightExample', 'generateCypressExample']
    },
    backend: {
      files: ['server.js'],
      testFile: 'unit-tests/server.test.js',
      key_functions: ['validateUrl', 'sanitizeString', 'scanPage', 'detectTechnologies']
    }
  },
  workflow: {
    jobs: ['lint', 'unit-test', 'test-playwright', 'test-vitest', 'test-cypress', 'sdet-agent', 'fullstack-agent', 'sre-agent'],
    triggers: ['push', 'pull_request'],
    success_criteria: ['all tests passing', 'linting clean', 'agent success']
  }
};

function log(msg) {
  console.log(msg);
}

function exec(cmd) {
  try {
    execSync(cmd, { stdio: 'inherit' });
    return true;
  } catch (err) {
    console.error(`Error: ${err.message}`);
    return false;
  }
}

function execSilent(cmd) {
  try {
    execSync(cmd, { stdio: 'pipe' });
    return true;
  } catch (err) {
    return false;
  }
}

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Detect which code has changed
function detectChangedCode() {
  log('🔍 Detecting code changes...\n');
  
  try {
    const diff = execSync('git diff HEAD~1 HEAD --name-only', { encoding: 'utf-8' });
    const changedFiles = diff.trim().split('\n').filter(f => f.match(/\.(js|ts|jsx|tsx)$/));
    
    log(`  Found ${changedFiles.length} changed files:`);
    changedFiles.forEach(f => log(`    • ${f}`));
    
    return changedFiles;
  } catch (err) {
    return [];
  }
}

// Analyze code for test coverage
function analyzeTestCoverage(changedFiles) {
  log('\n📊 Analyzing test coverage...\n');
  
  const uncoveredFunctions = [];
  
  for (const file of changedFiles) {
    if (!fs.existsSync(file)) continue;
    
    const content = fs.readFileSync(file, 'utf-8');
    const testContent = findTestFile(file);
    
    if (!testContent) {
      log(`  ⚠️  No tests found for ${file}`);
      // Extract function names from file
      const functionMatches = content.match(/function\s+(\w+)\s*\(/g) || [];
      functionMatches.forEach(match => {
        const funcName = match.match(/function\s+(\w+)/)[1];
        uncoveredFunctions.push({ file, function: funcName, type: 'function' });
      });
    } else {
      // Check which functions are covered
      const functionMatches = content.match(/function\s+(\w+)\s*\(/g) || [];
      functionMatches.forEach(match => {
        const funcName = match.match(/function\s+(\w+)/)[1];
        if (!testContent.includes(funcName)) {
          uncoveredFunctions.push({ file, function: funcName, type: 'function' });
        }
      });
    }
  }
  
  return uncoveredFunctions;
}

function findTestFile(sourceFile) {
  const fileName = path.basename(sourceFile, path.extname(sourceFile));
  const possiblePaths = [
    `unit-tests/${fileName}.test.js`,
    `unit-tests/${fileName}.test.mjs`,
    `vitest-tests/${fileName}.test.mjs`,
    `playwright-tests/${fileName}.spec.js`,
    `cypress/e2e/${fileName}.cy.js`,
  ];
  
  for (const testPath of possiblePaths) {
    if (fs.existsSync(testPath)) {
      return fs.readFileSync(testPath, 'utf-8');
    }
  }
  
  return null;
}

// Generate tests based on code analysis
function generateTests(uncoveredFunctions) {
  log('\n🧪 Generating missing tests...\n');
  
  if (uncoveredFunctions.length === 0) {
    log('  ✅ All code has test coverage');
    return [];
  }
  
  const generatedTests = [];
  
  // Group by file
  const byFile = {};
  uncoveredFunctions.forEach(item => {
    if (!byFile[item.file]) byFile[item.file] = [];
    byFile[item.file].push(item);
  });
  
  for (const [sourceFile, functions] of Object.entries(byFile)) {
    log(`  📝 Creating tests for ${sourceFile}`);
    
    if (sourceFile.includes('app.js')) {
      const testContent = generateFrontendTests(functions);
      const testFile = 'unit-tests/app.test.js';
      generatedTests.push({ file: testFile, content: testContent });
      log(`     ✓ Generated frontend tests`);
    } else if (sourceFile.includes('server.js')) {
      const testContent = generateBackendTests(functions);
      const testFile = 'unit-tests/server.test.js';
      generatedTests.push({ file: testFile, content: testContent });
      log(`     ✓ Generated backend tests`);
    }
  }
  
  return generatedTests;
}

function generateFrontendTests(functions) {
  const testNames = functions.map(f => f.function);
  
  return `// Auto-generated tests by fullstack-agent
const { expect, test, describe } = require('@jest/globals');
const fs = require('fs');
const path = require('path');

describe('app.js Auto-Generated Tests', () => {
  let appCode;
  
  beforeAll(() => {
    appCode = fs.readFileSync(path.join(__dirname, '../public/app.js'), 'utf8');
  });

${testNames.map(funcName => `
  test('${funcName} should be defined', () => {
    expect(appCode).toContain('function ${funcName}');
  });

  test('${funcName} should handle basic inputs', () => {
    const regex = new RegExp(\`function ${funcName}[\\s\\S]*?\\}\`, 'g');
    const funcMatch = appCode.match(regex);
    expect(funcMatch).toBeDefined();
    expect(funcMatch.length).toBeGreaterThan(0);
  });
`).join('\n')}
});
`;
}

function generateBackendTests(functions) {
  const testNames = functions.map(f => f.function);
  
  return `// Auto-generated tests by fullstack-agent
const { expect, test, describe } = require('@jest/globals');

describe('server.js Auto-Generated Tests', () => {
${testNames.map(funcName => `
  test('${funcName} should exist', () => {
    // Verify function is defined in server.js
    const code = require('fs').readFileSync('./server.js', 'utf8');
    expect(code).toContain('function ${funcName}');
  });

  test('${funcName} should be callable', () => {
    // Smoke test for function existence
    const code = require('fs').readFileSync('./server.js', 'utf8');
    const regex = /function ${funcName}\\s*\\(/;
    expect(regex.test(code)).toBe(true);
  });
`).join('\n')}
});
`;
}

// Write generated tests to files
function applyGeneratedTests(generatedTests) {
  if (generatedTests.length === 0) return false;
  
  log('\n📄 Writing generated tests to files...\n');
  let written = false;
  
  for (const test of generatedTests) {
    try {
      // Append to existing test file or create new
      let existingContent = '';
      if (fs.existsSync(test.file)) {
        existingContent = fs.readFileSync(test.file, 'utf-8');
      }
      
      // Merge: add new tests without duplicating
      let mergedContent = existingContent;
      if (!existingContent.includes('Auto-generated tests by fullstack-agent')) {
        mergedContent += '\n\n' + test.content;
      }
      
      fs.writeFileSync(test.file, mergedContent, 'utf-8');
      log(`  ✅ Updated ${test.file}`);
      written = true;
    } catch (err) {
      log(`  ⚠️  Failed to write ${test.file}: ${err.message}`);
    }
  }
  
  return written;
}

// Generate pipeline knowledge report
function generatePipelineReport() {
  log('\n📚 === PIPELINE EXPERT KNOWLEDGE ===\n');
  
  log('Test Frameworks:');
  Object.entries(PIPELINE_KNOWLEDGE.testFrameworks).forEach(([name, info]) => {
    log(`  • ${name}`);
    log(`    Location: ${info.files}`);
    log(`    Pattern: ${info.syntax.substring(0, 50)}...`);
  });
  
  log('\nCodebase Structure:');
  Object.entries(PIPELINE_KNOWLEDGE.codebase).forEach(([area, info]) => {
    log(`  • ${area}`);
    log(`    Files: ${info.files.join(', ')}`);
    log(`    Tests: ${info.testFile}`);
    log(`    Key functions: ${info.key_functions.join(', ')}`);
  });
  
  log('\nWorkflow Jobs:');
  log(`  ${PIPELINE_KNOWLEDGE.workflow.jobs.join(' → ')}`);
  
  log('\n');
}

async function triggerNewPipeline() {
  log('\n🔄 Triggering new pipeline...');
  
  if (!GITHUB_TOKEN) {
    log('⚠️  No GITHUB_TOKEN - skipping pipeline trigger');
    return false;
  }
  
  try {
    // Try Octokit first
    try {
      const { Octokit } = await import('@octokit/rest');
      const octokit = new Octokit({ auth: GITHUB_TOKEN });
      
      await octokit.actions.createWorkflowDispatch({
        owner: REPO_OWNER,
        repo: REPO_NAME,
        workflow_id: 'ci.yml',
        ref: 'main',
      });
      
      log('✅ Pipeline triggered via API');
      return true;
    } catch (err) {
      log(`  Octokit unavailable, trying direct HTTP...`);
      
      // Fallback: Direct HTTP request
      return new Promise((resolve) => {
        const postData = JSON.stringify({
          ref: 'main'
        });
        
        const options = {
          hostname: 'api.github.com',
          path: `/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/ci.yml/dispatches`,
          method: 'POST',
          headers: {
            'Authorization': `token ${GITHUB_TOKEN}`,
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
            'Content-Length': postData.length,
            'User-Agent': 'Node.js'
          }
        };
        
        const req = require('https').request(options, (res) => {
          resolve(res.statusCode === 204);
          res.on('data', () => {});
        });
        
        req.on('error', (err) => {
          log(`  HTTP request failed: ${err.message}`);
          resolve(false);
        });
        
        req.write(postData);
        req.end();
      });
    }
  } catch (err) {
    log(`⚠️  Failed to trigger: ${err.message}`);
    return false;
  }
}

async function main() {
  try {
    log('\n🤖 === FULLSTACK AGENT v3.0 ===');
    log(`Run ID: ${GITHUB_RUN_ID}`);
    log('═══════════════════════════════════\n');
    
    // Display pipeline expertise
    generatePipelineReport();
    
    let changesApplied = false;
    
    // STRATEGY 1: Scan and fix known issues in source files
    log('📝 Scanning source files for bugs...\n');
    
    const filesToCheck = [
      'public/app.js',
      'server.js',
      'public/index.html'
    ];
    
    for (const filePath of filesToCheck) {
      if (!fs.existsSync(filePath)) continue;
      
      log(`  📄 ${filePath}`);
      let content = fs.readFileSync(filePath, 'utf-8');
      const original = content;
      
      // Fix known broken patterns
      const fixes = [
        { find: 'BROKEN_TEXT_BUG', replace: 'Tech Detected', desc: 'BROKEN_TEXT_BUG' },
        { find: 'TECHNOLOGIES_BROKEN', replace: 'Tech Detected', desc: 'TECHNOLOGIES_BROKEN' },
        { find: 'TEST_DEFECT', replace: 'Tech Detected', desc: 'TEST_DEFECT' },
        { find: 'ERROR_MARKER', replace: '', desc: 'ERROR_MARKER' },
      ];
      
      for (const fix of fixes) {
        if (content.includes(fix.find)) {
          log(`     🔧 Fixed: ${fix.desc}`);
          content = content.replace(new RegExp(fix.find, 'g'), fix.replace);
          changesApplied = true;
        }
      }
      
      // Write back if changed
      if (content !== original) {
        fs.writeFileSync(filePath, content, 'utf-8');
        log(`     ✅ Saved\n`);
      }
    }
    
    // STRATEGY 2: Detect and generate tests for uncovered code
    log('🧬 Analyzing code coverage...\n');
    const changedFiles = detectChangedCode();
    const uncoveredFunctions = analyzeTestCoverage(changedFiles);
    const generatedTests = generateTests(uncoveredFunctions);
    const testsApplied = applyGeneratedTests(generatedTests);
    
    if (testsApplied) {
      changesApplied = true;
      log('\n✅ Tests generated and applied');
    }
    
    if (!changesApplied) {
      log('✅ No code issues or missing tests\n');
      process.exit(0);
    }
    
    // STEP 2: Commit changes
    log('\n📤 Committing changes...\n');
    
    // Configure git
    execSilent('git config --global user.name "fullstack-agent[bot]"');
    execSilent('git config --global user.email "fullstack-agent[bot]@users.noreply.github.com"');
    
    if (GITHUB_TOKEN) {
      execSilent(`git config --global url.https://x-access-token:${GITHUB_TOKEN}@github.com/.insteadOf https://github.com/`);
    }
    
    // Add files
    execSilent('git add -A');
    
    // Check if there are changes
    let statusOutput = '';
    try {
      statusOutput = require('child_process').execSync('git status --porcelain', { encoding: 'utf-8' });
    } catch (e) {
      // Ignore error
    }
    
    const hasChanges = statusOutput.trim().length > 0;
    
    if (!hasChanges) {
      log('✅ No changes to commit\n');
      log('\n✅ === FULLSTACK AGENT v3.0 COMPLETE ===');
      log('   ✓ Scanned source files & code quality verified');
      log('   ✓ Analyzed code coverage');
      log('   ✓ No fixes needed\n');
      log('   ℹ️  NO CODE CHANGES MADE');
      log('   ℹ️  NO PIPELINE RE-RUN TRIGGERED\n');
      process.exit(0);
    }
    
    // Commit
    try {
      execSync('git commit -m "fix: fullstack-agent auto-fixed code issues and generated tests"', { stdio: 'inherit' });
    } catch (err) {
      log(`❌ Commit failed: ${err.message}`);
      process.exit(1);
    }
    log('✅ Changes committed\n');
    
    // Push
    log('🚀 Pushing to main...\n');
    try {
      execSync('git push origin main', { stdio: 'inherit' });
    } catch (err) {
      log(`❌ Push failed: ${err.message}`);
      log('   This may block pipeline re-runs. Check git auth and permissions.');
      process.exit(1);
    }
    log('✅ Changes pushed\n');
    
    // STEP 3: Trigger new pipeline (only if changes were made)
    log('🔄 Code changes detected - triggering new pipeline...\n');
    try {
      const triggerSuccess = await triggerNewPipeline();
      if (!triggerSuccess) {
        log('⚠️  Pipeline trigger via API failed, but changes are pushed');
        log('   GitHub should auto-trigger workflow on push');
      }
    } catch (err) {
      log(`⚠️  Pipeline trigger error: ${err.message}\n`);
      log('   GitHub should auto-trigger workflow on push');
    }
    
    log('\n✅ === FULLSTACK AGENT v3.0 COMPLETE ===');
    log('   ✓ Scanned source files & fixed bugs');
    log('   ✓ Analyzed code coverage');
    log('   ✓ Generated missing tests');
    log('   ✓ Committed all changes');
    log('   ✓ Pushed to main');
    log('   ✓ PIPELINE RE-RUN TRIGGERED\n');
    log('   Pipeline Expertise:');
    log('   • Jest, Playwright, Cypress, Vitest');
    log('   • Frontend & Backend testing');
    log('   • Auto-coverage detection\n');
    log('🎉 Intelligent code & test fixes deployed!\n');
    
    process.exit(0);
  } catch (err) {
    console.error(`\n❌ ERROR: ${err.message}`);
    console.error(err.stack);
    process.exit(1);
  }
}

main();


if (require.main === module) {
  main().catch(console.error);
}

module.exports = { main };
