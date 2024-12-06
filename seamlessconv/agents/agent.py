import threading
import logging
import time
from uuid import UUID
from typing import Dict, List, Any, Optional
from seamlessconv.event.eventbus import EventBus, Event
from seamlessconv.event.event_types import EventType
from seamlessconv.llm.llm_utils import load_prompt
from seamlessconv.agents.speaker_types import SpeakerState
from seamlessconv.database.session_manager import SessionManager

logger = logging.getLogger(__name__)

class Agent:
    def __init__(self, agent_id: UUID, event_bus: EventBus, store: SessionManager, is_user: bool = False):
        self.agent_id: UUID = agent_id
        self.group_id: Optional[str] = None
        self.is_user: bool = is_user

        self._event_bus: EventBus = event_bus
        self._lock: threading.Lock = threading.Lock()
        self.state: SpeakerState = SpeakerState.WAITING
        self.store: SessionManager = store

        self._personality: Optional[str] = None
        self._decision_prompt: List[Dict[str, str]] = []
        self._response_prompt: List[Dict[str, str]] = []

    def set_system_prompts(self, personality_file_path: str) -> None:
        """Load and set system prompts for the agent"""
        self._personality = "\n[PERSONALITY]\n" + load_prompt(personality_file_path)

        self._decision_prompt = [{
            "role": "system",
            "content": load_prompt('ai_prompts/system/decision_prompt.txt') + self._personality
        }]

        self._response_prompt = [{
            "role": "system",
            "content": load_prompt('ai_prompts/system/response_prompt.txt') + self._personality
        }]

    def set_group(self, group_id: str) -> None:
        """Assign agent to a conversation group"""
        self.group_id = group_id

    def update_conversation(self, event: Event) -> None:
        """Handle incoming transcription events"""
        with self._lock:
            interruption = event.data.get('context', {}).get('interruption', {})
            is_interrupted = bool(interruption.get('interrupted'))
            logger.debug("Agent %s interrupted status: %s", self.agent_id, is_interrupted)

            if is_interrupted and self.state == SpeakerState.SPEAKING:
                self._handle_interruption(event)
                return

            if self.state == SpeakerState.WAITING:
                self.state = SpeakerState.PENDING_DECISION
                self._request_decision(event)

    def _handle_interruption(self, event: Event) -> None:
        """Handle interruption events"""
        logger.debug("Handling interruption for agent: %s", self.agent_id)
        self._request_llm_decision(event, include_interruption=True)

    def _request_decision(self, event: Event) -> None:
        """Request decision about whether to speak"""
        logger.debug("Requesting speaking decision for agent %s", self.agent_id)
        self._request_llm_decision(event)

    def _request_llm_decision(self, event: Event, include_interruption: bool = False) -> None:
        """Make LLM request for decision making"""
        history = self.store.get_messages(event, ["decision", "response"])

        context_data = {'type': 'decision'}
        if include_interruption:
            context_data['interruption'] = event.data['context']['interruption']

        self._event_bus.publish(Event(
            type=EventType.LLM_INPUT_RECEIVED,
            agent_id=self.agent_id,
            group_id=event.group_id,
            timestamp=event.timestamp,
            data={
                'text': self._decision_prompt + self._format_messages(history, self.agent_id),
                'context': context_data
            }
        ))

    def handle_llm(self, event: Event) -> None:
        """Handle LLM response events"""
        with self._lock:
            if self.state == SpeakerState.PENDING_RESPONSE:
                logger.error("Agent %s already pending response", self.agent_id)
                return

            if self.state != SpeakerState.SPEAKING:
                self.state = SpeakerState.PENDING_RESPONSE

            decision = event.data['text']

            if decision == "[SKIP]":
                self.reset_pending()
                return

            if decision == "[GETINTERRUPTED]":
                self._handle_get_interrupted(event)
                return

            if decision == "[CONTINUE]":
                return

            if decision != "[RESPONSE]" and self.state == SpeakerState.SPEAKING:
                return

            if self.state == SpeakerState.SPEAKING:
                logger.error("Agent %s requested response while speaking", self.agent_id)
                return

            self._request_response_generation(event)

    def _handle_get_interrupted(self, event: Event) -> None:
        """Handle getting interrupted"""
        self._event_bus.publish(Event(
            type=EventType.TTS_STOP_SPEAKING,
            agent_id=self.agent_id,
            group_id=event.group_id,
            timestamp=time.time(),
            data={}
        ))
        self.reset_pending()

    def _request_response_generation(self, event: Event) -> None:
        """Request response generation from LLM"""
        history = self.store.get_messages(event, ["response"])

        logger.debug("Agent %s requesting response generation. State: %s", self.agent_id, self.state)
        self._event_bus.publish(Event(
            type=EventType.LLM_INPUT_RECEIVED,
            agent_id=self.agent_id,
            group_id=event.group_id,
            timestamp=event.timestamp,
            data={
                'text': self._response_prompt + self._format_messages(history, self.agent_id),
                'context': {
                    'type': 'response'
                }
            }
        ))

    def reset_pending(self) -> None:
        """Reset agent state to waiting"""
        self.state = SpeakerState.WAITING

    def set_speaking(self) -> None:
        """Set agent state to speaking"""
        self.state = SpeakerState.SPEAKING

    @staticmethod
    def _format_messages(history: List[Dict[str, Any]], agent_id: str) -> List[Dict[str, str]]:
        """Formats conversation history into chat message format"""
        logger.debug(history)
        formatted_messages = []
        for msg in history:
            role = "assistant" if msg['source_agent_id'] == agent_id else "user"
            formatted_messages.append({"role": role, "content": msg['content']})
        return formatted_messages
