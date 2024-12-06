import threading
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Callable
from uuid import UUID
from seamlessconv.event.eventbus import EventBus, Event
from seamlessconv.event.event_types import EventType
from seamlessconv.agents.conversation_group import ConversationGroup
from seamlessconv.agents.agent import Agent
from seamlessconv.database.session_manager import SessionManager

logger = logging.getLogger(__name__)

@dataclass
class DialogueState:
    """Represents the current state of a conversation"""
    current_speaker: Optional[UUID] = None
    pending_responses: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    current_speech_start: float = 0
    speaking_members: Set[UUID] = field(default_factory=set)

    def is_interrupted(self) -> bool:
        """Check if there's an interruption in the conversation"""
        return bool(self.current_speaker and len(self.speaking_members) > 1)

    def get_interrupters(self) -> List[UUID]:
        """Get list of speakers interrupting the current agent"""
        if not self.current_speaker:
            return []
        return [s for s in self.speaking_members if s != self.current_speaker]

class DialogueManager:
    def __init__(self, event_bus: EventBus, store: SessionManager):
        self.event_bus = event_bus
        self.groups: Dict[UUID, ConversationGroup] = {}
        self.dialogue_states: Dict[UUID, DialogueState] = {}
        self.lock = threading.Lock()
        self.store = store
        self._init_event_subscriptions()

    def _init_event_subscriptions(self) -> None:
        """Initialize event subscriptions for the DialogueManager"""
        event_handlers: Dict[EventType, Callable[[Event], None]] = {
            EventType.STT_TRANSCRIPTION_READY: self._handle_speech,
            EventType.LLM_RESPONSE_READY: self._handle_llm_response,
            EventType.SPEECH_STARTED: self._handle_speech_started,
            EventType.TTS_STREAMING_RESPONSE: self._handle_speech_streaming,
            EventType.SPEECH_ENDED: self._handle_speech_ended,
        }

        for event_type, handler in event_handlers.items():
            self.event_bus.subscribe(event_type, handler)

    def create_group(self, group_id: UUID) -> ConversationGroup:
        """Create and initialize a new conversation group"""
        with self.lock:
            group = ConversationGroup(group_id)
            self.groups[group_id] = group
            self.dialogue_states[group_id] = DialogueState()
            return group

    def _get_state_and_group(self, group_id: UUID) -> (DialogueState, ConversationGroup):
        """Get state and group objects, raising if not found"""
        if group_id not in self.dialogue_states:
            raise KeyError(f"No dialogue state found for group {group_id}")
        return self.dialogue_states[group_id], self.groups[group_id]

    def _handle_speech(self, event: Event) -> None:
        """Handle new transcription from spoken words"""
        try:
            state, group = self._get_state_and_group(event.group_id)
        except KeyError as e:
            logger.error(str(e))
            return

        with self.lock:
            self._update_speaking_state(state, group, event)
            self._process_speech_event(state, group, event)
            self._notify_llm_members(group, event)

    def _update_speaking_state(self, state: DialogueState, group: ConversationGroup, event: Event) -> None:
        """Update the current speaking state based on group members"""
        state.speaking_members = {m.agent_id for m in group.get_speaking_members()}

        # Add user to speaking members if they're the agent
        agent = group.get_member(event.agent_id)
        if agent and agent.is_user:
            state.speaking_members.add(event.agent_id)

    def _process_speech_event(self, state: DialogueState, group: ConversationGroup, event: Event) -> None:
        """Process speech event including transcription and interruption detection"""
        context = event.data.get('context', {})

        if 'word_timestamps' in context:
            timestamps = context['word_timestamps']
            current_time = time.time() - state.current_speech_start
            completed_text = self._process_transcription(timestamps, current_time)
            event.data['text'] = completed_text

        # User is not an LMM Agent, so we manually append sender prefix
        agent = group.get_member(event.agent_id)
        if agent and agent.is_user:
            event.data['text'] = f"User: {event.data['text']}"

        event.data.setdefault('context', {}).update(self._create_interruption_context(state, event))

        group_member_ids = self.groups[event.group_id].get_member_ids()
        agents = [(member, "hear") for member in group_member_ids]
        self.store.store_message(
            event=event,
            agents=agents
        )

    def _create_interruption_context(self, state: DialogueState, event: Event) -> Dict[str, Any]:
        """Create context information about any interruptions"""
        return {
            'interruption': {
                'interrupted': state.current_speaker if state.is_interrupted() else None,
                'interrupters': state.get_interrupters(),
                'interruption_time': event.timestamp if state.is_interrupted() else None
            },
            'current_speaker': state.current_speaker,
            'speaking_members': list(state.speaking_members)
        }

    def _notify_llm_members(self, group: ConversationGroup, event: Event) -> None:
        """Notify LLM members about the speech event"""
        for member in group.get_members():
            if member.is_user:
                continue
            if event.agent_id == member.agent_id and event.data['context'].get('speech_finished'):
                continue
            logger.debug("Updating member %s", member.agent_id)
            member.update_conversation(event)

    @staticmethod
    def _process_transcription(timestamps: List[tuple[str, float]], current_time: float) -> str:
        """Process word timestamps to get the completed sentence up to current time"""
        return ' '.join(word for word, timestamp in timestamps if timestamp <= current_time)

    def _handle_llm_response(self, event: Event) -> None:
        """Handle response generated by LLM"""
        with self.lock:
            state, group = self._get_state_and_group(event.group_id)
            agent = group.get_member(event.agent_id)

            response_type = event.data['context'].get('type')
            if response_type == "decision":
                self._handle_decision_response(event, agent)
            elif response_type == "response":
                self._handle_speech_response(state, event)
            else:
                logger.error("Unknown response type: %s", response_type)

    def _handle_decision_response(self, event: Event, agent: Agent) -> None:
        """Handle a decision type response from LLM"""
        self.store.store_message(
            event,
            [(event.agent_id, "hear")]
        )
        agent.handle_llm(event)

    def _handle_speech_response(self, state: DialogueState, event: Event) -> None:
        """Handle a speech type response from LLM"""
        state.pending_responses.append(event.data['text'])
        self._speak_next_response(event.group_id, event.agent_id)

    def _handle_speech_started(self, event: Event) -> None:
        """Handle when a agent starts speaking"""
        with self.lock:
            state, group = self._get_state_and_group(event.group_id)
            agent = group.get_member(event.agent_id)

            state.current_speaker = event.agent_id
            state.current_speech_start = event.timestamp
            state.speaking_members.add(event.agent_id)
            agent.set_speaking()

    def _handle_speech_streaming(self, event: Event) -> None:
        self._handle_speech(event)

    def _handle_speech_ended(self, event: Event) -> None:
        """Handle when a agent stops speaking"""
        self._handle_speech(event)
        with self.lock:
            state, group = self._get_state_and_group(event.group_id)
            agent = group.get_member(event.agent_id)

            if state.current_speaker == event.agent_id:
                state.current_speaker = None

            state.speaking_members.discard(event.agent_id)
            agent.reset_pending()

    def _speak_next_response(self, group_id: UUID, agent_id: UUID) -> None:
        """Trigger TTS for the next pending response"""
        state = self.dialogue_states[group_id]

        if state.pending_responses:
            response = state.pending_responses.pop(0)
            response = self._clean_text_to_be_spoken(response)

            self.event_bus.publish(Event(
                type=EventType.TTS_START_SPEAKING,
                agent_id=agent_id,
                group_id=group_id,
                timestamp=time.time(),
                data={'text': response}
            ))

    @staticmethod
    def _clean_text_to_be_spoken(text: str, prefix_length: int = 20) -> str:
        """Clean text by removing agent prefix if present"""
        if not text:
            return text

        if ':' in text[:prefix_length]:
            return text[text.find(':') + 1:].strip()

        return text.strip()
