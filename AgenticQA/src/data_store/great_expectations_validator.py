"""Great Expectations integration for data quality validation"""

from typing import Any, Dict, Optional
import pandas as pd

try:
    from great_expectations.data_context import DataContext
    from great_expectations.core.batch import RuntimeBatchRequest
    GREAT_EXPECTATIONS_AVAILABLE = True
except ImportError:
    GREAT_EXPECTATIONS_AVAILABLE = False


class AgentDataValidator:
    """Great Expectations integration for agent result validation"""

    def __init__(self, context_root_dir: str = "great_expectations"):
        if not GREAT_EXPECTATIONS_AVAILABLE:
            raise ImportError(
                "great_expectations not installed. "
                "Install with: pip install great_expectations"
            )
        self.context = DataContext(context_root_dir=context_root_dir)

    def validate_agent_execution(
        self, agent_name: str, execution_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate agent execution against expectations"""

        # Convert result to DataFrame for validation
        df = pd.DataFrame([execution_result])

        batch_request = RuntimeBatchRequest(
            datasource_name="agent_results_datasource",
            data_connector_name="default_runtime_data_connector",
            data_asset_name=f"{agent_name}_results",
            runtime_parameters={"df": df},
            batch_identifiers={"run_id": execution_result.get("run_id")},
        )

        validator = self.context.get_validator(batch_request=batch_request)

        # Add expectations
        validator.expect_table_columns_to_match_ordered_list(
            column_list=["timestamp", "agent_name", "status", "output"]
        )
        validator.expect_column_values_to_not_be_null(column="timestamp")
        validator.expect_column_values_to_not_be_null(column="output")
        validator.expect_column_values_to_be_in_set(
            column="status", value_set=["success", "error", "timeout"]
        )

        validation_result = validator.validate()

        return validation_result.to_dict()

    def validate_data_schema(
        self, df: pd.DataFrame, expectation_suite: str
    ) -> Dict:
        """Validate DataFrame against expectation suite"""
        batch_request = RuntimeBatchRequest(
            datasource_name="agent_results_datasource",
            data_connector_name="default_runtime_data_connector",
            data_asset_name="validation_batch",
            runtime_parameters={"df": df},
        )

        validator = self.context.get_validator(batch_request=batch_request)
        validator.expectation_suite_name = expectation_suite

        return validator.validate().to_dict()
