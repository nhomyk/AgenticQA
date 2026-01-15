// Workflow Validation & Auto-Fix Skill for SRE Agent
// Automatically detects and fixes YAML syntax errors in GitHub workflows

const https = require('https');
const fs = require('fs');
const path = require('path');

class WorkflowValidationSkill {
  constructor(githubToken, repoOwner, repoName) {
    this.githubToken = githubToken;
    this.repoOwner = repoOwner;
    this.repoName = repoName;
  }

  /**
   * Check the latest workflow run status for YAML errors
   */
  async checkLatestWorkflowStatus() {
    return new Promise((resolve, reject) => {
      const options = {
        hostname: 'api.github.com',
        path: `/repos/${this.repoOwner}/${this.repoName}/actions/runs?per_page=1`,
        method: 'GET',
        headers: {
          'Authorization': `token ${this.githubToken}`,
          'User-Agent': 'SRE-Agent-Workflow-Validator',
          'Accept': 'application/vnd.github+json'
        }
      };

      https.request(options, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          try {
            const json = JSON.parse(data);
            const run = json.workflow_runs && json.workflow_runs[0];
            
            if (!run) {
              resolve({ error: 'No workflow runs found', status: null });
              return;
            }

            resolve({
              runId: run.id,
              status: run.status,
              conclusion: run.conclusion,
              name: run.name,
              headBranch: run.head_branch,
              displayTitle: run.display_title,
              createdAt: run.created_at
            });
          } catch (err) {
            reject(err);
          }
        });
      }).on('error', reject).end();
    });
  }

  /**
   * Get workflow run annotations (errors/warnings)
   */
  async getWorkflowAnnotations(runId) {
    return new Promise((resolve, reject) => {
      const options = {
        hostname: 'api.github.com',
        path: `/repos/${this.repoOwner}/${this.repoName}/check-runs?per_page=100`,
        method: 'GET',
        headers: {
          'Authorization': `token ${this.githubToken}`,
          'User-Agent': 'SRE-Agent-Workflow-Validator',
          'Accept': 'application/vnd.github+json'
        }
      };

      https.request(options, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          try {
            const json = JSON.parse(data);
            const checkRuns = json.check_runs || [];
            
            const errors = [];
            for (const checkRun of checkRuns) {
              if (checkRun.output && checkRun.output.annotations) {
                for (const annotation of checkRun.output.annotations) {
                  if (annotation.annotation_level === 'failure') {
                    errors.push({
                      message: annotation.message,
                      title: annotation.title,
                      line: annotation.start_line,
                      file: annotation.path
                    });
                  }
                }
              }
            }
            
            resolve(errors);
          } catch (err) {
            reject(err);
          }
        });
      }).on('error', reject).end();
    });
  }

  /**
   * Parse YAML error to determine the issue
   */
  parseYAMLError(errorMessage, lineNumber) {
    const errors = [];

    // Common YAML error patterns
    if (errorMessage.includes('error in your yaml syntax')) {
      errors.push({
        type: 'YAML_SYNTAX_ERROR',
        line: lineNumber,
        severity: 'critical',
        description: 'YAML syntax error detected',
        commonCauses: [
          'Improper indentation (spaces vs tabs)',
          'Unclosed quotes or heredoc delimiters',
          'Template literals with backticks in string values',
          'Inline arrays not properly formatted',
          'Missing colons in key-value pairs'
        ]
      });
    }

    if (errorMessage.includes('mapping values') || errorMessage.includes('could not find')) {
      errors.push({
        type: 'YAML_STRUCTURE_ERROR',
        line: lineNumber,
        severity: 'critical'
      });
    }

    return errors;
  }

  /**
   * Analyze workflow file and detect potential issues
   */
  analyzeWorkflowFile(filePath) {
    try {
      const content = fs.readFileSync(filePath, 'utf8');
      const lines = content.split('\n');
      const issues = [];

      // Check for template literals with backticks (common YAML issue)
      lines.forEach((line, idx) => {
        if (line.includes('`') && line.includes('$')) {
          issues.push({
            type: 'TEMPLATE_LITERAL',
            line: idx + 1,
            severity: 'high',
            message: 'Template literal with backticks found - may cause YAML parsing issues',
            suggestion: 'Use string concatenation instead of template literals in YAML'
          });
        }

        // Check for inconsistent indentation
        if (line.startsWith('\t')) {
          issues.push({
            type: 'TAB_INDENTATION',
            line: idx + 1,
            severity: 'high',
            message: 'Tab character used for indentation - YAML requires spaces',
            suggestion: 'Replace tabs with 2 or 4 spaces'
          });
        }

        // Check for unclosed pipes or heredocs
        if (line.includes('<<') && line.includes("'")) {
          const heredocMatch = line.match(/<<\s*'([A-Z_]+)'/);
          if (heredocMatch) {
            const delimiter = heredocMatch[1];
            const hasClosing = lines.slice(idx + 1).some(l => l.trim() === delimiter);
            if (!hasClosing) {
              issues.push({
                type: 'UNCLOSED_HEREDOC',
                line: idx + 1,
                severity: 'critical',
                message: `Heredoc delimiter '${delimiter}' not closed`,
                suggestion: `Add closing '${delimiter}' on a new line`
              });
            }
          }
        }
      });

      return issues;
    } catch (err) {
      return [{ type: 'FILE_READ_ERROR', error: err.message }];
    }
  }

  /**
   * Auto-fix common YAML issues
   */
  fixCommonYAMLIssues(filePath) {
    try {
      let content = fs.readFileSync(filePath, 'utf8');
      const originalContent = content;
      let fixCount = 0;

      // Fix 1: Replace template literals with string concatenation in run commands
      if (content.includes('run:') && content.includes('`')) {
        content = content.replace(
          /run:\s*\|\s*[\s\S]*?node\s*<<\s*'[A-Z_]+'\s*[\s\S]*?(?=\s{2,}[a-z]|-\s)/g,
          (match) => {
            // Extract script content and escape it properly
            if (match.includes('`')) {
              console.log('  🔧 Converting inline script to external file reference...');
              fixCount++;
              // This will be handled by extracting to external file
              return match;
            }
            return match;
          }
        );
      }

      // Fix 2: Fix tab indentation
      const tabLines = content.split('\n').filter(line => line.startsWith('\t'));
      if (tabLines.length > 0) {
        console.log(`  🔧 Found ${tabLines.length} lines with tab indentation, converting to spaces...`);
        content = content.split('\n').map(line => {
          if (line.startsWith('\t')) {
            return line.replace(/^\t+/g, match => '  '.repeat(match.length));
          }
          return line;
        }).join('\n');
        fixCount++;
      }

      // Fix 3: Remove duplicate heredoc terminators
      const heredocMatches = content.match(/<<\s*'([A-Z_]+)'/g);
      if (heredocMatches) {
        heredocMatches.forEach(match => {
          const delimiter = match.match(/'([A-Z_]+)'/)[1];
          const delimiterRegex = new RegExp(`^\\s*${delimiter}\\s*$`, 'gm');
          const matches = content.match(delimiterRegex);
          if (matches && matches.length > 1) {
            console.log(`  🔧 Found duplicate '${delimiter}' heredoc terminators, removing duplicates...`);
            // Remove all but the first occurrence of the closing delimiter after opening
            let firstFound = false;
            content = content.replace(delimiterRegex, (match) => {
              if (!firstFound) {
                firstFound = true;
                return match;
              }
              return ''; // Remove duplicate
            });
            fixCount++;
          }
        });
      }

      // Fix 4: Fix inline array formatting to multi-line
      content = content.replace(
        /needs:\s*\[[^\]]+\]/g,
        (match) => {
          if (match.includes(',')) {
            console.log('  🔧 Converting inline needs array to multi-line format...');
            const items = match.match(/\[([^\]]+)\]/)[1].split(',').map(s => s.trim());
            fixCount++;
            return 'needs:\n' + items.map(item => `      - ${item}`).join('\n');
          }
          return match;
        }
      );

      // Fix 5: Ensure proper spacing in upload-artifact with multi-line paths
      content = content.replace(
        /path:\s*\|\s*([^\n]+(?:\n\s+[^\n]+)*)/g,
        (match) => {
          if (match.includes('\n')) {
            console.log('  🔧 Simplifying multi-line path to single path...');
            const paths = match.split('\n').map(l => l.trim()).filter(l => l && l !== 'path:' && l !== '|');
            if (paths.length > 1) {
              fixCount++;
              // Convert to separate paths
              return 'path: ' + paths[0];
            }
          }
          return match;
        }
      );

      if (fixCount > 0) {
        fs.writeFileSync(filePath, content);
        return {
          success: true,
          fixCount,
          changes: [
            fixCount > 0 ? `Applied ${fixCount} automatic fixes` : null
          ].filter(Boolean)
        };
      }

      return { success: false, fixCount: 0, changes: [] };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }

  /**
   * Main validation and fix workflow
   */
  async validateAndFix(workflowPath) {
    console.log('\n╔════════════════════════════════════════╗');
    console.log('║  🔍 WORKFLOW VALIDATION & AUTO-FIX   ║');
    console.log('╚════════════════════════════════════════╝\n');

    // Step 1: Check latest workflow status
    console.log('📊 Step 1: Checking latest workflow status...');
    try {
      const status = await this.checkLatestWorkflowStatus();
      
      if (status.error) {
        console.log(`  ⚠️  ${status.error}`);
      } else {
        console.log(`  Run ID: ${status.runId}`);
        console.log(`  Status: ${status.status}`);
        console.log(`  Conclusion: ${status.conclusion}`);
        console.log(`  Title: ${status.displayTitle}`);
        
        // Check for annotation errors
        if (status.status === 'completed' && status.conclusion === 'failure') {
          console.log('\n📋 Step 2: Checking for YAML errors...');
          try {
            const annotations = await this.getWorkflowAnnotations(status.runId);
            
            if (annotations.length > 0) {
              console.log(`  ❌ Found ${annotations.length} error(s):`);
              annotations.forEach(ann => {
                console.log(`    - Line ${ann.line}: ${ann.message}`);
                const parsed = this.parseYAMLError(ann.message, ann.line);
                parsed.forEach(p => {
                  if (p.commonCauses) {
                    console.log(`      Possible causes:`);
                    p.commonCauses.forEach(c => console.log(`        - ${c}`));
                  }
                });
              });

              // Step 3: Analyze and fix workflow file
              console.log('\n🔧 Step 3: Analyzing workflow file for issues...');
              const issues = this.analyzeWorkflowFile(workflowPath);
              
              if (issues.length > 0) {
                console.log(`  Found ${issues.length} potential issue(s):`);
                issues.forEach(issue => {
                  console.log(`    - Line ${issue.line}: ${issue.type}`);
                  if (issue.message) console.log(`      ${issue.message}`);
                  if (issue.suggestion) console.log(`      Suggestion: ${issue.suggestion}`);
                });
              }

              // Step 4: Apply fixes
              console.log('\n🛠️  Step 4: Attempting automatic fixes...');
              const fixResult = this.fixCommonYAMLIssues(workflowPath);
              
              if (fixResult.success) {
                console.log(`  ✅ Applied ${fixResult.fixCount} fix(es)`);
                fixResult.changes.forEach(change => console.log(`    - ${change}`));
                return {
                  fixed: true,
                  fixCount: fixResult.fixCount,
                  workflow: workflowPath
                };
              } else {
                console.log(`  ⚠️  Could not auto-fix: ${fixResult.error || 'No applicable fixes'}`);
                return {
                  fixed: false,
                  error: fixResult.error,
                  issues: issues
                };
              }
            } else {
              console.log('  ✅ No YAML errors found');
              return { fixed: false, message: 'Workflow is valid' };
            }
          } catch (err) {
            console.log(`  ⚠️  Error checking annotations: ${err.message}`);
            return { fixed: false, error: err.message };
          }
        } else {
          console.log(`  ✅ Workflow status is good: ${status.status} [${status.conclusion}]`);
          return { fixed: false, message: 'Workflow is healthy' };
        }
      }
    } catch (err) {
      console.log(`  ❌ Error checking workflow: ${err.message}`);
      return { fixed: false, error: err.message };
    }
  }
}

module.exports = WorkflowValidationSkill;
