"""
AgenticQA Remote Client - Connect to AgenticQA REST API

Use this client to interact with AgenticQA from remote applications.

Example:
    >>> from agenticqa import RemoteClient
    >>> 
    >>> client = RemoteClient("http://localhost:8000")
    >>> results = client.execute_agents({"code": "...", "tests": "..."})
    >>> patterns = client.get_patterns()
"""

import requests
from typing import Dict, List, Any, Optional
from datetime import datetime


class RemoteClient:
    """Connect to AgenticQA REST API server."""
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 30):
        """
        Initialize RemoteClient.
        
        Args:
            base_url: Base URL of AgenticQA API server
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
    
    def execute_agents(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute all agents against test data.
        
        Args:
            test_data: Test data to execute agents against
            
        Returns:
            Agent execution results with QA, Performance, Compliance, and DevOps findings
            
        Example:
            >>> client = RemoteClient()
            >>> results = client.execute_agents({
            ...     "code": "def add(a, b): return a + b",
            ...     "tests": "assert add(1, 2) == 3"
            ... })
        """
        endpoint = f"{self.base_url}/api/agents/execute"
        response = self.session.post(
            endpoint,
            json=test_data,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
    
    def get_agent_insights(self, agent_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get insights and recommendations from agents.
        
        Args:
            agent_name: Specific agent name (qa, performance, compliance, devops) or None for all
            
        Returns:
            Agent insights and pattern analysis
        """
        endpoint = f"{self.base_url}/api/agents/insights"
        params = {}
        if agent_name:
            params["agent"] = agent_name
        
        response = self.session.get(
            endpoint,
            params=params,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
    
    def get_agent_history(self, agent_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get execution history for a specific agent.
        
        Args:
            agent_name: Agent name (qa, performance, compliance, or devops)
            limit: Number of recent executions to retrieve
            
        Returns:
            List of agent execution records
        """
        endpoint = f"{self.base_url}/api/agents/{agent_name}/history"
        params = {"limit": limit}
        
        response = self.session.get(
            endpoint,
            params=params,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
    
    def search_artifacts(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search test artifacts in the secure data store.
        
        Args:
            query: Search query (source, type, or tags)
            limit: Maximum results to return
            
        Returns:
            List of matching artifacts
        """
        endpoint = f"{self.base_url}/api/datastore/search"
        params = {"q": query, "limit": limit}
        
        response = self.session.get(
            endpoint,
            params=params,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
    
    def get_artifact(self, artifact_id: str) -> Dict[str, Any]:
        """
        Retrieve a specific artifact from data store.
        
        Args:
            artifact_id: Unique artifact identifier
            
        Returns:
            Artifact data with metadata
        """
        endpoint = f"{self.base_url}/api/datastore/artifact/{artifact_id}"
        
        response = self.session.get(
            endpoint,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
    
    def get_datastore_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the data store.
        
        Returns:
            Data store metrics (total artifacts, size, patterns detected, etc.)
        """
        endpoint = f"{self.base_url}/api/datastore/stats"
        
        response = self.session.get(
            endpoint,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
    
    def get_patterns(self) -> Dict[str, Any]:
        """
        Get detected patterns in historical agent data.
        
        Returns:
            Failure patterns, performance trends, and flakiness detection
        """
        endpoint = f"{self.base_url}/api/datastore/patterns"
        
        response = self.session.get(
            endpoint,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
    
    def health_check(self) -> bool:
        """
        Check if AgenticQA API server is healthy.
        
        Returns:
            True if server is reachable and healthy
        """
        try:
            response = self.session.get(
                f"{self.base_url}/health",
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def close(self):
        """Close the session."""
        self.session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
