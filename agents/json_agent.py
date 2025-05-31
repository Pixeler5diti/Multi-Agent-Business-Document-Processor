import json
import logging
from typing import Dict, Any
import jsonschema
from jsonschema import validate, ValidationError

logger = logging.getLogger(__name__)

class JSONAgent:
    def __init__(self):
        # Common business document schemas
        self.schemas = {
            "invoice": {
                "type": "object",
                "properties": {
                    "invoice_number": {"type": "string"},
                    "amount": {"type": "number"},
                    "date": {"type": "string"},
                    "vendor": {"type": "string"},
                    "items": {"type": "array"}
                },
                "required": ["invoice_number", "amount"]
            },
            "transaction": {
                "type": "object",
                "properties": {
                    "transaction_id": {"type": "string"},
                    "amount": {"type": "number"},
                    "timestamp": {"type": "string"},
                    "account": {"type": "string"},
                    "type": {"type": "string"}
                },
                "required": ["transaction_id", "amount"]
            },
            "rfq": {
                "type": "object",
                "properties": {
                    "rfq_id": {"type": "string"},
                    "items": {"type": "array"},
                    "deadline": {"type": "string"},
                    "contact": {"type": "object"}
                },
                "required": ["rfq_id", "items"]
            }
        }

    async def process(self, content: str, classification: Dict[str, Any]) -> Dict[str, Any]:
        """Process JSON content and validate structure"""
        try:
            # Parse JSON
            json_data = json.loads(content)
            
            # Validate structure
            validation_result = self._validate_structure(json_data, classification)
            
            # Extract business-specific data
            extracted_data = self._extract_business_data(json_data, classification)
            
            # Generate flags
            flags = self._generate_flags(json_data, extracted_data, validation_result)
            
            result = {
                "extracted_data": extracted_data,
                "metadata": {
                    "processing_agent": "json_agent",
                    "validation_result": validation_result,
                    "json_structure": self._analyze_structure(json_data),
                    "field_count": len(json_data) if isinstance(json_data, dict) else 0
                },
                "flags": flags,
                "confidence": 0.9 if validation_result["is_valid"] else 0.6
            }
            
            logger.info(f"JSON processed: valid={validation_result['is_valid']}, flags={flags}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format: {str(e)}")
            return self._handle_invalid_json(content, str(e))
        except Exception as e:
            logger.error(f"Error processing JSON: {str(e)}")
            return self._fallback_processing(content)

    def _validate_structure(self, json_data: Dict[str, Any], classification: Dict[str, Any]) -> Dict[str, Any]:
        """Validate JSON against expected schemas"""
        validation_result = {
            "is_valid": True,
            "schema_matches": [],
            "errors": [],
            "warnings": []
        }
        
        # Try to match against known schemas
        business_intent = classification.get("business_intent", "").lower()
        
        for schema_name, schema in self.schemas.items():
            try:
                validate(instance=json_data, schema=schema)
                validation_result["schema_matches"].append(schema_name)
                logger.info(f"JSON matches {schema_name} schema")
            except ValidationError as e:
                if business_intent in schema_name.lower():
                    validation_result["errors"].append(f"Expected {schema_name} schema but validation failed: {str(e)}")
                    validation_result["is_valid"] = False
        
        # Check for common data quality issues
        self._check_data_quality(json_data, validation_result)
        
        return validation_result

    def _check_data_quality(self, json_data: Dict[str, Any], validation_result: Dict[str, Any]):
        """Check for data quality issues"""
        if isinstance(json_data, dict):
            # Check for missing critical fields
            if not json_data:
                validation_result["warnings"].append("Empty JSON object")
            
            # Check for null values in important fields
            null_fields = [k for k, v in json_data.items() if v is None]
            if null_fields:
                validation_result["warnings"].append(f"Null values in fields: {null_fields}")
            
            # Check for suspicious values
            for key, value in json_data.items():
                if isinstance(value, str) and not value.strip():
                    validation_result["warnings"].append(f"Empty string value for field: {key}")
                
                # Check for extremely large numbers (potential data errors)
                if isinstance(value, (int, float)) and abs(value) > 1e10:
                    validation_result["warnings"].append(f"Unusually large number in field {key}: {value}")

    def _extract_business_data(self, json_data: Dict[str, Any], classification: Dict[str, Any]) -> Dict[str, Any]:
        """Extract business-relevant data from JSON"""
        extracted = {
            "json_type": type(json_data).__name__,
            "field_count": len(json_data) if isinstance(json_data, dict) else 0
        }
        
        if isinstance(json_data, dict):
            # Extract amount/monetary values
            amount_fields = ["amount", "total", "price", "value", "cost", "sum"]
            for field in amount_fields:
                if field in json_data:
                    extracted["monetary_value"] = json_data[field]
                    break
            
            # Extract identification fields
            id_fields = ["id", "invoice_id", "transaction_id", "rfq_id", "reference", "number"]
            for field in id_fields:
                if field in json_data:
                    extracted["document_id"] = json_data[field]
                    break
            
            # Extract date fields
            date_fields = ["date", "timestamp", "created_at", "due_date", "deadline"]
            for field in date_fields:
                if field in json_data:
                    extracted["date"] = json_data[field]
                    break
            
            # Extract contact information
            contact_fields = ["email", "contact", "vendor", "customer", "client"]
            for field in contact_fields:
                if field in json_data:
                    extracted["contact_info"] = json_data[field]
                    break
            
            # Extract arrays/lists
            array_fields = [k for k, v in json_data.items() if isinstance(v, list)]
            if array_fields:
                extracted["list_fields"] = {field: len(json_data[field]) for field in array_fields}
        
        return extracted

    def _analyze_structure(self, json_data: Any) -> Dict[str, Any]:
        """Analyze JSON structure"""
        if isinstance(json_data, dict):
            return {
                "type": "object",
                "keys": list(json_data.keys()),
                "nested_objects": len([v for v in json_data.values() if isinstance(v, dict)]),
                "arrays": len([v for v in json_data.values() if isinstance(v, list)]),
                "depth": self._calculate_depth(json_data)
            }
        elif isinstance(json_data, list):
            return {
                "type": "array",
                "length": len(json_data),
                "item_types": list(set(type(item).__name__ for item in json_data))
            }
        else:
            return {
                "type": type(json_data).__name__,
                "value": str(json_data)[:100]
            }

    def _calculate_depth(self, obj: Any, current_depth: int = 0) -> int:
        """Calculate the maximum depth of nested JSON structure"""
        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(self._calculate_depth(v, current_depth + 1) for v in obj.values())
        elif isinstance(obj, list):
            if not obj:
                return current_depth
            return max(self._calculate_depth(item, current_depth + 1) for item in obj)
        else:
            return current_depth

    def _generate_flags(self, json_data: Dict[str, Any], extracted_data: Dict[str, Any], validation_result: Dict[str, Any]) -> list:
        """Generate flags based on JSON analysis"""
        flags = []
        
        # Schema validation flags
        if not validation_result["is_valid"]:
            flags.append("SCHEMA_VALIDATION_FAILED")
        
        if validation_result["warnings"]:
            flags.append("DATA_QUALITY_ISSUES")
        
        # Business logic flags
        monetary_value = extracted_data.get("monetary_value")
        if monetary_value:
            try:
                amount = float(monetary_value)
                if amount > 10000:
                    flags.append("HIGH_VALUE_TRANSACTION")
                if amount < 0:
                    flags.append("NEGATIVE_AMOUNT")
            except (ValueError, TypeError):
                flags.append("INVALID_MONETARY_VALUE")
        
        # Fraud detection flags
        if isinstance(json_data, dict):
            # Check for suspicious patterns
            if "test" in str(json_data).lower():
                flags.append("TEST_DATA_DETECTED")
            
            # Check for duplicate keys (shouldn't happen in valid JSON but indicates issues)
            json_str = json.dumps(json_data)
            if len(json_str) > 10000:  # Very large JSON
                flags.append("LARGE_DOCUMENT")
        
        return flags

    def _handle_invalid_json(self, content: str, error: str) -> Dict[str, Any]:
        """Handle invalid JSON content"""
        return {
            "extracted_data": {
                "content_length": len(content),
                "parse_error": error,
                "content_preview": content[:200]
            },
            "metadata": {
                "processing_agent": "json_agent",
                "parse_successful": False,
                "error_details": error
            },
            "flags": ["INVALID_JSON", "PARSE_ERROR"],
            "confidence": 0.1
        }

    def _fallback_processing(self, content: str) -> Dict[str, Any]:
        """Fallback processing when main processing fails"""
        return {
            "extracted_data": {
                "content_length": len(content),
                "processing_status": "failed"
            },
            "metadata": {
                "processing_agent": "json_agent",
                "fallback_used": True
            },
            "flags": ["PROCESSING_ERROR"],
            "confidence": 0.2
        }
