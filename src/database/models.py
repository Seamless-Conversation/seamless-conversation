from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Boolean, Integer, Table, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

# Junction table for agent-group relationships
class ConversationParticipant(Base):
    __tablename__ = 'conversation_participants'

    participant_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(UUID(as_uuid=True), ForeignKey('conversation_groups.group_id'))
    agent_id = Column(UUID(as_uuid=True), ForeignKey('agents.agent_id'))
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)
    last_read_sequence = Column(Integer, default=0)  # Track what messages the agent has "seen"

class Agent(Base):
    __tablename__ = 'agents'

    agent_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)
    capabilities = Column(JSON)  # capabilities/configuration

class ConversationGroup(Base):
    __tablename__ = 'conversation_groups'

    group_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    contextdata = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey('agents.agent_id'))  # Track who created the group

class Message(Base):
    __tablename__ = 'messages'

    message_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(UUID(as_uuid=True), ForeignKey('conversation_groups.group_id'))
    sender_id = Column(UUID(as_uuid=True), ForeignKey('agents.agent_id'))
    content = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    message_type = Column(String)  # 'response', 'decision', etc.
    context = Column(JSON)
    sequence_number = Column(Integer, index=True)

    # If this is a decision message, track which agent it's about
    # This is for future implimentations when more actions are avalible
    target_agent_id = Column(UUID(as_uuid=True), ForeignKey('agents.agent_id'), nullable=True)

# Create indices
Index('idx_messages_group_sequence', Message.group_id, Message.sequence_number)
Index('idx_participants_group_agent', ConversationParticipant.group_id, ConversationParticipant.agent_id)
Index('idx_messages_sender_type', Message.sender_id, Message.message_type)