# app/services/rasa_trainer.py
import json
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.rasa_content import TrainingJob
from app.services.rasa_generator import generate_rasa_files

logger = logging.getLogger(__name__)


class RasaTrainer:
    """Handles Rasa model training with versioning"""
    
    def __init__(self, db: Session, rasa_dir: str = './rasa', models_dir: str = './models'):
        self.db = db
        self.rasa_dir = Path(rasa_dir)
        self.models_dir = Path(models_dir)
        self.versions_dir = Path('./model_versions')
        self.versions_dir.mkdir(parents=True, exist_ok=True)
    
    def train_model(self, job_id: UUID) -> TrainingJob:
        """Train a Rasa model with full versioning support"""
        job = self.db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
        if not job:
            raise ValueError(f"Training job {job_id} not found")
        
        start_time = datetime.utcnow()
        
        try:
            job.status = "running"
            job.started_at = start_time
            self.db.commit()
            
            logger.info(f"Starting training for job {job_id}")
            
            # Step 1: Generate files and capture snapshot
            logger.info("Generating Rasa files from database...")
            file_stats = generate_rasa_files(self.db, str(self.rasa_dir))
            
            # Capture YAML snapshot
            yaml_snapshot = self._capture_yaml_snapshot()
            content_counts = self._get_content_counts()
            
            # Step 2: Generate version and train
            self.models_dir.mkdir(parents=True, exist_ok=True)
            model_version = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            model_name = f"model_{model_version}"
            
            logger.info(f"Training model version: {model_version}")
            
            cmd = [
                'rasa', 'train',
                '--domain', str(self.rasa_dir / 'domain.yml'),
                '--data', str(self.rasa_dir / 'data'),
                '--out', str(self.models_dir),
                '--fixed-model-name', model_name
            ]
            
            result = subprocess.run(
                cmd,
                cwd=str(self.rasa_dir),
                capture_output=True,
                text=True,
                timeout=600
            )
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            if result.returncode == 0:
                model_path = self.models_dir / f"{model_name}.tar.gz"
                
                # Step 3: Store version snapshot
                version_snapshot_path = self._store_version_snapshot(
                    model_version, 
                    yaml_snapshot, 
                    content_counts
                )
                
                # Step 4: Update job with version info
                job.status = "completed"
                job.model_path = str(model_path)
                job.model_version = model_version
                job.logs = result.stdout
                job.completed_at = end_time
                job.duration_seconds = duration
                job.yaml_snapshot = yaml_snapshot
                job.content_counts = content_counts
                job.training_metadata = {
                    'file_stats': file_stats,
                    'model_name': model_name,
                    'trained_at': end_time.isoformat(),
                    'rasa_version': self._get_rasa_version(),
                    'duration_formatted': self._format_duration(duration),
                    'snapshot_path': str(version_snapshot_path)
                }
                
                logger.info(f"Training completed successfully: {model_version}")
                logger.info(f"Version snapshot stored at: {version_snapshot_path}")
            else:
                job.status = "failed"
                job.error_message = result.stderr or "Training failed"
                job.logs = result.stdout
                job.completed_at = end_time
                job.duration_seconds = duration
                logger.error(f"Training failed: {result.stderr}")
            
            self.db.commit()
            self.db.refresh(job)
            
            return job
            
        except Exception as e:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = end_time
            job.duration_seconds = duration
            self.db.commit()
            logger.error(f"Training error: {e}")
            raise
    
    def _capture_yaml_snapshot(self) -> dict:
        """Capture all YAML files as a snapshot"""
        snapshot = {}
        
        try:
            # Read domain.yml
            domain_path = self.rasa_dir / 'domain.yml'
            if domain_path.exists():
                with open(domain_path, 'r', encoding='utf-8') as f:
                    snapshot['domain'] = f.read()
            
            # Read data files
            data_dir = self.rasa_dir / 'data'
            if data_dir.exists():
                for yaml_file in data_dir.glob('*.yml'):
                    with open(yaml_file, 'r', encoding='utf-8') as f:
                        snapshot[f'data/{yaml_file.name}'] = f.read()
            
            logger.info(f"Captured YAML snapshot with {len(snapshot)} files")
            return snapshot
            
        except Exception as e:
            logger.error(f"Error capturing YAML snapshot: {e}")
            return {}
    
    def _get_content_counts(self) -> dict:
        """Get content counts at training time"""
        from app.models.rasa_content import (
            NLUIntent, RasaStory, RasaRule, RasaResponse, RasaSlot, RasaForm
        )
        
        return {
            'intents': self.db.query(NLUIntent).filter(NLUIntent.is_active == True).count(),
            'stories': self.db.query(RasaStory).filter(RasaStory.is_active == True).count(),
            'rules': self.db.query(RasaRule).filter(RasaRule.is_active == True).count(),
            'responses': self.db.query(RasaResponse).filter(RasaResponse.is_active == True).count(),
            'slots': self.db.query(RasaSlot).filter(RasaSlot.is_active == True).count(),
            'forms': self.db.query(RasaForm).filter(RasaForm.is_active == True).count(),
        }
    
    def _store_version_snapshot(self, version: str, yaml_snapshot: dict, content_counts: dict) -> Path:
        """Store version snapshot to disk for backup"""
        version_dir = self.versions_dir / version
        version_dir.mkdir(parents=True, exist_ok=True)
        
        # Store YAML files
        for filename, content in yaml_snapshot.items():
            file_path = version_dir / filename.replace('/', '_')
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        # Store metadata
        metadata_path = version_dir / 'metadata.json'
        with open(metadata_path, 'w') as f:
            json.dump({
                'version': version,
                'content_counts': content_counts,
                'created_at': datetime.utcnow().isoformat(),
                'files': list(yaml_snapshot.keys())
            }, f, indent=2)
        
        return version_dir
    
    def _get_rasa_version(self) -> str:
        """Get installed Rasa version"""
        try:
            result = subprocess.run(
                ['rasa', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip()
        except Exception:
            return "unknown"
    
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