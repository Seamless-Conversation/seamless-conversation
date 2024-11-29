import unittest
from src.database.config import DatabaseConfig
from src.database.event_store import EventStore

class TestEventStore(unittest.TestCase):
    """
    Test suite for the EventStore class, covering functionality such
    as event witnessing, agent uniqueness across save lineages, and agent
    interaction with conversation groups and messages.
    """

    def setUp(self):
        self.store = EventStore(DatabaseConfig())

        self.app_id = self.store.create_application("TestEventStore", "Testcategory", {})

        self.root_save_id = self.store.create_save(self.app_id, "RootSave")
        self.child_save_id = self.store.create_save(self.app_id, "ChildSave", self.root_save_id)

        self.app_ids = [self.app_id]
        self.save_ids = [self.child_save_id, self.root_save_id]
        self.agent_ids = []
        self.event_ids = []
        self.group_ids = []

    def test_agent_uniqueness_in_same_lineage(self):
        """
        Test that agents maintain uniqueness within a save lineage.
        """

        external_app_id = "unique_external_id"
        agent_id_1 = self.store.create_agent("Agent1", self.root_save_id, external_app_id)

        self.assertIsNotNone(agent_id_1)
        self.agent_ids.append(agent_id_1)

        with self.assertRaises(Exception) as context:
            self.store.create_agent("Agent2", self.child_save_id, external_app_id)
        self.assertIn("already exists in the save lineage", str(context.exception))

    def test_agent_uniqueness_in_different_lineage(self):
        """
        Test that agents with the same external_application_id can be created in
        unrelated save lineages.
        """

        external_app_id = "unique_external_id"

        # Create agent in root save
        agent_id_1 = self.store.create_agent("Agent1", self.root_save_id, external_app_id)
        self.assertIsNotNone(agent_id_1)
        self.agent_ids.append(agent_id_1)

        # # Create a separate save not in the lineage
        separate_save_id = self.store.create_save(self.app_id, "SeparateSave")
        self.save_ids.append(separate_save_id)

        # Attempt to create another agent with the same external_application_id in separate save
        agent_id_2 = self.store.create_agent("Agent2", separate_save_id, external_app_id)
        self.assertIsNotNone(agent_id_2)
        self.agent_ids.append(agent_id_2)

        self.assertNotEqual(agent_id_1, agent_id_2)

    def test_event_store_witness(self):
        """
        Test that agents can only retrieve events they have directly witnessed.
        """

        app = self.store.create_application("TestApp", "TestCategory", {})
        self.app_ids.append(app)

        alex = self.store.create_agent("Alex", self.root_save_id, "00000001")
        self.agent_ids.append(alex)
        sam = self.store.create_agent("Sam", self.root_save_id, "00000002")
        self.agent_ids.append(sam)
        bob = self.store.create_agent("Bob", self.root_save_id, "00000003")
        self.agent_ids.append(bob)

        conversation_init = self.store.create_event(
            save_id=self.root_save_id,
            event_type="conversation",
            data={
                "action": "talk",
                "source_agent": str(alex),
                "target_agent": str(sam),
                "location": "town_square"
            },
            witnesses=[
                {"agent_id": alex, "witness_type": "see_hear", "context": {"distance": 10}},
                {"agent_id": sam, "witness_type": "see_hear", "context": {"distance": 10}},
            ]
        )
        self.event_ids.append(conversation_init)

        conversation_1 = self.store.create_conversation_group(conversation_init)
        self.group_ids.append(conversation_1)

        spoken_event_1 = self.store.create_event(
            save_id=self.root_save_id,
            event_type="talking",
            data={
                "action": "talk",
                "source_agent": str(alex),
                "target_agent": str(sam),
                "location": "town_square"
            },
            witnesses=[
                {"agent_id": alex, "witness_type": "see_hear", "context": {"distance": 10}},
                {"agent_id": sam, "witness_type": "see_hear", "context": {"distance": 10}}
            ]
        )
        self.event_ids.append(spoken_event_1)

        self.store.create_conversation_message(
            event_id=spoken_event_1,
            group_id=conversation_1,
            content="Hello there Sam!",
            message_type="response",
            context={}
        )

        thinking_event_2 = self.store.create_event(
            save_id=self.child_save_id,
            event_type="talk",
            data={
                "action": "thinking",
                "source_agent": str(sam),
                "target_agent": str(alex),
                "location": "town_square"
            },
            witnesses=[
                {"agent_id": sam, "witness_type": "thought"},
            ]
        )
        self.event_ids.append(thinking_event_2)

        self.store.create_conversation_message(
            event_id=thinking_event_2,
            group_id=conversation_1,
            content="[RESPOND]",
            message_type="decision",
            context={}
        )

        spoken_event_2 = self.store.create_event(
            save_id=self.child_save_id,
            event_type="talking",
            data={
                "action": "talk",
                "source_agent": str(sam),
                "target_agent": str(alex),
                "location": "town_square"
            },
            witnesses=[
                {"agent_id": alex, "witness_type": "see_hear", "context": {"distance": 10}},
                {"agent_id": sam, "witness_type": "see_hear", "context": {"distance": 10}},
                {"agent_id": bob, "witness_type": "hear", "context": {"distance": 100}}
            ]
        )
        self.event_ids.append(spoken_event_2)

        self.store.create_conversation_message(
            event_id=spoken_event_2,
            group_id=conversation_1,
            content="Hi Alex. How are you?",
            message_type="response",
            context={}
        )

        messages_1 = self.store.get_agent_conversation_history(
            self.root_save_id, alex, conversation_1
        )
        messages_2 = self.store.get_agent_conversation_history(
            self.child_save_id, sam, conversation_1
        )
        messages_3 = self.store.get_agent_conversation_history(
            self.child_save_id, bob, conversation_1
        )

        # Alex in root_save_id should only know about the first message
        self.assertEqual(len(messages_1), 1)
        self.assertEqual(messages_1[0]['content'], "Hello there Sam!")
        self.assertEqual(messages_1[0]['type'], "response")

        # Sam in child_save_id should know about all three messages
        self.assertEqual(len(messages_2), 3)
        self.assertEqual(messages_2[0]['content'], "Hello there Sam!")
        self.assertEqual(messages_2[0]['type'], "response")
        self.assertEqual(messages_2[1]['content'], "[RESPOND]")
        self.assertEqual(messages_2[1]['type'], "decision")
        self.assertEqual(messages_2[2]['content'], "Hi Alex. How are you?")
        self.assertEqual(messages_2[2]['type'], "response")

        # Bob in child_save_id should only know about the last spoken message
        self.assertEqual(len(messages_3), 1)
        self.assertEqual(messages_3[0]['content'], "Hi Alex. How are you?")
        self.assertEqual(messages_3[0]['type'], "response")

    def tearDown(self):
        for group_id in self.group_ids:
            self.store.delete_conversation_group(group_id)
        for event_id in self.event_ids:
            self.store.delete_event(event_id)
        for agent_id in self.agent_ids:
            self.store.delete_agent(agent_id)
        for save_id in self.save_ids:
            self.store.delete_save(save_id)
        for app_id in self.app_ids:
            self.store.delete_application(app_id)

if __name__ == '__main__':
    unittest.main()
