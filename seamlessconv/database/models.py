"""
This module defines the SQLAlchemy ORM models representing the database schema for the application.
Each class corresponds to a table in the database and includes relationships and constraints that
enforce data integrity and structure.

Models:
    Application: Represents an application, which can have multiple saves.
    Save: Represents a save state for an application, possibly linked to a parent save.
    Event: Represents an event occurring within a save, associated with data and witnesses.
    EventWitness: Represents an agent's witness of an event, including context.
    Agent: Represents an agent within a save, with capabilities and an optional application ID.
    ConversationGroup: Represents a group for conversation, associated with messages.
    Message: Represents a message within a conversation group, linked to an event.

Constraints:
    - Uniqueness constraints are defined to enforce data integrity (e.g., unique application names).
    - Indexes are created to optimize query performance on frequently searched columns.

Usage:
    These models are used by the EventStore class to interact with the database using SQLAlchemy
    ORM. They define the structure of the database tables and the relationships between them.
"""

from datetime import datetime
from uuid import uuid4
from sqlalchemy import (
    Column, String, JSON, DateTime, Boolean, Integer, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID

Base = declarative_base()

class Application(Base):
    """
    Represents an application or environment where events and interactions occur.

    This is the top-level container for a specific instance of an application,
    such as a game, simulation, or interactive environment. It contains configuration
    settings and can have multiple saves representing different states or branches
    of the application's timeline.

    Attributes:
        application_id (UUID): Primary key, auto-generated unique identifier
        name (str): Name of the application
        type (str): Type/category of the application
        config (JSON): Application-specific configuration settings
    """
    __tablename__ = 'application'

    application_id = Column(PGUUID, primary_key=True, default=uuid4)
    name = Column(String, nullable=False, unique=True)
    type = Column(String, nullable=False)
    config = Column(JSON, nullable=False, default={})

    saves = relationship("Save", back_populates="application")

    __table_args__ = (
        Index('idx_application_name', name, unique=True),
    )

class Save(Base):
    """
    Represents a specific state or snapshot of an application at a point in time.

    Saves can form a tree structure where each save can branch into multiple
    alternate timelines. For example, in a game, a player might create Save B
    and Save C from the same parent save (ROOT), representing different choices
    or actions taken from that point.

    Attributes:
        save_id (UUID): Primary key, auto-generated unique identifier
        application_id (UUID): Foreign key to the parent Application
        parent_save_id (UUID): Foreign key to the parent Save (if any)
        name (str): Name of the save
        timestamp (DateTime): When the save was created
        state (JSON): The complete state data for this save
    """
    __tablename__ = 'save'

    save_id = Column(PGUUID, primary_key=True, default=uuid4)
    application_id = Column(PGUUID, ForeignKey('application.application_id'), nullable=False)
    parent_save_id = Column(PGUUID, ForeignKey('save.save_id'), nullable=True)
    name = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    state = Column(JSON, nullable=False, default={})

    application = relationship("Application", back_populates="saves")
    events = relationship("Event", back_populates="save")
    agents = relationship("Agent", back_populates="save")

    __table_args__ = (
        Index('idx_save_app_time', application_id, timestamp),
        Index('idx_save_parent', parent_save_id),
    )

class Event(Base):
    """
    Represents an occurrence or action within a save state.

    Events are discrete occurrences that can be witnessed by agents. They form
    the basis for all interactions and changes in the application state. Events
    can be witnessed by agents even if they're not direct participants (e.g.,
    an agent overhearing a conversation they're not part of).

    Attributes:
        event_id (UUID): Primary key, auto-generated unique identifier
        save_id (UUID): Foreign key to the Save where this event occurred
        event_type (str): Type of event (e.g., conversation, action, interaction)
        timestamp (DateTime): When the event occurred
        data (JSON): Event-specific data
    """
    __tablename__ = 'event'

    event_id = Column(PGUUID, primary_key=True, default=uuid4)
    save_id = Column(PGUUID, ForeignKey('save.save_id'), nullable=False)
    event_type = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    data = Column(JSON, nullable=False)

    save = relationship("Save", back_populates="events")
    witnesses = relationship("EventWitness", back_populates="event")
    messages = relationship("Message", back_populates="event")

    __table_args__ = (
        Index('idx_event_save_time', save_id, timestamp),
        Index('idx_event_type_time', save_id, event_type, timestamp),
    )

class EventWitness(Base):
    """
    Represents an agent's perception of an event.

    Tracks how and when agents witness events, even if they're not direct
    participants. For example, an agent might see or hear a conversation
    without being part of it. This allows for realistic information flow
    where agents only know about events they've actually witnessed.

    Attributes:
        witness_id (UUID): Primary key, auto-generated unique identifier
        event_id (UUID): Foreign key to the witnessed Event
        agent_id (UUID): Foreign key to the witnessing Agent
        timestamp (DateTime): When the event was witnessed
        witness_type (str): How the event was witnessed (e.g., 'see', 'hear')
        witness_context (JSON): Additional context about how the event was witnessed
    """
    __tablename__ = 'event_witness'

    witness_id = Column(PGUUID, primary_key=True, default=uuid4)
    event_id = Column(PGUUID, ForeignKey('event.event_id'), nullable=False)
    agent_id = Column(PGUUID, ForeignKey('agent.agent_id'), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    witness_type = Column(String, nullable=False)
    witness_context = Column(JSON, nullable=True)

    event = relationship("Event", back_populates="witnesses")
    agent = relationship("Agent", back_populates="witnessed_events")

    __table_args__ = (
        Index('idx_witness_event', event_id),
        Index('idx_witness_agent_time', agent_id, timestamp),
    )

class Agent(Base):
    """
    Represents an actor within the application, either AI or human.

    Agents can witness events, participate in conversations, and interact
    with the environment. They exist within a specific save state.

    Attributes:
        agent_id (UUID): Primary key, auto-generated unique identifier
        name (str): Name of the agent
        save_id (UUID): Foreign key to the Save this agent exists in
        created_at (DateTime): When the agent was created
        capabilities (JSON): Agent's capabilities and permissions
        external_application_id (str): Unique ID generated by foreign application
    """
    __tablename__ = 'agent'

    agent_id = Column(PGUUID, primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    save_id = Column(PGUUID, ForeignKey('save.save_id'), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    capabilities = Column(JSON, nullable=True)
    external_application_id = Column(String, nullable=True)

    save = relationship("Save", back_populates="agents")
    witnessed_events = relationship("EventWitness", back_populates="agent")

    __table_args__ = (
        Index('idx_agent_save', save_id),
        Index('idx_agent_application', save_id, 'external_application_id', unique=True)
    )

class ConversationGroup(Base):
    """
    Represents a group conversation or interaction between agents.

    Tracks an ongoing conversation between multiple agents. Conversations
    are created as events and can have multiple participants. Agents can
    join or leave conversations, and non-participating agents might still
    witness the conversation.

    Attributes:
        group_id (UUID): Primary key, auto-generated unique identifier
        created_event_id (UUID): Foreign key to the Event that created this group
        is_active (bool): Whether the conversation is ongoing
    """
    __tablename__ = 'conversation_group'

    group_id = Column(PGUUID, primary_key=True, default=uuid4)
    created_event_id = Column(PGUUID, ForeignKey('event.event_id'), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    messages = relationship("Message", back_populates="group")

    __table_args__ = (
        Index('idx_conv_active', is_active),
    )

class Message(Base):
    """
    Represents a single message or action within a conversation group.

    Messages can be of different types (e.g., 'response', 'decision') and
    are ordered within their conversation group. They represent both direct
    communication and decision points in the interaction.

    Attributes:
        message_id (UUID): Primary key, auto-generated unique identifier
        event_id (UUID): Foreign key to the associated Event
        group_id (UUID): Foreign key to the ConversationGroup
        content (str): The actual message content
        timestamp (DateTime): When the message was sent
        message_type (str): Type of message (e.g., 'response', 'decision')
        context (JSON): Additional context about the message
        sequence_number (int): Order of the message within the conversation
        target_agent_id (UUID): Foreign key to the Agent this message is directed to
    """
    __tablename__ = 'message'

    message_id = Column(PGUUID, primary_key=True, default=uuid4)
    event_id = Column(PGUUID, ForeignKey('event.event_id'), nullable=False)
    group_id = Column(PGUUID, ForeignKey('conversation_group.group_id'), nullable=False)
    content = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    message_type = Column(String, nullable=False)
    context = Column(JSON, nullable=False)
    sequence_number = Column(Integer, nullable=False)
    source_agent_id = Column(PGUUID, ForeignKey('agent.agent_id'), nullable=True)
    target_agent_id = Column(PGUUID, ForeignKey('agent.agent_id'), nullable=True)

    event = relationship("Event", back_populates="messages")
    group = relationship("ConversationGroup", back_populates="messages")

    __table_args__ = (
        Index('idx_message_group_seq', group_id, sequence_number),
        Index('idx_message_event', event_id),
        Index('idx_message_type_time', group_id, message_type, timestamp),
    )
