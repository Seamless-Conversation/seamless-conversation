"""
Helper module for managing the database for creation/fetching of data.
"""
from typing import List, Optional
from uuid import UUID
import logging
from sqlalchemy.exc import IntegrityError
from src.database.event_store import EventStore
from src.database.config import DatabaseConfig
from src.event.eventbus import Event

logger = logging.getLogger(__name__)

class SessionManager():
    """
    A helper class to manage creation/fetching of data in the database.
    Acts as a single point where the application/save is set and modified.
    """
    def __init__(self):
        self.store = EventStore(DatabaseConfig())
        self.save: UUID = None
        self.app_name = None
        self.app_id = None

    def set_application(
        self,
        application_name: str,
        category: Optional[str] = None
    ) -> UUID:
        """
        Set the application. If an existing application with the same name exists,
        set it as the current applicationt. Otherwise, create a new application.
        """
        app_id = self.store.get_application_id_by_name(application_name)
        if app_id:
            self.app_name = application_name
            self.app_id = app_id
            return app_id

        try:
            app_id = self.store.create_application(application_name, category or '', {})
            self.app_name = application_name
            self.app_id = app_id
            return app_id
        except IntegrityError as e:
            logger.error("Failed to create application '%s': %s", application_name, e)
            app_id = self.store.get_application_id_by_name(application_name)
            if app_id:
                self.app_name = application_name
                self.app_id = app_id
                return app_id
            else:
                raise

    def set_save(self, save_name: str, parent_save: Optional[UUID] = None) -> UUID:
        """
        Set the save. If an existing save with the same name exists, it is set to that.
        Returns the UUID of the save which was set.
        """
        saves = self.store.get_saves_by_application_and_name(self.app_name, save_name)

        if len(saves) == 1:
            self.save = saves[0]['save_id']
            return saves[0]['save_id']

        if len(saves) > 1:
            logger.warning("Multiple saves share the same. Returning first UUID in column.")
            self.save = saves[0]['save_id']
            return saves[0]['save_id']

        self.save = self.store.create_save(self.app_id, save_name, parent_save)

        return self.save

    def create_and_store_event(
        self,
        source_agent: UUID,
        agents: UUID,
        event_type: str,
    ) -> UUID:
        """
        Creates and stores the event as a general event in the active application/save.
        Set agents as witnesses.
        """
        witnesses = [
            {
                "agent_id": member[0],
                "witness_type": member[1],
                "context": {}
            }
            for member in agents
        ]
        event = self.store.create_event(
            save_id=self.save,
            event_type=event_type,
            data={
                "source_agent": str(source_agent),
                "target_agent": ""
            },
            witnesses=witnesses
        )
        return event

    def create_conversation_group(self, event_id) -> UUID:
        """Wrapper method for conversation group creation"""
        return self.store.create_conversation_group(event_id)

    def store_message(self, event: Event, agents) -> (UUID, UUID):
        """
        Stores the event as a message in active application/save.
        Sets agents as witnesses.

        Returns a tuple of (eventid, messageid)
        """
        witnesses = [
            {
                "agent_id": member[0],
                "witness_type": member[1],
                "context": {}
            } for member in agents
        ]
        new_event = self.store.create_event(
            save_id=self.save,
            event_type="talking",
            data={
                "source_agent": str(event.agent_id),
                "target_agent": ""
            },
            witnesses=witnesses
        )

        return (new_event, self.store.create_conversation_message(
            event_id=new_event,
            group_id=event.group_id,
            content=event.data['text'],
            message_type=event.data['context']['type'],
            context={},
            source_agent_id=event.agent_id
        ))

    def get_messages(self, event: Event, message_types: Optional[List[str]]=None):
        """
        Get messages in specified conversation group from active application/save.
        """
        return self.store.get_agent_conversation_history(
            save_id=self.save,
            agent_id=event.agent_id,
            group_id=event.group_id,
            message_types=message_types,
        )

    def create_agent(
        self,
        agent_name: str,
        allow_name_conflict: Optional[bool] = None,
        external_application_id: Optional[str] = None
    ) -> UUID:
        """
        Create a new agent.
        """
        if not allow_name_conflict:
            agents = self.store.get_agents(agent_name, self.save)
            if len(agents) == 1:
                return agents[0]['agent_id']
            if len(agents) > 1:
                logger.debug(
                    "Naming conflict present. Agents: %s .\
                    Returning first instance", agents)
                return agents[0]['agent_id']

        if external_application_id:
            agent_id = self.store.get_agent_id_by_application_id(self.save, external_application_id)
            if agent_id:
                agent = self.store.get_agent_by_id(self.save, agent_id)
                if agent["name"] != agent_name:
                    raise ValueError("Cannot re-assign external_application_id to a new agent")
                return agent_id

        try:
            return self.store.create_agent(agent_name, self.save, external_application_id)
        except IntegrityError as e:
            logger.error("Failed to create agent '%s': %s", agent_name, e)
            agent_id = self.store.get_agent_id_by_application_id(self.save, external_application_id)
            if agent_id:
                return agent_id
            else:
                raise
