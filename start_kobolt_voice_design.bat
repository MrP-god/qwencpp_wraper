@echo off
cd /d "%~dp0"
echo Launching Qwen3-TTS on AMD iGPU via Vulkan... (voice Design)
"koboldcpp-concedo\koboldcpp.exe" --usevulkan --ttsgpu --ttsmodel "Qwen3-TTS-12Hz-1.7B-VoiceDesign-Q8_0.gguf" --ttswavtokenizer "qwen3-tts-tokenizer-q8_0.gguf" --port 50020
pause