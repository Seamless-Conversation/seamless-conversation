# Seamless Conversation

A flexible and extensible framework for managing multi-agent conversations with support for speech recognition, text-to-speech, and language model integration.

With the ability for both the AI and user to interrupt each other, the interaction more closely resembles a natural, casual conversation. Both the user and the AI can interject at any point.

## Overview

This system enables natural conversations between human users and AI agents, supporting:

- Real-time speech recognition
- Natural language processing
- Text-to-speech synthesis
- Multi-agent conversation management
- Interruption handling
- Turn-taking mechanics

## Setup Instructions

### Prerequisites

- Python 3.8 or higher

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

### 3. Set up environment variables (Optional)
To make use of APIs either add your key to the config.yaml file:
```
api_key: YOUR_API_KEY
```
 or set the key as an environment variable:
```
export OPENAI_API_KEY=your_openai_api_key
```

### 4. Download Local Model (Optional)
```
python download_vosk_model.py
```

## Contribution

The dicussion tab is open if you have any questions, suggestions or want to talk about the project.

If you want to contribute to code or work on the project, fork it. Then pull request. Please use the <a href="https://www.conventionalcommits.org/en/v1.0.0/">conventional commits</a> when making a commit.

## Contact

We have a <a href="https://discord.gg/cuYKDGAxph">Discord Server</a>.

Alternatively reach out at: 
- **email:** squirrelmodeller@gmail.com
- **discord:** squirrelmodeller

## How it works (Basic overview)

Two system prompts are used. The first prompt is fed a personality and is only activated when the second prompt allows. The second prompt continually receives the conversation transcribed from the speech detected, be that an LLM (agent) or user talking. It then decides what action should be taken. It is informed if an interruption occurs or when an agent/user has finished speaking.
