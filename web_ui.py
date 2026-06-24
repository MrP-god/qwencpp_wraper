import os
import sys
import shutil
import tempfile
import gradio as gr
import socket
import json
import time
from qwencpp_wrapper import start_server, shutdown_server, clone_voice, design_voice, config

languages_list = ["English", "Chinese", "Japanese", "Korean", "German", "French", "Russian", "Portuguese", "Spanish", "Italian"]

cancel_generation = False
session_temp_files = []

def ui_stop_generation():
    global cancel_generation
    cancel_generation = True
    return "Stop request sent. Wait for active generation to stop."

def on_ui_unload():
    # Stop server
    shutdown_server()
    # Clean up temp files
    print("[UI] Cleaning up temporary session files...")
    for path in session_temp_files:
        try:
            if os.path.exists(path):
                os.remove(path)
                print(f"[UI] Cleaned up: {path}")
        except Exception as e:
            print(f"[UI] Error cleaning up {path}: {e}")

# Check if the KoboldCPP server port is open
def check_status():
    try:
        with socket.create_connection(("127.0.0.1", config.PORT), timeout=1):
            return "🟢 Online (Server is running)"
    except OSError:
        return "🔴 Offline (Server is stopped)"

# Helper to automatically detect models/voices in the current working directory
def scan_assets():
    cwd = os.getcwd()
    ggufs = [os.path.join(cwd, f) for f in os.listdir(cwd) if f.endswith(".gguf") and "tokenizer" not in f.lower()]
    tokenizers = [os.path.join(cwd, f) for f in os.listdir(cwd) if f.endswith(".gguf") and "tokenizer" in f.lower()]
    
    default_base = ""
    default_design = ""
    for g in ggufs:
        if "base" in g.lower():
            default_base = g
        elif "design" in g.lower():
            default_design = g
            
    # Fallback to first found gguf
    if not default_base and ggufs:
        default_base = ggufs[0]
    if not default_design and ggufs:
        default_design = ggufs[0]
        
    default_tok = tokenizers[0] if tokenizers else ""
    
    # Locate Voices directory
    default_voices = os.path.join(cwd, "Voices")
    if not os.path.exists(default_voices):
        default_voices = ""
        
    return default_base, default_design, default_tok, default_voices

# Start the server backend from Gradio controls
def ui_start_server(action_type, model, tokenizer, voices_dir, 
                    gpu_backend, use_tts_gpu, gpu_layers, threads, tts_threads, debug):
    if not model or not os.path.exists(model):
        return "Error: Model file does not exist. Please check your path.", check_status()
    if not tokenizer or not os.path.exists(tokenizer):
        return "Error: Tokenizer file does not exist. Please check your path.", check_status()
    if action_type == "base" and (not voices_dir or not os.path.exists(voices_dir)):
        return "Error: Voices directory must exist for Voice Cloning mode.", check_status()
        
    try:
        # Convert empty strings or zeros to None for threads
        t_val = int(threads) if threads and int(threads) > 0 else None
        tt_val = int(tts_threads) if tts_threads and int(tts_threads) > 0 else None
        layers_val = int(gpu_layers) if gpu_layers is not None else -1
        
        # Map human-readable dropdown choices to backend strings
        backend_map = {
            "Vulkan": "vulkan",
            "CUDA (Nvidia)": "cuda",
            "CPU Only": "cpu"
        }
        backend_str = backend_map.get(gpu_backend, "vulkan")
        
        start_server(
            action_type=action_type, 
            model_path=model, 
            tokenizer_path=tokenizer, 
            voices_dir=voices_dir,
            gpu_backend=backend_str,
            use_tts_gpu=use_tts_gpu,
            gpu_layers=layers_val,
            threads=t_val,
            tts_threads=tt_val,
            debug=debug
        )
        return "Server initialized successfully!", check_status()
    except Exception as e:
        return f"Failed to start server: {e}", check_status()

# Terminate the server backend from Gradio controls
def ui_stop_server():
    try:
        shutdown_server()
        return "Server stopped successfully.", check_status()
    except Exception as e:
        return f"Failed to stop server: {e}", check_status()

# Load Voice transcript if it exists
def load_voice_transcript(voice_ref, voices_dir):
    if not voice_ref or not voices_dir or not os.path.exists(voices_dir):
        return ""
    base, _ = os.path.splitext(voice_ref)
    txt_path = os.path.join(voices_dir, base + ".txt")
    if os.path.exists(txt_path):
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""

