/**
 * Agent with RAG Mixin
 * Enhances agents with semantic retrieval capabilities
 */

const RAGVectorStore = require('./vector-store');
const EmbeddingsProvider = require('./embeddings');

class AgentWithRAG {
  constructor(baseAgent) {
    this.agent = baseAgent;
    this.vectorStore = new RAGVectorStore();
    this.embedder = new EmbeddingsProvider();
    this.ragEnabled = process.env.RAG_ENABLED === 'true';
    this.stats = {
      queriesWithRAG: 0,
      ragLatency: [],
      successfulRetrievals: 0,
      failedRetrievals: 0
    };
  }

  /**
   * Initialize RAG components
   */
  async initialize() {
    if (!this.ragEnabled) {
      console.log('⚠️  RAG disabled via RAG_ENABLED=false');
      return;
    }

    try {
      await this.vectorStore.initialize();
      console.log('✅ RAG initialized for agent');
    } catch (err) {
      console.warn(`⚠️  RAG initialization failed: ${err.message}`);
      this.ragEnabled = false;
    }
  }

  /**
   * Enhanced decision-making with RAG context
   */
  async decide(query) {
    const startTime = Date.now();

    // Get base decision
    let decision = await this.agent.decide(query);

    // Augment with RAG context if enabled
    if (this.ragEnabled) {
      try {
        const context = await this.getContextForQuery(query);

        if (context && context.length > 0) {
          decision = this.augmentDecisionWithContext(decision, context);
          this.stats.successfulRetrievals++;
        } else {
          this.stats.failedRetrievals++;
        }

        this.stats.queriesWithRAG++;
      } catch (err) {
        console.warn(`⚠️  RAG augmentation failed: ${err.message}`);
        this.stats.failedRetrievals++;
        // Return base decision without RAG
      }
    }

    const latency = Date.now() - startTime;
    this.stats.ragLatency.push(latency);

    return {
      ...decision,
      ragEnhanced: this.ragEnabled,
      latency
    };
  }

  /**
   * Retrieve context for query
   */
  async getContextForQuery(query) {
    try {
      // Embed the query
      const embedding = await this.embedder.embed(query);

      // Retrieve relevant documents
      const context = await this.vectorStore.retrieveContext(embedding, {
        topK: 5,
        scoreThreshold: 0.5
      });

      return context;
    } catch (err) {
      console.warn(`Failed to retrieve RAG context: ${err.message}`);
      return null;
    }
  }

  /**
   * Augment decision with retrieved context
   */
  augmentDecisionWithContext(baseDecision, context) {
    return {
      ...baseDecision,
      ragContext: context.map(c => ({
        source: c.source,
        relevance: (c.score * 100).toFixed(1) + '%',
        preview: c.content.substring(0, 200)
      })),
      decision: `${baseDecision.decision} [Based on analysis of relevant codebase context]`
    };
  }

  /**
   * Get RAG statistics
   */
  getRAGStats() {
    const latencies = this.stats.ragLatency;
    const avgLatency = latencies.length > 0
      ? (latencies.reduce((a, b) => a + b, 0) / latencies.length).toFixed(0)
      : 0;

    return {
      enabled: this.ragEnabled,
      queriesProcessed: this.stats.queriesWithRAG,
      successfulRetrievals: this.stats.successfulRetrievals,
      failedRetrievals: this.stats.failedRetrievals,
      averageLatency: `${avgLatency}ms`,
      vectorStoreStats: this.vectorStore.getStats(),
      embedderStats: this.embedder.getStats()
    };
  }
}

module.exports = AgentWithRAG;
