from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from enum import Enum
import threading
import time
import logging
import re
from src.event.eventbus import EventBus, Event
from src.event.event_types import EventType
from src.conversation_group import ConversationGroup
from src.llm.llm_utils import load_prompt
from src.speech import SpeechType
from src.speaker_types import SpeakerState

logger = logging.getLogger(__name__)

@dataclass
class DialogueState:
    """Represents the current state of a conversation"""
    current_speaker: Optional[str] = None
    pending_responses: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    last_interruption_time: float = 0
    current_speech_start: float = 0
    speaking_members: Set[str] = field(default_factory=set)
    current_transcription: List[tuple[str, float]] = field(default_factory=list)

class DialogueManager:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.groups: Dict[str, ConversationGroup] = {}
        self.dialogue_states: Dict[str, DialogueState] = {}
        self.lock = threading.Lock()
        self._subscribe_to_events()

    def _subscribe_to_events(self) -> None:
        """Subscribe to all events that the DialogueManager needs to handle"""
        subscriptions = {
            EventType.STT_TRANSCRIPTION_READY: self._handle_speech,
            EventType.LLM_RESPONSE_READY: self._handle_llm_response,
            EventType.SPEECH_STARTED: self._handle_speech_started,
            EventType.TTS_STREAMING_RESPONSE: self._handle_speech_streaming,
            EventType.SPEECH_ENDED: self._handle_speech_ended,
        }

        for event_type, handler in subscriptions.items():
            self.event_bus.subscribe(event_type, handler)

    def create_group(self, group_id: str) -> ConversationGroup:
        """Create a new conversation group"""
        with self.lock:
            group = ConversationGroup(group_id)
            self.groups[group_id] = group
            self.dialogue_states[group_id] = DialogueState()
            return group

    def _process_transcription(self, state: DialogueState, timestamps: List[tuple[str, float]], current_time: float) -> str:
        """Process word timestamps to get the completed sentence up to current time"""
        completed_words = []
        for word, timestamp in timestamps:
            if timestamp <= current_time:
                completed_words.append(word)
            else:
                break
        return ' '.join(completed_words)

    def _detect_interruption(self, state: DialogueState, event: Event, speaking_members: Set[str]) -> Dict[str, Any]:
        """Detect and handle interruptions in the conversation"""
        interruption_context = {
            'interrupted': None,
            'interrupters': [],
            'interruption_time': None
        }

        # User is not part of SpeakerState, therefore we add them here
        if event.speaker_id == "user":
            speaking_members.add(event.speaker_id)

        # If there's a current speaker and others are speaking, it's an interruption
        if state.current_speaker and len(speaking_members) > 1:
            interruption_context.update({
                'interrupted': state.current_speaker,
                'interrupters': [s for s in speaking_members if s != state.current_speaker],
                'interruption_time': event.timestamp
            })
            state.last_interruption_time = event.timestamp

        return interruption_context

    def _handle_speech(self, event: Event) -> None:
        """Handle new transcription from spoken words"""
        # logger.debug(f"Speech event spoken by {event.speaker_id} group {event.group_id} text {event.data['text']}")
        if event.group_id not in self.dialogue_states:
            logger.error(f"No dialogue state found for group {event.group_id}")
            return

        with self.lock:
            state = self.dialogue_states[event.group_id]
            group = self.groups[event.group_id]

            # Update speaking members
            state.speaking_members = {m.speaker_id for m in group.get_speaking_members()}

            # Process transcription if available
            if 'word_timestamps' in event.data.get('context', {}):
                timestamps = event.data['context']['word_timestamps']
                current_time = time.time() - state.current_speech_start
                completed_text = self._process_transcription(state, timestamps, current_time)
                event.data['text'] = completed_text

            # Handle interruption detection
            interruption_context = self._detect_interruption(state, event, state.speaking_members)
            # logger.debug(f"Speaking members: {state.speaking_members}")

            # Update event context
            event.data.setdefault('context', {})
            event.data['context'].update({
                'speech_type': SpeechType.USER if event.speaker_id == "user" else SpeechType.LLM,
                'interruption': interruption_context,
                'current_speaker': state.current_speaker,
                'speaking_members': list(state.speaking_members)
            })

            logger.debug(f"Speech event spoken by {event.speaker_id} group {event.group_id} text {event.data['text']}")

            # Notify all LLM members of the group
            for member in group.get_members():
                if member.speaker_id != "user":
                    # Don't notify speaker about their own completed speech
                    if event.speaker_id == member.speaker_id and event.data['context'].get('speech_finished'):
                        continue
                    logger.debug(f" Updating member {member.speaker_id}")
                    member.update_conversation(event)

    def _handle_llm_response(self, event: Event) -> None:
        """Handle response generated by LLM"""
        with self.lock:
            logger.debug(f"  Response from llm for {event.speaker_id} group {event.group_id} type {event.data['context']['type']}")
            state = self.dialogue_states[event.group_id]
            speaker = self.groups[event.group_id].get_member(event.speaker_id)

            response_type = event.data['context'].get('type')
            if response_type == "decision":
                speaker.handle_llm(event)
            elif response_type == "response":
                state.pending_responses.append(event.data['text'])
                self._speak_next_response(event.group_id, event.speaker_id)
            else:
                logger.error(f"Unknown response type: {response_type}")

    def _handle_speech_started(self, event: Event) -> None:
        """Handle when a speaker starts speaking"""
        logger.debug(f" Agent {event.speaker_id} started speaking")
        with self.lock:
            state = self.dialogue_states[event.group_id]
            state.current_speaker = event.speaker_id
            state.current_speech_start = event.timestamp
            state.speaking_members.add(event.speaker_id)

            speaker = self.groups[event.group_id].get_member(event.speaker_id)
            speaker.set_speaking()

    def _handle_speech_streaming(self, event: Event) -> None:
        """Handle streaming speech updates"""
        self._handle_speech(event)

    def _handle_speech_ended(self, event: Event) -> None:
        self._handle_speech(event)
        """Handle when a speaker stops speaking"""
        with self.lock:
            state = self.dialogue_states[event.group_id]

            if state.current_speaker == event.speaker_id:
                state.current_speaker = None

            state.speaking_members.discard(event.speaker_id)

            speaker = self.groups[event.group_id].get_member(event.speaker_id)
            speaker.reset_pending()

            # Handle final speech event
            # But we don't really do anything with event here,
            # Should probably be removed, but we might want to modify it
            # in the future
            event.data.setdefault('context', {})

    def _speak_next_response(self, group_id: str, speaker_id: str) -> None:
        """Trigger TTS for the next pending response"""
        state = self.dialogue_states[group_id]

        if state.pending_responses:
            response = state.pending_responses.pop(0)
            self.event_bus.publish(Event(
                type=EventType.TTS_START_SPEAKING,
                speaker_id=speaker_id,
                group_id=group_id,
                timestamp=time.time(),
                data={'text': response}
            ))

    def get_conversation_context(self, group_id: str) -> Dict[str, Any]:
        """Get the current conversation context for a group"""
        with self.lock:
            return self.dialogue_states[group_id].context.copy()