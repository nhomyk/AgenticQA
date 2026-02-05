"""
Neo4j Graph Store for Agent Delegation Tracking

Implements GraphRAG pattern:
- Weaviate: Semantic similarity (vector embeddings)
- Neo4j: Relationship context (delegation chains, patterns)
- Combined: Intelligent recommendations with both semantic AND structural context
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import os
import logging
from contextlib import contextmanager

try:
    from neo4j import GraphDatabase, Driver, Session
    from neo4j.exceptions import ServiceUnavailable, AuthError
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logging.warning("neo4j package not installed. Run: pip install neo4j")


logger = logging.getLogger(__name__)


class DelegationGraphStore:
    """
    Neo4j-powered graph store for agent delegation tracking and analysis.

    Features:
    - Records agent delegations with full context
    - Tracks delegation chains and patterns
    - Provides analytics queries for bottlenecks and optimization
    - Enables GraphRAG by combining with Weaviate semantic search
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: str = "neo4j"
    ):
        """
        Initialize Neo4j connection.

        Args:
            uri: Neo4j connection URI (default: from env NEO4J_URI or bolt://localhost:7687)
            user: Neo4j username (default: from env NEO4J_USER or neo4j)
            password: Neo4j password (default: from env NEO4J_PASSWORD or agenticqa123)
            database: Neo4j database name (default: neo4j)
        """
        if not NEO4J_AVAILABLE:
            raise ImportError("neo4j package not installed. Run: pip install neo4j")

        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "agenticqa123")
        self.database = database

        self.driver: Optional[Driver] = None
        self._connected = False

    def connect(self):
        """Establish connection to Neo4j"""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            # Verify connectivity
            with self.driver.session(database=self.database) as session:
                session.run("RETURN 1")
            self._connected = True
            logger.info(f"Connected to Neo4j at {self.uri}")
        except (ServiceUnavailable, AuthError) as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
            self._connected = False
            logger.info("Neo4j connection closed")

    @contextmanager
    def session(self):
        """Context manager for Neo4j sessions"""
        if not self._connected:
            self.connect()
        session = self.driver.session(database=self.database)
        try:
            yield session
        finally:
            session.close()

    def initialize_schema(self):
        """
        Initialize Neo4j schema with constraints and indexes.
        Call this once during setup.
        """
        with self.session() as session:
            # Constraints
            constraints = [
                "CREATE CONSTRAINT agent_name_unique IF NOT EXISTS FOR (a:Agent) REQUIRE a.name IS UNIQUE",
                "CREATE CONSTRAINT execution_id_unique IF NOT EXISTS FOR (e:Execution) REQUIRE e.execution_id IS UNIQUE",
                "CREATE CONSTRAINT deployment_id_unique IF NOT EXISTS FOR (d:Deployment) REQUIRE d.deployment_id IS UNIQUE",
            ]

            # Indexes
            indexes = [
                "CREATE INDEX agent_name_idx IF NOT EXISTS FOR (a:Agent) ON (a.name)",
                "CREATE INDEX execution_timestamp_idx IF NOT EXISTS FOR (e:Execution) ON (e.timestamp)",
                "CREATE INDEX execution_deployment_idx IF NOT EXISTS FOR (e:Execution) ON (e.deployment_id)",
                "CREATE INDEX deployment_pipeline_idx IF NOT EXISTS FOR (d:Deployment) ON (d.pipeline_run)",
            ]

            for query in constraints + indexes:
                try:
                    session.run(query)
                    logger.debug(f"Executed: {query[:50]}...")
                except Exception as e:
                    logger.warning(f"Schema creation query failed (may already exist): {e}")

        logger.info("Neo4j schema initialized")

    def create_or_update_agent(self, agent_name: str, agent_type: str = "unknown") -> Dict:
        """
        Create or update an Agent node.

        Args:
            agent_name: Name of the agent (e.g., "SDET_Agent")
            agent_type: Type of agent (e.g., "qa", "devops")

        Returns:
            Agent node properties
        """
        with self.session() as session:
            result = session.run("""
                MERGE (a:Agent {name: $name})
                ON CREATE SET
                    a.type = $type,
                    a.created_at = datetime(),
                    a.total_executions = 0,
                    a.total_delegations_made = 0,
                    a.total_delegations_received = 0,
                    a.success_rate = 0.0
                ON MATCH SET
                    a.last_active = datetime()
                RETURN a
            """, name=agent_name, type=agent_type)

            record = result.single()
            return dict(record["a"]) if record else {}

    def record_delegation(
        self,
        from_agent: str,
        to_agent: str,
        task: Dict[str, Any],
        delegation_id: str,
        execution_id: Optional[str] = None,
        depth: int = 0,
        deployment_id: Optional[str] = None
    ) -> str:
        """
        Record a delegation from one agent to another.

        Args:
            from_agent: Source agent name
            to_agent: Target agent name
            task: Task details (dict)
            delegation_id: Unique delegation ID
            execution_id: Source execution ID
            depth: Delegation chain depth
            deployment_id: CI/CD deployment ID

        Returns:
            Delegation ID
        """
        with self.session() as session:
            session.run("""
                MERGE (from:Agent {name: $from_agent})
                MERGE (to:Agent {name: $to_agent})
                CREATE (from)-[d:DELEGATES_TO {
                    delegation_id: $delegation_id,
                    execution_id: $execution_id,
                    task: $task,
                    timestamp: datetime(),
                    depth: $depth,
                    status: 'pending',
                    deployment_id: $deployment_id
                }]->(to)
                SET from.total_delegations_made = from.total_delegations_made + 1,
                    to.total_delegations_received = to.total_delegations_received + 1
                RETURN d.delegation_id as id
            """,
                from_agent=from_agent,
                to_agent=to_agent,
                delegation_id=delegation_id,
                execution_id=execution_id,
                task=task,
                depth=depth,
                deployment_id=deployment_id
            )

        logger.debug(f"Recorded delegation: {from_agent} -> {to_agent} (depth: {depth})")
        return delegation_id

    def update_delegation_result(
        self,
        delegation_id: str,
        status: str,
        duration_ms: float,
        result: Optional[Dict] = None,
        error_message: Optional[str] = None
    ):
        """
        Update delegation with completion result.

        Args:
            delegation_id: Unique delegation ID
            status: "success", "failed", or "timeout"
            duration_ms: Execution duration in milliseconds
            result: Result data (optional)
            error_message: Error message if failed (optional)
        """
        with self.session() as session:
            session.run("""
                MATCH ()-[d:DELEGATES_TO {delegation_id: $delegation_id}]->()
                SET d.status = $status,
                    d.duration_ms = $duration_ms,
                    d.result = $result,
                    d.error_message = $error_message,
                    d.completed_at = datetime()
            """,
                delegation_id=delegation_id,
                status=status,
                duration_ms=duration_ms,
                result=result,
                error_message=error_message
            )

        logger.debug(f"Updated delegation {delegation_id}: {status} ({duration_ms}ms)")

    def create_execution(
        self,
        execution_id: str,
        agent_name: str,
        task_type: str,
        deployment_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Create an Execution node.

        Args:
            execution_id: Unique execution ID
            agent_name: Agent that performed execution
            task_type: Type of task (e.g., "coverage_analysis")
            deployment_id: CI/CD deployment ID
            metadata: Additional execution metadata

        Returns:
            Execution ID
        """
        with self.session() as session:
            session.run("""
                MERGE (e:Execution {execution_id: $execution_id})
                ON CREATE SET
                    e.agent_name = $agent_name,
                    e.task_type = $task_type,
                    e.deployment_id = $deployment_id,
                    e.timestamp = datetime(),
                    e.status = 'running',
                    e.metadata = $metadata
                MERGE (a:Agent {name: $agent_name})
                MERGE (e)-[:EXECUTED_BY]->(a)
                SET a.total_executions = a.total_executions + 1
            """,
                execution_id=execution_id,
                agent_name=agent_name,
                task_type=task_type,
                deployment_id=deployment_id,
                metadata=metadata or {}
            )

        return execution_id

    def update_execution_status(
        self,
        execution_id: str,
        status: str,
        duration_ms: Optional[float] = None,
        error_message: Optional[str] = None
    ):
        """
        Update execution status.

        Args:
            execution_id: Unique execution ID
            status: "success", "failed", or "partial"
            duration_ms: Execution duration
            error_message: Error message if failed
        """
        with self.session() as session:
            session.run("""
                MATCH (e:Execution {execution_id: $execution_id})
                SET e.status = $status,
                    e.duration_ms = $duration_ms,
                    e.error_message = $error_message,
                    e.completed_at = datetime()
            """,
                execution_id=execution_id,
                status=status,
                duration_ms=duration_ms,
                error_message=error_message
            )

    # ==================== Analytics Queries ====================

    def get_most_delegated_agents(self, limit: int = 5) -> List[Dict]:
        """
        Find agents that receive the most delegations.

        Returns:
            List of agents with delegation counts and avg duration
        """
        with self.session() as session:
            result = session.run("""
                MATCH (a:Agent)<-[d:DELEGATES_TO]-()
                RETURN a.name as agent,
                       count(d) as delegation_count,
                       avg(d.duration_ms) as avg_duration_ms,
                       sum(CASE WHEN d.status = 'success' THEN 1 ELSE 0 END) as successes
                ORDER BY delegation_count DESC
                LIMIT $limit
            """, limit=limit)

            return [dict(record) for record in result]

    def find_delegation_chains(self, min_length: int = 2, limit: int = 10) -> List[Dict]:
        """
        Find delegation chains (multi-hop delegations).

        Args:
            min_length: Minimum chain length
            limit: Max results

        Returns:
            List of delegation chains with metadata
        """
        with self.session() as session:
            result = session.run("""
                MATCH path = (start:Agent)-[:DELEGATES_TO*]->(end:Agent)
                WHERE length(path) >= $min_length
                WITH path, start, end,
                     [r in relationships(path) | r.duration_ms] as durations,
                     [r in relationships(path) | r.status] as statuses
                RETURN start.name as origin,
                       end.name as destination,
                       length(path) as chain_length,
                       durations,
                       statuses,
                       reduce(total = 0.0, d in durations | total + d) as total_duration_ms
                ORDER BY chain_length DESC
                LIMIT $limit
            """, min_length=min_length, limit=limit)

            return [dict(record) for record in result]

    def find_circular_delegations(self) -> List[Dict]:
        """
        Find circular delegation patterns (should be prevented by guardrails!).

        Returns:
            List of circular paths (should be empty)
        """
        with self.session() as session:
            result = session.run("""
                MATCH path = (a:Agent)-[:DELEGATES_TO*]->(a)
                RETURN [n in nodes(path) | n.name] as cycle,
                       length(path) as cycle_length
            """)

            return [dict(record) for record in result]

    def get_delegation_success_rate_by_pair(self, limit: int = 10) -> List[Dict]:
        """
        Get success rate for each (from_agent, to_agent) pair.

        Returns:
            List of agent pairs with success metrics
        """
        with self.session() as session:
            result = session.run("""
                MATCH (from:Agent)-[d:DELEGATES_TO]->(to:Agent)
                WITH from.name as from_agent,
                     to.name as to_agent,
                     count(d) as total,
                     sum(CASE WHEN d.status = 'success' THEN 1 ELSE 0 END) as successes,
                     avg(d.duration_ms) as avg_duration_ms
                WHERE total >= 3  // At least 3 delegations for statistical significance
                RETURN from_agent,
                       to_agent,
                       total,
                       successes,
                       (toFloat(successes) / total) as success_rate,
                       avg_duration_ms
                ORDER BY total DESC
                LIMIT $limit
            """, limit=limit)

            return [dict(record) for record in result]

    def find_bottleneck_agents(
        self,
        slow_threshold_ms: float = 1000.0,
        min_count: int = 5
    ) -> List[Dict]:
        """
        Find agents that are bottlenecks (slow delegations).

        Args:
            slow_threshold_ms: Threshold for "slow" delegation
            min_count: Minimum number of slow delegations

        Returns:
            List of bottleneck agents with performance metrics
        """
        with self.session() as session:
            result = session.run("""
                MATCH (a:Agent)<-[d:DELEGATES_TO]-()
                WHERE d.duration_ms > $threshold
                WITH a.name as agent,
                     count(d) as slow_delegations,
                     avg(d.duration_ms) as avg_duration,
                     percentileCont(d.duration_ms, 0.95) as p95_duration,
                     max(d.duration_ms) as max_duration
                WHERE slow_delegations >= $min_count
                RETURN agent, slow_delegations, avg_duration, p95_duration, max_duration
                ORDER BY avg_duration DESC
            """, threshold=slow_threshold_ms, min_count=min_count)

            return [dict(record) for record in result]

    # ==================== GraphRAG Queries ====================

    def recommend_delegation_target(
        self,
        from_agent: str,
        task_type: str,
        acceptable_duration_ms: float = 5000.0,
        min_success_count: int = 3
    ) -> Optional[Dict]:
        """
        Recommend optimal agent for delegation based on historical success.

        This is the core GraphRAG query that combines:
        - Historical delegation patterns (Neo4j)
        - Task similarity (could be enhanced with Weaviate)

        Args:
            from_agent: Agent making the delegation
            task_type: Type of task to delegate
            acceptable_duration_ms: Max acceptable duration
            min_success_count: Minimum successful delegations required

        Returns:
            Recommended agent with confidence metrics, or None
        """
        with self.session() as session:
            result = session.run("""
                MATCH (from:Agent {name: $from_agent})-[d:DELEGATES_TO]->(to:Agent)
                WHERE d.task.task_type = $task_type
                  AND d.status = 'success'
                  AND d.duration_ms < $acceptable_duration_ms
                WITH to.name as recommended_agent,
                     count(d) as success_count,
                     avg(d.duration_ms) as avg_duration,
                     stdDev(d.duration_ms) as duration_stddev
                WHERE success_count >= $min_success_count
                RETURN recommended_agent,
                       success_count,
                       avg_duration,
                       duration_stddev,
                       (success_count * 1000.0 / avg_duration) as priority_score
                ORDER BY priority_score DESC
                LIMIT 1
            """,
                from_agent=from_agent,
                task_type=task_type,
                acceptable_duration_ms=acceptable_duration_ms,
                min_success_count=min_success_count
            )

            record = result.single()
            return dict(record) if record else None

    def get_delegation_history_for_task(
        self,
        task_type: str,
        status: str = "success",
        limit: int = 5
    ) -> List[Dict]:
        """
        Get historical delegations for a specific task type.
        Used for GraphRAG pattern learning.

        Args:
            task_type: Type of task
            status: Filter by status (default: success)
            limit: Max results

        Returns:
            List of historical delegations
        """
        with self.session() as session:
            result = session.run("""
                MATCH (from:Agent)-[d:DELEGATES_TO]->(to:Agent)
                WHERE d.task.task_type = $task_type
                  AND d.status = $status
                RETURN from.name as from_agent,
                       to.name as to_agent,
                       d.task as task,
                       d.result as result,
                       d.duration_ms as duration_ms,
                       d.timestamp as timestamp
                ORDER BY d.timestamp DESC
                LIMIT $limit
            """, task_type=task_type, status=status, limit=limit)

            return [dict(record) for record in result]

    # ==================== Utility Methods ====================

    def get_agent_stats(self, agent_name: str) -> Optional[Dict]:
        """
        Get statistics for a specific agent.

        Returns:
            Agent statistics or None if not found
        """
        with self.session() as session:
            result = session.run("""
                MATCH (a:Agent {name: $name})
                OPTIONAL MATCH (a)-[d_out:DELEGATES_TO]->()
                OPTIONAL MATCH (a)<-[d_in:DELEGATES_TO]-()
                RETURN a,
                       count(DISTINCT d_out) as delegations_made,
                       count(DISTINCT d_in) as delegations_received
            """, name=agent_name)

            record = result.single()
            if not record:
                return None

            agent = dict(record["a"])
            agent["delegations_made"] = record["delegations_made"]
            agent["delegations_received"] = record["delegations_received"]
            return agent

    def clear_all_data(self):
        """
        Clear all data from Neo4j (use with caution!).
        Useful for testing and development.
        """
        with self.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        logger.warning("All Neo4j data cleared")

    def get_database_stats(self) -> Dict:
        """
        Get overall database statistics.

        Returns:
            Database statistics
        """
        with self.session() as session:
            result = session.run("""
                MATCH (a:Agent)
                OPTIONAL MATCH (e:Execution)
                OPTIONAL MATCH ()-[d:DELEGATES_TO]->()
                RETURN count(DISTINCT a) as total_agents,
                       count(DISTINCT e) as total_executions,
                       count(d) as total_delegations
            """)

            record = result.single()
            return dict(record) if record else {}
