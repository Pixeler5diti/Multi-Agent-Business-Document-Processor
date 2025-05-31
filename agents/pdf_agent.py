import PyPDF2
import logging
from typing import Dict, Any
import re
import os
import google.generativeai as genai
import json

logger = logging.getLogger(__name__)

class PDFAgent:
    def __init__(self):
        # Configure Gemini AI
        api_key = os.getenv("GEMINI_API_KEY", "default_key")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    async def process(self, file_path: str, classification: Dict[str, Any]) -> Dict[str, Any]:
        """Process PDF file and extract relevant information"""
        try:
            # Extract text from PDF
            text_content = self._extract_text(file_path)
            
            if not text_content.strip():
                logger.warning("No text content extracted from PDF")
                return self._handle_empty_pdf(file_path)
            
            # Get PDF metadata
            metadata = self._extract_metadata(file_path)
            
            # Use AI to extract structured data
            ai_analysis = await self._analyze_with_ai(text_content, classification)
            
            # Extract business-specific fields
            business_fields = self._extract_business_fields(text_content)
            
            # Combine extracted data
            extracted_data = {
                **business_fields,
                **ai_analysis.get("extracted_fields", {}),
                "text_length": len(text_content),
                "page_count": metadata.get("page_count", 0),
                "content_preview": text_content[:500]
            }
            
            # Generate flags
            flags = self._generate_flags(text_content, extracted_data, classification)
            
            result = {
                "extracted_data": extracted_data,
                "metadata": {
                    "processing_agent": "pdf_agent",
                    "pdf_metadata": metadata,
                    "text_extraction_successful": True,
                    "ai_analysis_confidence": ai_analysis.get("confidence", 0.5)
                },
                "flags": flags,
                "confidence": 0.8 if text_content else 0.3
            }
            
            logger.info(f"PDF processed: pages={metadata.get('page_count', 0)}, text_length={len(text_content)}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return self._fallback_processing(file_path, str(e))

    def _extract_text(self, file_path: str) -> str:
        """Extract text content from PDF"""
        text_content = ""
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        text_content += page_text + "\n"
                        
                        # Limit extraction to prevent memory issues
                        if len(text_content) > 50000:  # 50KB limit
                            logger.warning("PDF text extraction truncated due to size limit")
                            break
                            
                    except Exception as e:
                        logger.warning(f"Error extracting text from page {page_num}: {str(e)}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error opening PDF file: {str(e)}")
            raise
        
        return text_content.strip()

    def _extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract PDF metadata"""
        metadata = {}
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                metadata["page_count"] = len(pdf_reader.pages)
                
                # Extract document info
                if pdf_reader.metadata:
                    metadata["title"] = pdf_reader.metadata.get('/Title', '')
                    metadata["author"] = pdf_reader.metadata.get('/Author', '')
                    metadata["subject"] = pdf_reader.metadata.get('/Subject', '')
                    metadata["creator"] = pdf_reader.metadata.get('/Creator', '')
                    metadata["producer"] = pdf_reader.metadata.get('/Producer', '')
                    
                    # Convert dates if present
                    creation_date = pdf_reader.metadata.get('/CreationDate')
                    if creation_date:
                        metadata["creation_date"] = str(creation_date)
                
                # Check for encryption
                metadata["is_encrypted"] = pdf_reader.is_encrypted
                
                # File size
                metadata["file_size"] = os.path.getsize(file_path)
                
        except Exception as e:
            logger.error(f"Error extracting PDF metadata: {str(e)}")
            metadata["extraction_error"] = str(e)
        
        return metadata

    async def _analyze_with_ai(self, text_content: str, classification: Dict[str, Any]) -> Dict[str, Any]:
        """Use AI to analyze PDF content and extract structured data"""
        try:
            business_intent = classification.get("business_intent", "Unknown")
            
            prompt = f"""
Analyze this PDF document content and extract relevant information based on the business intent: {business_intent}

Document Content:
{text_content[:3000]}...

Extract the following information in JSON format:
{{
    "extracted_fields": {{
        "document_type": "invoice/contract/report/letter/other",
        "key_amounts": ["list of monetary amounts found"],
        "dates": ["list of important dates"],
        "contact_info": "any contact information found",
        "key_entities": ["companies, people, organizations mentioned"],
        "compliance_mentions": ["GDPR, FDA, or other regulatory mentions"]
    }},
    "confidence": 0.0-1.0,
    "summary": "brief summary of document content"
}}
"""
            
            response = self.model.generate_content(prompt)
            
            try:
                result = json.loads(response.text.strip())
                return result
            except json.JSONDecodeError:
                return self._fallback_ai_analysis(text_content)
                
        except Exception as e:
            logger.error(f"AI analysis failed: {str(e)}")
            return self._fallback_ai_analysis(text_content)

    def _fallback_ai_analysis(self, text_content: str) -> Dict[str, Any]:
        """Fallback analysis using rule-based extraction"""
        extracted_fields = {}
        
        # Extract monetary amounts
        money_pattern = r'\$\s*[\d,]+\.?\d*|\d+\.\d{2}\s*(?:USD|EUR|GBP)'
        amounts = re.findall(money_pattern, text_content)
        if amounts:
            extracted_fields["key_amounts"] = amounts[:5]  # Limit to first 5
        
        # Extract dates
        date_pattern = r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b'
        dates = re.findall(date_pattern, text_content)
        if dates:
            extracted_fields["dates"] = list(set(dates))[:5]  # Unique dates, limit to 5
        
        # Extract email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text_content)
        if emails:
            extracted_fields["contact_info"] = emails[0]  # First email found
        
        # Check for compliance mentions
        compliance_keywords = ["gdpr", "fda", "hipaa", "sox", "regulation", "compliance"]
        compliance_mentions = [keyword for keyword in compliance_keywords 
                             if keyword.lower() in text_content.lower()]
        if compliance_mentions:
            extracted_fields["compliance_mentions"] = compliance_mentions
        
        return {
            "extracted_fields": extracted_fields,
            "confidence": 0.6,
            "summary": "Rule-based extraction performed"
        }

    def _extract_business_fields(self, text_content: str) -> Dict[str, Any]:
        """Extract business-specific fields using regex patterns"""
        fields = {}
        
        # Invoice numbers
        invoice_patterns = [
            r'invoice\s*#?\s*(\d+)',
            r'inv\s*#?\s*(\d+)',
            r'bill\s*#?\s*(\d+)'
        ]
        
        for pattern in invoice_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                fields["invoice_number"] = match.group(1)
                break
        
        # Total amounts
        total_patterns = [
            r'total[:\s]*\$?\s*([\d,]+\.?\d*)',
            r'amount[:\s]*\$?\s*([\d,]+\.?\d*)',
            r'sum[:\s]*\$?\s*([\d,]+\.?\d*)'
        ]
        
        for pattern in total_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    fields["total_amount"] = float(amount_str)
                    break
                except ValueError:
                    continue
        
        # Phone numbers
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        phone_match = re.search(phone_pattern, text_content)
        if phone_match:
            fields["phone_number"] = phone_match.group()
        
        return fields

    def _generate_flags(self, text_content: str, extracted_data: Dict[str, Any], classification: Dict[str, Any]) -> list:
        """Generate flags based on PDF analysis"""
        flags = []
        
        # High value flag
        total_amount = extracted_data.get("total_amount")
        if total_amount and total_amount > 10000:
            flags.append("HIGH_VALUE_INVOICE")
        
        # Compliance flags
        compliance_mentions = extracted_data.get("compliance_mentions", [])
        if compliance_mentions:
            flags.append("REGULATORY_CONTENT")
            if "gdpr" in [mention.lower() for mention in compliance_mentions]:
                flags.append("GDPR_MENTIONED")
            if "fda" in [mention.lower() for mention in compliance_mentions]:
                flags.append("FDA_MENTIONED")
        
        # Content analysis flags
        text_lower = text_content.lower()
        
        if any(word in text_lower for word in ["urgent", "immediate", "asap"]):
            flags.append("URGENT_CONTENT")
        
        if any(word in text_lower for word in ["confidential", "private", "secret"]):
            flags.append("CONFIDENTIAL_CONTENT")
        
        if any(word in text_lower for word in ["fraud", "suspicious", "investigate"]):
            flags.append("FRAUD_INDICATORS")
        
        # Document quality flags
        if len(text_content) < 100:
            flags.append("SHORT_DOCUMENT")
        
        if not extracted_data.get("total_amount") and classification.get("business_intent") == "Invoice":
            flags.append("MISSING_AMOUNT")
        
        return flags

    def _handle_empty_pdf(self, file_path: str) -> Dict[str, Any]:
        """Handle PDFs with no extractable text"""
        metadata = self._extract_metadata(file_path)
        
        return {
            "extracted_data": {
                "text_content": "",
                "extraction_status": "no_text_found",
                "page_count": metadata.get("page_count", 0)
            },
            "metadata": {
                "processing_agent": "pdf_agent",
                "pdf_metadata": metadata,
                "text_extraction_successful": False
            },
            "flags": ["NO_TEXT_CONTENT", "POSSIBLE_IMAGE_PDF"],
            "confidence": 0.2
        }

    def _fallback_processing(self, file_path: str, error: str) -> Dict[str, Any]:
        """Fallback processing when main processing fails"""
        return {
            "extracted_data": {
                "processing_error": error,
                "file_path": os.path.basename(file_path)
            },
            "metadata": {
                "processing_agent": "pdf_agent",
                "fallback_used": True,
                "error_details": error
            },
            "flags": ["PROCESSING_ERROR", "PDF_READ_FAILED"],
            "confidence": 0.1
        }
