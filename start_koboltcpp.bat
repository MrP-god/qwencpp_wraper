@echo off
cd /d "%~dp0"
echo Launching Qwen3-TTS Base Model on AMD iGPU via Vulkan (Voice Cloning)...
"koboldcpp-concedo\koboldcpp.exe" --usevulkan --ttsgpu --ttsmodel "Qwen3-TTS-12Hz-1.7B-Base-Q8_0.gguf" --ttswavtokenizer "qwen3-tts-tokenizer-q8_0.gguf" --ttsdir "Voices" --port 50020
pause


