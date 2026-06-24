import os
import sys
import time
import subprocess
import socket
from koboldcpp_wrapper_server import config

class KoboldServerManager:
    def __init__(self, action_type, model_path, tokenizer_path, voices_dir=None):
        self.action_type = action_type
        # Resolve paths relative to where the script is called
        self.model_path = os.path.abspath(model_path)
        self.tokenizer_path = os.path.abspath(tokenizer_path)
        self.voices_dir = os.path.abspath(voices_dir) if voices_dir else None
        self.process = None
        self.log_file = None

    def kill_existing_processes(self):
        """Kill any running koboldcpp.exe processes to free the port and GPU memory."""
        print("[Server] Cleaning up any existing KoboldCPP processes...")
        if sys.platform == "win32":
            subprocess.run("taskkill /f /im koboldcpp.exe", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
            time.sleep(2)

    def start(self):
        self.kill_existing_processes()
        
        # Verify paths exist
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        if not os.path.exists(self.tokenizer_path):
            raise FileNotFoundError(f"Tokenizer not found: {self.tokenizer_path}")
            
        # Setup environment to use package temp directory
        temp_dir = os.path.join(config.PACKAGE_DIR, "tmp_temp")
        os.makedirs(temp_dir, exist_ok=True)
        os.environ["TEMP"] = temp_dir
        os.environ["TMP"] = temp_dir

        # Build startup command
        cmd = [
            config.KOBOLD_EXE,
            "--usevulkan",
            "--ttsgpu",
            "--ttsmodel", self.model_path,
            "--ttswavtokenizer", self.tokenizer_path,
            "--port", str(config.PORT)
        ]
        
        # If action_type is "base" (cloning), we specify the voices directory
        if self.action_type == "base":
            if not self.voices_dir:
                raise ValueError("voices_dir must be provided when action_type is 'base'")
            if not os.path.exists(self.voices_dir):
                raise FileNotFoundError(f"Voices directory not found: {self.voices_dir}")
            cmd.extend(["--ttsdir", self.voices_dir])

        print(f"[Server] Launching KoboldCPP server...")
        print(f"[Server] Model: {self.model_path}")
        print(f"[Server] Tokenizer: {self.tokenizer_path}")
        if self.voices_dir:
            print(f"[Server] Voices Dir: {self.voices_dir}")
        print(f"[Server] Command: {' '.join(cmd)}")
        
        # Write server logs to the current working directory (consumer's folder)
        log_dir = os.getcwd()
        self.log_path = os.path.join(log_dir, "kobold_server.log")
        self.log_file = open(self.log_path, "w", encoding="utf-8")
        
        self.process = subprocess.Popen(
            cmd,
            cwd=config.PACKAGE_DIR,
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
            env=os.environ
        )
        
        print("[Server] Waiting for KoboldCPP server to initialize (this can take up to 60 seconds)...")
        start_time = time.time()
        initialized = False
        
        while time.time() - start_time < 90:
            if self.process.poll() is not None:
                self.log_file.close()
                with open(self.log_path, "r", encoding="utf-8", errors="ignore") as lf:
                    stdout = lf.read()
                print("[Server] Server process exited unexpectedly:")
                print(stdout)
                raise RuntimeError("KoboldCPP failed to start.")

            # Check if port is open
            try:
                with socket.create_connection(("127.0.0.1", config.PORT), timeout=1):
                    print("[Server] Server is online!")
                    initialized = True
                    break
            except OSError:
                pass
            
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(2)
            
        print()
        if not initialized:
            self.terminate()
            raise TimeoutError("KoboldCPP server initialization timed out.")

    def terminate(self):
        if self.process:
            print("[Server] Terminating KoboldCPP server process...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("[Server] Force killing process...")
                self.process.kill()
            self.process = None
        if self.log_file:
            try:
                self.log_file.close()
            except Exception:
                pass
        self.kill_existing_processes()


# Global tracker for the active server instance
_active_server = None

def start_server(action_type: str, model_path: str, tokenizer_path: str, voices_dir: str = None):
    """
    Initializes the proxy by starting the KoboldCPP server with the specified parameters.
    action_type can be:
      - 'base': starts cloning model (requires voices_dir)
      - 'design': starts voice designing model
    """
    global _active_server
    if _active_server is not None:
        print("[Server] A server is already running. Shutting it down first...")
        shutdown_server()
        
    _active_server = KoboldServerManager(action_type, model_path, tokenizer_path, voices_dir)
    _active_server.start()
    return _active_server

def shutdown_server():
    """
    Shuts down the active KoboldCPP server and cleans up processes.
    """
    global _active_server
    if _active_server is not None:
        _active_server.terminate()
        _active_server = None
        print("[Server] Server shutdown completed.")
    else:
        print("[Server] No active server tracked. Running fallback process cleanup...")
        if sys.platform == "win32":
            subprocess.run("taskkill /f /im koboldcpp.exe", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
