import re
import logging
from typing import Dict, Any
import google.generativeai as genai
import os
import json

logger = logging.getLogger(__name__)

class EmailAgent:
    def __init__(self):
        # Configure Gemini AI
        api_key = os.getenv("GEMINI_API_KEY", "default_key")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    async def process(self, content: str, classification: Dict[str, Any]) -> Dict[str, Any]:
        """Process email content and extract relevant information"""
        try:
            # Extract basic email headers
            headers = self._extract_headers(content)
            
            # Use AI to analyze tone and urgency
            ai_analysis = await self._analyze_with_ai(content)
            
            # Combine extracted data
            extracted_data = {
                **headers,
                **ai_analysis,
                "content_length": len(content),
                "has_attachments": self._check_attachments(content)
            }
            
            # Generate flags based on analysis
            flags = self._generate_flags(extracted_data, classification)
            
            # Determine if CRM escalation is needed
            needs_escalation = (
                extracted_data.get("urgency", "").lower() in ["high", "urgent"] and
                extracted_data.get("tone", "").lower() in ["angry", "threatening"]
            )
            
            result = {
                "extracted_data": extracted_data,
                "metadata": {
                    "needs_crm_escalation": needs_escalation,
                    "processing_agent": "email_agent",
                    "analysis_confidence": ai_analysis.get("confidence", 0.5)
                },
                "flags": flags,
                "confidence": ai_analysis.get("confidence", 0.7)
            }
            
            logger.info(f"Email processed: sender={headers.get('sender', 'unknown')}, urgency={ai_analysis.get('urgency', 'unknown')}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing email: {str(e)}")
            return self._fallback_processing(content)

    def _extract_headers(self, content: str) -> Dict[str, str]:
        """Extract email headers using regex"""
        headers = {}
        
        # Extract sender
        sender_match = re.search(r'From:\s*(.+)', content, re.IGNORECASE)
        if sender_match:
            headers["sender"] = sender_match.group(1).strip()
        
        # Extract recipient
        to_match = re.search(r'To:\s*(.+)', content, re.IGNORECASE)
        if to_match:
            headers["recipient"] = to_match.group(1).strip()
        
        # Extract subject
        subject_match = re.search(r'Subject:\s*(.+)', content, re.IGNORECASE)
        if subject_match:
            headers["subject"] = subject_match.group(1).strip()
        
        # Extract date
        date_match = re.search(r'Date:\s*(.+)', content, re.IGNORECASE)
        if date_match:
            headers["date"] = date_match.group(1).strip()
        
        return headers

    async def _analyze_with_ai(self, content: str) -> Dict[str, Any]:
        """Use AI to analyze email tone and urgency"""
        try:
            prompt = f"""
Analyze this email and extract the following information:

Email Content:
{content[:2000]}...

Provide analysis in JSON format:
{{
    "urgency": "low/medium/high/urgent",
    "tone": "polite/neutral/frustrated/angry/threatening",
    "sentiment": "positive/neutral/negative",
    "confidence": 0.0-1.0,
    "key_concerns": ["list", "of", "main", "concerns"],
    "contact_info": "extracted phone/email if any"
}}
"""
            
            response = self.model.generate_content(prompt)
            
            try:
                result = json.loads(response.text.strip())
                return result
            except json.JSONDecodeError:
                # Fallback analysis
                return self._fallback_ai_analysis(content)
                
        except Exception as e:
            logger.error(f"AI analysis failed: {str(e)}")
            return self._fallback_ai_analysis(content)

    def _fallback_ai_analysis(self, content: str) -> Dict[str, Any]:
        """Fallback analysis using rule-based approach"""
        content_lower = content.lower()
        
        # Determine urgency
        urgency = "low"
        if any(word in content_lower for word in ["urgent", "asap", "immediately", "emergency"]):
            urgency = "urgent"
        elif any(word in content_lower for word in ["soon", "quickly", "priority"]):
            urgency = "high"
        elif any(word in content_lower for word in ["when possible", "convenient"]):
            urgency = "medium"
        
        # Determine tone
        tone = "neutral"
        if any(word in content_lower for word in ["please", "thank", "appreciate", "kind"]):
            tone = "polite"
        elif any(word in content_lower for word in ["disappointed", "frustrated", "upset"]):
            tone = "frustrated"
        elif any(word in content_lower for word in ["angry", "outraged", "unacceptable"]):
            tone = "angry"
        elif any(word in content_lower for word in ["lawyer", "legal", "sue", "lawsuit"]):
            tone = "threatening"
        
        # Determine sentiment
        sentiment = "neutral"
        if any(word in content_lower for word in ["happy", "satisfied", "excellent", "great"]):
            sentiment = "positive"
        elif any(word in content_lower for word in ["problem", "issue", "complaint", "terrible"]):
            sentiment = "negative"
        
        return {
            "urgency": urgency,
            "tone": tone,
            "sentiment": sentiment,
            "confidence": 0.6,
            "key_concerns": [],
            "contact_info": self._extract_contact_info(content)
        }

    def _extract_contact_info(self, content: str) -> str:
        """Extract contact information from email"""
        # Extract phone numbers
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        phone_match = re.search(phone_pattern, content)
        if phone_match:
            return phone_match.group()
        
        # Extract email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, content)
        if email_match:
            return email_match.group()
        
        return ""

    def _check_attachments(self, content: str) -> bool:
        """Check if email mentions attachments"""
        attachment_keywords = ["attachment", "attached", "file", "document", "pdf", "image"]
        content_lower = content.lower()
        return any(keyword in content_lower for keyword in attachment_keywords)

    def _generate_flags(self, extracted_data: Dict[str, Any], classification: Dict[str, Any]) -> list:
        """Generate flags based on extracted data"""
        flags = []
        
        if extracted_data.get("urgency") == "urgent":
            flags.append("URGENT_EMAIL")
        
        if extracted_data.get("tone") in ["angry", "threatening"]:
            flags.append("NEGATIVE_TONE")
        
        if extracted_data.get("tone") == "threatening":
            flags.append("LEGAL_THREAT")
        
        if classification.get("business_intent") == "Complaint":
            flags.append("CUSTOMER_COMPLAINT")
        
        if extracted_data.get("has_attachments"):
            flags.append("HAS_ATTACHMENTS")
        
        return flags

    def _fallback_processing(self, content: str) -> Dict[str, Any]:
        """Fallback processing when main processing fails"""
        return {
            "extracted_data": {
                "sender": "unknown",
                "urgency": "medium",
                "tone": "neutral",
                "content_length": len(content)
            },
            "metadata": {
                "needs_crm_escalation": False,
                "processing_agent": "email_agent",
                "fallback_used": True
            },
            "flags": ["PROCESSING_ERROR"],
            "confidence": 0.3
        }
