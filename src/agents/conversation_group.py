import threading
import logging
from typing import Dict, List, Optional
from src.agents.agent import Agent
from src.agents.speaker_types import SpeakerState

logger = logging.getLogger(__name__)

class ConversationGroup:
    def __init__(self, group_id: str):
        self.group_id: str = group_id
        self._members: Dict[str, Agent] = {}
        self._lock: threading.Lock = threading.Lock()

    def add_member(self, agent: Agent) -> None:
        """Add an agent to the conversation group"""
        with self._lock:
            self._members[agent.agent_id] = agent
            agent.set_group(self.group_id)

    def remove_member(self, agent: Agent) -> None:
        """Remove an agent from the conversation group"""
        with self._lock:
            agent.set_group(None)
            self._members.pop(agent.agent_id, None)

    def is_member(self, agent_id: str) -> bool:
        """Check if an agent is a member of this group"""
        return agent_id in self._members

    def get_speaking_members(self) -> List[Agent]:
        """Get all currently speaking members"""
        return [agent for agent in self._members.values() 
                if agent.state == SpeakerState.SPEAKING]

    def get_members(self) -> List[Agent]:
        """Get all members of the group"""
        return list(self._members.values())

    def get_member(self, agent_id: str) -> Optional[Agent]:
        """Get a specific member by ID"""
        return self._members.get(agent_id)
