/**
 * SRE Agent - Syntax & Parsing Error Recovery Module
 * Detects and automatically fixes common JavaScript syntax errors
 * Ensures pipeline can self-heal from parsing issues
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class SyntaxErrorRecovery {
  constructor() {
    this.fixes = [];
    this.errors = [];
  }

  /**
   * Main entry point: detect and fix syntax errors
   */
  async fixSyntaxErrors() {
    console.log('\n🔧 SRE AGENT - SYNTAX ERROR RECOVERY MODE\n');
    
    try {
      // Step 1: Get linting errors
      const lintErrors = this.getLintingErrors();
      
      if (lintErrors.length === 0) {
        console.log('✅ No linting errors detected');
        return { success: true, fixed: 0, errors: [] };
      }
      
      console.log(`🔴 Found ${lintErrors.length} linting/syntax errors\n`);
      
      // Step 2: Categorize and fix errors
      for (const error of lintErrors) {
        console.log(`🔍 Analyzing: ${error.file}:${error.line}\n   ${error.message}\n`);
        await this.fixError(error);
      }
      
      // Step 3: Verify fixes
      console.log('\n✅ VERIFICATION: Re-running linter...\n');
      const remainingErrors = this.getLintingErrors();
      
      if (remainingErrors.length === 0) {
        console.log('✅ All syntax errors fixed successfully!\n');
        return { success: true, fixed: this.fixes.length, errors: [] };
      } else {
        console.log(`⚠️ ${remainingErrors.length} errors remain after fixes\n`);
        return { success: false, fixed: this.fixes.length, remaining: remainingErrors.length };
      }
    } catch (error) {
      console.error('❌ Syntax recovery failed:', error.message);
      return { success: false, error: error.message };
    }
  }

  /**
   * Get all linting/syntax errors in JSON format
   */
  getLintingErrors() {
    try {
      const output = execSync('npx eslint . --ext .js --format json 2>&1', {
        encoding: 'utf8',
        stdio: ['pipe', 'pipe', 'pipe']
      });
      
      const results = JSON.parse(output || '[]');
      const errors = [];
      
      results.forEach(file => {
        if (file.messages.length > 0) {
          file.messages.forEach(msg => {
            errors.push({
              file: file.filePath,
              line: msg.line,
              column: msg.column,
              message: msg.message,
              rule: msg.ruleId,
              severity: msg.severity
            });
          });
        }
      });
      
      return errors;
    } catch (e) {
      // Linter might fail to parse - try alternative detection
      return this.detectSyntaxErrorsManually();
    }
  }

  /**
   * Manual syntax error detection (when linter can't parse file)
   */
  detectSyntaxErrorsManually() {
    console.log('⚠️ ESLint parser failed - attempting manual syntax detection...\n');
    
    const errors = [];
    const jsFiles = execSync('find . -name "*.js" -not -path "./node_modules/*"', {
      encoding: 'utf8'
    }).split('\n').filter(f => f);
    
    jsFiles.forEach(file => {
      try {
        const content = fs.readFileSync(file, 'utf8');
        const lines = content.split('\n');
        
        lines.forEach((line, idx) => {
          const lineNum = idx + 1;
          
          // Check for common syntax errors
          if (this.hasSyntaxError(line, lines, idx)) {
            errors.push({
              file,
              line: lineNum,
              column: 1,
              message: `Syntax error detected`,
              category: 'syntax'
            });
          }
        });
      } catch (e) {
        // Skip files that can't be read
      }
    });
    
    return errors;
  }

  /**
   * Detect common syntax error patterns
   */
  hasSyntaxError(line, allLines, lineIdx) {
    // Pattern 1: Invalid property assignment to built-in objects
    if (/^const\s+\w+\.\w+\s*=/.test(line) || /^let\s+\w+\.\w+\s*=/.test(line)) {
      return true; // Math.random_seed = ... is invalid
    }
    
    // Pattern 2: Unclosed brackets/parentheses
    const openBrackets = (line.match(/\{/g) || []).length;
    const closeBrackets = (line.match(/\}/g) || []).length;
    if (openBrackets !== closeBrackets && line.trim() && !line.trim().startsWith('//')) {
      return true;
    }
    
    // Pattern 3: Missing semicolons in specific contexts
    if (line.includes('import ') && !line.endsWith(';') && !line.includes('from')) {
      return true;
    }
    
    return false;
  }

  /**
   * Fix individual syntax errors
   */
  async fixError(error) {
    const content = fs.readFileSync(error.file, 'utf8');
    const lines = content.split('\n');
    const lineContent = lines[error.line - 1];
    
    let fixed = false;
    let newContent = content;
    
    // FIX 1: Invalid property assignment to built-in objects
    // Convert: const Math.random_seed = Math.random()
    // To:      const randomSeed = Math.random()
    if (/^const\s+(\w+)\.(\w+)\s*=/.test(lineContent)) {
      console.log(`  📌 FIX TYPE: Invalid property assignment to built-in\n`);
      newContent = this.fixInvalidPropertyAssignment(newContent, error.line - 1);
      fixed = true;
    }
    
    // FIX 2: Unclosed brackets
    else if (error.message && error.message.includes('Unexpected token')) {
      console.log(`  📌 FIX TYPE: Parsing error - attempting bracket/syntax fix\n`);
      newContent = this.fixParsingError(newContent, error.file, error.line - 1);
      fixed = true;
    }
    
    // FIX 3: Missing commas in object/array literals
    else if (error.message && error.message.includes('Expected')) {
      console.log(`  📌 FIX TYPE: Missing comma or syntax element\n`);
      newContent = this.fixMissingElements(newContent, error.line - 1);
      fixed = true;
    }
    
    // Write fixed content
    if (fixed && newContent !== content) {
      fs.writeFileSync(error.file, newContent);
      console.log(`  ✅ Fixed: ${error.file}:${error.line}\n`);
      this.fixes.push(error);
    } else {
      console.log(`  ⚠️ Could not auto-fix this error\n`);
      this.errors.push(error);
    }
  }

  /**
   * Fix: Invalid property assignment to built-in objects
   * const Math.prop = value → const mathProp = value
   */
  fixInvalidPropertyAssignment(content, lineIdx) {
    const lines = content.split('\n');
    const line = lines[lineIdx];
    
    // Extract: const Math.random_seed = Math.random()
    const match = line.match(/^(const|let)\s+(\w+)\.(\w+)\s*=/);
    if (!match) return content;
    
    const [fullMatch, keyword, builtIn, prop] = match;
    
    // Convert to camelCase: random_seed → randomSeed
    const newProp = prop.replace(/_([a-z])/g, (g) => g[1].toUpperCase());
    const newVar = builtIn.toLowerCase() + newProp.charAt(0).toUpperCase() + newProp.slice(1);
    
    lines[lineIdx] = line.replace(fullMatch, `${keyword} ${newVar} =`);
    return lines.join('\n');
  }

  /**
   * Fix: Parsing errors from unclosed brackets, etc.
   */
  fixParsingError(content, file, lineIdx) {
    const lines = content.split('\n');
    const line = lines[lineIdx];
    
    // Check for unclosed brackets/parens
    let opens = 0;
    for (let i = 0; i < line.length; i++) {
      if (line[i] === '{' || line[i] === '[' || line[i] === '(') opens++;
      if (line[i] === '}' || line[i] === ']' || line[i] === ')') opens--;
    }
    
    // Add closing brackets if needed
    if (opens > 0) {
      lines[lineIdx] = line + '}'.repeat(opens);
    }
    
    return lines.join('\n');
  }

  /**
   * Fix: Missing commas in object/array literals
   */
  fixMissingElements(content, lineIdx) {
    const lines = content.split('\n');
    const line = lines[lineIdx];
    
    // Check if line ends without comma when it should
    if (line.includes(':') && !line.trim().endsWith(',') && !line.trim().endsWith('{') && !line.trim().endsWith('}')) {
      lines[lineIdx] = line + ',';
    }
    
    return lines.join('\n');
  }

  /**
   * Fix: Import/require issues
   */
  async fixImportIssues(content) {
    // Find all require() calls
    const requireMatches = content.match(/require\(['"][^'"]+['"]\)/g) || [];
    
    for (const req of requireMatches) {
      const moduleName = req.match(/['"]([^'"]+)['"]/)[1];
      
      // Check if module exists
      try {
        require.resolve(moduleName);
      } catch (e) {
        console.log(`  ⚠️ Missing module: ${moduleName}`);
        // Attempt to install
        try {
          execSync(`npm install ${moduleName}`, { stdio: 'inherit' });
          console.log(`  ✅ Installed: ${moduleName}`);
        } catch (installError) {
          console.log(`  ❌ Failed to install: ${moduleName}`);
        }
      }
    }
    
    return content;
  }
}

/**
 * Export for use in SRE agent
 */
module.exports = SyntaxErrorRecovery;

// Standalone execution
if (require.main === module) {
  const recovery = new SyntaxErrorRecovery();
  recovery.fixSyntaxErrors().then(result => {
    console.log('\n📊 SUMMARY:');
    console.log(`  ✅ Fixed: ${result.fixed}`);
    console.log(`  ❌ Failed: ${result.errors.length}`);
    process.exit(result.success ? 0 : 1);
  });
}
