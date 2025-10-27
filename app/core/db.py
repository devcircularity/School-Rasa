# app/core/db.py - SQLAlchemy database setup with connection pooling
# app/core/db.py
from sqlalchemy import create_engine, text, event, pool
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool, QueuePool
from typing import Generator, Optional, Any
import logging
import time
import threading
from contextlib import contextmanager

from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Database manager with connection pooling and health monitoring"""
    
    def __init__(self):
        self.engine: Optional[Engine] = None
        self.SessionLocal: Optional[sessionmaker] = None
        self._initialized = False
        self._lock = threading.Lock()
        self._health_check_enabled = True
        
    def initialize(self):
        """Initialize database engine and session maker"""
        if self._initialized:
            return
            
        with self._lock:
            if self._initialized:
                return
                
            try:
                self.engine = self._create_engine()
                self.SessionLocal = sessionmaker(
                    autocommit=False,
                    autoflush=False,
                    bind=self.engine
                )
                
                # Set up event listeners
                self._setup_event_listeners()
                
                # Test connection
                self._test_connection()
                
                self._initialized = True
                logger.info("Database initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                raise
    
    def _create_engine(self) -> Engine:
        """Create SQLAlchemy engine with optimized configuration"""
        
        # Determine if we're using SQLite or PostgreSQL
        is_sqlite = settings.DATABASE_URL.startswith("sqlite")
        
        # Base engine arguments
        engine_args = {
            "url": settings.DATABASE_URL,
            "echo": settings.DATABASE_ECHO or settings.DEV_LOG_SQL,
            "future": True,  # Use SQLAlchemy 2.0 style
        }
        
        if is_sqlite:
            # SQLite specific configuration
            engine_args.update({
                "poolclass": StaticPool,
                "connect_args": {
                    "check_same_thread": False,
                    "timeout": 30,  # 30 second timeout for SQLite locks
                },
                "echo_pool": settings.is_development,
            })
        else:
            # PostgreSQL specific configuration
            engine_args.update({
                "poolclass": QueuePool,
                "pool_size": settings.DATABASE_POOL_SIZE,
                "max_overflow": settings.DATABASE_MAX_OVERFLOW,
                "pool_timeout": settings.DATABASE_POOL_TIMEOUT,
                "pool_recycle": settings.DATABASE_POOL_RECYCLE,
                "pool_pre_ping": True,  # Verify connections before use
                "echo_pool": settings.is_development,
                "connect_args": {
                    "connect_timeout": 10,
                    "application_name": f"school_assistant_{settings.ENV}",
                    # Enable prepared statements for better performance
                    "prepare_threshold": 5,
                    # Connection-level settings
                    "options": "-c timezone=UTC"
                }
            })
        
        return create_engine(**engine_args)
    
    def _setup_event_listeners(self):
        """Set up SQLAlchemy event listeners for monitoring and optimization"""
        
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            """Set SQLite pragmas for better performance and reliability"""
            if "sqlite" in settings.DATABASE_URL:
                cursor = dbapi_connection.cursor()
                # Enable WAL mode for better concurrency
                cursor.execute("PRAGMA journal_mode=WAL")
                # Enable foreign key constraints
                cursor.execute("PRAGMA foreign_keys=ON")
                # Set synchronous mode for better performance
                cursor.execute("PRAGMA synchronous=NORMAL")
                # Set temp store to memory
                cursor.execute("PRAGMA temp_store=memory")
                # Set cache size (negative value means KB)
                cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
                cursor.close()
        
        @event.listens_for(self.engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """Monitor connection checkout"""
            connection_record.checkout_time = time.time()
            if settings.is_development:
                logger.debug(f"Database connection checked out: {id(dbapi_connection)}")
        
        @event.listens_for(self.engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """Monitor connection checkin and log usage time"""
            if hasattr(connection_record, 'checkout_time'):
                duration = time.time() - connection_record.checkout_time
                if settings.is_development and duration > 1.0:  # Log slow connections
                    logger.warning(f"Long-running connection ({duration:.2f}s): {id(dbapi_connection)}")
        
        @event.listens_for(self.engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Log slow queries in development"""
            if settings.is_development:
                context._query_start_time = time.time()
        
        @event.listens_for(self.engine, "after_cursor_execute")
        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Log slow queries in development"""
            if settings.is_development and hasattr(context, '_query_start_time'):
                total = time.time() - context._query_start_time
                if total > 0.1:  # Log queries taking more than 100ms
                    logger.warning(f"Slow query ({total:.3f}s): {statement[:100]}...")
    
    def _test_connection(self):
        """Test database connection and log status"""
        try:
            with self.engine.connect() as conn:
                # Test basic connectivity
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
                
                # Get database info
                if "postgresql" in settings.DATABASE_URL:
                    db_info = conn.execute(text("SELECT version()")).fetchone()
                    logger.info(f"Connected to PostgreSQL: {db_info[0][:50]}...")
                elif "sqlite" in settings.DATABASE_URL:
                    db_info = conn.execute(text("SELECT sqlite_version()")).fetchone()
                    logger.info(f"Connected to SQLite: {db_info[0]}")
                
                logger.info("Database connection test successful")
                
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            raise
    
    def get_session(self) -> Generator[Session, None, None]:
        """
        Get database session with automatic cleanup and error handling.
        
        Yields:
            Session: SQLAlchemy database session
        """
        if not self._initialized:
            self.initialize()
        
        session = self.SessionLocal()
        try:
            yield session
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions with automatic rollback.
        
        Usage:
            with db_manager.transaction() as session:
                session.add(user)
                # Automatically commits on success, rolls back on error
        """
        if not self._initialized:
            self.initialize()
        
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Transaction error: {e}")
            raise
        finally:
            session.close()
    
    def execute_raw_sql(self, sql: str, params: dict = None) -> Any:
        """
        Execute raw SQL query safely.
        
        Args:
            sql: SQL query string
            params: Query parameters
            
        Returns:
            Query result
        """
        if not self._initialized:
            self.initialize()
        
        with self.engine.connect() as conn:
            return conn.execute(text(sql), params or {})
    
    def health_check(self) -> dict:
        """
        Perform database health check.
        
        Returns:
            Dict with health status information
        """
        if not self._health_check_enabled:
            return {"status": "disabled"}
        
        try:
            start_time = time.time()
            
            with self.engine.connect() as conn:
                # Test basic connectivity
                conn.execute(text("SELECT 1"))
                
                # Check pool status
                pool_status = {
                    "size": self.engine.pool.size(),
                    "checked_out": self.engine.pool.checkedout(),
                    "overflow": self.engine.pool.overflow(),
                    "checked_in": self.engine.pool.checkedin(),
                }
                
                response_time = (time.time() - start_time) * 1000  # Convert to ms
                
                return {
                    "status": "healthy",
                    "response_time_ms": round(response_time, 2),
                    "pool": pool_status,
                    "database_url": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "local"
                }
                
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def set_rls_context(self, session: Session, user_id: str = None, school_id: str = None):
        """
        Set Row Level Security context for PostgreSQL.
        
        Args:
            session: Database session
            user_id: Current user ID
            school_id: Current school ID
        """
        try:
            if user_id:
                session.execute(
                    text("SELECT set_config('myapp.current_user_id', :user_id, true)"),
                    {"user_id": str(user_id)}
                )
            if school_id:
                session.execute(
                    text("SELECT set_config('myapp.current_school_id', :school_id, true)"),
                    {"school_id": str(school_id)}
                )
            session.commit()
        except Exception as e:
            logger.warning(f"Could not set RLS context: {e}")
            session.rollback()
    
    def close(self):
        """Close database connections and cleanup"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connections closed")
    
    def disable_health_checks(self):
        """Disable health checks (useful for testing)"""
        self._health_check_enabled = False
    
    def enable_health_checks(self):
        """Enable health checks"""
        self._health_check_enabled = True

# Create global database manager instance
db_manager = DatabaseManager()

# Convenience functions for backward compatibility and ease of use
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency to get database session.
    
    Usage in FastAPI:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    
    Yields:
        Session: SQLAlchemy database session
    """
    yield from db_manager.get_session()

def get_engine() -> Engine:
    """Get SQLAlchemy engine instance"""
    if not db_manager._initialized:
        db_manager.initialize()
    return db_manager.engine

def get_session_maker() -> sessionmaker:
    """Get session maker for manual session creation"""
    if not db_manager._initialized:
        db_manager.initialize()
    return db_manager.SessionLocal

def set_rls_context(session: Session, user_id: str = None, school_id: str = None):
    """Set Row Level Security context (convenience function)"""
    db_manager.set_rls_context(session, user_id, school_id)

def health_check() -> dict:
    """Get database health status (convenience function)"""
    return db_manager.health_check()

def execute_sql(sql: str, params: dict = None) -> Any:
    """Execute raw SQL safely (convenience function)"""
    return db_manager.execute_raw_sql(sql, params)

# Initialize database on import (in production)
if not settings.is_development:
    try:
        db_manager.initialize()
    except Exception as e:
        logger.error(f"Failed to initialize database on import: {e}")
        # Don't raise in production to allow graceful degradation

# Export commonly used items
__all__ = [
    "get_db",
    "get_engine", 
    "get_session_maker",
    "set_rls_context",
    "health_check",
    "execute_sql",
    "db_manager"
]
