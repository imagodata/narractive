"""
XTTS v2 bridge script — runs inside an environment with Coqui TTS installed.

Called as::

    python xtts_bridge.py --ref_audio REF.wav --text "Hello world" \
        --output_file OUT.wav --language en [--speed 1.0] [--gpu]

This script is executed via subprocess from the Narrator class, similar
to f5_tts_bridge.py.  It loads the XTTS v2 model and generates speech
that clones the voice from the reference audio.

Requirements (in the target environment)::

    pip install TTS torch torchaudio
"""

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="XTTS v2 bridge for voice cloning TTS")
    parser.add_argument("--ref_audio", required=True, help="Path to reference voice WAV (6-15s)")
    parser.add_argument("--text", default="", help="Text to synthesize")
    parser.add_argument("--text_file", default="", help="UTF-8 file with text (overrides --text)")
    parser.add_argument("--output_file", required=True, help="Output WAV path")
    parser.add_argument("--language", default="en", help="Language code (en, fr, pt, es, de, ...)")
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed multiplier")
    parser.add_argument("--gpu", action="store_true", help="Use GPU for inference")
    args = parser.parse_args()

    # Read text from file if provided
    text = args.text
    if args.text_file and os.path.exists(args.text_file):
        with open(args.text_file, encoding="utf-8") as f:
            text = f.read().strip()

    if not text:
        print("ERROR: no text provided (use --text or --text_file)", file=sys.stderr)
        sys.exit(1)

    # Import TTS (Coqui)
    try:
        from TTS.api import TTS
    except ImportError:
        print(
            "ERROR: Coqui TTS not installed. Run: pip install TTS",
            file=sys.stderr,
        )
        sys.exit(1)

    model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
    print(f"Loading XTTS v2 model: {model_name}", flush=True)

    tts = TTS(model_name=model_name, gpu=args.gpu)

    print(f"Generating: {os.path.basename(args.output_file)} (lang={args.language})", flush=True)

    tts.tts_to_file(
        text=text,
        speaker_wav=args.ref_audio,
        language=args.language,
        file_path=args.output_file,
        speed=args.speed,
    )

    if os.path.exists(args.output_file):
        size = os.path.getsize(args.output_file)
        print(f"OK: {args.output_file} ({size} bytes)", flush=True)
    else:
        print("ERROR: output file not created", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
