import os
from openai import OpenAI

class ConversationManager:
    def __init__(self, api_key, system_prompt_path):
        self.client = OpenAI(api_key=api_key)
        self.system_prompt = self.load_prompt(system_prompt_path)
        self.conversation_history = [
            {
                "role": "system",
                "content": self.system_prompt
            }
        ]

    def load_prompt(self, file_path):
        with open(file_path, 'r') as file:
            prompt = file.read()
        return prompt

    def get_user_input(self):
        return input("User: ")

    def update_conversation(self, role, content):
        self.conversation_history.append({
            "role": role,
            "content": content
        })

    def get_assistant_response(self):
        response = self.client.chat.completions.create(
            messages=self.conversation_history,
            model="gpt-3.5-turbo"
        )
        return response.choices[0].message.content.strip()

    def handle_should_respond(self):
        user_input = self.get_user_input()
        self.update_conversation("user", user_input)

        assistant_reply = self.get_assistant_response()
        print(f"Assistant: {assistant_reply}")

        self.update_conversation("assistant", assistant_reply)

    def handle_full_response(self):
        pass

def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    system_prompt_path = 'ai_prompts/system/response_decision_prompt.txt'
    
    conversation_manager = ConversationManager(api_key, system_prompt_path)
    while (True):
        conversation_manager.handle_should_respond()
    
if __name__ == "__main__":
    main()
