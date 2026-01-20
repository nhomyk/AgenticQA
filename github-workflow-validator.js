/**
 * GitHub Workflow Validator
 * Prevents workflow trigger failures by validating parameters against actual workflow files
 * 
 * This diagnostic tool helps agents quickly identify and fix parameter mismatches
 */

const fs = require('fs');
const path = require('path');

class GitHubWorkflowValidator {
  constructor(token, owner, repo) {
    this.token = token;
    this.owner = owner;
    this.repo = repo;
  }

  /**
   * Get the actual workflow file from GitHub and parse its inputs
   */
  async getWorkflowInputs(workflowFilename) {
    try {
      console.log(`[Workflow Validator] Fetching workflow file: ${workflowFilename}`);
      
      const response = await fetch(
        `https://api.github.com/repos/${this.owner}/${this.repo}/contents/.github/workflows/${workflowFilename}`,
        {
          headers: {
            'Authorization': `token ${this.token}`,
            'Accept': 'application/vnd.github.v3.raw'
          }
        }
      );

      if (!response.ok) {
        throw new Error(`GitHub API returned ${response.status}`);
      }

      const content = await response.text();
      
      // Parse YAML to extract input parameters
      const inputs = this._parseWorkflowInputs(content);
      console.log(`[Workflow Validator] Found inputs in workflow:`, inputs);
      
      return inputs;
    } catch (error) {
      console.error(`[Workflow Validator] Error fetching workflow file:`, error.message);
      throw error;
    }
  }

  /**
   * Parse YAML workflow content to extract input parameter names
   */
  _parseWorkflowInputs(yamlContent) {
    const inputs = [];
    const lines = yamlContent.split('\n');
    
    let inInputsSection = false;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      
      // Check if we're entering the inputs section
      if (line.trim() === 'inputs:') {
        inInputsSection = true;
        continue;
      }
      
      // If we hit another top-level key (like 'jobs:'), we're done with inputs
      if (inInputsSection && line.match(/^[a-z_]+:/)) {
        break;
      }
      
      // Extract input names (they're indented under 'inputs:')
      if (inInputsSection && line.match(/^  [a-z_]+:/)) {
        const inputName = line.trim().replace(':', '').trim();
        inputs.push(inputName);
      }
    }
    
    return inputs;
  }

  /**
   * Validate that input parameters being sent are defined in the workflow
   * Returns: { valid: boolean, errors: string[], warnings: string[] }
   */
  async validateInputs(workflowFilename, inputsToSend) {
    const result = {
      valid: true,
      errors: [],
      warnings: [],
      expectedInputs: [],
      providedInputs: Object.keys(inputsToSend)
    };

    try {
      const workflowInputs = await this.getWorkflowInputs(workflowFilename);
      result.expectedInputs = workflowInputs;

      // Check if any provided inputs are NOT in the workflow
      for (const [key, value] of Object.entries(inputsToSend)) {
        if (!workflowInputs.includes(key)) {
          result.valid = false;
          result.errors.push(
            `Parameter '${key}' is not defined in workflow file. ` +
            `Expected one of: [${workflowInputs.join(', ')}]`
          );
        }
      }

      // Warn if required inputs are missing (optional check - add logic as needed)
      for (const expectedInput of workflowInputs) {
        if (!inputsToSend.hasOwnProperty(expectedInput)) {
          result.warnings.push(`Expected input '${expectedInput}' not provided`);
        }
      }

    } catch (error) {
      result.valid = false;
      result.errors.push(`Failed to validate workflow: ${error.message}`);
    }

    return result;
  }

  /**
   * Quick pre-flight check - run before triggering workflow
   * Throws an error if validation fails
   */
  async preflight(workflowFilename, inputsToSend) {
    const validation = await this.validateInputs(workflowFilename, inputsToSend);
    
    if (!validation.valid) {
      const errorMsg = `Workflow validation failed:\n${validation.errors.join('\n')}`;
      console.error(`[Workflow Validator] ${errorMsg}`);
      throw new Error(errorMsg);
    }

    if (validation.warnings.length > 0) {
      console.warn(`[Workflow Validator] Warnings:`, validation.warnings);
    }

    console.log(`[Workflow Validator] ✓ Validation passed. Ready to trigger workflow.`);
    return validation;
  }
}

module.exports = GitHubWorkflowValidator;
