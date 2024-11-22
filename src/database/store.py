from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import sessionmaker
from .models import Base, ConversationGroup, Message, Agent, ConversationParticipant
from .config import DatabaseConfig

class ConversationStore:
    def __init__(self, config: DatabaseConfig):
        self.engine = create_engine(config.connection_string)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def create_agent(self, name: str, capabilities: Dict[str, Any] = None) -> str:
        """Create a new agent"""
        session = self.Session()
        try:
            agent = Agent(
                name=name,
                capabilities=capabilities
            )
            session.add(agent)
            session.commit()
            return str(agent.agent_id)
        finally:
            session.close()

    def create_group(self, creator_id: str, contextdata: Dict[str, Any] = None) -> str:
        """Create a new conversation group"""
        session = self.Session()
        try:
            group = ConversationGroup(
                created_by=uuid.UUID(creator_id),
                contextdata=contextdata
            )
            session.add(group)
            session.commit()
            return str(group.group_id)
        finally:
            session.close()

    def join_conversation(self, group_id: str, agent_id: str) -> None:
        """Add an agent to a conversation"""
        session = self.Session()
        try:
            # Check if already in conversation
            existing = session.query(ConversationParticipant).filter(
                ConversationParticipant.group_id == uuid.UUID(group_id),
                ConversationParticipant.agent_id == uuid.UUID(agent_id)
            ).first()
            
            if not existing:
                participant = ConversationParticipant(
                    group_id=uuid.UUID(group_id),
                    agent_id=uuid.UUID(agent_id)
                )
                session.add(participant)
                session.commit()
        finally:
            session.close()

    def get_next_sequence(self, session, group_id: str) -> int:
        """Get next sequence number for messages in a group"""
        result = session.query(func.max(Message.sequence_number))\
            .filter(Message.group_id == uuid.UUID(group_id))\
            .scalar()
        return (result + 1) if result is not None else 0

    def store_message(self, group_id: str, sender_id: str, content: str, message_type: str, target_agent_id: Optional[str] = None,context: Dict[str, Any] = None) -> str:
        """Store a new message"""
        session = self.Session()
        try:
            message = Message(
                group_id=uuid.UUID(group_id),
                sender_id=uuid.UUID(sender_id),
                content=content,
                message_type=message_type,
                target_agent_id=uuid.UUID(target_agent_id) if target_agent_id else None,
                context=context,
                sequence_number=self.get_next_sequence(session, group_id)
            )
            session.add(message)
            session.commit()
            return str(message.message_id)
        finally:
            session.close()

    def get_conversation_history(self, group_id: str, agent_id: str, include_decisions: bool = False, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get conversation history visible to the specified agent
        """
        session = self.Session()
        try:
            # Get when the agent joined the conversation
            participant = session.query(ConversationParticipant)\
                .filter(
                    ConversationParticipant.group_id == uuid.UUID(group_id),
                    ConversationParticipant.agent_id == uuid.UUID(agent_id)
                ).first()
            
            if not participant:
                return []

            # Build query for messages
            query = session.query(Message)\
                .filter(
                    Message.group_id == uuid.UUID(group_id),
                    Message.timestamp >= participant.joined_at
                )

            if include_decisions:
                # Include all messages and exclude the agent's own decisions
                query = query.filter(
                    ~((Message.message_type == 'decision') & (Message.sender_id != uuid.UUID(agent_id)))
                )
            else:
                query = query.filter(Message.message_type != 'decision')

            # Order by sequence number to maintain conversation flow
            query = query.order_by(Message.sequence_number.asc())

            if limit:
                query = query.limit(limit)
            
            messages = query.all()
            
            # Update last read sequence
            if messages:
                participant.last_read_sequence = max(
                    participant.last_read_sequence,
                    messages[0].sequence_number
                )
                session.commit()

            return [
                {
                    'message_id': str(msg.message_id),
                    'sender_id': str(msg.sender_id),
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat(),
                    'message_type': msg.message_type,
                    'context': msg.context,
                    'sequence_number': msg.sequence_number,
                    'target_agent_id': str(msg.target_agent_id) if msg.target_agent_id else None
                }
                for msg in messages
            ]
        finally:
            session.close()