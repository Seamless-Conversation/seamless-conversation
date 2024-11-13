from enum import Enum

# Tried working with numbers to see if I could include
# it in speech.py, to avoid the non-matches from classes
# importing speech.py. Did not work.

class SpeakerState(Enum):
    SPEAKING = 1
    PENDING_DECISION = 2
    PENDING_RESPONSE = 3
    INTERRUPTED = 4
    WAITING = 5