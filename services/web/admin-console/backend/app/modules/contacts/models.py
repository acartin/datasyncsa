from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.dal.database import Base
import uuid

class LeadContact(Base):
    """
    Person-Centric Identity Model (The "Person").
    Separates Identity from System Access.
    """
    __tablename__ = "lead_contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("lead_clients.id"), nullable=False, index=True)
    
    first_name = Column(String)
    last_name = Column(String)
    position = Column(String, nullable=True) # Cargo: e.g. "Gerente de Ventas"
    avatar_url = Column(String, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship to Channels
    channels = relationship("ContactChannel", backref="contact", cascade="all, delete-orphan")

class ContactChannel(Base):
    """
    Communication Channels belonging to a person.
    Replaces the flattened 'lead_client_channels'.
    """
    __tablename__ = "lead_contact_channels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("lead_contacts.id"), nullable=False, index=True)
    
    # Type of channel: 'whatsapp', 'email', 'phone', 'instagram', etc.
    type = Column(String, nullable=False) 
    
    # The actual value: '+57300...', 'pedro@gmail.com'
    value = Column(String, nullable=False)
    
    label = Column(String, nullable=True) # e.g. "Personal", "Trabajo"
    is_primary = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
