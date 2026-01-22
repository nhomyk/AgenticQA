/**
 * RAG Vector Store Integration
 * Manages embeddings and semantic retrieval for agent context
 * Supports Pinecone (cloud) and local Chroma fallback
 */

const fs = require('fs');
const path = require('path');

class RAGVectorStore {
  constructor(config = {}) {
    this.config = {
      provider: process.env.RAG_PROVIDER || 'chroma', // 'pinecone' or 'chroma'
      apiKey: process.env.PINECONE_API_KEY || '',
      indexName: process.env.PINECONE_INDEX || 'agenticqa',
      localPath: config.localPath || '.rag-index/chroma',
      topK: config.topK || 5,
      scoreThreshold: config.scoreThreshold || 0.5
    };

    this.initialized = false;
    this.localIndex = new Map(); // In-memory fallback
    this.stats = {
      totalDocuments: 0,
      lastIndexed: null,
      retrievals: 0,
      averageScore: 0
    };
  }

  /**
   * Initialize vector store (Pinecone or local)
   */
  async initialize() {
    console.log(`📊 Initializing RAG Vector Store (${this.config.provider})...`);

    if (this.config.provider === 'pinecone' && this.config.apiKey) {
      await this.initializePinecone();
    } else {
      await this.initializeLocal();
    }

    this.initialized = true;
    console.log('✅ RAG Vector Store ready');
  }

  /**
   * Initialize Pinecone cloud integration
   */
  async initializePinecone() {
    try {
      const { Pinecone } = require('@pinecone-database/pinecone');

      this.client = new Pinecone({ apiKey: this.config.apiKey });
      this.index = this.client.Index(this.config.indexName);

      // Verify connection
      const stats = await this.index.describeIndexStats();
      this.stats.totalDocuments = stats.totalRecordCount || 0;

      console.log(`✅ Connected to Pinecone index "${this.config.indexName}"`);
      console.log(`   Total documents: ${this.stats.totalDocuments}`);
    } catch (err) {
      console.warn('⚠️  Pinecone initialization failed, falling back to local storage');
      console.warn(`   Error: ${err.message}`);
      await this.initializeLocal();
    }
  }

  /**
   * Initialize local Chroma fallback
   */
  async initializeLocal() {
    if (!fs.existsSync(this.config.localPath)) {
      fs.mkdirSync(this.config.localPath, { recursive: true });
    }

    // Load existing index
    const indexFile = path.join(this.config.localPath, 'index.json');
    if (fs.existsSync(indexFile)) {
      const data = JSON.parse(fs.readFileSync(indexFile, 'utf8'));
      this.localIndex = new Map(data.index);
      this.stats.totalDocuments = data.count;
      this.stats.lastIndexed = data.lastIndexed;
    }

    console.log(`✅ Using local RAG index at ${this.config.localPath}`);
    console.log(`   Total documents: ${this.stats.totalDocuments}`);
  }

  /**
   * Store embeddings and metadata
   */
  async storeEmbeddings(documents, embeddings) {
    if (!this.initialized) {
      await this.initialize();
    }

    console.log(`\n📝 Storing ${documents.length} embeddings...`);

    if (this.config.provider === 'pinecone' && this.client) {
      await this.storePinecone(documents, embeddings);
    } else {
      await this.storeLocal(documents, embeddings);
    }

    this.stats.totalDocuments = documents.length;
    this.stats.lastIndexed = new Date().toISOString();
    console.log('✅ Embeddings stored successfully');
  }

  /**
   * Store in Pinecone
   */
  async storePinecone(documents, embeddings) {
    const vectors = documents.map((doc, i) => ({
      id: this.sanitizeId(doc.id),
      values: embeddings[i],
      metadata: {
        source: doc.source,
        type: doc.type,
        chunk: doc.chunk || 0,
        content: doc.content.substring(0, 1000) // Store preview
      }
    }));

    // Batch upsert (Pinecone has limits)
    const batchSize = 100;
    for (let i = 0; i < vectors.length; i += batchSize) {
      const batch = vectors.slice(i, i + batchSize);
      await this.index.upsert(batch);
      console.log(`  ✓ Upserted batch ${Math.floor(i / batchSize) + 1}`);
    }
  }

