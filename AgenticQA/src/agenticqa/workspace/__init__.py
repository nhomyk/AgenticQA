"""AgenticQA Workspace — safe in-browser file, mail, and link tools.

All operations are sandboxed and gated through the safety stack:
  - DestructiveActionInterceptor (pre-execution classification)
  - AgentScopeLeaseManager (hard operational caps)
  - ConstitutionalGate (semantic action validation)
  - OutputScanner (post-execution credential/leak scanning)
"""
