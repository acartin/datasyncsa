from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import Column, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.dal.database import Base
from app.modules.contacts.models import LeadContact
import uuid

# 0. Legacy Tenant Table (Reference Only)
class LeadClient(Base):
    __tablename__ = "lead_clients"
    id = Column(UUID(as_uuid=True), primary_key=True)
    name = Column(String, nullable=True) # Mapping for display

# 1. Identity Table (FastAPI Users Standard)
class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "auth_users"
    
    # Standard Fields (Mixin provides: id, email, hashed_password, is_active, is_superuser, is_verified)
    name = Column(String, nullable=True)
    
    # Person-Centric Identity Link
    contact_id = Column(UUID(as_uuid=True), ForeignKey("lead_contacts.id"), nullable=True, index=True)
    
    # Relationships
    tenants = relationship("ClientUser", back_populates="user", lazy="selectin")
    contact = relationship("LeadContact", lazy="joined")

# 2. Roles Table (Clean Role Definitions)
class Role(Base):
    __tablename__ = "auth_roles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)   # Display Name (e.g. "Administrator")
    slug = Column(String, unique=True, nullable=False) # Code Name (e.g. "admin")
    
    # Relationships
    client_users = relationship("ClientUser", back_populates="role")

# 3. Pivot Table (Multi-tenancy + RBAC)
class ClientUser(Base):
    __tablename__ = "auth_client_user"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("auth_users.id"), nullable=False)
    client_id = Column(UUID(as_uuid=True), ForeignKey("lead_clients.id"), nullable=False) # Linking to legacy/shared table
    role_id = Column(UUID(as_uuid=True), ForeignKey("auth_roles.id"), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="tenants")
    role = relationship("Role", back_populates="client_users", lazy="joined")
    client = relationship("LeadClient", lazy="joined") # Eager load for display name