  /**
   * Store locally (development/fallback)
   */
  async storeLocal(documents, embeddings) {
    documents.forEach((doc, i) => {
      const id = this.sanitizeId(doc.id);
      this.localIndex.set(id, {
        embedding: embeddings[i],
        metadata: {
          source: doc.source,
          type: doc.type,
          chunk: doc.chunk || 0,
          content: doc.content
        }
      });
    });

    // Persist to disk
    const indexFile = path.join(this.config.localPath, 'index.json');
    fs.writeFileSync(
      indexFile,
      JSON.stringify({
        index: Array.from(this.localIndex.entries()),
        count: this.localIndex.size,
        lastIndexed: new Date().toISOString()
      }, null, 2)
    );
  }

  /**
   * Retrieve context via semantic search
   */
  async retrieveContext(queryEmbedding, topK = null, scoreThreshold = null) {
    if (!this.initialized) {
      await this.initialize();
    }

    topK = topK || this.config.topK;
    scoreThreshold = scoreThreshold !== null ? scoreThreshold : this.config.scoreThreshold;

    if (this.config.provider === 'pinecone' && this.client) {
      return this.retrievePinecone(queryEmbedding, topK, scoreThreshold);
    } else {
      return this.retrieveLocal(queryEmbedding, topK, scoreThreshold);
    }
  }

  /**
   * Retrieve from Pinecone
   */
  async retrievePinecone(queryEmbedding, topK, scoreThreshold) {
    const results = await this.index.query({
      vector: queryEmbedding,
      topK,
      includeMetadata: true
    });

    const matches = results.matches
      .filter(m => m.score >= scoreThreshold)
      .map(m => ({
        source: m.metadata.source,
        content: m.metadata.content,
        type: m.metadata.type,
        score: m.score,
        chunk: m.metadata.chunk
      }));

    this.recordRetrieval(matches);
    return matches;
  }

  /**
   * Retrieve from local index (simple cosine similarity)
   */
  retrieveLocal(queryEmbedding, topK, scoreThreshold) {
    const matches = [];

    for (const [id, data] of this.localIndex.entries()) {
      const score = this.cosineSimilarity(queryEmbedding, data.embedding);

      if (score >= scoreThreshold) {
        matches.push({
          id,
          source: data.metadata.source,
          content: data.metadata.content,
          type: data.metadata.type,
          score,
          chunk: data.metadata.chunk
        });
      }
    }

    // Sort by score and return top K
    matches.sort((a, b) => b.score - a.score);
    const results = matches.slice(0, topK);

    this.recordRetrieval(results);
    return results;
  }

  /**
   * Cosine similarity calculation
   */
  cosineSimilarity(a, b) {
    let dotProduct = 0;
    let normA = 0;
    let normB = 0;

    for (let i = 0; i < a.length; i++) {
      dotProduct += a[i] * b[i];
      normA += a[i] * a[i];
      normB += b[i] * b[i];
    }

    normA = Math.sqrt(normA);
    normB = Math.sqrt(normB);

    if (normA === 0 || normB === 0) return 0;
    return dotProduct / (normA * normB);
  }

  /**
   * Record retrieval statistics
   */
  recordRetrieval(matches) {
    this.stats.retrievals++;
    if (matches.length > 0) {
      const avgScore = matches.reduce((sum, m) => sum + m.score, 0) / matches.length;
      this.stats.averageScore = avgScore;
    }
  }

  /**
   * Sanitize IDs for storage
   */
  sanitizeId(id) {
    return id.replace(/[^a-zA-Z0-9_-]/g, '_').substring(0, 64);
  }

  /**
   * Get indexing statistics
   */
  getStats() {
    return {
      ...this.stats,
      provider: this.config.provider,
      initialized: this.initialized
    };
  }

  /**
   * Clear index
   */
  async clearIndex() {
    if (this.config.provider === 'pinecone' && this.client) {
      await this.index.deleteAll();
    } else {
      this.localIndex.clear();
      const indexFile = path.join(this.config.localPath, 'index.json');
      if (fs.existsSync(indexFile)) {
        fs.unlinkSync(indexFile);
      }
    }
    this.stats.totalDocuments = 0;
    console.log('✅ Index cleared');
  }
}

module.exports = RAGVectorStore;