# Trigger Voice Cloning
def ui_clone_voice(text, voice_ref, output_name, voices_dir, reference_text):
    if not voice_ref:
        return None, "Error: Please select a reference voice template."
    if not text.strip():
        return None, "Error: Please enter text to generate."
        
    try:
        if "🔴" in check_status():
            return None, "Error: Server is offline. Please start the server first."
            
        output_file = os.path.join(os.getcwd(), output_name)
        clone_voice(text, voice_ref, output_file, reference_text=reference_text)
        return output_file, f"Success! Saved to: {output_file}"
    except Exception as e:
        return None, f"Voice cloning failed: {e}"

# Trigger Voice Design
def ui_design_voice(text, prompt, output_name):
    if not prompt.strip():
        return None, "Error: Instruction prompt cannot be empty."
    if not text.strip():
        return None, "Error: Please enter text to generate."
        
    try:
        if "🔴" in check_status():
            return None, "Error: Server is offline. Please start the server first."
            
        output_file = os.path.join(os.getcwd(), output_name)
        design_voice(text, prompt, output_file)
        return output_file, f"Success! Saved to: {output_file}"
    except Exception as e:
        return None, f"Voice design failed: {e}"

# Get list of .wav voice files


def render_history_html(history):
    if not history:
        return "<div style='color: #9CA3AF; text-align: center; padding: 2rem;'>No designed voices in this session yet. Enter text below and click 'Design & Synthesize'!</div>"
    
    grouped = {}
    for item in history:
        phrase = item["phrase"]
        if phrase not in grouped:
            grouped[phrase] = []
        grouped[phrase].append(item)
        
    html = "<div class='history-container' style='display: flex; flex-direction: column; gap: 1.25rem; margin-top: 1rem; max-height: 500px; overflow-y: auto; padding-right: 0.5rem;'>"
    
    ordered_phrases = []
    for item in reversed(history):
        if item["phrase"] not in ordered_phrases:
            ordered_phrases.append(item["phrase"])
            
    for phrase in ordered_phrases:
        clips = grouped[phrase]
        safe_phrase = phrase.replace("'", "\\'").replace('"', '&quot;')
        html += f'''
        <div class="phrase-group" style="padding: 1rem; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.08); background: rgba(17, 24, 39, 0.45); backdrop-filter: blur(8px); display: flex; flex-direction: column; gap: 0.75rem;">
            <div style="border-bottom: 1px solid rgba(255, 255, 255, 0.08); padding-bottom: 0.4rem; margin-bottom: 0.1rem; display: flex; justify-content: space-between; align-items: center;">
                <h4 style="margin: 0; color: #818CF8; font-size: 0.95rem; font-weight: 700; word-break: break-all;">Phrase: "{phrase}"</h4>
                <div style="display: flex; align-items: center; gap: 0.6rem;">
                    <span style="font-size: 0.75rem; color: #9CA3AF; background: rgba(255,255,255,0.05); padding: 0.1rem 0.4rem; border-radius: 4px;">{len(clips)} clips</span>
                    <button onclick="deletePhrase('{safe_phrase}')" style="background: transparent; border: 1px solid rgba(239, 68, 68, 0.3); color: #EF4444; font-size: 0.75rem; cursor: pointer; font-weight: 600; padding: 0.1rem 0.4rem; border-radius: 4px; transition: all 0.2s ease;">Delete Group</button>
                </div>
            </div>
            <div style="display: flex; flex-direction: column; gap: 0.6rem;">
        '''
        
        for clip in clips:
            idx = clip["index"]
            status = clip["status"]
            audio_url = clip.get("audio_path", "")
            json_url = clip.get("json_path", "")
            txt_url = clip.get("txt_path", "")
            clip_id = clip.get("id", "")
            
            status_badge = "Success" if status == "Success" else "Failed"
            
            html += f'''
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; padding: 0.35rem 0; border-bottom: 1px dashed rgba(255, 255, 255, 0.03); flex-wrap: wrap;">
                <div style="display: flex; align-items: center; gap: 0.4rem; min-width: 80px;">
                    <span style="font-size: 0.8rem; font-weight: 600; color: #E5E7EB;">Clip #{idx}</span>
                    <span style="font-size: 0.75rem; color: #9CA3AF;">{status_badge}</span>
                </div>
            '''
            
            if status == "Success":
                html += f'''
                <audio src="{audio_url}" controls style="height: 28px; max-width: 280px; flex-grow: 1;"></audio>
                <div style="display: flex; gap: 0.4rem;">
                    <a href="{audio_url}" download="voice_clip_{idx}.wav" style="display: inline-flex; align-items: center; justify-content: center; padding: 0.3rem 0.6rem; border-radius: 5px; border: 1px solid rgba(129, 140, 248, 0.25); background: rgba(99, 102, 241, 0.1); color: #818CF8; font-size: 0.75rem; text-decoration: none; font-weight: 600; transition: all 0.2s ease;">WAV</a>
                    <a href="{txt_url}" download="voice_clip_{idx}.txt" style="display: inline-flex; align-items: center; justify-content: center; padding: 0.3rem 0.6rem; border-radius: 5px; border: 1px solid rgba(16, 185, 129, 0.25); background: rgba(16, 185, 129, 0.1); color: #10B981; font-size: 0.75rem; text-decoration: none; font-weight: 600; transition: all 0.2s ease;">TXT</a>
                    <a href="{json_url}" download="meta_clip_{idx}.json" style="display: inline-flex; align-items: center; justify-content: center; padding: 0.3rem 0.6rem; border-radius: 5px; border: 1px solid rgba(255,255,255,0.12); background: rgba(255,255,255,0.03); color: #D1D5DB; font-size: 0.75rem; text-decoration: none; font-weight: 600; transition: all 0.2s ease;">JSON</a>
                    <button onclick="deleteClip('{clip_id}')" style="display: inline-flex; align-items: center; justify-content: center; padding: 0.3rem 0.6rem; border-radius: 5px; border: 1px solid rgba(239, 68, 68, 0.25); background: rgba(239, 68, 68, 0.1); color: #EF4444; font-size: 0.75rem; font-weight: 600; cursor: pointer; transition: all 0.2s ease;">Delete</button>
                </div>
                '''
            else:
                html += f"<div style='color: #EF4444; font-size: 0.75rem;'>Error: {clip.get('error_msg', 'Unknown error')}</div>"
                
            html += "</div>"
            
        html += "</div></div>"
    html += "</div>"
    
    # Inject JavaScript triggers using hidden buttons to bypass Svelte reactive state blocks
    html += '''<script>
    function deleteClip(clipId) {
        const wrapper = document.getElementById("delete_trigger");
        if (!wrapper) {
            console.error("delete_trigger wrapper not found");
            return;
        }
        const el = wrapper.querySelector("textarea") || wrapper.querySelector("input");
        const btnWrapper = document.getElementById("delete_btn");
        if (!btnWrapper) {
            console.error("delete_btn wrapper not found");
            return;
        }
        const btn = btnWrapper.querySelector("button") || btnWrapper.querySelector("input") || btnWrapper;
        if (el && btn) {
            // Use native Svelte setter to force update
            const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value")?.set
                || Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")?.set;
            if (nativeSetter) {
                nativeSetter.call(el, clipId);
            } else {
                el.value = clipId;
            }
            el.dispatchEvent(new Event("input", { bubbles: true }));
            el.dispatchEvent(new Event("change", { bubbles: true }));
            
            // Allow 50ms for Svelte store compilation before triggering backend
            setTimeout(() => {
                btn.click();
            }, 50);
        } else {
            console.error("Delete elements not found inside wrappers:", {el, btn});
        }
    }
    
    function deletePhrase(phraseText) {
        const wrapper = document.getElementById("delete_phrase_trigger");
        if (!wrapper) {
            console.error("delete_phrase_trigger wrapper not found");
            return;
        }
        const el = wrapper.querySelector("textarea") || wrapper.querySelector("input");
        const btnWrapper = document.getElementById("delete_phrase_btn");
        if (!btnWrapper) {
            console.error("delete_phrase_btn wrapper not found");
            return;
        }
        const btn = btnWrapper.querySelector("button") || btnWrapper.querySelector("input") || btnWrapper;
        if (el && btn) {
            // Use native Svelte setter to force update
            const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value")?.set
                || Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")?.set;
            if (nativeSetter) {
                nativeSetter.call(el, phraseText);
            } else {
                el.value = phraseText;
            }
            el.dispatchEvent(new Event("input", { bubbles: true }));
            el.dispatchEvent(new Event("change", { bubbles: true }));
            
            // Allow 50ms for Svelte store compilation before triggering backend
            setTimeout(() => {
                btn.click();
            }, 50);
        } else {
            console.error("Delete Phrase elements not found inside wrappers:", {el, btn});
        }
    }
    </script>'''
    return html

