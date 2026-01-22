#!/usr/bin/env node

/**
 * RAG Indexing Script
 * Loads codebase, chunks documents, embeds, and stores in vector DB
 */

const DocumentLoader = require('./document-loader');
const EmbeddingsProvider = require('./embeddings');
const RAGVectorStore = require('./vector-store');
const fs = require('fs');
const path = require('path');

async function indexCodebase() {
  console.log('\n╔════════════════════════════════════════╗');
  console.log('║         🤖 RAG Indexing Pipeline      ║');
  console.log('║   Loading & Embedding Codebase        ║');
  console.log('╚════════════════════════════════════════╝\n');

  try {
    // Step 1: Load documents
    const loader = new DocumentLoader({
      rootDir: process.cwd(),
      extensions: ['.js', '.md', '.json'],
      ignorePatterns: ['node_modules', '.git', 'coverage', '.rag-index']
    });

    console.log('\n📝 Step 1: Loading Documents');
    console.log('─'.repeat(40));
    const docs = await loader.loadCodebase();
    const chunkedDocs = loader.chunkDocuments(docs);

    // Step 2: Generate embeddings
    const embedder = new EmbeddingsProvider({
      provider: process.env.EMBEDDING_PROVIDER || 'mock',
      dimension: 1536
    });

    console.log('\n🔢 Step 2: Generating Embeddings');
    console.log('─'.repeat(40));
    const embeddings = await embedder.embedBatch(
      chunkedDocs.map(d => d.content)
    );

    console.log('\n📊 Embedding Stats:');
    console.log(`   Provider: ${embedder.config.provider}`);
    console.log(`   Model: ${embedder.config.model}`);
    console.log(`   Dimensions: ${embeddings[0]?.length || 'N/A'}`);
    console.log(`   Tokens used: ${embedder.stats.tokensUsed}`);
    console.log(`   Cost estimate: $${embedder.stats.costEstimate.toFixed(4)}`);

    // Step 3: Store embeddings
    const vectorStore = new RAGVectorStore({
      provider: process.env.RAG_PROVIDER || 'chroma'
    });

    console.log('\n💾 Step 3: Storing Embeddings');
    console.log('─'.repeat(40));
    await vectorStore.initialize();
    await vectorStore.storeEmbeddings(chunkedDocs, embeddings);

    // Step 4: Generate manifest
    console.log('\n📋 Step 4: Generating Index Manifest');
    console.log('─'.repeat(40));

    const manifest = {
      timestamp: new Date().toISOString(),
      rootDirectory: process.cwd(),
      statistics: {
        documentsLoaded: docs.length,
        chunksCreated: chunkedDocs.length,
        averageChunkSize: Math.round(
          chunkedDocs.reduce((sum, d) => sum + d.content.length, 0) / chunkedDocs.length
        ),
        embeddingModel: embedder.config.model,
        vectorDimension: embeddings[0]?.length || 0,
        vectorStoreProvider: vectorStore.config.provider,
        totalTokensUsed: embedder.stats.tokensUsed,
        estimatedCost: `$${embedder.stats.costEstimate.toFixed(4)}`
      },
      fileBreakdown: docs.reduce((acc, doc) => {
        const ext = doc.type;
        acc[ext] = (acc[ext] || 0) + 1;
        return acc;
      }, {}),
      vectorStoreStats: vectorStore.getStats(),
      indexReadyForRetrieval: true
    };

    const manifestPath = path.join('.rag-index', 'manifest.json');
    fs.mkdirSync('.rag-index', { recursive: true });
    fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));

    console.log('\n✅ Index manifest saved to .rag-index/manifest.json');

    // Step 5: Verification
    console.log('\n✅ RAG Indexing Complete!');
    console.log('\n📊 Summary:');
    console.log(`   ✓ Loaded ${docs.length} documents`);
    console.log(`   ✓ Created ${chunkedDocs.length} chunks`);
    console.log(`   ✓ Generated ${embeddings.length} embeddings`);
    console.log(`   ✓ Stored in ${vectorStore.config.provider}`);
    console.log(`   ✓ Ready for retrieval`);

    process.exit(0);
  } catch (err) {
    console.error('\n❌ Indexing failed:');
    console.error(err.message);
    console.error(err.stack);
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  indexCodebase();
}

module.exports = indexCodebase;
