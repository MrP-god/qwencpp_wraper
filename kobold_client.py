import urllib.request
import json
import os
import random
from koboldcpp_wrapper_server import config

def generate_tts(text: str, voice: str, instruction: str = None) -> bytes:
    """
    Proxy function to send TTS request to the KoboldCPP server.
    """
    payload = {
        "text": text,
        "voice": voice
    }
    if instruction:
        payload["instruction"] = instruction

    req = urllib.request.Request(
        config.TTS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    with urllib.request.urlopen(req) as response:
        return response.read()

def clone_voice(text: str, voice_ref: str, output_path: str):
    """
    Clones a voice using a reference voice.
    Saves the output to the specified path (which can be a directory or a filename).
    """
    print(f"[Package] Cloning voice: generating '{text[:50]}...' using ref '{voice_ref}'")
    
    # Generate the audio bytes
    audio_bytes = generate_tts(text=text, voice=voice_ref)
    
    # Resolve the output path
    if os.path.isdir(output_path):
        output_file = os.path.join(output_path, "cloned_voice.wav")
    else:
        output_file = os.path.abspath(output_path)
        
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, "wb") as f:
        f.write(audio_bytes)
        
    print(f"[Package] Voice cloning successful! Saved to: {output_file}")
    return output_file

def design_voice(text: str, design_prompt: str, output_path: str):
    """
    Designs a voice using instructions.
    Saves the output to the specified path (which can be a directory or a filename).
    """
    print(f"[Package] Designing voice: generating '{text[:50]}...' with instruction '{design_prompt}'")
    
    # Generate a unique speaker ID to force a unique speaker seed
    speaker_name = f"designed_speaker_{random.randint(100000, 999999)}"
    
    # Generate the audio bytes
    audio_bytes = generate_tts(text=text, voice=speaker_name, instruction=design_prompt)
    
    # Resolve the output path
    if os.path.isdir(output_path):
        output_file = os.path.join(output_path, "designed_voice.wav")
    else:
        output_file = os.path.abspath(output_path)
        
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, "wb") as f:
        f.write(audio_bytes)
        
    print(f"[Package] Voice design successful! Saved to: {output_file}")
    return output_file
