from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from database import ProcessingResult, get_db, SessionLocal
from typing import Dict, Any, List, Optional
import logging
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MemoryStore:
    def __init__(self):
        self.SessionLocal = SessionLocal

    async def store_processing_result(self, filename: str, file_type: str, business_intent: str, 
                                    status: str = "pending", metadata: Optional[Dict[str, Any]] = None,
                                    extracted_data: Optional[Dict[str, Any]] = None,
                                    actions_taken: Optional[List[str]] = None) -> int:
        """Store a new processing result and return the ID"""
        try:
            db = self.SessionLocal()
            
            result = ProcessingResult(
                filename=filename,
                file_type=file_type,
                business_intent=business_intent,
                status=status,
                processing_metadata=metadata or {},
                extracted_data=extracted_data or {},
                actions_taken=actions_taken or []
            )
            
            db.add(result)
            db.commit()
            db.refresh(result)
            
            processing_id = result.id
            logger.info(f"Stored processing result with ID: {processing_id}")
            
            db.close()
            return processing_id
            
        except Exception as e:
            logger.error(f"Error storing processing result: {str(e)}")
            if 'db' in locals():
                db.rollback()
                db.close()
            raise

    async def update_processing_result(self, processing_id: int, status: Optional[str] = None,
                                     extracted_data: Optional[Dict[str, Any]] = None,
                                     metadata: Optional[Dict[str, Any]] = None,
                                     actions_taken: Optional[List[str]] = None) -> bool:
        """Update an existing processing result"""
        try:
            db = self.SessionLocal()
            
            result = db.query(ProcessingResult).filter(ProcessingResult.id == processing_id).first()
            
            if not result:
                logger.error(f"Processing result not found: {processing_id}")
                db.close()
                return False
            
            # Update fields if provided
            if status is not None:
                result.status = status
            
            if extracted_data is not None:
                # Merge with existing data
                existing_data = result.extracted_data or {}
                existing_data.update(extracted_data)
                result.extracted_data = existing_data
            
            if metadata is not None:
                # Merge with existing metadata
                existing_metadata = result.processing_metadata or {}
                existing_metadata.update(metadata)
                result.processing_metadata = existing_metadata
            
            if actions_taken is not None:
                # Append to existing actions
                existing_actions = result.actions_taken or []
                existing_actions.extend(actions_taken)
                result.actions_taken = list(set(existing_actions))  # Remove duplicates
            
            result.updated_at = datetime.utcnow()
            
            db.commit()
            logger.info(f"Updated processing result: {processing_id}")
            
            db.close()
            return True
            
        except Exception as e:
            logger.error(f"Error updating processing result {processing_id}: {str(e)}")
            if 'db' in locals():
                db.rollback()
                db.close()
            return False

    async def get_result(self, processing_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific processing result"""
        try:
            db = self.SessionLocal()
            
            result = db.query(ProcessingResult).filter(ProcessingResult.id == processing_id).first()
            
            if not result:
                db.close()
                return None
            
            result_dict = self._result_to_dict(result)
            db.close()
            
            return result_dict
            
        except Exception as e:
            logger.error(f"Error fetching result {processing_id}: {str(e)}")
            if 'db' in locals():
                db.close()
            return None

    async def get_all_results(self, limit: int = 100, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all processing results with optional filtering"""
        try:
            db = self.SessionLocal()
            
            query = db.query(ProcessingResult)
            
            if status:
                query = query.filter(ProcessingResult.status == status)
            
            results = query.order_by(ProcessingResult.created_at.desc()).limit(limit).all()
            
            results_list = [self._result_to_dict(result) for result in results]
            db.close()
            
            return results_list
            
        except Exception as e:
            logger.error(f"Error fetching all results: {str(e)}")
            if 'db' in locals():
                db.close()
            return []

    async def get_results_by_file_type(self, file_type: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get processing results filtered by file type"""
        try:
            db = self.SessionLocal()
            
            results = db.query(ProcessingResult).filter(
                ProcessingResult.file_type == file_type
            ).order_by(ProcessingResult.created_at.desc()).limit(limit).all()
            
            results_list = [self._result_to_dict(result) for result in results]
            db.close()
            
            return results_list
            
        except Exception as e:
            logger.error(f"Error fetching results by file type {file_type}: {str(e)}")
            if 'db' in locals():
                db.close()
            return []

    async def get_results_by_business_intent(self, business_intent: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get processing results filtered by business intent"""
        try:
            db = self.SessionLocal()
            
            results = db.query(ProcessingResult).filter(
                ProcessingResult.business_intent == business_intent
            ).order_by(ProcessingResult.created_at.desc()).limit(limit).all()
            
            results_list = [self._result_to_dict(result) for result in results]
            db.close()
            
            return results_list
            
        except Exception as e:
            logger.error(f"Error fetching results by business intent {business_intent}: {str(e)}")
            if 'db' in locals():
                db.close()
            return []

    async def get_flagged_results(self, flag_pattern: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get processing results that have specific flags"""
        try:
            db = self.SessionLocal()
            
            # Note: This is a simplified search. For production, consider using a proper full-text search
            query = db.query(ProcessingResult)
            
            if flag_pattern:
                # Filter based on metadata or actions containing the flag pattern
                results = []
                all_results = query.order_by(ProcessingResult.created_at.desc()).limit(limit * 2).all()
                
                for result in all_results:
                    metadata_str = json.dumps(result.metadata or {}).lower()
                    actions_str = json.dumps(result.actions_taken or []).lower()
                    
                    if flag_pattern.lower() in metadata_str or flag_pattern.lower() in actions_str:
                        results.append(result)
                        
                    if len(results) >= limit:
                        break
            else:
                results = query.order_by(ProcessingResult.created_at.desc()).limit(limit).all()
            
            results_list = [self._result_to_dict(result) for result in results]
            db.close()
            
            return results_list
            
        except Exception as e:
            logger.error(f"Error fetching flagged results: {str(e)}")
            if 'db' in locals():
                db.close()
            return []

    async def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics"""
        try:
            db = self.SessionLocal()
            
            # Total counts
            total_count = db.query(ProcessingResult).count()
            
            # Status breakdown
            status_counts = {}
            statuses = db.query(ProcessingResult.status).distinct().all()
            for (status,) in statuses:
                count = db.query(ProcessingResult).filter(ProcessingResult.status == status).count()
                status_counts[status] = count
            
            # File type breakdown
            file_type_counts = {}
            file_types = db.query(ProcessingResult.file_type).distinct().all()
            for (file_type,) in file_types:
                count = db.query(ProcessingResult).filter(ProcessingResult.file_type == file_type).count()
                file_type_counts[file_type] = count
            
            # Business intent breakdown
            intent_counts = {}
            intents = db.query(ProcessingResult.business_intent).distinct().all()
            for (intent,) in intents:
                count = db.query(ProcessingResult).filter(ProcessingResult.business_intent == intent).count()
                intent_counts[intent] = count
            
            # Recent activity (last 24 hours)
            from datetime import datetime, timedelta
            yesterday = datetime.utcnow() - timedelta(days=1)
            recent_count = db.query(ProcessingResult).filter(
                ProcessingResult.created_at >= yesterday
            ).count()
            
            statistics = {
                "total_processed": total_count,
                "status_breakdown": status_counts,
                "file_type_breakdown": file_type_counts,
                "business_intent_breakdown": intent_counts,
                "recent_24h": recent_count,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            db.close()
            return statistics
            
        except Exception as e:
            logger.error(f"Error generating statistics: {str(e)}")
            if 'db' in locals():
                db.close()
            return {}

    def _result_to_dict(self, result: ProcessingResult) -> Dict[str, Any]:
        """Convert SQLAlchemy result to dictionary"""
        return {
            "id": result.id,
            "filename": result.filename,
            "file_type": result.file_type,
            "business_intent": result.business_intent,
            "status": result.status,
            "extracted_data": result.extracted_data or {},
            "metadata": result.processing_metadata or {},
            "actions_taken": result.actions_taken or [],
            "created_at": result.created_at.isoformat() if result.created_at else None,
            "updated_at": result.updated_at.isoformat() if result.updated_at else None
        }

    async def cleanup_old_results(self, days_old: int = 30) -> int:
        """Clean up old processing results (for maintenance)"""
        try:
            db = self.SessionLocal()
            
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            deleted_count = db.query(ProcessingResult).filter(
                ProcessingResult.created_at < cutoff_date
            ).delete()
            
            db.commit()
            db.close()
            
            logger.info(f"Cleaned up {deleted_count} old results")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old results: {str(e)}")
            if 'db' in locals():
                db.rollback()
                db.close()
            return 0
