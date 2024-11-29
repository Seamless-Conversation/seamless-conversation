# Seamless Conversation
<a><img align="right" src="https://github.com/user-attachments/assets/c1c4ee06-3720-464d-ac99-f6a3d17f9b39" width="150px"></a>
A flexible and extensible framework for managing multi-agent conversations with support for speech recognition, text-to-speech, and language model integration.

With the ability for both the AI and user to interrupt each other, the interaction more closely resembles a natural, casual conversation. Both the user and the AI can interject at any point.

<div>
    <p align="center">
        <a href="https://github.com/Seamless-Conversation/seamless-conversation/issues"> <img src="https://img.shields.io/github/issues/Seamless-Conversation/seamless-conversation"></a>
        <a href="https://github.com/Seamless-Conversation/seamless-conversation/pulls"> <img src="https://img.shields.io/github/issues-pr/Seamless-Conversation/seamless-conversation"></a>
        <a href="https://discord.gg/cuYKDGAxph"> <img src="https://img.shields.io/discord/1300460327628046376?style=flat&logo=discord&logoColor=fff&color=404eed" alt="discord"></a>
    </p>
</div>

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
- Python >= 3.9, < 3.12

### 1. Clone the repository
```bash
git clone https://github.com/SquirrelModeller/seamless-conversation.git
cd seamless-conversation
```

### 2. Install dependencies
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

Install PostgreSQL and Start the Service
- Windows:
    - Download and install PostgreSQL from the official website: postgresql.org/download/windows
    - Follow the installer prompts and ensure the PostgreSQL service is running

- macOS:
    ```
    brew install postgresql
    brew services start postgresql@14
    ```
- Debian/Ununtu
    ```
    sudo apt-get install postgresql postgresql-contrib
    sudo systemctl start postgresql
    ```


### 3. Set Up the Python Virtual Environment
Create a virtual environment (using Python 3.10 as an example):
- Windows
    ```
    python -m venv seampyconvo
    seampyconvo\Scripts\activate
    ```
- Unix-based systems (macOS and Linux):
    ```
    python3.10 -m venv seampyconvo
    source seampyconvo/bin/activate
    ```

### 4. Install Python Dependencies
With the virtual environment activated, install the required Python packages:
```
python -m pip install -r requirements.txt
```

### 5. Setup the Database
- macOS
    Setup database user
    ```
    createuser postgres
    createdb conversation_db
    ```

Run the Database Setup Script:
```
python src/database/setup_database.py
```

### 6. Set up environment variables (Optional)
To make use of APIs either add your key to the config.yaml file:
```
api_key: YOUR_API_KEY
```
Or set the key as an environment variable:
- Unix-based systems (macOS and Linux):
    ```
    export OPENAI_API_KEY=your_openai_api_key
    ```

### 7. Download Local Model (Optional)
```
python download_vosk_model.py
```

## Contribution
The dicussion tab is open if you have any questions, suggestions or want to talk about the project.

If you want to contribute to the code or work on the project, fork the repository and create a pull request. Please use the <a href="https://www.conventionalcommits.org/en/v1.0.0/">conventional commits</a> format when making a commit.

## Contact
We have a <a href="https://discord.gg/cuYKDGAxph">Discord Server</a>.

Alternatively reach out at: 
- **email:** seamlessconversation@gmail.com

## How it works (Basic overview)
Two system prompts are used. The first prompt is fed a personality and is only activated when the second prompt allows. The second prompt continually receives the conversation transcribed from the speech detected, be that an LLM (agent) or user talking. It then decides what action should be taken. It is informed if an interruption occurs or when an agent/user has finished speaking.
