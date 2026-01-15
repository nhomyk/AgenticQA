#!/usr/bin/env node
/**
 * Pre-commit workflow validation script
 * Validates all workflow YAML before pushing to prevent broken deployments
 * 
 * Usage: node scripts/validate-workflows.js
 * Exit codes: 0 = all valid, 1 = errors found
 */

const fs = require('fs');
const path = require('path');

try {
  const yaml = require('js-yaml');
} catch (e) {
  console.error('❌ js-yaml not installed. Install with: npm install js-yaml');
  process.exit(1);
}

const yaml = require('js-yaml');

const WORKFLOWS_DIR = '.github/workflows';
const VALID_EXTENSIONS = ['.yml', '.yaml'];

function validateWorkflows() {
  console.log('\n╔════════════════════════════════════════════════════════════╗');
  console.log('║           🔍 WORKFLOW YAML VALIDATION SCRIPT              ║');
  console.log('╚════════════════════════════════════════════════════════════╝\n');

  if (!fs.existsSync(WORKFLOWS_DIR)) {
    console.error(`❌ Directory not found: ${WORKFLOWS_DIR}`);
    return false;
  }

  const files = fs.readdirSync(WORKFLOWS_DIR)
    .filter(f => VALID_EXTENSIONS.some(ext => f.endsWith(ext)))
    .sort();

  if (files.length === 0) {
    console.log(`⚠️  No workflow files found in ${WORKFLOWS_DIR}`);
    return true;
  }

  console.log(`📋 Found ${files.length} workflow file(s):\n`);

  let allValid = true;
  const results = [];

  files.forEach(file => {
    const filePath = path.join(WORKFLOWS_DIR, file);
    const displayName = path.relative('.', filePath);

    try {
      const content = fs.readFileSync(filePath, 'utf8');
      yaml.load(content);
      
      results.push({
        file: displayName,
        valid: true,
        error: null
      });
      
      console.log(`  ✅ ${displayName}`);
    } catch (err) {
      allValid = false;
      
      results.push({
        file: displayName,
        valid: false,
        error: err.message
      });
      
      console.log(`  ❌ ${displayName}`);
      console.log(`     Error: ${err.message}`);
      
      // Show line number if available
      if (err.mark) {
        console.log(`     Line ${err.mark.line + 1}: ${err.mark.snippet || ''}`);
      }
    }
  });

  console.log('\n' + '═'.repeat(60));
  console.log('VALIDATION SUMMARY');
  console.log('═'.repeat(60));
  
  const valid = results.filter(r => r.valid).length;
  const invalid = results.filter(r => !r.valid).length;
  
  console.log(`Total files: ${results.length}`);
  console.log(`✅ Valid:    ${valid}`);
  console.log(`❌ Invalid:  ${invalid}`);
  console.log('═'.repeat(60));

  if (allValid) {
    console.log('\n✅ ALL WORKFLOWS ARE VALID - Safe to deploy\n');
    return true;
  } else {
    console.log('\n❌ WORKFLOW VALIDATION FAILED - DO NOT PUSH\n');
    console.log('Fix errors above before deploying.\n');
    return false;
  }
}

function validateSourceScripts() {
  console.log('📝 Validating source scripts...\n');

  const scripts = [
    'sdet-agent.js',
    'agentic_sre_engineer.js',
    'fullstack-agent.js'
  ];

  let allValid = true;

  scripts.forEach(script => {
    if (fs.existsSync(script)) {
      try {
        const content = fs.readFileSync(script, 'utf8');
        // Basic syntax check - can parse as module
        new Function(content); // Will throw if syntax error
        console.log(`  ✅ ${script}`);
      } catch (err) {
        allValid = false;
        console.log(`  ❌ ${script}`);
        console.log(`     Syntax Error: ${err.message}`);
      }
    }
  });

  return allValid;
}

async function main() {
  const workflowsValid = validateWorkflows();
  const scriptsValid = validateSourceScripts();

  if (!workflowsValid || !scriptsValid) {
    console.error('\n❌ VALIDATION FAILED');
    process.exit(1);
  }

  console.log('\n✅ ALL VALIDATIONS PASSED - Ready to deploy\n');
  process.exit(0);
}

main().catch(err => {
  console.error('❌ Validation error:', err.message);
  process.exit(1);
});
