/**
 * Embeddings Integration
 * Supports OpenAI, local models, and mock embeddings for testing
 */

const https = require('https');

class EmbeddingsProvider {
  constructor(config = {}) {
    this.config = {
      provider: process.env.EMBEDDING_PROVIDER || 'mock', // 'openai', 'local', 'mock'
      apiKey: process.env.OPENAI_API_KEY || '',
      model: process.env.EMBEDDING_MODEL || 'text-embedding-3-small',
      dimension: config.dimension || 1536,
      batchSize: config.batchSize || 10
    };

    this.stats = {
      tokensUsed: 0,
      costEstimate: 0,
      queriesProcessed: 0
    };
  }

  /**
   * Embed text using configured provider
   */
  async embed(text) {
    switch (this.config.provider) {
      case 'openai':
        return this.embedOpenAI(text);
      case 'local':
        return this.embedLocal(text);
      case 'mock':
      default:
        return this.embedMock(text);
    }
  }

  /**
   * Embed multiple texts (batch)
   */
  async embedBatch(texts) {
    const embeddings = [];

    for (let i = 0; i < texts.length; i += this.config.batchSize) {
      const batch = texts.slice(i, i + this.config.batchSize);

      for (const text of batch) {
        const embedding = await this.embed(text);
        embeddings.push(embedding);
      }

      console.log(`  ✓ Embedded batch ${Math.floor(i / this.config.batchSize) + 1}/${Math.ceil(texts.length / this.config.batchSize)}`);
    }

    return embeddings;
  }

  /**
   * OpenAI API embedding (production)
   */
  async embedOpenAI(text) {
    return new Promise((resolve, reject) => {
      const data = JSON.stringify({
        model: this.config.model,
        input: text
      });

      const options = {
        hostname: 'api.openai.com',
        path: '/v1/embeddings',
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.config.apiKey}`,
          'Content-Type': 'application/json',
          'Content-Length': data.length
        }
      };

      const req = https.request(options, (res) => {
        let responseData = '';

        res.on('data', chunk => {
          responseData += chunk;
        });

        res.on('end', () => {
          try {
            const parsed = JSON.parse(responseData);

            if (parsed.error) {
              reject(new Error(`OpenAI API error: ${parsed.error.message}`));
            } else {
              const embedding = parsed.data[0].embedding;
              this.recordUsage(parsed.usage);
              resolve(embedding);
            }
          } catch (err) {
            reject(err);
          }
        });
      });

      req.on('error', reject);
      req.write(data);
      req.end();
    });
  }

  /**
   * Local embedding model (mock - replace with actual implementation)
   */
  async embedLocal(text) {
    // In production, you'd use something like:
    // const { pipeline } = require('@xenova/transformers');
    // const extractor = await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2');
    // const result = await extractor(text, { pooling: 'mean', normalize: true });
    // return result.data;

    console.warn('⚠️  Local embeddings not fully implemented, using mock');
    return this.embedMock(text);
  }

  /**
   * Mock embedding (for testing/development)
   * Deterministic based on text hash
   */
  embedMock(text) {
    // Create deterministic embedding based on text
    const hash = this.hashString(text);
    const embedding = [];

    for (let i = 0; i < this.config.dimension; i++) {
      // Pseudo-random but deterministic
      const seed = (hash + i) * 16807 % 2147483647;
      embedding.push((seed / 2147483647) * 2 - 1); // Normalize to [-1, 1]
    }

    // Normalize to unit vector
    const norm = Math.sqrt(embedding.reduce((sum, val) => sum + val * val, 0));
    return embedding.map(val => val / norm);
  }

  /**
   * Simple hash function for text
   */
  hashString(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash);
  }

  /**
   * Record API usage for cost tracking
   */
  recordUsage(usage) {
    if (usage && usage.total_tokens) {
      this.stats.tokensUsed += usage.total_tokens;
      // Rough estimate: $0.02 per 1M tokens for text-embedding-3-small
      this.stats.costEstimate = (this.stats.tokensUsed / 1000000) * 0.02;
    }
    this.stats.queriesProcessed++;
  }

  /**
   * Get usage statistics
   */
  getStats() {
    return {
      ...this.stats,
      provider: this.config.provider,
      model: this.config.model
    };
  }
}

module.exports = EmbeddingsProvider;
