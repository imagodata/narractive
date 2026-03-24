"""
Kokoro TTS bridge script — lightweight, high-quality local TTS.

Called as::

    python kokoro_bridge.py --text "Hello world" --output_file OUT.wav \
        --lang en [--voice af_heart] [--speed 1.0]

Or with text from a file (avoids CLI encoding issues)::

    python kokoro_bridge.py --text_file input.txt --output_file OUT.wav \
        --lang fr --voice ff_siwis

Voice mixing (blend multiple voices with weights)::

    python kokoro_bridge.py --text_file input.txt --output_file OUT.wav \
        --lang fr --voices '[{"voice":"ff_siwis","weight":0.7},{"voice":"ff_alpha","weight":0.3}]'

Custom voice pack::

    python kokoro_bridge.py --text_file input.txt --output_file OUT.wav \
        --lang fr --voice_file /path/to/my_voice.pt

Kokoro TTS is a StyleTTS2-based model (~82M params) that runs extremely
fast (25-50x real-time on GPU, 5x on CPU) with high-quality output.
No voice cloning — uses built-in voices per language.

Requirements::

    pip install kokoro soundfile

For GPU acceleration, also install torch with CUDA support.

Supported languages and default voices:
    en (American English) : af_heart
    en-gb (British English) : bf_emma
    fr (French) : ff_siwis
    pt-br (Portuguese BR) : pf_dora
    es (Spanish) : ef_dora
    it (Italian) : if_sara
    ja (Japanese) : jf_alpha
    zh (Mandarin) : zf_xiaobei
    hi (Hindi) : hf_alpha
    ko (Korean) : kf_alpha
"""

import argparse
import json
import os
import sys


# Language code mapping: user-friendly -> Kokoro internal code
LANG_MAP = {
    "en": "a",       # American English
    "en-us": "a",
    "en-gb": "b",    # British English
    "fr": "f",       # French
    "pt": "p",       # Brazilian Portuguese
    "pt-br": "p",
    "es": "e",       # Spanish
    "it": "i",       # Italian
    "ja": "j",       # Japanese
    "zh": "z",       # Mandarin Chinese
    "hi": "h",       # Hindi
    "ko": "k",       # Korean
}

# Default voice per Kokoro language code
DEFAULT_VOICES = {
    "a": "af_heart",      # American English female
    "b": "bf_emma",       # British English female
    "f": "ff_siwis",      # French female
    "p": "pf_dora",       # Portuguese BR female
    "e": "ef_dora",       # Spanish female
    "i": "if_sara",       # Italian female
    "j": "jf_alpha",      # Japanese female
    "z": "zf_xiaobei",    # Mandarin female
    "h": "hf_alpha",      # Hindi female
    "k": "kf_alpha",      # Korean female
}


