import argparse
import time
import sys
import os

# Add parent directory of koboldcpp_wrapper_server to python path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from koboldcpp_wrapper_server import start_server, shutdown_server, launch_ui, config

def main():
    parser = argparse.ArgumentParser(description="KoboldCPP TTS Server & Web UI CLI")
    parser.add_argument("--ui", action="store_true", help="Launch the Gradio Web UI instead of running in console mode")
    parser.add_argument("--action", choices=["base", "design"], help="Action mode (required for console mode, optional for UI mode)")
    parser.add_argument("--model", help="Path to the model GGUF file")
    parser.add_argument("--tokenizer", help="Path to the tokenizer GGUF file")
    parser.add_argument("--voices", help="Path to the voices directory (required for base/cloning mode)")
    
    args = parser.parse_args()
    
    if args.ui:
        # Prepare auto-start settings if parameters are provided
        auto_start = None
        if args.model and args.tokenizer:
            auto_start = {
                "action_type": args.action or "base",
                "model_path": args.model,
                "tokenizer_path": args.tokenizer,
                "voices_dir": args.voices
            }
        print("[Launcher] Launching Gradio Web UI...")
        launch_ui(auto_start_args=auto_start)
    else:
        # Console Mode
        if not args.action or not args.model or not args.tokenizer:
            parser.error("Console mode requires --action, --model, and --tokenizer parameters. Run with --ui to launch the Web UI.")
            
        try:
            start_server(args.action, args.model, args.tokenizer, args.voices, debug=True)
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
