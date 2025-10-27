# app/services/training_automation.py
"""
Automated training workflow with notifications
"""
import subprocess
import logging
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from app.models.rasa_content import TrainingJob
from app.services.rasa_trainer import RasaTrainer

logger = logging.getLogger(__name__)


class TrainingAutomation:
    """Handles automated training workflows with bot restart"""
    
    def __init__(self, db: Session):
        self.db = db
        self.trainer = RasaTrainer(db)
    
    async def train_and_deploy(
        self, 
        job_id: UUID,
        auto_restart: bool = True,
        notification_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Complete automated workflow: Train -> Deploy -> Notify
        
        Args:
            job_id: Training job UUID
            auto_restart: Whether to automatically restart bot after training
            notification_callback: Async function to call with status updates
            
        Returns:
            Dictionary with deployment status and details
        """
        result = {
            'job_id': str(job_id),
            'training_status': 'pending',
            'deployment_status': 'pending',
            'notifications_sent': []
        }
        
        try:
            # Notify: Training started
            if notification_callback:
                await notification_callback({
                    'event': 'training_started',
                    'job_id': str(job_id),
                    'message': 'Model training has started'
                })
                result['notifications_sent'].append('training_started')
            
            # Step 1: Train the model
            logger.info(f"Starting automated training for job {job_id}")
            job = self.trainer.train_model(job_id)
            
            result['training_status'] = job.status
            result['model_path'] = job.model_path
            result['model_version'] = job.model_version
            result['duration_seconds'] = job.duration_seconds
            
            if job.status != "completed":
                # Training failed
                result['deployment_status'] = 'skipped'
                result['error'] = job.error_message
                
                if notification_callback:
                    await notification_callback({
                        'event': 'training_failed',
                        'job_id': str(job_id),
                        'error': job.error_message,
                        'duration': job.duration_seconds
                    })
                    result['notifications_sent'].append('training_failed')
                
                return result
            
            # Notify: Training completed
            if notification_callback:
                await notification_callback({
                    'event': 'training_completed',
                    'job_id': str(job_id),
                    'model_version': job.model_version,
                    'duration': job.duration_seconds,
                    'message': f'Training completed in {job.training_metadata.get("duration_formatted", "unknown")}'
                })
                result['notifications_sent'].append('training_completed')
            
            # Step 2: Restart bot (if enabled)
            if auto_restart:
                logger.info(f"Restarting bot with model: {job.model_path}")
                
                restart_result = self._restart_bot()
                result['deployment_status'] = restart_result['status']
                result['restart_output'] = restart_result.get('output')
                
                if restart_result['status'] == 'success':
                    # Notify: Deployment successful
                    if notification_callback:
                        await notification_callback({
                            'event': 'deployment_completed',
                            'job_id': str(job_id),
                            'model_version': job.model_version,
                            'model_path': job.model_path,
                            'message': 'Bot restarted successfully with new model'
                        })
                        result['notifications_sent'].append('deployment_completed')
                else:
                    # Notify: Restart failed
                    if notification_callback:
                        await notification_callback({
                            'event': 'deployment_failed',
                            'job_id': str(job_id),
                            'error': restart_result.get('error'),
                            'message': 'Training succeeded but bot restart failed'
                        })
                        result['notifications_sent'].append('deployment_failed')
            else:
                result['deployment_status'] = 'skipped'
                logger.info("Auto-restart disabled, skipping bot restart")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in automated training workflow: {e}")
            result['training_status'] = 'error'
            result['deployment_status'] = 'error'
            result['error'] = str(e)
            
            # Notify: Workflow error
            if notification_callback:
                await notification_callback({
                    'event': 'workflow_error',
                    'job_id': str(job_id),
                    'error': str(e),
                    'message': 'Training workflow encountered an error'
                })
                result['notifications_sent'].append('workflow_error')
            
            return result
    
    def _restart_bot(self) -> Dict[str, Any]:
        """Restart the Rasa bot using PM2"""
        try:
            result = subprocess.run(
                ['pm2', 'restart', 'rasa-server'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return {
                    'status': 'success',
                    'output': result.stdout
                }
            else:
                return {
                    'status': 'failed',
                    'error': result.stderr,
                    'output': result.stdout
                }
                
        except subprocess.TimeoutExpired:
            return {
                'status': 'timeout',
                'error': 'PM2 restart timed out after 30 seconds'
            }
        except FileNotFoundError:
            return {
                'status': 'not_found',
                'error': 'PM2 not found - is it installed?'
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def get_training_summary(self, job_id: UUID) -> Dict[str, Any]:
        """Get detailed summary of a training job"""
        job = self.db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
        
        if not job:
            return {'error': 'Job not found'}
        
        summary = {
            'job_id': str(job.id),
            'status': job.status,
            'model_version': job.model_version,
            'model_path': job.model_path,
            'triggered_by': str(job.triggered_by),
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'duration_seconds': job.duration_seconds,
            'duration_formatted': self._format_duration(job.duration_seconds) if job.duration_seconds else None,
        }
        
        if job.status == 'completed':
            summary['success'] = True
            summary['metadata'] = job.training_metadata
        elif job.status == 'failed':
            summary['success'] = False
            summary['error'] = job.error_message
            summary['logs'] = job.logs
        
        return summary
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f} minutes"
        else:
            hours = seconds / 3600
            return f"{hours:.1f} hours"