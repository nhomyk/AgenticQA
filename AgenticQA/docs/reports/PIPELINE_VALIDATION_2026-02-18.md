# Pipeline Validation Report (2026-02-18)

## Scope
- Local full-pipeline batch test runs by capability area
- End-to-end Prompt Ops API trigger to validate worker/orchestrator/SDET flow

## Batch Results

| Batch | Result | Notes |
|---|---:|---|
| core_workflow | PASS | All tests passed |
| agent_collab_policy | FAIL (1) | See failure details below |
| rag_vector_data | FAIL (1) | See failure details below |
| pipeline_validation | FAIL (2) | See failure details below |
| dashboard_ui | PASS | All tests passed |

## End-to-End Agent Trigger Proof
- Request ID: `wr_0f74483dc66d`
- Workflow Status: `COMPLETED`
- Trace Found: `True`
- Event Count: `5`
- Event Signatures:
  - `PromptOpsOrchestrator::orchestrate::COMPLETED`
  - `PromptOpsOrchestrator::orchestrate::STARTED`
  - `SDET_Agent::sdet_test_loop::STARTED`
  - `WorkflowWorker::run_request::COMPLETED`
  - `WorkflowWorker::run_request::STARTED`

## Failures (Honest Snapshot)
### agent_collab_policy
```text
......                                [ 27%]
tests/test_policy_engine.py ....                                         [ 38%]
tests/test_graphrag_delegation.py ...FF.                                 [ 55%]
tests/test_pattern_strategy.py .....                                     [ 69%]
tests/test_strategy_selection.py .........                               [ 94%]
tests/test_trace_replay.py ..                                            [100%]

=================================== FAILURES ===================================
___________ TestGraphRAGDelegation.test_outcome_recorded_on_success ____________
tests/test_graphrag_delegation.py:111: in test_outcome_recorded_on_success
    assert len(rows) == 1
E   assert 0 == 1
E    +  where 0 = len([])
----------------------------- Captured stdout call -----------------------------
[2026-02-18T21:31:48.248758] [QA_Assistant] [INFO] Delegating task to SRE_Agent
[2026-02-18T21:31:48.248796] [QA_Assistant] [INFO] Delegation to SRE_Agent completed
___________ TestGraphRAGDelegation.test_outcome_recorded_on_failure ____________
tests/test_graphrag_delegation.py:130: in test_outcome_recorded_on_failure
    assert row["actual_success"] == 0
           ^^^^^^^^^^^^^^^^^^^^^
E   TypeError: 'NoneType' object is not subscriptable
----------------------------- Captured stdout call -----------------------------
[2026-02-18T21:31:48.325202] [QA_Assistant] [INFO] Delegating task to SRE_Agent
=========================== short test summary info ============================
FAILED tests/test_graphrag_delegation.py::TestGraphRAGDelegation::test_outcome_recorded_on_success
FAILED tests/test_graphrag_delegation.py::TestGraphRAGDelegation::test_outcome_recorded_on_failure
================== 2 failed, 34 passed, 250 warnings in 2.57s ==================
```
### rag_vector_data
```text
============================= test session starts ==============================
platform darwin -- Python 3.13.2, pytest-9.0.2, pluggy-1.6.0
rootdir: /Users/nicholashomyk/mono/AgenticQA
configfile: pytest.ini (WARNING: ignoring pytest config in pyproject.toml!)
plugins: anyio-4.12.1, langsmith-0.7.3, cov-7.0.0
collected 59 items

tests/test_hybrid_rag.py ............                                    [ 20%]
tests/test_vector_provider_config.py ......                              [ 30%]
tests/test_dual_write_vector_store.py ...                                [ 35%]
tests/test_vector_migration.py ...                                       [ 40%]
tests/test_data_validation.py .........................F.........        [100%]

=================================== FAILURES ===================================
_____________________ TestDataSecurity.test_pii_detection ______________________
tests/test_data_validation.py:473: in test_pii_detection
    assert len(detected_pii["credit_card"]) == 3, "Credit card values not detected"
E   AssertionError: Credit card values not detected
E   assert 2 == 3
E    +  where 2 = len(['4111-1111-1111-1111', '5555-5555-5555-4444'])
=========================== short test summary info ============================
FAILED tests/test_data_validation.py::TestDataSecurity::test_pii_detection - ...
=================== 1 failed, 58 passed, 8 warnings in 0.86s ===================
```
### pipeline_validation
```text
============================= test session starts ==============================
platform darwin -- Python 3.13.2, pytest-9.0.2, pluggy-1.6.0
rootdir: /Users/nicholashomyk/mono/AgenticQA
configfile: pytest.ini (WARNING: ignoring pytest config in pyproject.toml!)
plugins: anyio-4.12.1, langsmith-0.7.3, cov-7.0.0
collected 79 items / 1 error

==================================== ERRORS ====================================
______________ ERROR collecting tests/test_pipeline_snapshots.py _______________
ImportError while importing test module '/Users/nicholashomyk/mono/AgenticQA/tests/test_pipeline_snapshots.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_pipeline_snapshots.py:10: in <module>
    from agenticqa import AgentOrchestrator
E   ImportError: cannot import name 'AgentOrchestrator' from 'agenticqa' (/Users/nicholashomyk/mono/AgenticQA/src/agenticqa/__init__.py)
=========================== short test summary info ============================
ERROR tests/test_pipeline_snapshots.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.69s ===============================
```

## Immediate Remediation Priorities
1. Fix `tests/test_graphrag_delegation.py` outcome-tracker persistence assertions.
2. Fix PII detector coverage in `tests/test_data_validation.py::test_pii_detection` (credit-card detection gap).
3. Fix `agenticqa.__init__` exports (`AgentOrchestrator`) to unblock `test_pipeline_snapshots` collection.
4. Re-run the same validation matrix after fixes and compare against this baseline.
