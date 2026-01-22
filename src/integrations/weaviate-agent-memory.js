/**
 * Weaviate Semantic Agent Memory Integration
 * 
 * Provides semantic search and context retrieval for agent decision-making
 * Features:
 * - Agent memory persistence
 * - Context-aware decision making
 * - Compliance pattern recognition
 * - Semantic similarity search
 */

const weaviate = require('weaviate-ts-client');

class WeaviateAgentMemory {
  constructor(host = process.env.WEAVIATE_HOST || 'http://localhost:8080') {
    this.host = host;
    this.client = null;
    this.initialized = false;
  }

  async init() {
    try {
      this.client = weaviate.client({
        scheme: this.host.includes('https') ? 'https' : 'http',
        host: this.host.replace(/^https?:\/\//, '').split(':')[0],
        port: parseInt(this.host.split(':')[2]) || 8080
      });
      
      // Test connection
      const ready = await this.client.misc.readyChecker().do();
      this.initialized = true;
      console.log('✅ Weaviate Semantic Memory initialized');
      return true;
    } catch (error) {
      console.warn('⚠️ Weaviate not available (optional): ', error.message);
      return false;
    }
  }

  async storeAgentMemory(agentId, memoryType, content, metadata = {}) {
    if (!this.initialized || !this.client) return null;
    
    try {
      const className = 'AgentMemory';
      
      // Ensure class exists
      await this.ensureClass(className);
      
      const dataObject = {
        agentId,
        memoryType,
        content,
        metadata: JSON.stringify(metadata),
        timestamp: new Date().toISOString()
      };
      
      const response = await this.client.data
        .create()
        .withClassName(className)
        .withProperties(dataObject)
        .do();
      
      console.log(`✓ Agent memory stored: ${agentId} (${memoryType})`);
      return response.id;
    } catch (error) {
      console.error(`✗ Error storing agent memory: ${error.message}`);
      return null;
    }
  }

  async storeCompliancePattern(patternId, standard, description, examples = []) {
    if (!this.initialized || !this.client) return null;
    
    try {
      const className = 'CompliancePattern';
      
      // Ensure class exists
      await this.ensureClass(className);
      
      const dataObject = {
        patternId,
        standard,
        description,
        examples: JSON.stringify(examples),
        timestamp: new Date().toISOString()
      };
      
      const response = await this.client.data
        .create()
        .withClassName(className)
        .withProperties(dataObject)
        .do();
      
      console.log(`✓ Compliance pattern stored: ${patternId} (${standard})`);
      return response.id;
    } catch (error) {
      console.error(`✗ Error storing compliance pattern: ${error.message}`);
      return null;
    }
  }

  async searchSimilarMemories(query, agentId, limit = 5) {
    if (!this.initialized || !this.client) return [];
    
    try {
      const className = 'AgentMemory';
      const results = await this.client.graphql
        .get()
        .withClassName(className)
        .withWhere({
          path: ['agentId'],
          operator: 'Equal',
          valueString: agentId
        })
        .withNearText({
          concepts: [query]
        })
        .withLimit(limit)
        .withFields(['agentId', 'memoryType', 'content', 'metadata'])
        .do();
      
      return results.data?.Get?.[className] || [];
    } catch (error) {
      console.error(`✗ Error searching memories: ${error.message}`);
      return [];
    }
  }

  async findCompliancePatternsForStandard(standard, limit = 10) {
    if (!this.initialized || !this.client) return [];
    
    try {
      const className = 'CompliancePattern';
      const results = await this.client.graphql
        .get()
        .withClassName(className)
        .withWhere({
          path: ['standard'],
          operator: 'Equal',
          valueString: standard
        })
        .withLimit(limit)
        .withFields(['patternId', 'standard', 'description', 'examples'])
        .do();
      
      return results.data?.Get?.[className] || [];
    } catch (error) {
      console.error(`✗ Error finding compliance patterns: ${error.message}`);
      return [];
    }
  }

  async getAgentContextWindow(agentId, limit = 10) {
    if (!this.initialized || !this.client) return [];
    
    try {
      const className = 'AgentMemory';
      const results = await this.client.graphql
        .get()
        .withClassName(className)
        .withWhere({
          path: ['agentId'],
          operator: 'Equal',
          valueString: agentId
        })
        .withSort({
          path: ['timestamp'],
          order: 'desc'
        })
        .withLimit(limit)
        .withFields(['memoryType', 'content', 'metadata', 'timestamp'])
        .do();
      
      return results.data?.Get?.[className] || [];
    } catch (error) {
      console.error(`✗ Error retrieving context window: ${error.message}`);
      return [];
    }
  }

  async ensureClass(className) {
    if (!this.client) return false;
    
    try {
      // Check if class exists
      const schema = await this.client.schema.getter().do();
      const classExists = schema.classes?.some(c => c.class === className);
      
      if (!classExists) {
        const classObj = {
          class: className,
          description: `${className} for AgenticQA agent memory and patterns`,
          properties: [
            {
              name: 'content',
              dataType: ['text'],
              description: 'Main content or memory data'
            },
            {
              name: 'metadata',
              dataType: ['text'],
              description: 'JSON metadata associated with content'
            },
            {
              name: 'timestamp',
              dataType: ['date'],
              description: 'Creation timestamp'
            }
          ]
        };
        
        await this.client.schema.classCreator().withClass(classObj).do();
        console.log(`✓ Weaviate class created: ${className}`);
      }
      return true;
    } catch (error) {
      console.warn(`⚠️ Could not ensure class ${className}: ${error.message}`);
      return false;
    }
  }
}

module.exports = WeaviateAgentMemory;
