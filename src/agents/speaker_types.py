from enum import Enum

# Tried working with numbers to see if I could include
# it in speech.py, to avoid the non-matches from classes
# importing speech.py. Did not work.

class SpeakerState(Enum):
    SPEAKING = "speaking"
    PENDING_DECISION = "pending_decision"
    PENDING_RESPONSE = "pending_response"
    INTERRUPTED = "interrupted"
    WAITING = "waiting"
