"""Deep security validation for stored data"""

import json
import hashlib
import re
import pickle
from typing import Dict, Any, Tuple, List


class DataSecurityValidator:
    """Deep security validation for stored data"""

    @staticmethod
    def validate_data_immutability(original: Dict, current: Dict) -> Tuple[bool, str]:
        """Ensure data hasn't been modified"""
        orig_hash = hashlib.sha256(json.dumps(original, sort_keys=True).encode()).hexdigest()
        curr_hash = hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest()

        if orig_hash == curr_hash:
            return True, "Data integrity verified"
        return False, f"Data mismatch: {orig_hash} != {curr_hash}"

    @staticmethod
    def validate_schema_compliance(data: Dict, schema: Dict) -> Tuple[bool, List[str]]:
        """Validate data conforms to schema"""
        errors = []

        for field, field_type in schema.items():
            if field not in data:
                errors.append(f"Missing required field: {field}")
            else:
                try:
                    expected_type = eval(field_type)
                    if not isinstance(data[field], expected_type):
                        errors.append(
                            f"Field {field} type mismatch: "
                            f"expected {field_type}, got {type(data[field])}"
                        )
                except (NameError, TypeError):
                    errors.append(f"Invalid type specification: {field_type}")

        return len(errors) == 0, errors

    @staticmethod
    def validate_no_pii_leakage(data: Dict) -> Tuple[bool, List[str]]:
        """Detect potential PII in stored data"""
        pii_patterns = {
            "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "ssn": r"\d{3}-\d{2}-\d{4}",
            "credit_card": r"\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}",
            "api_key": r"[a-zA-Z0-9]{32,}",
        }

        found_pii = []
        data_str = json.dumps(data)

        for pii_type, pattern in pii_patterns.items():
            if re.search(pattern, data_str):
                found_pii.append(f"Potential {pii_type} detected")

        return len(found_pii) == 0, found_pii

    @staticmethod
    def validate_encryption_ready(data: Dict) -> Tuple[bool, str]:
        """Ensure data can be encrypted"""
        try:
            json_str = json.dumps(data)
            pickle.dumps(data)
            return True, "Data is encryption-ready"
        except Exception as e:
            return False, f"Data cannot be encrypted: {str(e)}"
