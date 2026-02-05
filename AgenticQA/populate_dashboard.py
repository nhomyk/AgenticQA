#!/usr/bin/env python3
"""
Populate Neo4j with sample delegation data for dashboard visualization.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))

from agenticqa.graph.delegation_store import DelegationGraphStore
import uuid
import random
import json

print("🔌 Connecting to Neo4j...")
store = DelegationGraphStore()
store.connect()
store.initialize_schema()

print("🧹 Clearing old data...")
store.clear_all_data()

print("\n👥 Creating agents...")
agents = [
    ("SDET_Agent", "qa"),
    ("SRE_Agent", "devops"),
    ("Fullstack_Agent", "development"),
    ("Compliance_Agent", "security"),
    ("DevOps_Agent", "devops"),
    ("QA_Agent", "qa"),
    ("Performance_Agent", "qa")
]

for name, agent_type in agents:
    store.create_or_update_agent(agent_name=name, agent_type=agent_type)
    print(f"  ✓ Created {name}")

print("\n🔗 Creating delegations with explicit transactions...")

# Use direct Neo4j driver for explicit transaction control
deployment_id = str(uuid.uuid4())

delegations_data = [
    # SDET delegates to SRE (high success)
    ("SDET_Agent", "SRE_Agent", "deploy_tests", "success", 250),
    ("SDET_Agent", "SRE_Agent", "deploy_tests", "success", 300),
    ("SDET_Agent", "SRE_Agent", "deploy_tests", "success", 280),
    ("SDET_Agent", "SRE_Agent", "monitor_tests", "failed", 150),

    # SDET delegates to Fullstack (medium success)
    ("SDET_Agent", "Fullstack_Agent", "generate_tests", "success", 1200),
    ("SDET_Agent", "Fullstack_Agent", "generate_tests", "failed", 800),
    ("SDET_Agent", "Fullstack_Agent", "generate_tests", "success", 1100),

    # Fullstack delegates to QA (high success)
    ("Fullstack_Agent", "QA_Agent", "validate_code", "success", 500),
    ("Fullstack_Agent", "QA_Agent", "validate_code", "success", 450),
    ("Fullstack_Agent", "QA_Agent", "validate_code", "success", 520),

    # DevOps delegates to SRE (very high success)
    ("DevOps_Agent", "SRE_Agent", "deploy", "success", 2000),
    ("DevOps_Agent", "SRE_Agent", "deploy", "success", 1800),
    ("DevOps_Agent", "SRE_Agent", "deploy", "success", 2100),
    ("DevOps_Agent", "SRE_Agent", "rollback", "success", 900),

    # Compliance delegates to multiple (mixed)
    ("Compliance_Agent", "SDET_Agent", "security_scan", "success", 3000),
    ("Compliance_Agent", "SDET_Agent", "security_scan", "failed", 2500),
    ("Compliance_Agent", "Fullstack_Agent", "code_review", "success", 1500),

    # Performance delegates to DevOps (low success - bottleneck!)
    ("Performance_Agent", "DevOps_Agent", "load_test", "failed", 5000),
    ("Performance_Agent", "DevOps_Agent", "load_test", "failed", 5500),
    ("Performance_Agent", "DevOps_Agent", "load_test", "success", 4800),

    # QA delegates to Performance (medium)
    ("QA_Agent", "Performance_Agent", "benchmark", "success", 2200),
    ("QA_Agent", "Performance_Agent", "benchmark", "failed", 1800),

    # Multi-hop chain
    ("SDET_Agent", "Fullstack_Agent", "implement_feature", "success", 800),
    ("Fullstack_Agent", "DevOps_Agent", "deploy_feature", "success", 1200),
    ("DevOps_Agent", "Performance_Agent", "validate_feature", "success", 600),
]

# Create all delegations in one batch transaction
with store.driver.session(database=store.database) as session:
    with session.begin_transaction() as tx:
        for from_agent, to_agent, task_type, status, duration_ms in delegations_data:
            delegation_id = str(uuid.uuid4())

            # Create task as JSON string
            task_data = {
                "type": task_type,
                "description": f"Execute {task_type}",
                "priority": random.choice(["high", "medium", "low"])
            }

            # Create delegation
            tx.run("""
                MERGE (from:Agent {name: $from_agent})
                MERGE (to:Agent {name: $to_agent})
                CREATE (from)-[d:DELEGATES_TO {
                    delegation_id: $delegation_id,
                    task: $task,
                    timestamp: datetime(),
                    depth: 0,
                    status: $status,
                    duration_ms: $duration_ms,
                    deployment_id: $deployment_id,
                    completed_at: datetime(),
                    error_message: $error_message
                }]->(to)
                SET from.total_delegations_made = from.total_delegations_made + 1,
                    to.total_delegations_received = to.total_delegations_received + 1
            """,
                from_agent=from_agent,
                to_agent=to_agent,
                delegation_id=delegation_id,
                task=json.dumps(task_data),
                status=status,
                duration_ms=duration_ms,
                deployment_id=deployment_id,
                error_message=None if status == "success" else f"Error in {task_type}"
            )

            status_icon = "✓" if status == "success" else "✗"
            print(f"  {status_icon} {from_agent} → {to_agent}: {task_type} ({duration_ms}ms)")

        # Commit the transaction
        tx.commit()
        print("\n💾 Transaction committed")

print("\n📊 Verifying data...")
with store.session() as session:
    result = session.run("MATCH (a:Agent) RETURN count(a) as count")
    agent_count = result.single()["count"]
    print(f"  Agents: {agent_count}")

    result = session.run("MATCH ()-[d:DELEGATES_TO]->() RETURN count(d) as count")
    delegation_count = result.single()["count"]
    print(f"  Delegations: {delegation_count}")

print("\n✅ Sample data created successfully!")
print("🚀 Dashboard is ready at: http://localhost:8501")
print("\nRefresh your browser to see the visualizations!")

store.close()
