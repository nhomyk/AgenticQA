/**
 * TypeScript SDK Example 2: React Integration
 * 
 * This example shows how to integrate AgenticQA with React
 * for real-time QA dashboard updates.
 */

import React, { useState, useEffect } from 'react';
import { AgenticQAClient } from 'agenticqa';

interface AgentStatus {
  status: string;
  timestamp?: string;
  details?: Record<string, unknown>;
}

export function AgenticQADashboard() {
  const [client] = useState(() => new AgenticQAClient('http://localhost:8000'));
  const [loading, setLoading] = useState(true);
  const [agents, setAgents] = useState<Record<string, AgentStatus>>({
    qa: { status: 'unknown' },
    performance: { status: 'unknown' },
    compliance: { status: 'unknown' },
    devops: { status: 'unknown' },
  });
  const [patterns, setPatterns] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Get insights for each agent
        const qaInsights = await client.getAgentInsights('qa');
        const perfInsights = await client.getAgentInsights('performance');
        const complianceInsights = await client.getAgentInsights('compliance');
        const devopsInsights = await client.getAgentInsights('devops');

        setAgents({
          qa: qaInsights as AgentStatus,
          performance: perfInsights as AgentStatus,
          compliance: complianceInsights as AgentStatus,
          devops: devopsInsights as AgentStatus,
        });

        // Get patterns and stats
        setPatterns(await client.getPatterns());
        setStats(await client.getDatastoreStats());

        setLoading(false);
      } catch (error) {
        console.error('Error fetching data:', error);
        setLoading(false);
      }
    };

    // Initial fetch
    fetchData();

    // Refresh every 10 seconds
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [client]);

  if (loading) {
    return <div>Loading AgenticQA dashboard...</div>;
  }

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'passed':
        return '#10b981';
      case 'failed':
        return '#ef4444';
      case 'warning':
        return '#f59e0b';
      default:
        return '#6b7280';
    }
  };

  return (
    <div style={{ padding: '20px', fontFamily: 'system-ui' }}>
      <h1>🎯 AgenticQA Dashboard</h1>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px', marginBottom: '40px' }}>
        {Object.entries(agents).map(([name, agent]) => (
          <div
            key={name}
            style={{
              border: `3px solid ${getStatusColor(agent.status)}`,
              borderRadius: '8px',
              padding: '15px',
            }}
          >
            <h3 style={{ margin: '0 0 10px 0', textTransform: 'capitalize' }}>{name} Agent</h3>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: getStatusColor(agent.status) }}>
              {agent.status.toUpperCase()}
            </div>
            {agent.timestamp && <p style={{ fontSize: '12px', color: '#666' }}>Last run: {agent.timestamp}</p>}
          </div>
        ))}
      </div>

      <h2>📊 Patterns Detected</h2>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '15px' }}>
        <div style={{ backgroundColor: '#f3f4f6', padding: '15px', borderRadius: '8px' }}>
          <div style={{ fontSize: '12px', color: '#666' }}>Failure Patterns</div>
          <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{patterns?.failure_patterns?.length || 0}</div>
        </div>
        <div style={{ backgroundColor: '#f3f4f6', padding: '15px', borderRadius: '8px' }}>
          <div style={{ fontSize: '12px', color: '#666' }}>Performance Trends</div>
          <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{patterns?.performance_trends?.length || 0}</div>
        </div>
        <div style={{ backgroundColor: '#f3f4f6', padding: '15px', borderRadius: '8px' }}>
          <div style={{ fontSize: '12px', color: '#666' }}>Flaky Tests</div>
          <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{patterns?.flakiness_detection?.length || 0}</div>
        </div>
      </div>

      <h2 style={{ marginTop: '40px' }}>📈 Data Store Statistics</h2>
      <p>Total Artifacts: {stats?.total_artifacts}</p>
      <p>Storage Size: {(stats?.storage_size / 1024 / 1024).toFixed(2)} MB</p>
    </div>
  );
}
