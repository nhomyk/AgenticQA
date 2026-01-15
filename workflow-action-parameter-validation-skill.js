/**
 * Workflow Action Parameter Validation Skill
 * Detects and fixes common GitHub Actions parameter errors
 * - Detects 'continue-on-error' used as action parameter instead of step property
 * - Detects invalid parameters for specific actions
 * - Fixes indentation and parameter placement
 */

module.exports = {
  name: 'Workflow Action Parameter Validation',
  version: '1.0.0',

  /**
   * Known valid parameters for common GitHub Actions
   */
  actionParameters: {
    'actions/upload-artifact@v4': ['name', 'path', 'if-no-files-found', 'retention-days', 'compression-level', 'overwrite', 'include-hidden-files'],
    'actions/download-artifact@v4': ['name', 'artifact-ids', 'path', 'pattern', 'merge-multiple', 'github-token', 'repository', 'run-id'],
    'actions/setup-node@v4': ['node-version', 'cache', 'cache-dependency-path', 'architecture', 'check-latest'],
    'actions/checkout@v4': ['repository', 'ref', 'token', 'ssh-key', 'ssh-known-hosts', 'ssh-strict', 'persist-credentials', 'clean', 'fetch-depth', 'lfs', 'submodules', 'set-safe-directory']
  },

  /**
   * Step-level properties that should not be action parameters
   */
  stepProperties: ['if', 'continue-on-error', 'timeout-minutes', 'env', 'defaults', 'name', 'run', 'shell', 'working-directory', 'id'],

  /**
   * Detect invalid parameters in workflow YAML
   */
  detectErrors(yamlContent) {
    const errors = [];
    const lines = yamlContent.split('\n');

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      // Check for 'uses:' lines (action invocations)
      if (line.match(/^\s+- uses:/)) {
        const usesMatch = line.match(/uses:\s*([\w\/@\.-]+@[\w\.-]+)/);
        if (!usesMatch) continue;

        const actionName = usesMatch[1];
        const validParams = this.actionParameters[actionName];

        // If we know this action, check for invalid parameters in the 'with:' block
        if (validParams) {
          let j = i + 1;
          let inWithBlock = false;
          const baseIndent = line.match(/^(\s+)/)[1].length;

          while (j < lines.length) {
            const nextLine = lines[j];
            const nextIndent = nextLine.match(/^(\s*)/)[1].length;

            // If indentation drops to or below base level, we've left the action
            if (nextLine.trim() && nextIndent <= baseIndent) break;

            // Found 'with:' block
            if (nextLine.match(/^\s+with:/)) {
              inWithBlock = true;
              j++;
              continue;
            }

            // If we're in the with block, check parameters
            if (inWithBlock && nextLine.trim()) {
              const paramMatch = nextLine.match(/^\s+(\w+):/);
              if (paramMatch) {
                const param = paramMatch[1];

                // Check if it's a step-level property used as action parameter
                if (this.stepProperties.includes(param) && !validParams.includes(param)) {
                  errors.push({
                    line: j + 1,
                    error: `Invalid parameter "${param}" for action "${actionName}" - should be at step level, not in "with:" block`,
                    action: actionName,
                    parameter: param,
                    severity: 'error',
                    fix: `Move "${param}" outside of the "with:" block to the step level`
                  });
                }
              }
            }

            j++;
          }
        }
      }
    }

    return errors;
  },

  /**
   * Fix invalid parameters by moving them to step level
   */
  fixErrors(yamlContent) {
    let fixed = yamlContent;
    const lines = fixed.split('\n');
    let modified = false;

    // Fix 1: Move 'continue-on-error' from within 'with:' blocks to step level
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      // Look for action parameters that should be step-level
      if (line.match(/^\s+continue-on-error:/)) {
        // Check if it's indented as an action parameter (nested in 'with:')
        const indent = line.match(/^(\s+)/)[1];
        
        // Look backwards to find if we're in a 'with:' block
        let j = i - 1;
        let inWith = false;
        
        while (j >= 0 && lines[j].match(/^(\s+)/)) {
          const prevIndent = lines[j].match(/^(\s+)/)[1];
          if (prevIndent.length < indent.length) {
            if (lines[j].match(/^\s+with:$/)) {
              inWith = true;
              // We're inside a 'with:' block - this is wrong
              // Move it to step level (same indent as 'uses:')
              const stepIndent = prevIndent; // Same as 'with:'
              const parentIndent = lines[j - 1] ? lines[j - 1].match(/^(\s+)/)[1] : '      ';
              
              // Remove this line
              lines.splice(i, 1);
              
              // Add it after the closing of the action block (after all the 'with:' content)
              let k = i;
              while (k < lines.length) {
                const nextLine = lines[k];
                if (nextLine.trim() && !nextLine.match(/^\s{' '.repeat(indent.length)}/) && nextLine.match(/^(\s+)/) && lines[k].match(/^(\s+)/)[1].length <= parentIndent.length) {
                  break;
                }
                k++;
              }
              
              // Insert continue-on-error at step level
              lines.splice(i, 0, parentIndent + 'continue-on-error: true');
              modified = true;
              break;
            }
            break;
          }
          j--;
        }
      }
    }

    // Fix 2: Use regex for a more reliable fix
    // Pattern: (\s+)with:\n(\s+)name/path/retention-days etc\n(\s+)continue-on-error:
    // Should become: (\s+)with:\n(\s+)name/path etc\n(\s+)continue-on-error:
    // (at the same level as the action 'uses:', not nested)

    fixed = fixed.replace(/(\s+)with:\n((?:\s+\w+:.*\n)*)\s+continue-on-error:\s*(true|false)/g, (match, indent, content, value) => {
      // Check what indent level we should use for continue-on-error
      const parentIndent = indent.slice(0, -2); // Remove 2 spaces to get action-level indent
      return indent + 'with:\n' + content + parentIndent + 'continue-on-error: ' + value;
    });

    // Fix 3: More direct approach - find upload-artifact/download-artifact with continue-on-error in with
    fixed = fixed.replace(/(\s+)with:\n(\s+name:|[ \t]*\n)+(\s+)continue-on-error:/gm, (match, baseIndent, nameSection, indent) => {
      const stepLevelIndent = baseIndent.slice(0, -2);
      const withIndent = baseIndent;
      // Reconstruct: 'with:' block, then step-level 'continue-on-error'
      const withContent = match.split('\n').slice(1, -1).join('\n'); // Everything except first and last line
      return baseIndent + 'with:\n' + withContent + '\n' + stepLevelIndent + 'continue-on-error:';
    });

    // Fix 4: Simpler approach - move 'continue-on-error' that appears after 'with:' properties
    // Pattern: "        with:\n          name: xxx\n          retention-days: 30\n          continue-on-error: true"
    // Should become: "        with:\n          name: xxx\n          retention-days: 30\n        continue-on-error: true"
    const lines2 = fixed.split('\n');
    for (let i = 0; i < lines2.length; i++) {
      if (lines2[i].match(/^\s+continue-on-error:/)) {
        const currentIndent = lines2[i].match(/^(\s+)/)[1].length;
        
        // Look back to find the 'with:' line
        let withIndex = -1;
        for (let j = i - 1; j >= 0; j--) {
          const checkIndent = lines2[j].match(/^(\s+)/)[1].length;
          if (checkIndent < currentIndent) {
            if (lines2[j].match(/^\s+with:\s*$/)) {
              withIndex = j;
              const withIndent = lines2[j].match(/^(\s+)/)[1].length;
              const stepIndent = withIndent - 2; // Go back to step level
              if (currentIndent > withIndent) {
                // continue-on-error is indented more than 'with:', so it's inside the with block
                lines2[i] = ' '.repeat(withIndent) + 'continue-on-error: true';
              }
            }
            break;
          }
        }
      }
    }
    fixed = lines2.join('\n');

    return { fixed, modified: modified || fixed !== yamlContent };
  },

  /**
   * Generate a report of all errors found
   */
  generateReport(errors) {
    if (errors.length === 0) {
      return '✅ No action parameter errors found';
    }

    let report = `⚠️ Found ${errors.length} action parameter error(s):\n\n`;
    errors.forEach((err, idx) => {
      report += `${idx + 1}. Line ${err.line}: ${err.error}\n`;
      report += `   Action: ${err.action}\n`;
      report += `   Parameter: ${err.parameter}\n`;
      report += `   Fix: ${err.fix}\n\n`;
    });

    return report;
  }
};
