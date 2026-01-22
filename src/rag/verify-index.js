#!/usr/bin/env node

/**
 * RAG Index Verification
 * Validates index integrity and performs test retrieval
 */

const RAGVectorStore = require('./vector-store');
const EmbeddingsProvider = require('./embeddings');
const fs = require('fs');
const path = require('path');

async function verifyIndex() {
  console.log('\n╔════════════════════════════════════════╗');
  console.log('║      🔍 RAG Index Verification        ║');
  console.log('╚════════════════════════════════════════╝\n');

  try {
    // Load manifest
    const manifestPath = path.join('.rag-index', 'manifest.json');
    if (!fs.existsSync(manifestPath)) {
      throw new Error('Index manifest not found. Run indexing.js first.');
    }

    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));

    console.log('📋 Index Information:');
    console.log(`   Created: ${manifest.timestamp}`);
    console.log(`   Documents: ${manifest.statistics.documentsLoaded}`);
    console.log(`   Chunks: ${manifest.statistics.chunksCreated}`);
    console.log(`   Provider: ${manifest.statistics.vectorStoreProvider}`);
    console.log(`   Embedding Model: ${manifest.statistics.embeddingModel}`);
    console.log(`   Vector Dimension: ${manifest.statistics.vectorDimension}`);

    // Initialize vector store
    const vectorStore = new RAGVectorStore();
    await vectorStore.initialize();

    console.log(`\n✅ Vector store connected`);
    console.log(`   Total documents indexed: ${vectorStore.stats.totalDocuments}`);

    // Test retrieval
    console.log('\n🧪 Testing Retrieval...');
    console.log('─'.repeat(40));

    const testQueries = [
      'How do agents coordinate?',
      'What is data validation?',
      'Testing and compliance checks',
      'Error recovery and monitoring'
    ];

    const embedder = new EmbeddingsProvider();

    for (const query of testQueries) {
      const embedding = await embedder.embed(query);
      const results = await vectorStore.retrieveContext(embedding, 3, 0.3);

      console.log(`\n📌 Query: "${query}"`);
      console.log(`   Results: ${results.length} matches`);

      results.forEach((result, i) => {
        console.log(`\n   [${i + 1}] ${result.source}${result.chunk ? ` (chunk ${result.chunk})` : ''}`);
        console.log(`       Score: ${(result.score * 100).toFixed(1)}%`);
        console.log(`       Preview: ${result.content.substring(0, 100)}...`);
      });
    }

    // Stats
    console.log('\n\n📊 Verification Stats:');
    console.log(`   Retrievals: ${vectorStore.stats.retrievals}`);
    console.log(`   Average score: ${(vectorStore.stats.averageScore * 100).toFixed(1)}%`);

    console.log('\n✅ Index Verification Complete!');
    console.log('\n🚀 RAG is ready for use in agents');

    process.exit(0);
  } catch (err) {
    console.error('\n❌ Verification failed:');
    console.error(err.message);
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  verifyIndex();
}

module.exports = verifyIndex;