def ui_design_voice_batch(text, language, prompt, multiplier, history):
    global cancel_generation
    cancel_generation = False
    
    if not prompt.strip():
        raise gr.Error("Error: Instruction prompt cannot be empty.")
    if not text.strip():
        raise gr.Error("Error: Please enter text to generate.")
        
    try:
        if "Online" not in check_status():
            raise gr.Error("Error: Server is offline. Please start the server first.")
        
        phrases = [line.strip() for line in text.split("\\n") if line.strip()]
        if not phrases:
            raise gr.Error("Error: Please enter at least one non-empty phrase.")
            
        total_steps = len(phrases) * int(multiplier)
        step_count = 0
        
        if history is None:
            history = []
            
        yield history, render_history_html(history), f"Starting batch generation: {len(phrases)} phrases x {multiplier} repetitions = {total_steps} clips."
        
        from qwencpp_wrapper.qwen_client import generate_tts
        import base64
        import json
        
        for i, phrase in enumerate(phrases):
            if cancel_generation:
                break
            for rep in range(1, int(multiplier) + 1):
                if cancel_generation:
                    break
                step_count += 1
                progress_msg = f"Generating Phrase {i+1}/{len(phrases)} ('{phrase[:20]}...') | Clip {rep}/{multiplier} (Step {step_count}/{total_steps})..."
                yield history, render_history_html(history), progress_msg
                
                try:
                    timestamp = int(time.time() * 1000)
                    full_prompt = f"language: {language}. {prompt}" if language else prompt
                    
                    # Generate TTS audio bytes directly in memory
                    audio_bytes = generate_tts(text=phrase, voice=None, instruction=full_prompt)
                    
                    # Convert to base64 URIs
                    b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
                    audio_url = f"data:audio/wav;base64,{b64_audio}"
                    
                    meta = {
                        "prompt": full_prompt,
                        "text": phrase
                    }
                    meta_json = json.dumps(meta, indent=2, ensure_ascii=False)
                    b64_json = base64.b64encode(meta_json.encode("utf-8")).decode("utf-8")
                    json_url = f"data:application/json;charset=utf-8;base64,{b64_json}"
                    
                    b64_txt = base64.b64encode(phrase.encode("utf-8")).decode("utf-8")
                    txt_url = f"data:text/plain;charset=utf-8;base64,{b64_txt}"
                    
                    history.append({
                        "id": f"clip_{timestamp}_{step_count}",
                        "phrase": phrase,
                        "index": rep,
                        "audio_path": audio_url,
                        "json_path": json_url,
                        "txt_path": txt_url,
                        "status": "Success"
                    })
                except Exception as e:
                    print(f"Error generating phrase '{phrase}' clip {rep}: {e}")
                    history.append({
                        "id": f"clip_failed_{step_count}",
                        "phrase": phrase,
                        "index": rep,
                        "status": "Failed",
                        "error_msg": str(e)
                    })
                    
                yield history, render_history_html(history), progress_msg
                
        if cancel_generation:
            yield history, render_history_html(history), "Generation stopped by user."
        else:
            yield history, render_history_html(history), f"Batch generation complete! Finished {total_steps} clips."
    except Exception as e:
        raise gr.Error(f"Voice design batch generation failed: {e}")