def main():
    parser = argparse.ArgumentParser(description="Kokoro TTS bridge for narration generation")
    parser.add_argument("--text", default="", help="Text to synthesize")
    parser.add_argument("--text_file", default="", help="UTF-8 file with text (overrides --text)")
    parser.add_argument("--output_file", required=True, help="Output WAV path")
    parser.add_argument("--lang", default="en", help="Language code (en, fr, pt, pt-br, es, ...)")
    parser.add_argument("--voice", default="", help="Voice name (e.g. af_heart, ff_siwis)")
    parser.add_argument(
        "--voices",
        default="",
        help='JSON list of voice mixing entries: [{"voice":"ff_siwis","weight":0.7},...]',
    )
    parser.add_argument(
        "--voice_file",
        default="",
        help="Path to a custom .pt voice pack file",
    )
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed multiplier")
    args = parser.parse_args()

    # Read text
    text = args.text
    if args.text_file and os.path.exists(args.text_file):
        with open(args.text_file, encoding="utf-8") as f:
            text = f.read().strip()

    if not text:
        print("ERROR: no text provided (use --text or --text_file)", file=sys.stderr)
        sys.exit(1)

    # Resolve language code
    lang_key = args.lang.lower().strip()
    kokoro_lang = LANG_MAP.get(lang_key)
    if kokoro_lang is None:
        # Try using the raw value as a Kokoro code (single char)
        if len(lang_key) == 1 and lang_key in DEFAULT_VOICES:
            kokoro_lang = lang_key
        else:
            print(
                f"ERROR: unsupported language '{args.lang}'. "
                f"Supported: {', '.join(sorted(LANG_MAP.keys()))}",
                file=sys.stderr,
            )
            sys.exit(1)

    # Import Kokoro
    try:
        from kokoro import KPipeline
    except ImportError:
        print(
            "ERROR: kokoro not installed. Run: pip install kokoro soundfile",
            file=sys.stderr,
        )
        sys.exit(1)

    import numpy as np
    import soundfile as sf

    pipeline = KPipeline(lang_code=kokoro_lang)

    # Resolve effective voice — priority: voice_file > voices (mixing) > voice > default
    effective_voice: object  # str or numpy array (mixed voice tensor)

    if args.voice_file:
        # Custom voice pack (.pt file)
        if not os.path.exists(args.voice_file):
            print(f"ERROR: voice_file not found: {args.voice_file}", file=sys.stderr)
            sys.exit(1)
        try:
            import torch  # type: ignore
            effective_voice = torch.load(args.voice_file, map_location="cpu", weights_only=True)
            print(f"Loading Kokoro TTS (lang={kokoro_lang}, voice_file={os.path.basename(args.voice_file)})", flush=True)
        except Exception as exc:
            print(f"ERROR: failed to load voice_file: {exc}", file=sys.stderr)
            sys.exit(1)
    elif args.voices:
        # Voice mixing: blend multiple voices with weights
        try:
            voices_list = json.loads(args.voices)
        except json.JSONDecodeError as exc:
            print(f"ERROR: invalid --voices JSON: {exc}", file=sys.stderr)
            sys.exit(1)

        if not isinstance(voices_list, list) or len(voices_list) < 2:
            print("ERROR: --voices must be a JSON list with at least 2 entries", file=sys.stderr)
            sys.exit(1)

        try:
            voice_names = [entry["voice"] for entry in voices_list]
            weights = [float(entry.get("weight", 1.0)) for entry in voices_list]
            total_weight = sum(weights)
            weights = [w / total_weight for w in weights]  # normalize

            # Build mixed voice tensor using pipeline.voices dict
            import torch  # type: ignore
            voice_tensors = []
            for vname in voice_names:
                if vname not in pipeline.voices:
                    print(f"ERROR: voice '{vname}' not found in Kokoro pipeline", file=sys.stderr)
                    sys.exit(1)
                voice_tensors.append(pipeline.voices[vname])

            effective_voice = sum(w * v for w, v in zip(weights, voice_tensors))
            print(
                f"Loading Kokoro TTS (lang={kokoro_lang}, mixed voices={voice_names}, weights={weights})",
                flush=True,
            )
        except (KeyError, TypeError) as exc:
            print(f"ERROR: voice mixing failed: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        # Simple single voice (original behavior)
        effective_voice = args.voice if args.voice else DEFAULT_VOICES.get(kokoro_lang, "af_heart")
        print(f"Loading Kokoro TTS (lang={kokoro_lang}, voice={effective_voice})", flush=True)

    print(f"Generating: {os.path.basename(args.output_file)}", flush=True)

    # Generate audio chunks
    audio_chunks = []
    for _graphemes, _phonemes, audio in pipeline(text, voice=effective_voice, speed=args.speed):
        if audio is not None:
            audio_chunks.append(audio)

    if not audio_chunks:
        print("ERROR: Kokoro produced no audio output", file=sys.stderr)
        sys.exit(1)

    # Concatenate all chunks and save as WAV (24 kHz)
    full_audio = np.concatenate(audio_chunks)
    sf.write(args.output_file, full_audio, 24000)

    if os.path.exists(args.output_file):
        size = os.path.getsize(args.output_file)
        duration = len(full_audio) / 24000
        print(f"OK: {args.output_file} ({size} bytes, {duration:.1f}s)", flush=True)
    else:
        print("ERROR: output file not created", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
