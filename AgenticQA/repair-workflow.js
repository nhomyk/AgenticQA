/**
 * Emergency workflow repair stub.
 * Called by pipeline-rescue when YAML validation fails.
 * Logs the issue; human review required for structural YAML fixes.
 */
console.log('repair-workflow: invalid YAML detected — human review required.');
console.log('Check .github/workflows/ for syntax errors and fix manually.');
process.exit(0);
