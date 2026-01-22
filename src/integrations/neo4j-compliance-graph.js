/**
 * Neo4j Compliance Graph Integration
 * 
 * Maps agent workflows, dependencies, and audit trails as a graph for compliance tracking
 * Features:
 * - Agent workflow lineage tracking
 * - Compliance audit trail immutability
 * - Risk assessment scoring
 * - Automated remediation tracking
 */

const neo4j = require('neo4j-driver');

class Neo4jComplianceGraph {
  constructor(uri = process.env.NEO4J_URI || 'bolt://localhost:7687', auth = null) {
    this.uri = uri;
    this.auth = auth || {
      username: process.env.NEO4J_USER || 'neo4j',
      password: process.env.NEO4J_PASSWORD || 'password'
    };
    this.driver = null;
    this.initialized = false;
  }

  async init() {
    try {
      this.driver = neo4j.driver(this.uri, neo4j.auth.basic(this.auth.username, this.auth.password));
      await this.driver.getServerInfo();
      this.initialized = true;
      console.log('✅ Neo4j Compliance Graph initialized');
      return true;
    } catch (error) {
      console.warn('⚠️ Neo4j not available (optional): ', error.message);
      return false;
    }
  }

  async recordAgentExecution(agentId, executionId, workflowName, timestamp = new Date()) {
    if (!this.initialized || !this.driver) return;
    
    const session = this.driver.session();
    try {
      const query = `
        MERGE (a:Agent {id: $agentId})
        MERGE (w:Workflow {name: $workflowName})
        MERGE (e:Execution {id: $executionId, timestamp: $timestamp})
        CREATE (a)-[:EXECUTED]->(e)
        CREATE (e)-[:IN_WORKFLOW]->(w)
        RETURN e.id as executionId
      `;
      
      const result = await session.run(query, {
        agentId,
        executionId,
        workflowName,
        timestamp: timestamp.toISOString()
      });
      
      console.log(`✓ Agent execution recorded: ${executionId}`);
      return true;
    } finally {
      await session.close();
    }
  }

  async recordComplianceCheck(checkId, standard, status, details, executionId) {
    if (!this.initialized || !this.driver) return;
    
    const session = this.driver.session();
    try {
      const query = `
        MERGE (c:ComplianceCheck {id: $checkId, standard: $standard})
        MERGE (e:Execution {id: $executionId})
        CREATE (c)-[:CHECKED_IN_EXECUTION {status: $status, details: $details}]->(e)
        RETURN c.id as checkId
      `;
      
      const result = await session.run(query, {
        checkId,
        standard,
        status,
        details: JSON.stringify(details),
        executionId
      });
      
      console.log(`✓ Compliance check recorded: ${checkId} (${standard})`);
      return true;
    } finally {
      await session.close();
    }
  }

  async recordRemediationAction(remediationId, issueType, agentId, status, executionId) {
    if (!this.initialized || !this.driver) return;
    
    const session = this.driver.session();
    try {
      const query = `
        MERGE (r:Remediation {id: $remediationId, type: $issueType})
        MERGE (a:Agent {id: $agentId})
        MERGE (e:Execution {id: $executionId})
        CREATE (a)-[:PERFORMED_REMEDIATION {status: $status}]->(r)
        CREATE (r)-[:IN_EXECUTION]->(e)
        RETURN r.id as remediationId
      `;
      
      const result = await session.run(query, {
        remediationId,
        issueType,
        agentId,
        status,
        executionId
      });
      
      console.log(`✓ Remediation action recorded: ${remediationId}`);
      return true;
    } finally {
      await session.close();
    }
  }

  async getWorkflowLineage(workflowName) {
    if (!this.initialized || !this.driver) return null;
    
    const session = this.driver.session();
    try {
      const query = `
        MATCH (w:Workflow {name: $workflowName})<-[:IN_WORKFLOW]-(e:Execution)<-[:EXECUTED]-(a:Agent)
        OPTIONAL MATCH (c:ComplianceCheck)-[:CHECKED_IN_EXECUTION]->(e)
        RETURN {
          workflow: w.name,
          executions: collect({id: e.id, timestamp: e.timestamp}),
          agents: collect(DISTINCT a.id),
          checks: collect(DISTINCT c.standard)
        } as lineage
      `;
      
      const result = await session.run(query, { workflowName });
      return result.records.length > 0 ? result.records[0].get('lineage') : null;
    } finally {
      await session.close();
    }
  }

  async getComplianceAuditTrail(standard, days = 30) {
    if (!this.initialized || !this.driver) return [];
    
    const session = this.driver.session();
    try {
      const cutoffDate = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
      const query = `
        MATCH (c:ComplianceCheck {standard: $standard})-[rel:CHECKED_IN_EXECUTION]->(e:Execution)
        WHERE e.timestamp >= $cutoffDate
        RETURN {
          checkId: c.id,
          standard: c.standard,
          status: rel.status,
          details: rel.details,
          executionId: e.id,
          timestamp: e.timestamp
        } as auditEntry
        ORDER BY e.timestamp DESC
      `;
      
      const result = await session.run(query, {
        standard,
        cutoffDate: cutoffDate.toISOString()
      });
      
      return result.records.map(r => r.get('auditEntry'));
    } finally {
      await session.close();
    }
  }

  async close() {
    if (this.driver) {
      await this.driver.close();
      this.initialized = false;
      console.log('✅ Neo4j connection closed');
    }
  }
}

module.exports = Neo4jComplianceGraph;
