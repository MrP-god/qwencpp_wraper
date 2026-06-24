import os
import sys
import time
import subprocess
import socket
from koboldcpp_wrapper_server import config

class KoboldServerManager:
    def __init__(self, action_type, model_path, tokenizer_path, voices_dir=None, 
                 gpu_backend="vulkan", use_tts_gpu=True, threads=None, tts_threads=None, gpu_layers=-1):
        self.action_type = action_type
        # Resolve paths relative to where the script is called
        self.model_path = os.path.abspath(model_path)
        self.tokenizer_path = os.path.abspath(tokenizer_path)
        self.voices_dir = os.path.abspath(voices_dir) if voices_dir else None
        self.gpu_backend = gpu_backend
        self.use_tts_gpu = use_tts_gpu
        self.threads = threads
        self.tts_threads = tts_threads
        self.gpu_layers = gpu_layers
        self.process = None
        self.log_file = None

    def kill_existing_processes(self):
        """Kill any running koboldcpp.exe processes to free the port and GPU memory."""
        config.log("[Server] Cleaning up any existing KoboldCPP processes...")
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
            "--port", str(config.PORT)
        ]
        
        # GPU Acceleration Backend
        if self.gpu_backend == "vulkan":
            cmd.append("--usevulkan")
        elif self.gpu_backend == "cuda":
            cmd.append("--usecuda")
        else:
            cmd.append("--usecpu")
            
        # TTS GPU Offload
        if self.use_tts_gpu and self.gpu_backend != "cpu":
            cmd.append("--ttsgpu")
            
        # Thread Tuning
        if self.threads is not None:
            cmd.extend(["--threads", str(self.threads)])
        if self.tts_threads is not None:
            cmd.extend(["--ttsthreads", str(self.tts_threads)])
            
        # VRAM Offload
        if self.gpu_layers is not None:
            cmd.extend(["--gpulayers", str(self.gpu_layers)])
            
        # Load TTS models
        cmd.extend([
            "--ttsmodel", self.model_path,
            "--ttswavtokenizer", self.tokenizer_path
        ])
        
        # If action_type is "base" (cloning), we specify the voices directory
        if self.action_type == "base":
            if not self.voices_dir:
                raise ValueError("voices_dir must be provided when action_type is 'base'")
            if not os.path.exists(self.voices_dir):
                raise FileNotFoundError(f"Voices directory not found: {self.voices_dir}")
            cmd.extend(["--ttsdir", self.voices_dir])

        config.log(f"[Server] Launching KoboldCPP server...")
        config.log(f"[Server] Model: {self.model_path}")
        config.log(f"[Server] Tokenizer: {self.tokenizer_path}")
        if self.voices_dir:
            config.log(f"[Server] Voices Dir: {self.voices_dir}")
        config.log(f"[Server] Command: {' '.join(cmd)}")
        
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
        
        config.log("[Server] Waiting for KoboldCPP server to initialize (this can take up to 60 seconds)...")
        start_time = time.time()
        initialized = False
        
        while time.time() - start_time < 90:
            if self.process.poll() is not None:
                self.log_file.close()
                with open(self.log_path, "r", encoding="utf-8", errors="ignore") as lf:
                    stdout = lf.read()
                raise RuntimeError(f"KoboldCPP failed to start. Logs:\n{stdout}")

            # Check if port is open
            try:
                with socket.create_connection(("127.0.0.1", config.PORT), timeout=1):
                    config.log("[Server] Server is online!")
                    initialized = True
                    break
            except OSError:
                pass
            
            if config.DEBUG:
                sys.stdout.write(".")
                sys.stdout.flush()
            time.sleep(2)
            
        if config.DEBUG:
            print()
            
        if not initialized:
            self.terminate()
            raise TimeoutError("KoboldCPP server initialization timed out.")

    def terminate(self):
        if self.process:
            config.log("[Server] Terminating KoboldCPP server process...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                config.log("[Server] Force killing process...")
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

def start_server(action_type: str, model_path: str, tokenizer_path: str, voices_dir: str = None,
                 gpu_backend: str = "vulkan", use_tts_gpu: bool = True, threads: int = None,
                 tts_threads: int = None, gpu_layers: int = -1, debug: bool = False):
    """
    Initializes the proxy by starting the KoboldCPP server with the specified parameters.
    """
    global _active_server
    config.DEBUG = debug
    
    if _active_server is not None:
        config.log("[Server] A server is already running. Shutting it down first...")
        shutdown_server()
        
    _active_server = KoboldServerManager(
        action_type=action_type,
        model_path=model_path,
        tokenizer_path=tokenizer_path,
        voices_dir=voices_dir,
        gpu_backend=gpu_backend,
        use_tts_gpu=use_tts_gpu,
        threads=threads,
        tts_threads=tts_threads,
        gpu_layers=gpu_layers
    )
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
        config.log("[Server] Server shutdown completed.")
    else:
        config.log("[Server] No active server tracked. Running fallback process cleanup...")
        if sys.platform == "win32":
            subprocess.run("taskkill /f /im koboldcpp.exe", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
