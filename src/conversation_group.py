import threading
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from src.event.eventbus import EventBus, Event
from src.event.event_types import EventType
from src.llm.llm_utils import load_prompt
from src.speaker_types import SpeakerState
from src.database.store import ConversationStore
import time

logger = logging.getLogger(__name__)

class Speaker:
    def __init__(self, speaker_id: str, event_bus: EventBus, conversation_store: ConversationStore, database_agent_id: str):
        self.speaker_id = speaker_id
        self.database_agent_id  = database_agent_id
        self.group_id: None
        
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self.state = SpeakerState.WAITING

        self.conversation_store = conversation_store

        self.personality: str = ""

        self.decision_prompt: List[Dict[str, str]] = []
        self.response_prompt: List[Dict[str, str]] = []


    def set_system_prompts(self, personality_file_path: str) -> None:
        self.personality = "\n[PERSONALITY]\n" + load_prompt(personality_file_path)
        self.decision_prompt.append({
            "role": "system",
            "content": load_prompt('ai_prompts/system/decision_prompt.txt') + self.personality         
        })
        self.response_prompt.append({
            "role": "system",
            "content": load_prompt('ai_prompts/system/response_prompt.txt') + self.personality
        })

    def set_group(self, group_id: str) -> None:
        self.group_id = group_id

    def update_conversation(self, event: Event) -> None:
        """Handle incoming transcription events"""
        with self._lock:
            is_interrupted = bool(event.data.get('context', {}).get('interruption', {}).get('interrupted'))
            logger.debug(f" Is agent {self.speaker_id} interrupted? {is_interrupted}")

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

        history = self.conversation_store.get_conversation_history(
            group_id=event.group_id,
            agent_id=self.database_agent_id,
            include_decisions=True,
            limit=500
        )
        
        self._event_bus.publish(Event(
            type=EventType.LLM_INPUT_RECEIVED,
            speaker_id=self.speaker_id,
            group_id=event.group_id,
            timestamp=event.timestamp,
            data={
                'text': self.decision_prompt + self._format_database_response(history),
                'context': {
                    'type': 'decision',
                    'interruption': event.data['context']['interruption']
                }
            }
        ))

    def _request_speaking_decision(self, event: Event) -> None:
        """Request LLM decision about whether to speak"""
        logger.debug(f"Should agent {self.speaker_id} speak? Asking llm")

        history = self.conversation_store.get_conversation_history(
            group_id=event.group_id,
            agent_id=self.database_agent_id,
            include_decisions=True,
            limit=500
        )

        self._event_bus.publish(Event(
            type=EventType.LLM_INPUT_RECEIVED,
            speaker_id=self.speaker_id,
            group_id=event.group_id,
            timestamp=event.timestamp,
            data={
                'text': self.decision_prompt + self._format_database_response(history),
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

            # Handle different decision types
            if event.data['text'] == "[SKIP]":
                self.reset_pending()
                return

            if event.data['text'] == "[GETINTERRUPTED]":
                self._event_bus.publish(Event(
                    type=EventType.TTS_STOP_SPEAKING,
                    speaker_id=self.speaker_id,
                    group_id=event.group_id,
                    timestamp=time.time(),
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

            history = self.conversation_store.get_conversation_history(
                group_id=event.group_id,
                agent_id=self.database_agent_id,
                include_decisions=False,
                limit=500
            )

            logger.debug(f"SENT REQUEST TO SPEAK {self.state}")
            self._event_bus.publish(Event(
                type=EventType.LLM_INPUT_RECEIVED,
                speaker_id=self.speaker_id,
                group_id=event.group_id,
                timestamp=event.timestamp,
                data={
                    'text': self.response_prompt + self._format_database_response(history),
                    'context': {
                        'type': 'response'
                    }
                }
            ))

    def _format_database_response(self, history: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        history_to_return = []

        for msg in history:
            assistant_role = "assistant" if msg['sender_id'] == self.database_agent_id else "user"

            history_to_return.append({"role": assistant_role, "content": msg['content']})

        return history_to_return

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
            self.members[speaker.speaker_id].set_group(self.group_id)

    def remove_member(self, speaker: 'Speaker') -> None:
        with self._lock:
            self.members[speaker.speaker_id].set_group(None)
            self.members.pop(speaker.speaker_id, None)

    def is_member(self, speaker_id: str) -> bool:
        return speaker_id in self.members

    def get_speaking_members(self) -> List['Speaker']:
        return [speaker for speaker in self.members.values() if speaker.state == SpeakerState.SPEAKING]

    def get_members(self) -> List['Speaker']:
        return self.members.values()

    def get_member(self, speaker_id) -> Speaker:
        return self.members.get(speaker_id)