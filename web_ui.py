import os
import sys
import shutil
import gradio as gr
import socket
from koboldcpp_wrapper_server import start_server, shutdown_server, clone_voice, design_voice, config

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

# Launch function
def launch_ui(auto_start_args=None):
    default_base, default_design, default_tok, default_voices = scan_assets()
    
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

    with gr.Blocks(title="KoboldCPP Voice Studio", theme=gr.themes.Soft(primary_hue="teal", secondary_hue="slate")) as demo:
        gr.Markdown(
            """
            # 🎙️ KoboldCPP Voice Studio
            An interactive dashboard to manage KoboldCPP and generate voice cloning/design outputs.
            """
        )
        
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
                
                model_path = gr.Textbox(
                    value=auto_start_args.get("model_path", default_base) if auto_start_args else default_base, 
                    label="Model Path (GGUF)", 
                    placeholder="Path to model GGUF"
                )
                
                tokenizer_path = gr.Textbox(
                    value=auto_start_args.get("tokenizer_path", default_tok) if auto_start_args else default_tok, 
                    label="Tokenizer Path (GGUF)", 
                    placeholder="Path to tokenizer GGUF"
                )
                
                voices_dir = gr.Textbox(
                    value=auto_start_args.get("voices_dir", default_voices) if auto_start_args else default_voices, 
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
                        label="Use GPU for TTS (--ttsgpu)"
                    )
                    gpu_layers = gr.Number(
                        value=-1,
                        label="GPU Layers to Offload (--gpulayers, -1 for auto)",
                        precision=0
                    )
                    with gr.Row():
                        threads = gr.Number(
                            value=0,
                            label="Main Threads (0 for default)",
                            precision=0
                        )
                        tts_threads = gr.Number(
                            value=0,
                            label="TTS Threads (0 for default)",
                            precision=0
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
                        
                        initial_voices = get_voice_list(voices_dir.value or default_voices)
                        voice_dropdown = gr.Dropdown(
                            choices=initial_voices, 
                            label="Select Voice Template (.wav)", 
                            value=initial_voices[0] if initial_voices else None
                        )
                        
                        btn_refresh = gr.Button("🔄 Refresh Voice List", size="sm")
                        
                        initial_transcript = load_voice_transcript(initial_voices[0], voices_dir.value or default_voices) if initial_voices else ""
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
                        
                        btn_clone = gr.Button("⚡ Generate Cloned Voice", variant="primary")
                        clone_audio = gr.Audio(label="Generated Audio", type="filepath")
                        clone_status = gr.Textbox(label="Status Log", interactive=False)

                    # Tab 2: Voice Design
                    with gr.Tab("🎨 Voice Design", id="design_tab"):
                        gr.Markdown("Design a voice using characteristics and descriptions.")
                        
                        design_text = gr.Textbox(
                            label="Text to Speak", 
                            placeholder="Type the text you want the designed voice to speak...", 
                            lines=3
                        )
                        
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
                        
                        design_output_name = gr.Textbox(
                            value="designed_voice_output.wav", 
                            label="Save Output Filename"
                        )
                        
                        btn_design = gr.Button("⚡ Generate Designed Voice", variant="primary")
                        design_audio = gr.Audio(label="Generated Audio", type="filepath")
                        design_status = gr.Textbox(label="Status Log", interactive=False)

        # Wire events
        action_mode.change(on_mode_change, inputs=action_mode, outputs=model_path)
        
        voice_dropdown.change(
            load_voice_transcript,
            inputs=[voice_dropdown, voices_dir],
            outputs=ref_text_box
        )
        
        btn_start.click(
            ui_start_server, 
            inputs=[action_mode, model_path, tokenizer_path, voices_dir, 
                    gpu_backend, use_tts_gpu, gpu_layers, threads, tts_threads, debug_logs], 
            outputs=[log_box, status_text]
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
            ui_design_voice,
            inputs=[design_text, prompt_box, design_output_name],
            outputs=[design_audio, design_status]
        )
        
        # Shutdown server automatically when Gradio shuts down
        demo.unload(shutdown_server)
        
    demo.launch(inbrowser=True)

if __name__ == "__main__":
    launch_ui()
