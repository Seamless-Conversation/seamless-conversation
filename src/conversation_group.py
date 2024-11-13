import threading
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from src.event.eventbus import EventBus, Event
from src.event.event_types import EventType
from src.llm.llm_utils import load_prompt
from src.speaker_types import SpeakerState

logger = logging.getLogger(__name__)

@dataclass
class PendingTranscript:
    """Holds pending transcripts for batching"""
    speaker_id: str
    messages: List[str] = field(default_factory=list)
    last_timestamp: float = 0
    conversation_index: int = -1  # Track where this pending transcript started in conversation

class Speaker:
    def __init__(self, speaker_id: str, event_bus: EventBus):
        self.speaker_id = speaker_id
        self.group_id: Optional[str] = None
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self.state = SpeakerState.WAITING

        self.conversations: Dict[str, List[Dict[str, Any]]] = {}
        self.personality: List[Dict[str, str]] = []

        # Pending transcript buffer for batching
        self.pending_transcripts: Dict[str, PendingTranscript] = {}

        self.system_prompt = [{
            "role": "system",
            "content": load_prompt('ai_prompts/system/response_decision_prompt.txt')
        }]

    def set_personality(self, personality_file_path: str) -> None:
        self.personality.append({
            "role": "system",
            "content": load_prompt(personality_file_path)
        })

    def _append_to_conversation(self, speaker_id: str, message: str, group_id: str) -> int:
        """Append message to conversation and return its index"""
        conversation = self.conversations.setdefault(group_id, [])
        conversation.append({
            "role": "user",
            "content": f"{speaker_id}: {message}"
        })
        return len(conversation) - 1

    def _update_conversation_entry(self, group_id: str, index: int, new_message: str) -> None:
        """Update an existing conversation entry with new content"""
        if group_id in self.conversations and 0 <= index < len(self.conversations[group_id]):
            self.conversations[group_id][index]["content"] = new_message

    def _flush_pending_transcript(self, speaker_id: str) -> None:
        """Flush pending transcript for a speaker by updating the conversation entry"""
        if speaker_id in self.pending_transcripts:
            pending = self.pending_transcripts[speaker_id]
            if pending.messages and pending.conversation_index >= 0:
                combined_message = f"{speaker_id}: {' '.join(pending.messages)}"
                self._update_conversation_entry(self.group_id, pending.conversation_index, combined_message)
            del self.pending_transcripts[speaker_id]

    def _flush_all_pending_transcripts(self) -> None:
        """Flush all pending transcripts"""
        speaker_ids = list(self.pending_transcripts.keys())
        for speaker_id in speaker_ids:
            self._flush_pending_transcript(speaker_id)

    def update_conversation(self, event: Event) -> None:
        """Handle incoming transcription events"""
        with self._lock:
            transcript_text = event.data['text']
            is_interrupted = bool(event.data.get('context', {}).get('interruption', {}).get('interrupted'))
            logger.debug(f" Is agent {self.speaker_id} interrupted? {is_interrupted}")

            # If there's an interruption, flush existing transcripts
            if is_interrupted:
                self._flush_all_pending_transcripts()

            # Handle continuation of existing pending transcript or start new one
            if event.speaker_id in self.pending_transcripts:
                pending = self.pending_transcripts[event.speaker_id]
                pending.messages.append(transcript_text)
                pending.last_timestamp = event.timestamp
                # Update the existing conversation entry
                combined_message = f"{event.speaker_id}: {' '.join(pending.messages)}"
                self._update_conversation_entry(event.group_id, pending.conversation_index, combined_message)
            else:
                # Immediately append to conversation and create new pending transcript
                conv_index = self._append_to_conversation(event.speaker_id, transcript_text, event.group_id)
                self.pending_transcripts[event.speaker_id] = PendingTranscript(
                    speaker_id=event.speaker_id,
                    messages=[transcript_text],
                    last_timestamp=event.timestamp,
                    conversation_index=conv_index
                )

            # Handle self-transcription interruption
            if is_interrupted and self.state == SpeakerState.SPEAKING:
                self._request_interruption_decision(event)
                return

            # Handle other speaker transcription
            if self.state == SpeakerState.WAITING:
                self.state = SpeakerState.PENDING_DECISION
                self._request_speaking_decision(event)

    def _request_interruption_decision(self, event: Event) -> None:
        """Request LLM decision when being interrupted"""
        logger.debug(f"Interrupted, asking llm. Agent: {self.speaker_id}")
        self._flush_all_pending_transcripts()

        # the context even data is not doing anything yet
        # keeping as an example
        self._event_bus.publish(Event(
            type=EventType.LLM_INPUT_RECEIVED,
            speaker_id=self.speaker_id,
            group_id=event.group_id,
            timestamp=event.timestamp,
            data={
                'text': self.conversations.get(event.group_id),
                'system_prompt': self.system_prompt,
                'context': {
                    'type': 'decision',
                    'interruption': event.data['context']['interruption']
                }
            }
        ))

    def _request_speaking_decision(self, event: Event) -> None:
        """Request LLM decision about whether to speak"""
        logger.debug(f"Should agent {self.speaker_id} speak? Asking llm")
        logger.debug(f"Conversation: {self.conversations.get(event.group_id)}")
        self._flush_all_pending_transcripts()
        self._event_bus.publish(Event(
            type=EventType.LLM_INPUT_RECEIVED,
            speaker_id=self.speaker_id,
            group_id=event.group_id,
            timestamp=event.timestamp,
            data={
                'text': self.conversations.get(event.group_id),
                'system_prompt': self.system_prompt,
                'context': {
                    'type': 'decision'
                }
            }
        ))

    def handle_llm(self, event: Event) -> None:
        """Handle LLM responses"""
        with self._lock:
            if self.state == SpeakerState.PENDING_RESPONSE:
                logger.error(f"Agent {self.speaker_id} requested response generation while already pending response")
                return

            if self.state != SpeakerState.SPEAKING:
                self.state = SpeakerState.PENDING_RESPONSE

            # Add LLM decision to conversation history
            decision_text = f"{event.speaker_id}: {event.data['text']}"
            self.conversations.setdefault(event.group_id, []).append({
                "role": "user", 
                "content": decision_text
            })

            # Handle different decision types
            if event.data['text'] == "[SKIP]":
                self._event_bus.publish(Event(
                    type=EventType.TTS_STOP_SPEAKING,
                    speaker_id=event.speaker_id,
                    group_id=event.group_id,
                    timestamp=event.timestamp,
                    data={}
                ))
                self.reset_pending()
                return

            if event.data['text'] == "[CONTINUE]":
                return

            if event.data['text'] != "[RESPONSE]" and self.state == SpeakerState.SPEAKING:
                return

            if self.state == SpeakerState.SPEAKING:
                logger.error(f"Agent {self.speaker_id} requested response generation while speaking")
                return

            logger.debug(f"SENT REQUEST TO SPEAK {self.state}")
            # Request response generation
            self._event_bus.publish(Event(
                type=EventType.LLM_INPUT_RECEIVED,
                speaker_id=event.speaker_id,
                group_id=event.group_id,
                timestamp=event.timestamp,
                data={
                    'text': self.conversations.get(event.group_id),
                    'system_prompt': self.personality,
                    'context': {
                        'type': 'response'
                    }
                }
            ))

    def reset_pending(self) -> None:
        """Reset speaker state to waiting"""
        self.state = SpeakerState.WAITING

    def set_speaking(self) -> None:
        """Set speaker state to speaking"""
        with self._lock:
            self.state = SpeakerState.SPEAKING

class ConversationGroup:
    def __init__(self, group_id: str):
        self.group_id = group_id
        self.members: Dict[str, 'Speaker'] = {}
        self._lock = threading.Lock()

    def add_member(self, speaker: 'Speaker') -> None:
        with self._lock:
            self.members[speaker.speaker_id] = speaker

    def remove_member(self, speaker_id: str) -> None:
        with self._lock:
            self.members.pop(speaker_id, None)

    def is_member(self, speaker_id: str) -> bool:
        return speaker_id in self.members

    def get_speaking_members(self) -> List['Speaker']:
        return [speaker for speaker in self.members.values() if speaker.state == SpeakerState.SPEAKING]

    def get_members(self) -> List['Speaker']:
        return self.members.values()

    def get_member(self, speaker_id) -> Speaker:
        return self.members.get(speaker_id)