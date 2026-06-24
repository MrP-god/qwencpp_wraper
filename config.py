import os

# Root directory of the package folder (koboldcpp_wrapper_server)
PACKAGE_DIR = os.path.abspath(os.path.dirname(__file__))

# KoboldCPP executable path inside the package
KOBOLD_EXE = os.path.join(PACKAGE_DIR, "koboldcpp-concedo", "koboldcpp.exe")

# Server Config
PORT = 50020
BASE_URL = f"http://127.0.0.1:{PORT}"
TTS_URL = f"{BASE_URL}/api/extra/tts"
