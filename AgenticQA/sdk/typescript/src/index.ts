/**
 * AgenticQA - Intelligent Autonomous QA Platform
 * TypeScript/JavaScript SDK
 */

import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';

interface TestData {
  [key: string]: unknown;
}

interface AgentResults {
  qa?: Record<string, unknown>;
  performance?: Record<string, unknown>;
  compliance?: Record<string, unknown>;
  devops?: Record<string, unknown>;
}

interface Artifact {
  id: string;
  timestamp: string;
  source: string;
  type: string;
  tags: string[];
  metadata: Record<string, unknown>;
  checksum: string;
}

interface DataStoreStats {
  total_artifacts: number;
  storage_size: number;
  oldest_artifact?: string;
  newest_artifact?: string;
}

interface Patterns {
  failure_patterns: Array<Record<string, unknown>>;
  performance_trends: Array<Record<string, unknown>>;
  flakiness_detection: Array<Record<string, unknown>>;
}

/**
 * Client for connecting to AgenticQA REST API
 */
export class AgenticQAClient {
  private client: AxiosInstance;
  private baseUrl: string;

  constructor(baseUrl: string = 'http://localhost:8000', timeout: number = 30000) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.client = axios.create({
      baseURL: this.baseUrl,
      timeout,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  /**
   * Execute all agents against test data
   */
  async executeAgents(testData: TestData): Promise<AgentResults> {
    const response = await this.client.post('/api/agents/execute', testData);
    return response.data;
  }

  /**
   * Get insights and recommendations from agents
   */
  async getAgentInsights(agentName?: string): Promise<Record<string, unknown>> {
    const config: AxiosRequestConfig = {};
    if (agentName) {
      config.params = { agent: agentName };
    }
    const response = await this.client.get('/api/agents/insights', config);
    return response.data;
  }

  /**
   * Get execution history for a specific agent
   */
  async getAgentHistory(agentName: string, limit: number = 50): Promise<Array<Record<string, unknown>>> {
    const response = await this.client.get(`/api/agents/${agentName}/history`, {
      params: { limit },
    });
    return response.data;
  }

  /**
   * Search test artifacts in the secure data store
   */
  async searchArtifacts(query: string, limit: number = 50): Promise<Artifact[]> {
    const response = await this.client.get('/api/datastore/search', {
      params: { q: query, limit },
    });
    return response.data;
  }

  /**
   * Retrieve a specific artifact from data store
   */
  async getArtifact(artifactId: string): Promise<Artifact> {
    const response = await this.client.get(`/api/datastore/artifact/${artifactId}`);
    return response.data;
  }

  /**
   * Get statistics about the data store
   */
  async getDatastoreStats(): Promise<DataStoreStats> {
    const response = await this.client.get('/api/datastore/stats');
    return response.data;
  }

  /**
   * Get detected patterns in historical agent data
   */
  async getPatterns(): Promise<Patterns> {
    const response = await this.client.get('/api/datastore/patterns');
    return response.data;
  }

  /**
   * Check if AgenticQA API server is healthy
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await this.client.get('/health', { timeout: 5000 });
      return response.status === 200;
    } catch {
      return false;
    }
  }

  /**
   * Set custom headers for all requests
   */
  setHeaders(headers: Record<string, string>): void {
    Object.assign(this.client.defaults.headers.common, headers);
  }

  /**
   * Set authentication token
   */
  setAuthToken(token: string): void {
    this.setHeaders({ Authorization: `Bearer ${token}` });
  }
}

export default AgenticQAClient;
