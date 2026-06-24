import urllib.request
import json
import os
import random
from qwencpp_wrapper import config

def generate_tts(text: str, voice: str = None, instruction: str = None) -> bytes:
    """
    Proxy function to send TTS request to the QwenTTS server.
    """
    payload = {
        "input": text,
        "response_format": "wav"
    }
    if voice:
        payload["voice"] = voice
    if instruction:
        payload["instructions"] = instruction

    req = urllib.request.Request(
        config.TTS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    with urllib.request.urlopen(req) as response:
        return response.read()

def clone_voice(text: str, voice_ref: str, output_path: str, reference_text: str = None):
    """
    Clones a voice using a reference voice.
    Saves the output to the specified path (which can be a directory or a filename).
    """
    config.log(f"[Package] Cloning voice: generating '{text[:50]}...' using ref '{voice_ref}'")
    
    # Save the reference text transcript if provided
    if reference_text:
        # Resolve reference audio path
        if os.path.isabs(voice_ref) or os.path.exists(voice_ref):
            ref_audio_path = os.path.abspath(voice_ref)
        else:
            from qwencpp_wrapper import qwen_server
            if qwen_server._active_server and qwen_server._active_server.voices_dir:
                ref_audio_path = os.path.join(qwen_server._active_server.voices_dir, voice_ref)
            else:
                ref_audio_path = None
        
        if ref_audio_path:
            base, _ = os.path.splitext(ref_audio_path)
            ref_txt_path = base + ".txt"
            try:
                with open(ref_txt_path, "w", encoding="utf-8") as f:
                    f.write(reference_text)
                config.log(f"[Package] Reference text saved to: {ref_txt_path}")
            except Exception as e:
                config.log(f"[Package] Warning: Could not save reference text to {ref_txt_path}: {e}")

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
        
    config.log(f"[Package] Voice cloning successful! Saved to: {output_file}")
    return output_file

def design_voice(text: str, design_prompt: str, output_path: str):
    """
    Designs a voice using instructions.
    Saves the output to the specified path (which can be a directory or a filename).
    """
    config.log(f"[Package] Designing voice: generating '{text[:50]}...' with instruction '{design_prompt}'")
    
    # Generate the audio bytes
    audio_bytes = generate_tts(text=text, instruction=design_prompt)
    
    # Resolve the output path
    if os.path.isdir(output_path):
        output_file = os.path.join(output_path, "designed_voice.wav")
    else:
        output_file = os.path.abspath(output_path)
        
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, "wb") as f:
        f.write(audio_bytes)
        
    config.log(f"[Package] Voice design successful! Saved to: {output_file}")
    return output_file
