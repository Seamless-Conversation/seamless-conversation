"""
This module defines the EventStore class, which serves as the Data Access Layer (DAL)
for storing and retrieving events and related entities in the database. It provides
methods to interact with applications, saves, agents, events, conversations, and messages.

Classes:
    EventStore: Provides methods for database operations related to events and associated entities.

Example:
    from event_store import EventStore
    from database_config import DatabaseConfig

    event_store = EventStore(DatabaseConfig())
    application_id = event_store.create_application('MyApp', 'Category', {})
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import declarative_base, sessionmaker, aliased
from sqlalchemy.sql import select
from seamlessconv.database.config import DatabaseConfig
from seamlessconv.database.models import (
    Application, Save, Event, EventWitness, Agent, ConversationGroup, Message
)

Base = declarative_base()

class EventStore:
    """
    The EventStore class acts as the Data Access Layer (DAL) for the application,
    providing methods to interact with the database for various entities such as
    Applications, Saves, Agents, Events, Conversations, and Messages. It encapsulates
    all database operations, ensuring that the higher-level business logic can interact
    with the database without dealing with raw SQL queries or ORM complexities.

    Note:
        This class should be used as a low-level data access layer. It does not contain
        business logic or application-specific error handling, which should be implemented
        in higher-level components like the SessionManager.
    """

    def __init__(self, config: DatabaseConfig):
        self.engine = create_engine(config.connection_string)
        Base.metadata.create_all(self.engine)
        self.c_session = sessionmaker(bind=self.engine)

    def get_witnessed_events_by_agent(
        self,
        save_id: UUID,
        agent_id: UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
        limit: Optional[int] = None,
        witness_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve events witnessed by an agent with various filters."""
        with self.c_session() as c_session:
            save_cte = self.get_save_cte(save_id)

            query = (
                c_session.query(Event)
                .join(EventWitness)
                .filter(
                    and_(
                        Event.save_id.in_(select(save_cte.c.save_id)),
                        EventWitness.agent_id == agent_id
                    )
                )
            )

            if start_time:
                query = query.filter(Event.timestamp >= start_time)
            if end_time:
                query = query.filter(Event.timestamp <= end_time)
            if event_types:
                query = query.filter(Event.event_type.in_(event_types))
            if witness_types:
                query = query.filter(EventWitness.witness_type.in_(witness_types))

            query = query.order_by(Event.timestamp.desc())

            if limit:
                query = query.limit(limit)

            return [
                {
                    "event_id": event.event_id,
                    "type": event.event_type,
                    "timestamp": event.timestamp,
                    "data": event.data
                }
                for event in query.all()
            ]

    def get_agent_conversation_history(
        self,
        save_id: UUID,
        agent_id: UUID,
        group_id: UUID,
        start_sequence: Optional[int] = None,
        message_types: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve conversation history visible to an agent."""
        with self.c_session() as c_session:
            save_cte = self.get_save_cte(save_id)

            query = (
                c_session.query(Message)
                .join(Event, Message.event_id == Event.event_id)
                .join(EventWitness, Event.event_id == EventWitness.event_id)
                .filter(
                    and_(
                        Event.save_id.in_(select(save_cte.c.save_id)),
                        Message.group_id == group_id,
                        EventWitness.agent_id == agent_id
                    )
                )
            )

            if start_sequence:
                query = query.filter(Message.sequence_number >= start_sequence)
            if message_types:
                query = query.filter(Message.message_type.in_(message_types))

            query = query.order_by(Message.sequence_number)

            if limit:
                query = query.limit(limit)

            return [
                {
                    "message_id": msg.message_id,
                    "content": msg.content,
                    "type": msg.message_type,
                    "sequence": msg.sequence_number,
                    "timestamp": msg.timestamp,
                    "context": msg.context,
                    "source_agent_id": msg.source_agent_id
                }
                for msg in query.all()
            ]

    def create_conversation_group(self,event_id: UUID) -> UUID:
        """Create a conversation ogorup"""
        with self.c_session() as c_session:
            group = ConversationGroup(
                created_event_id=event_id
            )

            c_session.add(group)
            c_session.commit()

            return group.group_id

    def get_conversation_groups(
        self,
        save_id: UUID,
        is_active: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve conversation groups within the save timeline."""
        with self.c_session() as c_session:
            save_cte = self.get_save_cte(save_id)

            query = (
                c_session.query(ConversationGroup)
                .join(Event, ConversationGroup.created_event_id == Event.event_id)
                .filter(
                    Event.save_id.in_(select(save_cte.c.save_id))
                )
            )

            if is_active is not None:
                query = query.filter(ConversationGroup.is_active == is_active)

            return [
                {
                    "group_id": group.group_id,
                    "created_event_id": group.created_event_id,
                    "is_active": group.is_active
                }
                for group in query.all()
            ]

    def create_event(
        self,
        save_id: UUID,
        event_type: str,
        data: Dict[str, Any],
        witnesses: List[Dict[str, Any]]
    ) -> UUID:
        """Create a new event with witnesses."""
        with self.c_session() as c_session:
            event = Event(
                save_id=save_id,
                event_type=event_type,
                data=data
            )
            c_session.add(event)
            c_session.flush()

            for witness_data in witnesses:
                witness = EventWitness(
                    event_id=event.event_id,
                    agent_id=witness_data['agent_id'],
                    witness_type=witness_data['witness_type'],
                    witness_context=witness_data.get('context')
                )
                c_session.add(witness)

            c_session.commit()
            return event.event_id

    def create_conversation_message(
        self,
        event_id: UUID,
        group_id: UUID,
        content: str,
        message_type: str,
        context: Dict[str, Any],
        source_agent_id: Optional[UUID] = None,
        target_agent_id: Optional[UUID] = None
    ) -> UUID:
        """Create a new conversation message."""
        with self.c_session() as c_session:
            last_sequence = (
                c_session.query(Message.sequence_number)
                .filter(Message.group_id == group_id)
                .order_by(Message.sequence_number.desc())
                .first()
            )
            next_sequence = (last_sequence[0] + 1) if last_sequence else 0

            message = Message(
                event_id=event_id,
                group_id=group_id,
                content=content,
                message_type=message_type,
                context=context,
                sequence_number=next_sequence,
                source_agent_id=source_agent_id,
                target_agent_id=target_agent_id
            )
            c_session.add(message)
            c_session.commit()
            return message.message_id

    def create_application(self, name: str, dtype: str, config: Dict[str, Any]) -> UUID:
        """Create a new application to store data in"""
        with self.c_session() as c_session:
            application = Application(
                name=name,
                type=dtype,
                config=config
            )

            c_session.add(application)
            c_session.commit()

            return application.application_id

    def get_application_id_by_name(self, name: str) -> Optional[UUID]:
        """Get the ID for an existing application"""
        with self.c_session() as c_session:
            query = (
                c_session.query(Application)
                .filter(Application.name == name)
            ).first()

            if query:
                return query.application_id
            return None

    def create_save(self, application_id: UUID, name: str, parent_save_id: UUID = None) -> UUID:
        """Create a new save for an application"""
        with self.c_session() as c_session:
            save = Save(
                application_id=application_id,
                parent_save_id=parent_save_id,
                name=name
            )

            c_session.add(save)
            c_session.commit()

            return save.save_id

    def get_saves_by_application_and_name(
        self,
        application_name: str,
        save_name: str
    ) -> List[Dict[str, Any]]:
        """Retrieve saves by name"""
        with self.c_session() as c_session:
            query = (
                c_session.query(Save)
                .join(Application)
                .filter(
                    and_(
                        Application.name==application_name,
                        Save.name==save_name
                    )
                )
            )

            return [
                {
                    "save_id": save.save_id,
                    "application_id": save.application_id,
                    "parent_save_id": save.parent_save_id,
                    "name": save.name,
                    "timestamp": save.timestamp,
                    "state": save.state
                }
                for save in query.all()
            ]

    def create_agent(self,
        name: str,
        save_id: UUID,
        external_application_id: Optional[str] = None
    ) -> UUID:
        """Create a new Agent for a save"""
        with self.c_session() as c_session:
            if external_application_id:
                save_cte = self.get_save_cte(save_id)

                existing_agent = (
                    c_session.query(Agent)
                    .filter(
                        Agent.save_id.in_(select(save_cte.c.save_id)),
                        Agent.external_application_id == external_application_id
                    )
                    .first()
                )
                if existing_agent:
                    raise ValueError(f"An Agent with external_application_id\
                                '{external_application_id}' already exists in the save lineage.")

            agent = Agent(name=name, save_id=save_id)
            if external_application_id:
                agent.external_application_id = external_application_id
            c_session.add(agent)
            c_session.commit()
            return agent.agent_id


    def get_agents(self,
        name: Optional[str] = None,
        save_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """Get agents matching the specified criteria."""
        with self.c_session() as c_session:
            query = c_session.query(Agent)

            if save_id:
                save_cte = self.get_save_cte(save_id)
                query = query.filter(
                    Agent.save_id.in_(select(save_cte.c.save_id))
                )

            if name:
                query = query.filter(Agent.name == name)

            return [
                {
                    "agent_id": agent.agent_id,
                    "name": agent.name,
                    "save_id": agent.save_id,
                    "created_at": agent.created_at,
                    "capabilities": agent.capabilities,
                    "external_application_id": agent.external_application_id
                }
                for agent in query.all()
            ]

    def get_agent_id_by_application_id(
        self,
        save_id: UUID,
        external_application_id: str
    ) -> UUID:
        """Get a specific agent by targeting their application ID"""
        with self.c_session() as c_session:
            save_cte = self.get_save_cte(save_id)

            query = (
                c_session.query(Agent)
                .filter(
                    Agent.save_id.in_(select(save_cte.c.save_id)),
                    Agent.external_application_id == external_application_id
                )
            ).first()

            if query:
                return query.agent_id
            return None

    def get_agent_by_id(self, save_id: UUID, agent_id: UUID) -> [str, str]:
        """Get agent information by targeting their agent ID"""
        with self.c_session() as c_session:
            save_cte = self.get_save_cte(save_id)

            query = (
                c_session.query(Agent)
                .filter(
                    Agent.save_id.in_(select(save_cte.c.save_id)),
                    Agent.agent_id == agent_id
                )
            ).first()

            if query:
                return {
                    "agent_id": query.agent_id,
                    "name": query.name,
                    "save_id": query.save_id,
                    "created_at": query.created_at,
                    "capabilities": query.capabilities,
                    "external_application_id": query.external_application_id
                }
            return None

    def get_save_timeline(self, save_id: UUID) -> List[Dict[str, Any]]:
        """Get the timeline of saves leading to this save."""
        with self.c_session() as c_session:
            timeline = []
            current_save = c_session.query(Save).get(save_id)

            while current_save:
                timeline.append({
                    "save_id": current_save.save_id,
                    "name": current_save.name,
                    "timestamp": current_save.timestamp
                })
                if current_save.parent_save_id:
                    current_save = c_session.query(Save).get(current_save.parent_save_id)
                else:
                    break

            return timeline

    def get_save_cte(self, save_id: UUID):
        """Create a recursive CTE to get all ancestor saves."""
        with self.c_session() as c_session:
            save_cte = (
                c_session.query(Save.save_id, Save.parent_save_id)
                .filter(Save.save_id == save_id)
                .cte(name='save_cte', recursive=True)
            )

            parent_save = aliased(Save, name="parent_save")

            save_cte = save_cte.union_all(
                c_session.query(parent_save.save_id, parent_save.parent_save_id)
                .filter(parent_save.save_id == save_cte.c.parent_save_id)
            )

        return save_cte

    def delete_application(self, application_id: UUID):
        """Delete an application and all associated data."""
        with self.c_session() as c_session:
            saves = c_session.query(Save).filter(Save.application_id == application_id).all()
            for save in saves:
                self.delete_save(save.save_id, session=c_session)
            c_session.query(Application).filter(
                Application.application_id == application_id
            ).delete()
            c_session.commit()

    def delete_save(self, save_id: UUID, session=None):
        """Delete a save and all associated data."""
        c_session = session or self.c_session()
        with c_session:
            agents = c_session.query(Agent).filter(Agent.save_id == save_id).all()
            for agent in agents:
                self.delete_agent(agent.agent_id, session=c_session)
            events = c_session.query(Event).filter(Event.save_id == save_id).all()
            for event in events:
                self.delete_event(event.event_id, session=c_session)
            c_session.query(Save).filter(Save.save_id == save_id).delete()

            if not session:
                c_session.commit()

    def delete_agent(self, agent_id: UUID, session=None):
        """Delete an agent."""
        c_session = session or self.c_session()
        with c_session:
            c_session.query(EventWitness).filter(EventWitness.agent_id == agent_id).delete()
            c_session.query(Agent).filter(Agent.agent_id == agent_id).delete()
            if not session:
                c_session.commit()

    def delete_event(self, event_id: UUID, session=None):
        """Delete an event and associated data."""
        c_session = session or self.c_session()
        with c_session:
            c_session.query(EventWitness).filter(EventWitness.event_id == event_id).delete()
            c_session.query(Message).filter(Message.event_id == event_id).delete()
            c_session.query(ConversationGroup).filter(
                ConversationGroup.created_event_id == event_id
            ).delete()
            c_session.query(Event).filter(Event.event_id == event_id).delete()

            if not session:
                c_session.commit()

    def delete_conversation_group(self, group_id: UUID):
        """Delete a conversation group and all associated messages."""
        with self.c_session() as c_session:
            c_session.query(Message).filter(Message.group_id == group_id).delete()
            c_session.query(ConversationGroup).filter(
                ConversationGroup.group_id == group_id
            ).delete()
            c_session.commit()
