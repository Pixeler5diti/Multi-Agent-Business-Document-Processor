import logging
import httpx
from typing import Dict, Any, List
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class ActionRouter:
    def __init__(self):
        self.base_url = "http://localhost:5000"  # Local webhooks for testing
        
        # Action routing rules
        self.routing_rules = {
            "crm_escalation": {
                "conditions": [
                    ("urgency", ["high", "urgent"]),
                    ("tone", ["angry", "threatening"]),
                    ("business_intent", ["Complaint"])
                ],
                "webhook": "/webhooks/crm/escalate"
            },
            "risk_alert": {
                "conditions": [
                    ("business_intent", ["Fraud Risk"]),
                    ("high_value", True),
                    ("regulatory_flags", True)
                ],
                "webhook": "/webhooks/risk_alert"
            }
        }

    async def route_actions(self, classification: Dict[str, Any], agent_result: Dict[str, Any], processing_id: int) -> List[str]:
        """Route actions based on classification and agent results"""
        actions_taken = []
        
        try:
            # Prepare decision context
            context = self._build_decision_context(classification, agent_result)
            
            # Check each routing rule
            for action_name, rule in self.routing_rules.items():
                if self._should_trigger_action(context, rule):
                    success = await self._execute_action(action_name, rule, context, processing_id)
                    if success:
                        actions_taken.append(action_name)
                        logger.info(f"Action executed: {action_name} for processing_id: {processing_id}")
                    else:
                        logger.error(f"Failed to execute action: {action_name}")
            
            # Check for additional business logic
            additional_actions = self._check_additional_actions(context, processing_id)
            actions_taken.extend(additional_actions)
            
            return actions_taken
            
        except Exception as e:
            logger.error(f"Error in action routing: {str(e)}")
            return ["routing_error"]

    def _build_decision_context(self, classification: Dict[str, Any], agent_result: Dict[str, Any]) -> Dict[str, Any]:
        """Build context for action routing decisions"""
        context = {
            "file_type": classification.get("file_type"),
            "business_intent": classification.get("business_intent"),
            "confidence": classification.get("confidence", 0.5)
        }
        
        # Add agent-specific data
        if agent_result and "extracted_data" in agent_result:
            extracted_data = agent_result["extracted_data"]
            
            # Email-specific context
            if classification.get("file_type") == "email":
                context.update({
                    "urgency": extracted_data.get("urgency", "medium"),
                    "tone": extracted_data.get("tone", "neutral"),
                    "sentiment": extracted_data.get("sentiment", "neutral"),
                    "needs_crm_escalation": agent_result.get("metadata", {}).get("needs_crm_escalation", False)
                })
            
            # JSON-specific context
            elif classification.get("file_type") == "json":
                monetary_value = extracted_data.get("monetary_value")
                context.update({
                    "high_value": monetary_value and float(str(monetary_value).replace(',', '')) > 10000 if monetary_value else False,
                    "schema_valid": agent_result.get("metadata", {}).get("validation_result", {}).get("is_valid", False)
                })
            
            # PDF-specific context
            elif classification.get("file_type") == "pdf":
                total_amount = extracted_data.get("total_amount")
                compliance_mentions = extracted_data.get("compliance_mentions", [])
                context.update({
                    "high_value": total_amount and total_amount > 10000 if total_amount else False,
                    "regulatory_flags": len(compliance_mentions) > 0
                })
        
        # Add flags context
        if agent_result and "flags" in agent_result:
            flags = agent_result["flags"]
            context.update({
                "has_urgent_flags": any("URGENT" in flag for flag in flags),
                "has_risk_flags": any("FRAUD" in flag or "RISK" in flag for flag in flags),
                "has_compliance_flags": any("GDPR" in flag or "FDA" in flag or "REGULATORY" in flag for flag in flags)
            })
        
        return context

    def _should_trigger_action(self, context: Dict[str, Any], rule: Dict[str, Any]) -> bool:
        """Determine if an action should be triggered based on context and rules"""
        conditions = rule.get("conditions", [])
        
        for condition in conditions:
            field, expected_values = condition
            
            if field not in context:
                continue
            
            context_value = context[field]
            
            # Handle different condition types
            if isinstance(expected_values, list):
                if context_value not in expected_values:
                    return False
            elif isinstance(expected_values, bool):
                if bool(context_value) != expected_values:
                    return False
            else:
                if context_value != expected_values:
                    return False
        
        return len(conditions) > 0  # Only trigger if there are conditions and all are met

    async def _execute_action(self, action_name: str, rule: Dict[str, Any], context: Dict[str, Any], processing_id: int) -> bool:
        """Execute the specified action"""
        try:
            webhook_path = rule.get("webhook")
            if not webhook_path:
                logger.error(f"No webhook configured for action: {action_name}")
                return False
            
            # Prepare webhook payload
            payload = {
                "action": action_name,
                "processing_id": processing_id,
                "context": context,
                "timestamp": datetime.utcnow().isoformat(),
                "trigger_conditions": rule.get("conditions", [])
            }
            
            # Send webhook request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}{webhook_path}",
                    json=payload,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    logger.info(f"Webhook successful for {action_name}: {response.status_code}")
                    return True
                else:
                    logger.error(f"Webhook failed for {action_name}: {response.status_code}")
                    return False
                    
        except httpx.TimeoutException:
            logger.error(f"Webhook timeout for action: {action_name}")
            return False
        except Exception as e:
            logger.error(f"Error executing action {action_name}: {str(e)}")
            return False

    def _check_additional_actions(self, context: Dict[str, Any], processing_id: int) -> List[str]:
        """Check for additional business logic actions"""
        additional_actions = []
        
        # High confidence classification
        if context.get("confidence", 0) > 0.9:
            additional_actions.append("high_confidence_processing")
        
        # Multiple risk indicators
        risk_score = 0
        if context.get("has_risk_flags"):
            risk_score += 1
        if context.get("has_compliance_flags"):
            risk_score += 1
        if context.get("high_value"):
            risk_score += 1
        if context.get("tone") in ["angry", "threatening"]:
            risk_score += 1
        
        if risk_score >= 2:
            additional_actions.append("multi_risk_flag_review")
        
        # Business intent specific actions
        business_intent = context.get("business_intent")
        if business_intent == "Invoice" and context.get("high_value"):
            additional_actions.append("high_value_invoice_approval")
        elif business_intent == "RFQ":
            additional_actions.append("rfq_sales_notification")
        elif business_intent == "Regulation" and context.get("has_compliance_flags"):
            additional_actions.append("compliance_team_alert")
        
        return additional_actions

    async def test_webhooks(self) -> Dict[str, bool]:
        """Test webhook endpoints availability"""
        results = {}
        
        for action_name, rule in self.routing_rules.items():
            webhook_path = rule.get("webhook")
            if webhook_path:
                try:
                    async with httpx.AsyncClient() as client:
                        # Send a test payload
                        test_payload = {
                            "test": True,
                            "action": action_name,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        
                        response = await client.post(
                            f"{self.base_url}{webhook_path}",
                            json=test_payload,
                            timeout=5.0
                        )
                        
                        results[action_name] = response.status_code == 200
                        
                except Exception as e:
                    logger.error(f"Webhook test failed for {action_name}: {str(e)}")
                    results[action_name] = False
            else:
                results[action_name] = False
        
        return results