def on_delete_clip(clip_id, history):
    if not clip_id or history is None:
        return history, render_history_html(history)
    new_history = [item for item in history if item.get("id") != clip_id]
    return new_history, render_history_html(new_history)

def on_delete_phrase(phrase, history):
    if not phrase or history is None:
        return history, render_history_html(history)
    new_history = [item for item in history if item.get("phrase") != phrase]
    return new_history, render_history_html(new_history)

def on_save_clip(audio_path, voices_dir_path, history):
    return "Feature disabled. Use WAV/TXT/JSON downloads directly.", gr.skip()


def get_voice_list(voices_dir):
    if not voices_dir or not os.path.exists(voices_dir):
        return []
    return [f for f in os.listdir(voices_dir) if f.endswith(".wav")]

# Handle copy on voice template uploads
def handle_voice_upload(file_obj, voices_dir):
    if not voices_dir or not os.path.exists(voices_dir):
        return gr.Dropdown(choices=[]), "Error: Configure a valid Voices Folder first."
    if not file_obj:
        return gr.Dropdown(choices=get_voice_list(voices_dir)), "No file uploaded."
        
    try:
        filename = os.path.basename(file_obj.name)
        dest_path = os.path.join(voices_dir, filename)
        shutil.copy(file_obj.name, dest_path)
        
        voices = get_voice_list(voices_dir)
        return gr.Dropdown(choices=voices, value=filename), f"Uploaded '{filename}' into Voices folder."
    except Exception as e:
        return gr.Dropdown(choices=get_voice_list(voices_dir)), f"Upload failed: {e}"

