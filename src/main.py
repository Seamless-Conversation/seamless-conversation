import os
from queue import Queue
from speech_recognition import SpeechRecognition
from conversation_manager import ConversationManager
import time

def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    system_prompt_path = 'ai_prompts/system/response_decision_prompt.txt'
    model_path = "models/vosk-model-en-us-0.22"

    shared_queue = Queue(maxsize=2000)

    speech_recognizer = SpeechRecognition(shared_queue, model_path)
    conversation_manager = ConversationManager(api_key, system_prompt_path, shared_queue)

    try:
        speech_recognizer.start()
        conversation_manager.start()

        while True:
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("Recieved KeyboardInterrupt, stopping.")
        speech_recognizer.stop()
        conversation_manager.stop()
    except Exception as e:
        print(f"An error occurred: {e}")
        speech_recognizer.stop()
        conversation_manager.stop()
        raise

if __name__ == "__main__":
    main()
