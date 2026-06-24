import argparse
import time
import sys
import os

# Add parent directory of koboldcpp_wrapper_server to python path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from koboldcpp_wrapper_server import start_server, shutdown_server, config

def main():
    parser = argparse.ArgumentParser(description="KoboldCPP TTS Server CLI")
    parser.add_argument("--action", choices=["base", "design"], required=True, help="Action mode (base = voice cloning, design = voice designing)")
    parser.add_argument("--model", required=True, help="Path to the model GGUF file")
    parser.add_argument("--tokenizer", required=True, help="Path to the tokenizer GGUF file")
    parser.add_argument("--voices", help="Path to the voices directory (required for base action)")
    
    args = parser.parse_args()
    
    try:
        start_server(args.action, args.model, args.tokenizer, args.voices)
        print("\n" + "="*60)
        print(f"KoboldCPP Server is running with '{args.action}' action.")
        print(f"Web UI: http://127.0.0.1:{config.PORT}")
        print("Press Ctrl+C to stop the server.")
        print("="*60 + "\n")
        
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        shutdown_server()

if __name__ == "__main__":
    main()
