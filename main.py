from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import tempfile
import logging
from typing import List
import json
from datetime import datetime

from database import init_db
from models import ProcessingResult
from agents.classifier import ClassifierAgent
from agents.email_agent import EmailAgent
from agents.json_agent import JSONAgent
from agents.pdf_agent import PDFAgent
from services.action_router import ActionRouter
from services.memory_store import MemoryStore
from utils.retry import retry_with_backoff

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Multi-Agent Business Document Processor", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize database
init_db()

# Initialize components
memory_store = MemoryStore()
classifier_agent = ClassifierAgent()
email_agent = EmailAgent()
json_agent = JSONAgent()
pdf_agent = PDFAgent()
action_router = ActionRouter()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main HTML page"""
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload and process a file through the multi-agent system"""
    try:
        # Validate file size (10MB limit)
        if file.size and file.size > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB")
        
        # Read file content
        content = await file.read()
        
        # Save to temporary file for processing
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # Step 1: Classify the file
            classification_result = await retry_with_backoff(
                classifier_agent.classify,
                temp_file_path,
                file.filename,
                content
            )
            
            # Step 2: Store initial metadata
            processing_id = await memory_store.store_processing_result(
                filename=file.filename,
                file_type=classification_result["file_type"],
                business_intent=classification_result["business_intent"],
                status="processing",
                metadata=classification_result
            )
            
            # Step 3: Route to specialized agent
            agent_result = None
            if classification_result["file_type"] == "email":
                agent_result = await retry_with_backoff(
                    email_agent.process,
                    content.decode('utf-8', errors='ignore'),
                    classification_result
                )
            elif classification_result["file_type"] == "json":
                agent_result = await retry_with_backoff(
                    json_agent.process,
                    content.decode('utf-8', errors='ignore'),
                    classification_result
                )
            elif classification_result["file_type"] == "pdf":
                agent_result = await retry_with_backoff(
                    pdf_agent.process,
                    temp_file_path,
                    classification_result
                )
            
            # Step 4: Update with agent results
            if agent_result:
                await memory_store.update_processing_result(
                    processing_id,
                    status="processed",
                    extracted_data=agent_result["extracted_data"],
                    metadata={**classification_result, **agent_result["metadata"]}
                )
            
            # Step 5: Route actions
            actions_taken = await action_router.route_actions(
                classification_result,
                agent_result if agent_result else {},
                processing_id
            )
            
            # Step 6: Final update with actions
            await memory_store.update_processing_result(
                processing_id,
                status="completed",
                actions_taken=actions_taken
            )
            
            return JSONResponse({
                "success": True,
                "processing_id": processing_id,
                "classification": classification_result,
                "agent_result": agent_result,
                "actions_taken": actions_taken
            })
            
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)
            
    except Exception as e:
        logger.error(f"Error processing file {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.get("/results")
async def get_all_results():
    """Get all processing results"""
    try:
        results = await memory_store.get_all_results()
        return JSONResponse({"success": True, "results": results})
    except Exception as e:
        logger.error(f"Error fetching results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching results: {str(e)}")

@app.get("/results/{processing_id}")
async def get_result(processing_id: int):
    """Get a specific processing result"""
    try:
        result = await memory_store.get_result(processing_id)
        if not result:
            raise HTTPException(status_code=404, detail="Result not found")
        return JSONResponse({"success": True, "result": result})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching result {processing_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching result: {str(e)}")

# Mock webhook endpoints for testing actions
@app.post("/webhooks/crm/escalate")
async def crm_escalate_webhook(request: Request):
    """Mock CRM escalation webhook"""
    body = await request.json()
    logger.info(f"CRM Escalation triggered: {body}")
    return JSONResponse({"success": True, "message": "Escalation processed"})

@app.post("/webhooks/risk_alert")
async def risk_alert_webhook(request: Request):
    """Mock risk alert webhook"""
    body = await request.json()
    logger.info(f"Risk Alert triggered: {body}")
    return JSONResponse({"success": True, "message": "Risk alert processed"})

@app.post("/retry-action")
async def retry_action(request: Request):
    """Retry a specific action for a processing result"""
    try:
        data = await request.json()
        processing_id = data.get("processing_id")
        action_type = data.get("action_type")
        
        if not processing_id or not action_type:
            raise HTTPException(status_code=400, detail="Missing processing_id or action_type")
        
        # Get the processing result
        result = await memory_store.get_result(processing_id)
        if not result:
            raise HTTPException(status_code=404, detail="Processing result not found")
        
        # Re-trigger the specific action
        action_router = ActionRouter()
        
        # Build context for action retry
        context = {
            "file_type": result["file_type"],
            "business_intent": result["business_intent"],
            "confidence": result.get("metadata", {}).get("confidence", 0),
            "extracted_data": result.get("extracted_data", {}),
            "processing_id": processing_id
        }
        
        # Execute the specific action
        success = await action_router._execute_action(action_type, {}, context, processing_id)
        
        if success:
            # Update actions_taken list
            current_actions = result.get("actions_taken", [])
            if action_type not in current_actions:
                current_actions.append(action_type)
                await memory_store.update_processing_result(
                    processing_id, 
                    actions_taken=current_actions
                )
            
            return {"status": "success", "message": f"Action {action_type} retried successfully"}
        else:
            return {"status": "failed", "message": f"Failed to retry action {action_type}"}
            
    except Exception as e:
        logger.error(f"Error retrying action: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrying action: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
