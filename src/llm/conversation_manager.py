import time
import os
from llm.base import LLMProvider
from threading import Thread, Event, Lock
from queue import Queue
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class ConversationManager:
    def __init__(self, llm_provider: LLMProvider, system_prompt_path: str, shared_queue: Queue):
        self.llm = llm_provider

        self._setup_system_prompt(system_prompt_path)
        self.queue = shared_queue
        self.should_stop = Event()
        self.manager_thread = None
        self.processing_lock = Lock()

        self.last_process_time = 0
        self.debounce_delay = 1.0
        self.accumulated_text = ""
        self.accumulation_lock = Lock()

        self.end_of_input_time = 0
        self.sent_end_of_input = True

    def _setup_system_prompt(self, system_prompt_path):
        system_prompt = self.load_prompt("ai_prompts/system/response_decision_prompt.txt")
        debug_scene = self.load_prompt("ai_prompts/conversation_tests/whiterun_scene_test.txt")
        self.conversation_history = [{"role": "system", "content": system_prompt + debug_scene}]

    def start(self):
        self.manager_thread = Thread(target=self.handle_should_respond)
        self.manager_thread.start()

    def stop(self):
        self.should_stop.set()
        if self.manager_thread:
            self.manager_thread.join()

    def load_prompt(self, file_path):
        try:
            with open(file_path, 'r') as file:
                prompt = file.read()
        except IOError as ioe:
            logger.error(f"Error opening the prompt file {file_path}: {ioe}")
        return prompt

    def update_conversation(self, role, content):
        self.conversation_history.append({
            "role": role,
            "content": content
        })

    def should_process(self):
        current_time = time.time()
        return (current_time - self.last_process_time) >= self.debounce_delay

    def _empty_queue(self):
        accumulated_text = []

        while not self.queue.qsize() == 0:
            try:
                text = self.queue.get_nowait()
                accumulated_text.append(text)
                self.queue.task_done()
            except Exception as e:
                logger.error(f"Error getting item form queue: {e}")
                break

        return " ".join(accumulated_text)

    def handle_should_respond(self):
        while not self.should_stop.is_set():
            try:
                if self.queue.qsize() == 0:
                    time.sleep(0.01)

                    if not self.sent_end_of_input and time.time() - self.end_of_input_time > 3:
                        with self.processing_lock:
                            self.sent_end_of_input = True
                            self.update_conversation("user", "USER: [EOI]")
                            logger.debug("EOI sent")
                            assistant_reply = self.llm.generate_response(self.conversation_history)
                            logger.debug(f"AI Response: {assistant_reply}")
                            self.update_conversation("assistant", assistant_reply)
                    continue

                self.end_of_input_time = time.time()
                self.sent_end_of_input = False

                with self.accumulation_lock:
                    self.accumulated_text += " " + self._empty_queue()
                
                if not self.processing_lock.locked():
                    self.process_accumulated_text()

            except Exception as e:
                logger.error(f"Error in conversation manager: {e}")

    def process_accumulated_text(self):
        with self.processing_lock:
            with self.accumulation_lock:
                if not self.accumulated_text.strip():
                    return
                
                text_to_process = self.accumulated_text.strip()
                self.accumulated_text = ""

            logger.debug(f"processing accumulated text: {text_to_process}")

            self.update_conversation("user", "USER: " + text_to_process)
            assistant_reply = self.llm.generate_response(self.conversation_history)
            logger.debug(f"AI Response: {assistant_reply}")
            self.update_conversation("assistant", assistant_reply)