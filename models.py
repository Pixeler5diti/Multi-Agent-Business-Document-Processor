from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

class FileClassification(BaseModel):
    file_type: str
    business_intent: str
    confidence: float
    reasoning: str

class AgentResult(BaseModel):
    extracted_data: Dict[str, Any]
    metadata: Dict[str, Any]
    flags: List[str] = []
    confidence: float

class ProcessingResult(BaseModel):
    id: Optional[int] = None
    filename: str
    file_type: str
    business_intent: str
    status: str
    extracted_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    actions_taken: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ActionRequest(BaseModel):
    processing_id: int
    action_type: str
    data: Dict[str, Any]
    urgency: str = "normal"
