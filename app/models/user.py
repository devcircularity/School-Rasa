# app/models/user.py - Updated User model with password reset relationship
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.models.base import Base
from app.models.password_reset import PasswordResetToken

import enum

class UserRole(str, enum.Enum):
    """System-wide user roles"""
    SUPER_ADMIN = "SUPER_ADMIN"  # Can manage all schools and users
    ADMIN = "ADMIN"              # Can manage specific schools
    TESTER = "TESTER"           # Can review and suggest intent improvements
    TEACHER = "TEACHER"         # Can manage classes and students
    ACCOUNTANT = "ACCOUNTANT"   # Can manage fees and payments
    PARENT = "PARENT"           # Basic user access

class User(Base):
    __tablename__ = "users"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic info
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Role system - store as CSV for multiple roles
    roles_csv: Mapped[str] = mapped_column(String(255), default="ADMIN", nullable=False)

    
    # Account status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    last_login: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        "PasswordResetToken", 
        back_populates="user",
        cascade="all, delete-orphan"
    )
    # school_memberships: Mapped[list["SchoolMember"]] = relationship("SchoolMember", back_populates="user")
    
    @property
    def roles(self) -> list[str]:
        """Get list of user roles"""
        if not self.roles_csv:
            return ["ADMIN"]
        return [role.strip() for role in self.roles_csv.split(",") if role.strip()]
    
    def set_roles(self, roles: list[str]) -> None:
        """Set user roles from list"""
        # Validate roles
        valid_roles = [role for role in roles if role in [r.value for r in UserRole]]
        if not valid_roles:
            valid_roles = ["ADMIN"]
        
        self.roles_csv = ",".join(sorted(set(valid_roles)))
        self.updated_at = func.now()
    
    def add_role(self, role: str) -> None:
        """Add a role to the user"""
        if role in [r.value for r in UserRole]:
            current_roles = self.roles
            if role not in current_roles:
                current_roles.append(role)
                self.set_roles(current_roles)
    
    def remove_role(self, role: str) -> None:
        """Remove a role from the user"""
        current_roles = self.roles
        if role in current_roles:
            current_roles.remove(role)
            # Ensure at least one role remains
            if not current_roles:
                current_roles = ["ADMIN"]
            self.set_roles(current_roles)
    
    def has_role(self, role: str) -> bool:
        """Check if user has a specific role"""
        return role in self.roles
    
    def has_any_role(self, roles: list[str]) -> bool:
        """Check if user has any of the specified roles"""
        return any(role in self.roles for role in roles)
    
    def is_admin(self) -> bool:
        """Check if user has admin privileges"""
        return self.has_any_role(["SUPER_ADMIN", "ADMIN"])
    
    def is_super_admin(self) -> bool:
        """Check if user is a super admin"""
        return self.has_role("SUPER_ADMIN")
    
    def is_tester(self) -> bool:
        """Check if user can access tester features"""
        return self.has_any_role(["SUPER_ADMIN", "ADMIN", "TESTER"])
    
    def can_manage_users(self) -> bool:
        """Check if user can manage other users"""
        return self.has_any_role(["SUPER_ADMIN", "ADMIN"])
    
    def has_active_reset_tokens(self) -> bool:
        """Check if user has any active password reset tokens"""
        from datetime import datetime
        for token in self.password_reset_tokens:
            if token.is_valid():
                return True
        return False
    
    def get_active_reset_tokens_count(self) -> int:
        """Get count of active password reset tokens"""
        from datetime import datetime
        return sum(1 for token in self.password_reset_tokens if token.is_valid())
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', roles={self.roles})>"