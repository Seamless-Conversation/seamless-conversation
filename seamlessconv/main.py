import os
import time
import argparse
import logging
from seamlessconv.config.loader import load_config
from seamlessconv.event.eventbus import EventBus
from seamlessconv.dialogue.dialogue_manager import DialogueManager
from seamlessconv.llm.factory import LLMFactory
from seamlessconv.stt.factory import STTFactory
from seamlessconv.tts.factory import TTSFactory
from seamlessconv.agents.agent import Agent
from seamlessconv.database.session_manager import SessionManager

DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

def parse_args():
    parser = argparse.ArgumentParser("Seamless conversation with AI")

    parser.add_argument('-overridelog', action='store_true', help='Override logging of external libraries and enable logging')
    parser.add_argument('-stt', help='Set the speech to text model')
    parser.add_argument('-tts', help='Set the text to speech model')
    parser.add_argument('-llm', help='Set the large language model')

    return parser.parse_args()

class ModuleFilter(logging.Filter):
    def filter(self, record):
        return record.name.startswith('seamlessconv')

def setup_logging(override_log):
    if DEBUG or override_log:
        logging.basicConfig(level=logging.DEBUG)

    if not override_log:
        return
    root_logger = logging.getLogger()

    filter_module = ModuleFilter()
    root_logger.addFilter(filter_module)

    logger_names = list(logging.Logger.manager.loggerDict.keys())
    for logger_name in logger_names:
        logger = logging.getLogger(logger_name)
        logger.addFilter(filter_module)

def main():
    args  = parse_args()

    config = load_config("config.yaml")

    if args.llm:
        config.llm.provider = args.llm
    if args.stt:
        config.stt.provider = args.stt
    if args.tts:
        config.tts.provider = args.tts

    # Enable initial logging, we need a better solution here.
    setup_logging(args.overridelog)

    event_bus = EventBus()

    stt_provider = STTFactory.create(event_bus, config.stt)
    llm_provider = LLMFactory.create(event_bus, config.llm)
    tts_provider = TTSFactory.create(event_bus, config.tts)

    # "Temporary" group. We want to init these based upon config/enviorment
    # This is very confusing. We are updating groups both in Dialogue Manager and Database
    # We need a new dataclass or something that Dialogue Manager and Database can share

    # Database setup
    store = SessionManager()

    store.set_application("App", "Example")

    store.set_save("Root")

    user_id = store.create_agent("User", external_application_id="00002003")
    sam_id = store.create_agent("Sam", external_application_id="00010004")

    event_id = store.create_and_store_event(
        user_id,
        [(user_id, "hear"), (sam_id, "hear")],
        "conversation"
    )

    group_id = store.create_conversation_group(event_id)

    # Dialogue Manager setup
    dialogue_manager = DialogueManager(event_bus, store)

    user = Agent(user_id, event_bus, store, True)
    sam = Agent(sam_id, event_bus, store)

    group_dm_1 = dialogue_manager.create_group(group_id)
    group_dm_1.add_member(user)
    group_dm_1.add_member(sam)

    sam.set_system_prompts("ai_prompts/npc_personalities/npc_sam")

    stt_provider.set_group_id(group_id)
    stt_provider.set_agent_id(user_id)


    # Setup logging here, libs need to be imported
    # before we can filter for them.
    setup_logging(args.overridelog)

    stt_provider.start()
    llm_provider.start()
    tts_provider.start()

    try:
        while True:
            time.sleep(0.1)

    except KeyboardInterrupt:
        logging.info("Recieved KeyboardInterrupt, stopping.")
        stt_provider.stop()
        llm_provider.stop()
        tts_provider.stop()
        event_bus.shutdown()

if __name__ == "__main__":
    main()
