import google.generativeai as genai
import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ClassifierAgent:
    def __init__(self):
        # Configure Gemini AI
        api_key = os.getenv("GEMINI_API_KEY", "default_key")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Few-shot examples for classification
        self.classification_examples = """
Examples of file classification:

1. Email about pricing inquiry:
   File Type: email
   Business Intent: RFQ
   
2. JSON invoice data with amount > $10,000:
   File Type: json
   Business Intent: Invoice
   
3. PDF complaint letter with angry tone:
   File Type: pdf
   Business Intent: Complaint
   
4. Email mentioning GDPR violations:
   File Type: email
   Business Intent: Regulation
   
5. JSON transaction data with suspicious patterns:
   File Type: json
   Business Intent: Fraud Risk
"""

    async def classify(self, file_path: str, filename: str, content: bytes) -> Dict[str, Any]:
        """Classify file type and business intent"""
        try:
            # Determine file type from extension and content
            file_type = self._detect_file_type(filename, content)
            
            # Prepare content for AI analysis
            text_content = self._extract_text_content(content, file_type)
            
            # Create classification prompt
            prompt = f"""
{self.classification_examples}

Analyze this {file_type} file and classify it:

Filename: {filename}
Content preview: {text_content[:2000]}...

Classify this file with:
1. File Type: email, json, or pdf
2. Business Intent: RFQ, Complaint, Invoice, Regulation, or Fraud Risk

Provide your response in JSON format:
{{
    "file_type": "email/json/pdf",
    "business_intent": "RFQ/Complaint/Invoice/Regulation/Fraud Risk",
    "confidence": 0.0-1.0,
    "reasoning": "explanation of classification decision"
}}
"""

            # Get AI classification
            response = self.model.generate_content(prompt)
            
            try:
                # Parse AI response
                ai_result = json.loads(response.text.strip())
                
                # Validate and normalize the result
                result = {
                    "file_type": ai_result.get("file_type", file_type).lower(),
                    "business_intent": ai_result.get("business_intent", "Unknown"),
                    "confidence": float(ai_result.get("confidence", 0.5)),
                    "reasoning": ai_result.get("reasoning", "AI classification"),
                    "filename": filename,
                    "detected_file_type": file_type
                }
                
                logger.info(f"Classified {filename} as {result['file_type']} with intent {result['business_intent']}")
                return result
                
            except json.JSONDecodeError:
                # Fallback if AI response is not valid JSON
                logger.warning(f"AI response not valid JSON for {filename}, using fallback classification")
                return self._fallback_classification(filename, file_type, text_content)
                
        except Exception as e:
            logger.error(f"Error classifying file {filename}: {str(e)}")
            return self._fallback_classification(filename, file_type if 'file_type' in locals() else "unknown", "")

    def _detect_file_type(self, filename: str, content: bytes) -> str:
        """Detect file type from filename and content"""
        filename_lower = filename.lower()
        
        if filename_lower.endswith('.pdf'):
            return "pdf"
        elif filename_lower.endswith('.json'):
            return "json"
        elif filename_lower.endswith(('.eml', '.msg', '.txt')):
            return "email"
        
        # Try to detect from content
        try:
            text_content = content.decode('utf-8', errors='ignore')
            
            # Check for PDF signature
            if content.startswith(b'%PDF'):
                return "pdf"
            
            # Check for JSON structure
            try:
                json.loads(text_content)
                return "json"
            except json.JSONDecodeError:
                pass
            
            # Check for email headers
            if any(header in text_content.lower() for header in ['from:', 'to:', 'subject:', 'date:']):
                return "email"
                
        except Exception:
            pass
        
        return "unknown"

    def _extract_text_content(self, content: bytes, file_type: str) -> str:
        """Extract text content for AI analysis"""
        try:
            if file_type == "pdf":
                # For PDF, we'll extract text in the PDF agent
                return f"PDF file detected - content will be extracted by PDF agent"
            else:
                return content.decode('utf-8', errors='ignore')
        except Exception:
            return "Could not extract text content"

    def _fallback_classification(self, filename: str, file_type: str, content: str) -> Dict[str, Any]:
        """Fallback classification when AI fails"""
        # Enhanced rule-based classification with better keyword matching
        business_intent = "Unknown"
        confidence = 0.3
        reasoning = "Rule-based classification"
        
        content_lower = content.lower()
        filename_lower = filename.lower()
        
        # Check filename for hints
        filename_hints = {
            'complaint': 'Complaint',
            'invoice': 'Invoice', 
            'bill': 'Invoice',
            'quote': 'RFQ',
            'rfq': 'RFQ',
            'regulation': 'Regulation',
            'compliance': 'Regulation',
            'fraud': 'Fraud Risk'
        }
        
        for hint, intent in filename_hints.items():
            if hint in filename_lower:
                business_intent = intent
                confidence = 0.7
                reasoning = f"Filename contains '{hint}'"
                break
        
        # If no filename hint, analyze content more thoroughly
        if business_intent == "Unknown":
            # RFQ keywords
            rfq_keywords = ['quote', 'rfq', 'request for quote', 'pricing', 'proposal', 'bid', 'quotation']
            rfq_score = sum(1 for keyword in rfq_keywords if keyword in content_lower)
            
            # Complaint keywords  
            complaint_keywords = ['complaint', 'dissatisfied', 'problem', 'issue', 'unhappy', 'terrible', 
                                'disappointed', 'angry', 'frustrated', 'unacceptable', 'poor service']
            complaint_score = sum(1 for keyword in complaint_keywords if keyword in content_lower)
            
            # Invoice keywords
            invoice_keywords = ['invoice', 'bill', 'payment', 'amount', 'total', 'due', 'balance', 
                              'invoice number', 'account payable', 'remittance']
            invoice_score = sum(1 for keyword in invoice_keywords if keyword in content_lower)
            
            # Regulation keywords
            regulation_keywords = ['gdpr', 'regulation', 'compliance', 'fda', 'regulatory', 'policy', 
                                 'standard', 'requirement', 'audit', 'certification']
            regulation_score = sum(1 for keyword in regulation_keywords if keyword in content_lower)
            
            # Fraud keywords
            fraud_keywords = ['fraud', 'suspicious', 'anomaly', 'irregular', 'unauthorized', 
                            'security breach', 'investigation', 'alert']
            fraud_score = sum(1 for keyword in fraud_keywords if keyword in content_lower)
            
            # Determine intent based on highest score
            scores = {
                'RFQ': rfq_score,
                'Complaint': complaint_score, 
                'Invoice': invoice_score,
                'Regulation': regulation_score,
                'Fraud Risk': fraud_score
            }
            
            max_score = max(scores.values())
            if max_score > 0:
                business_intent = max(scores, key=scores.get)
                confidence = min(0.8, 0.4 + (max_score * 0.1))  # Scale confidence with keyword matches
                reasoning = f"Content analysis: {max_score} relevant keywords found"
        
        return {
            "file_type": file_type,
            "business_intent": business_intent,
            "confidence": confidence,
            "reasoning": reasoning,
            "filename": filename,
            "detected_file_type": file_type
        }
