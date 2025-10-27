# app/services/rasa_rollback.py
"""
Service to handle model rollbacks
"""
import subprocess
import shutil
import logging
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.rasa_content import TrainingJob

logger = logging.getLogger(__name__)


class RasaRollback:
    """Handles rolling back to previous model versions"""
    
    def __init__(self, db: Session, rasa_dir: str = './rasa', models_dir: str = './models'):
        self.db = db
        self.rasa_dir = Path(rasa_dir)
        self.models_dir = Path(models_dir)
        self.versions_dir = Path('./model_versions')
    
    def rollback_to_version(self, job_id: UUID, auto_restart: bool = True) -> dict:
        """
        Rollback to a specific model version
        
        Args:
            job_id: Training job ID to rollback to
            auto_restart: Whether to automatically restart the bot
            
        Returns:
            Dictionary with rollback status and details
        """
        # Get the target job
        target_job = self.db.query(TrainingJob).filter(
            TrainingJob.id == job_id,
            TrainingJob.status == "completed"
        ).first()
        
        if not target_job:
            raise ValueError(f"Training job {job_id} not found or not completed")
        
        if not target_job.model_path or not Path(target_job.model_path).exists():
            raise ValueError(f"Model file not found: {target_job.model_path}")
        
        logger.info(f"Rolling back to version: {target_job.model_version}")
        
        try:
            # Step 1: Deactivate current active model
            current_active = self.db.query(TrainingJob).filter(
                TrainingJob.school_id == target_job.school_id,
                TrainingJob.is_active == True
            ).first()
            
            if current_active:
                current_active.is_active = False
                logger.info(f"Deactivated current model: {current_active.model_version}")
            
            # Step 2: Set target as active
            target_job.is_active = True
            self.db.commit()
            
            # Step 3: Restore YAML files if snapshot exists
            if target_job.yaml_snapshot:
                self._restore_yaml_snapshot(target_job.yaml_snapshot)
                logger.info("Restored YAML files from snapshot")
            
            # Step 4: Copy model to standard location (optional)
            # This ensures the "latest" symlink or expected path points to this model
            target_model_path = Path(target_job.model_path)
            if target_model_path.exists():
                latest_link = self.models_dir / 'latest.tar.gz'
                if latest_link.exists() or latest_link.is_symlink():
                    latest_link.unlink()
                shutil.copy(target_model_path, latest_link)
                logger.info(f"Copied model to: {latest_link}")
            
            result = {
                'status': 'success',
                'model_version': target_job.model_version,
                'model_path': target_job.model_path,
                'rolled_back_from': current_active.model_version if current_active else None,
                'yaml_restored': bool(target_job.yaml_snapshot),
                'content_counts': target_job.content_counts
            }
            
            # Step 5: Restart bot if requested
            if auto_restart:
                restart_result = self._restart_bot()
                result['restart_status'] = restart_result['status']
                result['restart_output'] = restart_result.get('output')
                
                if restart_result['status'] != 'success':
                    result['warning'] = 'Rollback completed but bot restart failed'
            
            return result
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Rollback failed: {e}")
            raise
    
    def _restore_yaml_snapshot(self, yaml_snapshot: dict):
        """Restore YAML files from snapshot"""
        try:
            for file_path, content in yaml_snapshot.items():
                if file_path == 'domain':
                    full_path = self.rasa_dir / 'domain.yml'
                elif file_path.startswith('data/'):
                    filename = file_path.replace('data/', '')
                    full_path = self.rasa_dir / 'data' / filename
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                else:
                    continue
                
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                logger.info(f"Restored: {full_path}")
                
        except Exception as e:
            logger.error(f"Error restoring YAML snapshot: {e}")
            raise
    
    def _restart_bot(self) -> dict:
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
                'error': 'PM2 restart timed out'
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def get_version_history(self, limit: int = 20) -> list:
        """Get version history with details"""
        jobs = self.db.query(TrainingJob).filter(
            TrainingJob.status == "completed",
            TrainingJob.school_id == None  # Global models
        ).order_by(
            TrainingJob.created_at.desc()
        ).limit(limit).all()
        
        return [{
            'id': str(job.id),
            'version': job.model_version,
            'is_active': job.is_active,
            'created_at': job.created_at.isoformat(),
            'duration': job.duration_seconds,
            'content_counts': job.content_counts,
            'model_path': job.model_path
        } for job in jobs]