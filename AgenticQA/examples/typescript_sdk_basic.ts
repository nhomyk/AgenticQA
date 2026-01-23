/**
 * TypeScript SDK Example 1: Basic Usage
 * 
 * This example shows how to use AgenticQA TypeScript SDK
 * in a Node.js or browser environment.
 */

import { AgenticQAClient } from 'agenticqa';

async function main() {
  // Create client connected to AgenticQA server
  const client = new AgenticQAClient('http://localhost:8000');

  // Check server health
  const isHealthy = await client.healthCheck();
  if (!isHealthy) {
    console.error('❌ AgenticQA server is not available');
    process.exit(1);
  }

  console.log('✅ Connected to AgenticQA server');

  // Test data
  const testData = {
    code: `
      function fibonacci(n) {
        if (n <= 1) return n;
        return fibonacci(n - 1) + fibonacci(n - 2);
      }
    `,
    tests: `
      describe('fibonacci', () => {
        test('should return 0 for n=0', () => expect(fibonacci(0)).toBe(0));
        test('should return 1 for n=1', () => expect(fibonacci(1)).toBe(1));
        test('should return 1 for n=2', () => expect(fibonacci(2)).toBe(1));
        test('should return 5 for n=5', () => expect(fibonacci(5)).toBe(5));
      });
    `,
  };

  // Execute agents
  console.log('\n🚀 Executing agents...');
  const results = await client.executeAgents(testData);

  console.log('\n📊 Agent Results:');
  console.log(`  QA Status: ${results.qa?.status || 'unknown'}`);
  console.log(`  Performance Status: ${results.performance?.status || 'unknown'}`);
  console.log(`  Compliance Status: ${results.compliance?.status || 'unknown'}`);
  console.log(`  DevOps Status: ${results.devops?.status || 'unknown'}`);

  // Get insights
  const insights = await client.getAgentInsights();
  console.log(`\n💡 Insights: ${Object.keys(insights).length} items`);

  // Get patterns
  const patterns = await client.getPatterns();
  console.log(`\n🎯 Patterns:`);
  console.log(`  Failure patterns: ${patterns.failure_patterns?.length || 0}`);
  console.log(`  Performance trends: ${patterns.performance_trends?.length || 0}`);
  console.log(`  Flaky tests: ${patterns.flakiness_detection?.length || 0}`);

  // Get datastore stats
  const stats = await client.getDatastoreStats();
  console.log(`\n📈 Data Store:`);
  console.log(`  Total artifacts: ${stats.total_artifacts}`);
  console.log(`  Storage size: ${stats.storage_size} bytes`);
}

main().catch(console.error);