def on_mode_change(mode):
    default_base, default_design, _, _ = scan_assets()
    return default_base if mode == "base" else default_design

def update_designed_prompt(gender, age, pitch, clarity, speed):
    traits = [
        f"gender: {gender}",
        f"age: {age}",
        f"pitch: {pitch}",
        f"clarity: {clarity}",
        f"speed: {speed}"
    ]
    return ". ".join(traits) + "."

def apply_preset(preset):
    presets = {
        "Warm Female": ("Female", "Young Adult", "Medium, warm", "High clarity", "Moderate"),
        "Deep Male": ("Male", "Middle Aged", "Low, deep", "High clarity", "Moderate, steady"),
        "Cheerful Child": ("Female", "Child", "High, bright", "High clarity", "Moderate, fast"),
        "Standard Narrator": ("Male", "Young Adult", "Medium", "High", "Moderate"),
    }
    if preset not in presets:
        return gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()
    return presets[preset]


# Persistent UI Configuration
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_config.json")

def load_ui_config():
    defaults = {
        "models_dir": os.getcwd(),
        "voices_dir": os.path.join(os.getcwd(), "voices"),
        "model_file": "",
        "tokenizer_file": "",
        "action_mode": "base",
        "gpu_backend": "Vulkan",
        "use_tts_gpu": True,
        "threads": 0,
        "debug_logs": False
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                defaults.update(saved)
        except Exception as e:
            print(f"[UI Config] Warning: Failed to load config: {e}")
    return defaults

def save_ui_config(config_dict):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=4, ensure_ascii=False)
        print(f"[UI Config] Saved config to {CONFIG_PATH}")
    except Exception as e:
        print(f"[UI Config] Warning: Failed to save config: {e}")

def get_gguf_files(folder_path):
    if not folder_path or not os.path.exists(folder_path):
        return [], []
    try:
        if not os.path.isdir(folder_path):
            return [], []
        files = os.listdir(folder_path)
        ggufs = [f for f in files if f.endswith(".gguf") and "tokenizer" not in f.lower()]
        tokenizers = [f for f in files if f.endswith(".gguf") and "tokenizer" in f.lower()]
        return sorted(ggufs), sorted(tokenizers)
    except Exception as e:
        print(f"[UI] Error scanning folder {folder_path}: {e}")
        return [], []

