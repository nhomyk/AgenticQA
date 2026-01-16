#!/usr/bin/env node

/**
 * DIRECT SRE AGENT TEST
 * Directly invokes syntax-error-recovery on real test files
 * Proves the module works in isolation
 */

const fs = require('fs');
const path = require('path');
const SyntaxErrorRecovery = require('./syntax-error-recovery.js');

async function testSREDirect() {
  console.log('\n╔════════════════════════════════════════╗');
  console.log('║  🔧 DIRECT SRE AGENT TEST             ║');
  console.log('║  Testing syntax-error-recovery module  ║');
  console.log('╚════════════════════════════════════════╝\n');

  const testCases = [
    {
      name: 'Invalid Math property assignment',
      code: `const Math.randomSeed = Math.random();
const insecureToken = Math.random().toString(36);`,
      file: 'test-math-invalid.js',
    },
    {
      name: 'Invalid object property',
      code: `const user.id = 123;
function test() { return user.id; }`,
      file: 'test-invalid-object-prop.js',
    },
    {
      name: 'Multiple assignment errors',
      code: `const Math.seed = Math.random();
const stringSanitized = "test";
const x = 42;`,
      file: 'test-multi-invalid.js',
    },
  ];

  for (const testCase of testCases) {
    console.log(`\n🧪 TEST: ${testCase.name}`);
    console.log(`   File: ${testCase.file}`);

    // Write test file
    const testFile = path.join(__dirname, testCase.file);
    fs.writeFileSync(testFile, testCase.code);
    console.log(`   ✓ Created test file with syntax error`);

    // Show error code
    console.log(`\n   ❌ Error code:\n${testCase.code.split('\n').map(line => `      ${line}`).join('\n')}`);

    // Try to fix
    console.log(`\n   🔧 Running SyntaxErrorRecovery.fixSyntaxErrors()...\n`);

    try {
      const recovery = new SyntaxErrorRecovery();
      const result = await recovery.fixSyntaxErrors();

      console.log(`   Result:`, result);

      // Check if file was modified
      const newCode = fs.readFileSync(testFile, 'utf8');
      if (newCode !== testCase.code) {
        console.log(`   ✅ FILE WAS MODIFIED`);
        console.log(`\n   ✅ Fixed code:\n${newCode.split('\n').map(line => `      ${line}`).join('\n')}`);
      } else {
        console.log(`   ⚠️  File was not modified`);
      }

      // Verify with linter
      try {
        const { execSync } = require('child_process');
        execSync(`npx eslint ${testCase.file} 2>&1`, { encoding: 'utf8' });
        console.log(`   ✅ LINTER PASSES - Fix successful!`);
      } catch (e) {
        console.log(`   ⚠️  Linter still reports issues`);
      }
    } catch (e) {
      console.log(`   ❌ Error: ${e.message}`);
    }

    // Cleanup
    if (fs.existsSync(testFile)) {
      fs.unlinkSync(testFile);
    }
  }

  console.log('\n✅ Direct SRE test complete\n');
}

testSREDirect().catch(console.error);
