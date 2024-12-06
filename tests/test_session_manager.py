import unittest
from seamlessconv.database.session_manager import SessionManager
from seamlessconv.event.eventbus import Event, EventType

class TestSessionManager(unittest.TestCase):
    """
    Test suite for the SessionManager class, which is responsible for managing
    applications, saves, agents, events, and conversation groups within a session.
    """
    def setUp(self):
        self.session_manager = SessionManager()
        self.app_name = "TestApp"
        self.session_manager.set_application(self.app_name, "TestCategory")
        self.save_name = "TestSave"
        self.session_manager.set_save(self.save_name)
        self.agent_name = "TestAgent"
        self.agent_id = self.session_manager.create_agent(
            self.agent_name,
            external_application_id="agent_ext_id"
        )

        self.app_ids = [self.session_manager.app_id]
        self.save_ids = [self.session_manager.save]
        self.agent_ids = [self.agent_id]
        self.event_ids = []
        self.group_ids = []

    def test_set_application(self):
        """Test that setting an application correctly updates its ID and name."""
        app_id = self.session_manager.set_application(self.app_name)
        self.assertEqual(self.session_manager.app_name, self.app_name)
        self.assertEqual(self.session_manager.app_id, app_id)

    def test_set_save(self):
        """Test that setting a save correctly updates its ID."""
        save_id = self.session_manager.set_save(self.save_name)
        self.assertEqual(self.session_manager.save, save_id)

    def test_create_agent(self):
        """Test creating agents and handling naming conflicts."""
        self.assertIsNotNone(self.agent_id)

        agent_id_same = self.session_manager.create_agent(self.agent_name)
        self.assertEqual(self.agent_id, agent_id_same)

        new_agent_name = "NewTestAgent"
        new_agent_id = self.session_manager.create_agent(new_agent_name)
        self.assertNotEqual(self.agent_id, new_agent_id)
        self.agent_ids.append(new_agent_id)

    def test_create_and_store_event(self):
        """Test creating and storing an event in the session."""
        agents = [(self.agent_id, "see_hear")]
        event_type = "test_event"
        event_id = self.session_manager.create_and_store_event(self.agent_id, agents, event_type)
        self.assertIsNotNone(event_id)
        self.event_ids.append(event_id)

    def test_store_message_and_get_messages(self):
        """Test storing a message and retrieving it from the session."""
        agents = [(self.agent_id, "see_hear")]
        event_type = "test_message_event"
        event_id = self.session_manager.create_and_store_event(self.agent_id, agents, event_type)
        self.event_ids.append(event_id)

        group_id = self.session_manager.create_conversation_group(event_id)
        self.assertIsNotNone(group_id)
        self.group_ids.append(group_id)

        event = Event(
            type=EventType.LLM_RESPONSE_READY,
            agent_id=self.agent_id,
            group_id=group_id,
            data={'text': 'Hello, this is a test message.', 'context': {'type': 'test'}},
            timestamp=None
        )

        talk_event_id = self.session_manager.store_message(event, agents)
        self.event_ids.append(talk_event_id[0])

        messages = self.session_manager.get_messages(event)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['content'], 'Hello, this is a test message.')
        self.assertEqual(messages[0]['type'], 'test')


    def test_create_agent_uniqueness_violation(self):
        """
        Test that attempting to create an agent with a duplicate
        external_application_id raises an error.
        """
        with self.assertRaises(Exception) as context:
            self.session_manager.create_agent(
                "AnotherAgent", external_application_id="agent_ext_id"
            )
        self.assertIn(
            "Cannot re-assign external_application_id to a new agent",
            str(context.exception)
        )

    def test_create_agent_uniqueness_same_name(self):
        """
        Test that creating an agent with a matching name and
        external_application_id returns the same ID.
        """
        agent = self.session_manager.create_agent(
            "TestAgent", external_application_id="agent_ext_id"
        )
        self.assertEqual(agent, self.agent_id)

    def tearDown(self):
        for group_id in self.group_ids:
            self.session_manager.store.delete_conversation_group(group_id)
        for event_id in self.event_ids:
            self.session_manager.store.delete_event(event_id)
        for agent_id in self.agent_ids:
            self.session_manager.store.delete_agent(agent_id)
        for save_id in self.save_ids:
            self.session_manager.store.delete_save(save_id)
        for app_id in self.app_ids:
            self.session_manager.store.delete_application(app_id)


if __name__ == '__main__':
    unittest.main()