# Launch function
def launch_ui(auto_start_args=None):
    saved_cfg = load_ui_config()
    models_dir_val = saved_cfg["models_dir"]
    voices_dir_val = saved_cfg["voices_dir"]
    
    ggufs, tokenizers = get_gguf_files(models_dir_val)
    default_model = saved_cfg["model_file"] if saved_cfg["model_file"] in ggufs else (ggufs[0] if ggufs else "")
    default_tok = saved_cfg["tokenizer_file"] if saved_cfg["tokenizer_file"] in tokenizers else (tokenizers[0] if tokenizers else "")
    default_voices = voices_dir_val
    default_base = os.path.join(models_dir_val, default_model) if (models_dir_val and default_model) else ""
    default_design = "" 
    
    # Auto-start if requested
    if auto_start_args:
        try:
            print("[UI] Autostarting background server...")
            start_server(
                action_type=auto_start_args.get("action_type"),
                model_path=auto_start_args.get("model_path"),
                tokenizer_path=auto_start_args.get("tokenizer_path"),
                voices_dir=auto_start_args.get("voices_dir")
            )
        except Exception as e:
            print(f"[UI] Autostart failed: {e}")

    custom_css = """
    #delete_trigger, #delete_phrase_trigger, #save_trigger, #delete_btn, #delete_phrase_btn, #save_btn {
        position: absolute !important;
        width: 0px !important;
        height: 0px !important;
        opacity: 0 !important;
        pointer-events: none !important;
        overflow: hidden !important;
        border: none !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    """
    with gr.Blocks(title="QwenTTS Voice Studio", theme=gr.themes.Soft(primary_hue="teal", secondary_hue="slate"), css=custom_css) as demo:
        gr.Markdown(
            """
            # 🎙️ QwenTTS Voice Studio
            An interactive dashboard to manage Qwen3-TTS (qwentts.cpp) and generate voice cloning/design outputs.
            """
        )
        # Hidden inputs and buttons for browser JS triggers
        delete_trigger = gr.Textbox(visible=True, elem_id="delete_trigger", interactive=True)
        delete_phrase_trigger = gr.Textbox(visible=True, elem_id="delete_phrase_trigger", interactive=True)
        save_trigger = gr.Textbox(visible=True, elem_id="save_trigger", interactive=True)
        
        delete_btn = gr.Button(visible=True, elem_id="delete_btn")
        delete_phrase_btn = gr.Button(visible=True, elem_id="delete_phrase_btn")
        save_btn = gr.Button(visible=True, elem_id="save_btn")
        
        with gr.Row():
            # Server controls sidebar
            with gr.Column(scale=1):
                gr.Markdown("### ⚙️ Server Controls")
                status_text = gr.Textbox(value=check_status(), label="Server Status", interactive=False)
                
                action_mode = gr.Radio(
                    choices=[("Voice Cloning (Base)", "base"), ("Voice Design", "design")], 
                    value=auto_start_args.get("action_type", "base") if auto_start_args else "base", 
                    label="Server Mode"
                )
                
                models_dir_input = gr.Textbox(
                    value=models_dir_val,
                    label="Models Folder Path",
                    placeholder="Path to folder containing GGUF models"
                )
                
                model_dropdown = gr.Dropdown(
                    choices=ggufs,
                    value=default_model,
                    label="Select Model GGUF"
                )
                
                tokenizer_dropdown = gr.Dropdown(
                    choices=tokenizers,
                    value=default_tok,
                    label="Select Tokenizer GGUF"
                )
                
                model_path = gr.Textbox(
                    value=os.path.join(models_dir_val, default_model) if (models_dir_val and default_model) else "", 
                    label="Resolved Model Path (read-only)", 
                    interactive=False
                )
                
                tokenizer_path = gr.Textbox(
                    value=os.path.join(models_dir_val, default_tok) if (models_dir_val and default_tok) else "", 
                    label="Resolved Tokenizer Path (read-only)", 
                    interactive=False
                )
                
                voices_dir = gr.Textbox(
                    value=voices_dir_val,
                    label="Voices Folder Path (Cloning only)", 
                    placeholder="Path to reference voices"
                )
                
                with gr.Accordion("🔌 Performance & Debug Settings", open=False):
                    gpu_backend = gr.Dropdown(
                        choices=["Vulkan", "CUDA (Nvidia)", "CPU Only"],
                        value="Vulkan",
                        label="GPU Backend Mode"
                    )
                    use_tts_gpu = gr.Checkbox(
                        value=True,
                        label="Use GPU Backend Acceleration"
                    )
                    gpu_layers = gr.Number(
                        value=-1,
                        label="GPU Layers (Auto-offloaded in qwentts)",
                        precision=0,
                        visible=False
                    )
                    with gr.Row():
                        threads = gr.Number(
                            value=0,
                            label="GGML CPU Threads (0 for default)",
                            precision=0
                        )
                        tts_threads = gr.Number(
                            value=0,
                            label="TTS Threads (Ignored)",
                            precision=0,
                            visible=False
                        )
                    debug_logs = gr.Checkbox(
                        value=False,
                        label="Verbose Terminal Output (Debug)"
                    )
                
                with gr.Row():
                    btn_start = gr.Button("Start Server", variant="primary")
                    btn_stop = gr.Button("Stop Server", variant="stop")
                    
                log_box = gr.Textbox(label="Execution Status", interactive=False, placeholder="Click Start Server...")

            # Operations Panel
            with gr.Column(scale=2):
                with gr.Tabs() as tabs:
                    # Tab 1: Voice Cloning
                    with gr.Tab("🗣️ Voice Cloning", id="clone_tab"):
                        gr.Markdown("Zero-shot cloning based on a reference voice.")
                        
                        clone_text = gr.Textbox(
                            label="Text to Speak", 
                            placeholder="Type the text you want the cloned voice to speak...", 
                            lines=3
                        )
                        
                        initial_voices = get_voice_list(voices_dir_val)
                        voice_dropdown = gr.Dropdown(
                            choices=initial_voices, 
                            label="Select Voice Template (.wav)", 
                            value=initial_voices[0] if initial_voices else None
                        )
                        
                        btn_refresh = gr.Button("🔄 Refresh Voice List", size="sm")
                        
                        initial_transcript = load_voice_transcript(initial_voices[0], voices_dir_val) if initial_voices else ""
                        ref_text_box = gr.Textbox(
                            value=initial_transcript,
                            label="Voice Template Reference Text / Transcript (optional)",
                            placeholder="Enter the text that matches the reference audio file to improve voice cloning quality...",
                            lines=2
                        )
                        
                        gr.Markdown("--- or upload a new template ---")
                        voice_uploader = gr.File(
                            label="Upload Voice Template (.wav)", 
                            file_types=[".wav"],
                            file_count="single"
                        )
                        uploader_status = gr.Textbox(label="Upload Log", interactive=False)
                        
                        clone_output_name = gr.Textbox(
                            value="cloned_voice_output.wav", 
                            label="Save Output Filename"
                        )
                        
                        with gr.Row():
                            btn_clone = gr.Button("⚡ Generate Cloned Voice", variant="primary")
                            btn_stop_clone = gr.Button("⏹️ Stop Generation", variant="stop")
                        clone_audio = gr.Audio(label="Generated Audio", type="filepath")
                        clone_status = gr.Textbox(label="Status Log", interactive=False)

                    # Tab 2: Voice Design
                    with gr.Tab("🎨 Voice Design", id="design_tab"):
                        gr.Markdown("Design a voice using characteristics and descriptions.")
                        
                        preset_dropdown = gr.Dropdown(
                            choices=["Warm Female", "Deep Male", "Cheerful Child", "Standard Narrator", "Custom"], 
                            value="Warm Female", 
                            label="Voice Presets"
                        )
                        
                        with gr.Row():
                            with gr.Column():
                                gender = gr.Radio(choices=["Female", "Male"], value="Female", label="Gender")
                                age = gr.Radio(choices=["Child", "Young Adult", "Middle Aged", "Elderly"], value="Young Adult", label="Age")
                            with gr.Column():
                                pitch = gr.Textbox(value="Medium, warm", label="Pitch / Tone description")
                                clarity = gr.Textbox(value="High clarity", label="Clarity description")
                                speed = gr.Textbox(value="Moderate", label="Speech Speed description")
                                
                        prompt_box = gr.Textbox(
                            value="gender: Female. age: Young Adult. pitch: Medium, warm. clarity: High clarity. speed: Moderate.", 
                            label="Instruction Prompt (auto-generated or custom)", 
                            lines=2
                        )
                        
                        lang_design_dd = gr.Dropdown(
                            label="Language", 
                            choices=languages_list, 
                            value="English"
                        )
                        
                        design_text = gr.Textbox(
                            label="Speech Input Text (Enter one phrase per line for batch generation)", 
                            placeholder="Type the text you want the designed voice to speak...\nEach line will be generated as a separate clip.", 
                            lines=5
                        )
                        
                        with gr.Row():
                            multiplier_slider = gr.Slider(
                                minimum=1, 
                                maximum=5, 
                                value=1, 
                                step=1, 
                                label="Generation Multiplier (Runs per phrase)"
                            )
                            stream_design_cb = gr.Checkbox(
                                label="Enable Low-Latency Optimization (Ignored by QwenCPP)", 
                                value=False
                            )
                        
                        with gr.Row():
                            btn_design = gr.Button("✨ Design & Synthesize", variant="primary")
                            btn_stop_design = gr.Button("⏹️ Stop Generation", variant="stop")
                        
                        # Progress & History
                        design_progress = gr.Textbox(
                            label="Generation Progress", 
                            value="Ready.", 
                            interactive=False
                        )
                        design_history_html = gr.HTML(
                            label="Generated Audio History", 
                            value=render_history_html([])
                        )
                        
                        # State to keep history list
                        design_history_state = gr.State(value=[])

        # Wire events
        action_mode.change(on_mode_change, inputs=action_mode, outputs=model_path)
        
        voice_dropdown.change(
            load_voice_transcript,
            inputs=[voice_dropdown, voices_dir],
            outputs=ref_text_box
        )
        
        def on_start_click(action_m, m_path, t_path, v_path, gpu_b, use_g, gpu_l, th, t_th, dbg, m_dir, v_dir, m_file, t_file):
            cfg = {
                "models_dir": m_dir,
                "voices_dir": v_dir,
                "model_file": m_file,
                "tokenizer_file": t_file,
                "action_mode": action_m,
                "gpu_backend": gpu_b,
                "use_tts_gpu": use_g,
                "threads": th,
                "debug_logs": dbg
            }
            save_ui_config(cfg)
            return ui_start_server(action_m, m_path, t_path, v_path, gpu_b, use_g, gpu_l, th, t_th, dbg)

        btn_start.click(
            on_start_click, 
            inputs=[action_mode, model_path, tokenizer_path, voices_dir, 
                    gpu_backend, use_tts_gpu, gpu_layers, threads, tts_threads, debug_logs,
                    models_dir_input, voices_dir, model_dropdown, tokenizer_dropdown], 
            outputs=[log_box, status_text]
        )

        # Reactive dropdown hooks
        def on_voices_dir_change(v_dir):
            voices = get_voice_list(v_dir)
            sel_voice = voices[0] if voices else None
            return gr.Dropdown(choices=voices, value=sel_voice)
            
        voices_dir.change(
            on_voices_dir_change,
            inputs=voices_dir,
            outputs=voice_dropdown
        )

        def on_models_dir_change(m_dir):
            ggufs, tokenizers = get_gguf_files(m_dir)
            sel_model = ggufs[0] if ggufs else ""
            sel_tok = tokenizers[0] if tokenizers else ""
            m_path_val = os.path.join(m_dir, sel_model) if (m_dir and sel_model) else ""
            t_path_val = os.path.join(m_dir, sel_tok) if (m_dir and sel_tok) else ""
            return (
                gr.Dropdown(choices=ggufs, value=sel_model),
                gr.Dropdown(choices=tokenizers, value=sel_tok),
                m_path_val,
                t_path_val
            )
            
        models_dir_input.change(
            on_models_dir_change,
            inputs=models_dir_input,
            outputs=[model_dropdown, tokenizer_dropdown, model_path, tokenizer_path]
        )
        
        def on_model_select(m_dir, m_file):
            return os.path.join(m_dir, m_file) if (m_dir and m_file) else ""
            
        model_dropdown.change(
            on_model_select,
            inputs=[models_dir_input, model_dropdown],
            outputs=model_path
        )
        
        def on_tok_select(m_dir, t_file):
            return os.path.join(m_dir, t_file) if (m_dir and t_file) else ""
            
        tokenizer_dropdown.change(
            on_tok_select,
            inputs=[models_dir_input, tokenizer_dropdown],
            outputs=tokenizer_path
        )
        btn_stop.click(ui_stop_server, outputs=[log_box, status_text])
        
        btn_refresh.click(
            lambda v_dir: gr.Dropdown(choices=get_voice_list(v_dir)),
            inputs=voices_dir,
            outputs=voice_dropdown
        )
        
        voice_uploader.upload(
            handle_voice_upload,
            inputs=[voice_uploader, voices_dir],
            outputs=[voice_dropdown, uploader_status]
        )
        
        btn_clone.click(
            ui_clone_voice,
            inputs=[clone_text, voice_dropdown, clone_output_name, voices_dir, ref_text_box],
            outputs=[clone_audio, clone_status]
        )
        
        def on_trait_change(g, a, p, c, s):
            return update_designed_prompt(g, a, p, c, s)
            
        trait_inputs = [gender, age, pitch, clarity, speed]
        for t in trait_inputs:
            t.change(on_trait_change, inputs=trait_inputs, outputs=prompt_box)
            
        preset_dropdown.change(
            apply_preset, 
            inputs=preset_dropdown, 
            outputs=[gender, age, pitch, clarity, speed]
        )
        
        btn_design.click(
            ui_design_voice_batch,
            inputs=[design_text, lang_design_dd, prompt_box, multiplier_slider, design_history_state],
            outputs=[design_history_state, design_history_html, design_progress]
        )
        
        # Wiring for Stop Generation Buttons
        btn_stop_clone.click(ui_stop_generation, outputs=clone_status)
        btn_stop_design.click(ui_stop_generation, outputs=design_progress)
        
        # Wiring for browser-triggered Delete events via hidden buttons
        delete_btn.click(
            on_delete_clip, 
            inputs=[delete_trigger, design_history_state], 
            outputs=[design_history_state, design_history_html]
        )
        delete_phrase_btn.click(
            on_delete_phrase, 
            inputs=[delete_phrase_trigger, design_history_state], 
            outputs=[design_history_state, design_history_html]
        )
        
        # Wiring for browser-triggered Save events via hidden button
        save_btn.click(
            on_save_clip,
            inputs=[save_trigger, voices_dir, design_history_state],
            outputs=[design_progress, voice_dropdown]
        )
        
        # Shutdown server and clean up temp files when Gradio shuts down
        demo.unload(on_ui_unload)
        
    demo.launch(inbrowser=True, allowed_paths=[os.getcwd(), tempfile.gettempdir(), "c:/", "C:/", "d:/", "D:/"])

if __name__ == "__main__":
    launch_ui()
