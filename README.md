# Seamless Conversation

This project aims to provide a seamless experience when interacitng with an LLM model, with integrated speech recognition using the Vosk model.

With the ability for both the AI and user to interrupt each other, the interaction more closely resembles a natural, casual conversation. Both the user and the AI can interject at any point.

## Contribution

We have a <a href="https://discord.gg/cuYKDGAxph">Discord Server</a>.

The dicussion tab is open if you have any questions, suggestions or want to talk about the project.

If you want to contribute to code or work on the project, fork it. Then pull request.

Reach out to me at: squirrelmodeller@gmail.com or contact me on Discord: squirrelmodeller

## Setup Instructions

### Prerequisites

- Python 3.7 or higher
- OpenAI API Key (for GPT model interaction)
- Vosk model for speech recognition


### 1. Clone the repository

```bash
git clone https://github.com/SquirrelModeller/seamless-conversation.git
cd seamless-conversation
```

### 2. Install dependencies
Install all required Python packages using pip:
```
pip install -r requirements.txt
```

Install PortAudio

- Windows:
    ```
    python -m pip install pyaudio
    ```

- macOS:
    ```
    brew install portaudio
    ```

- Debian/Ununtu:
    ```
    sudo apt-get install libportaudio2
    ```

### 3. Set up environment variables

Make sure you have your OpenAI API key set up as an environment variable:
```
export OPENAI_API_KEY=your_openai_api_key
```

### 4. Download Vosk Model
```
python download_vosk_model.py
```


## How it works

Two system prompts are used. The first prompt is fed a personality and is only activated when the second prompt allows. The second prompt continually receives the conversation transcribed from the user's speech-to-text input and decides what action should be taken. It is informed if an interruption occurs or when the user has finished speaking.
