# KoboldCPP Server Wrapper

A self-contained, lightweight Python wrapper package for [KoboldCPP](https://github.com/LostRuins/koboldcpp). This package provides clean, programmatic APIs to manage the KoboldCPP server lifecycle and generate TTS audio using zero-shot voice cloning and voice design.

---

## Features
- **Lifecycle Management**: Programmatically start and stop the KoboldCPP Vulkan GPU-accelerated server.
- **Detached Asset Storage**: Keep GGUF models, tokenizers, and reference voice files fully inside your consumer projects—the package is decoupled.
- **Voice Cloning**: Generate audio by referencing a `.wav` file template.
- **Voice Design**: Generate designed voices by specifying audio traits (e.g., gender, age, clarity, speed).
- **Web UI Access**: Easily launch the server persistently to access the built-in KoboldCPP Web UI in your browser.

---

## Directory Structure
To use the wrapper, copy the `koboldcpp_wrapper_server/` directory into your project:

> [!NOTE]
> The `koboldcpp-concedo` folder containing `koboldcpp.exe` is excluded from this repository due to GitHub's file size limits. To use this package, you must download the compiled `koboldcpp.exe` binary from the official [KoboldCPP Releases Page](https://github.com/LostRuins/koboldcpp/releases) and place it inside a directory named `koboldcpp-concedo/` at the root of the package.

```text
your_project/
├── koboldcpp_wrapper_server/   # This package folder (copied inside your project)
│   ├── koboldcpp-concedo/      # Add the downloaded koboldcpp.exe here
├── Voices/                     # Your reference voice templates (.wav files)
├── your_base_model.gguf        # GGUF Base Model
├── your_design_model.gguf      # GGUF VoiceDesign Model
├── your_tokenizer.gguf         # GGUF Tokenizer
└── main.py                     # Your consumer script
```

---

## Quick Start Example

Here is how you can use the wrapper package in your python consumer script:

```python
import os
from koboldcpp_wrapper_server import start_server, shutdown_server, clone_voice, design_voice

# 1. Resolve local paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_BASE = os.path.join(BASE_DIR, "Qwen3-TTS-12Hz-1.7B-Base-q8_0.gguf")
MODEL_DESIGN = os.path.join(BASE_DIR, "Qwen3-TTS-12Hz-1.7B-VoiceDesign-Q8_0.gguf")
TOKENIZER = os.path.join(BASE_DIR, "qwen3-tts-tokenizer-q8_0.gguf")
VOICES_DIR = os.path.join(BASE_DIR, "Voices")

# Outputs
OUTPUT_CLONE = os.path.join(BASE_DIR, "output_cloned.wav")
OUTPUT_DESIGN = os.path.join(BASE_DIR, "output_designed.wav")

try:
    # 2. Start the cloning server
    print("Starting voice cloning server...")
    start_server(
        action_type="base",
        model_path=MODEL_BASE,
        tokenizer_path=TOKENIZER,
        voices_dir=VOICES_DIR
    )
    
    # 3. Generate cloned voice
    clone_voice(
        text="Hello, this is a voice cloning test using the alice reference template.",
        voice_ref="alice.wav",
        output_path=OUTPUT_CLONE
    )
finally:
    # Always shutdown when finished
    shutdown_server()
```

---

## License & Credits

- **Credits**: This package wraps **KoboldCPP** developed by [LostRuins](https://github.com/LostRuins/koboldcpp).
- **License**: KoboldCPP is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. This wrapper and its bundled binaries are distributed under the same terms. Please see the [LICENSE](LICENSE) file for more information.
