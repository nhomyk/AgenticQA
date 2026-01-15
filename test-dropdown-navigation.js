/**
 * Dropdown Navigation Tests
 * Ensures Products dropdown menu works correctly and all links are valid
 */

const fs = require('fs');
const path = require('path');

// ANSI color codes
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m'
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function runTests() {
  const results = [];
  const indexPath = path.join(__dirname, 'public', 'index.html');
  const publicPath = path.join(__dirname, 'public');

  // Test 1: Check Products dropdown link exists
  log('\n🧪 Running Dropdown Navigation Tests\n', 'blue');

  const indexContent = fs.readFileSync(indexPath, 'utf8');
  
  // Test 1: Products dropdown button exists
  log('Test 1: Products dropdown button exists', 'yellow');
  const hasDropdownBtn = indexContent.includes('class="dropdown-btn"');
  results.push({
    name: 'Products dropdown button exists',
    passed: hasDropdownBtn,
    details: hasDropdownBtn ? 'Found dropdown button' : 'Missing dropdown button'
  });

  // Test 2: Products menu links exist
  log('Test 2: Products menu exists with links', 'yellow');
  const hasDropdownMenu = indexContent.includes('class="dropdown-menu"');
  results.push({
    name: 'Products dropdown menu exists',
    passed: hasDropdownMenu,
    details: hasDropdownMenu ? 'Found dropdown menu' : 'Missing dropdown menu'
  });

  // Test 3: All linked product files exist
  log('Test 3: All product file links are valid', 'yellow');
  
  const productLinkRegex = /href="(\/product-[^"]+\.html)"/g;
  const matches = [...indexContent.matchAll(productLinkRegex)];
  const uniqueLinks = [...new Set(matches.map(m => m[1]))];
  
  let allFilesExist = true;
  const missingFiles = [];
  
  uniqueLinks.forEach(link => {
    const filename = link.replace('/', '');
    const filePath = path.join(publicPath, filename);
    if (!fs.existsSync(filePath)) {
      allFilesExist = false;
      missingFiles.push({ link, file: filename, exists: false });
    } else {
      missingFiles.push({ link, file: filename, exists: true });
    }
  });

  results.push({
    name: 'All product files exist',
    passed: allFilesExist,
    details: missingFiles.map(m => 
      `${m.exists ? '✓' : '✗'} ${m.link} → ${m.file}`
    ).join('\n    ')
  });

  // Test 4: orbitQA product page link is correct
  log('Test 4: orbitQA product link points to correct file', 'yellow');
  const orbitQALink = indexContent.match(/href="(\/product-orbitqa\.html)"/);
  const orbitQAFile = fs.existsSync(path.join(publicPath, 'product-orbitqa.html'));
  
  results.push({
    name: 'orbitQA product link is correct',
    passed: orbitQALink !== null && orbitQAFile,
    details: orbitQALink ? `Link found: ${orbitQALink[1]}` : 'No orbitQA link found',
    note: orbitQAFile ? 'File exists' : 'File missing - mismatch detected!'
  });

  // Test 5: Dropdown has proper CSS styling
  log('Test 5: Dropdown CSS styling is present', 'yellow');
  const hasDropdownCSS = indexContent.includes('.dropdown-menu {') && 
                         indexContent.includes('display: none');
  results.push({
    name: 'Dropdown CSS styling exists',
    passed: hasDropdownCSS,
    details: hasDropdownCSS ? 'CSS found' : 'CSS missing'
  });

  // Test 6: Hover behavior prevents menu from disappearing
  log('Test 6: Dropdown hover state handling', 'yellow');
  const hasPaddingBottom = indexContent.includes('padding-bottom');
  const hasZIndex = indexContent.includes('z-index');
  
  results.push({
    name: 'Dropdown has proper hover/z-index handling',
    passed: hasPaddingBottom && hasZIndex,
    details: `${hasPaddingBottom ? '✓' : '✗'} padding-bottom | ${hasZIndex ? '✓' : '✗'} z-index`
  });

  // Print results
  log('\n📊 Test Results\n', 'blue');
  
  let passCount = 0;
  let failCount = 0;
  
  results.forEach((result, idx) => {
    const status = result.passed ? '✅ PASS' : '❌ FAIL';
    const color = result.passed ? 'green' : 'red';
    
    log(`${idx + 1}. ${status} - ${result.name}`, color);
    
    if (result.details) {
      const detailLines = result.details.split('\n');
      detailLines.forEach(line => {
        log(`   ${line}`, result.passed ? 'green' : 'red');
      });
    }
    
    if (result.note) {
      log(`   ⚠️  ${result.note}`, 'yellow');
    }
    
    if (result.passed) passCount++;
    else failCount++;
    
    log('');
  });

  // Summary
  const totalTests = results.length;
  const percentage = Math.round((passCount / totalTests) * 100);
  
  log('═'.repeat(50), 'blue');
  log(`Total: ${totalTests} | Passed: ${passCount} | Failed: ${failCount} | ${percentage}%`, 
    failCount === 0 ? 'green' : 'red');
  log('═'.repeat(50), 'blue');

  return failCount === 0 ? 0 : 1;
}

process.exit(runTests());
