#!/usr/bin/env python3
"""ABA Observer — AI-powered behavioral data collection from video sessions.

Analyzes video+audio of ABA therapy sessions using multimodal AI models
to produce structured ABC (Antecedent-Behavior-Consequence) data.

Usage:
    python main.py analyze --video session.mp4
    python main.py analyze --video session.mp4 --provider qwen
    python main.py analyze --video session.mp4 --config configs/example_client.json
    python main.py analyze --video session.mp4 --provider gemini --fallback qwen
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def load_client_config(config_path: str | None) -> dict | None:
    """Load client behavior target configuration."""
    if not config_path:
        return None
    path = Path(config_path)
    if not path.exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    with open(path) as f:
        config = json.load(f)
    print(f"Loaded client config: {config.get('client_id', 'unknown')} "
          f"({len(config.get('behavior_targets', []))} targets, "
          f"{len(config.get('replacement_behaviors', []))} replacements, "
          f"{len(config.get('skill_acquisition_targets', []))} skills)")
    return config


def get_provider(name: str):
    """Get a provider instance by name."""
    if name == "gemini":
        from providers.gemini import GeminiProvider
        return GeminiProvider()
    elif name == "qwen":
        from providers.qwen import QwenProvider
        return QwenProvider()
    else:
        print(f"Error: Unknown provider '{name}'. Choose 'gemini' or 'qwen'.")
        sys.exit(1)


def save_output(data: dict, video_path: Path, output_dir: str = "output") -> Path:
    """Save analysis results to JSON and print summary."""
    out_dir = Path(output_dir)
    out_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = video_path.stem
    out_path = out_dir / f"{stem}_{timestamp}.json"

    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    return out_path


def print_summary(data: dict):
    """Print a human-readable summary of the observation data."""
    print("\n" + "=" * 60)
    print("  ABA OBSERVATION SUMMARY")
    print("=" * 60)

    # Session info
    session = data.get("session_summary", {})
    if session:
        print(f"\n  Setting: {session.get('setting', 'N/A')}")
        people = session.get("people_present", [])
        if people:
            print(f"  People:  {', '.join(people)}")
        duration = session.get("duration_seconds")
        if duration:
            mins = int(duration) // 60
            secs = int(duration) % 60
            print(f"  Duration: {mins}m {secs}s")
        notes = session.get("overall_notes")
        if notes:
            print(f"  Notes: {notes}")

    # ABC chains
    chains = data.get("abc_chains", [])
    if chains:
        print(f"\n  ABC Chains Identified: {len(chains)}")
        print("  " + "-" * 56)
        for chain in chains[:10]:  # Show first 10
            a = chain.get("antecedent", {})
            b = chain.get("behavior", {})
            c = chain.get("consequence", {})
            print(f"  [{a.get('timestamp', '??:??')}] A: {a.get('description', 'N/A')}")
            print(f"  [{b.get('timestamp', '??:??')}] B: {b.get('description', 'N/A')} ({b.get('target', '')})")
            print(f"  [{c.get('timestamp', '??:??')}] C: {c.get('description', 'N/A')}")
            print("  " + "-" * 56)

    # Frequency summary
    freq = data.get("frequency_summary", {})
    if freq:
        print("\n  Behavior Frequencies:")
        for behavior, info in freq.items():
            if isinstance(info, dict):
                count = info.get("count", 0)
            else:
                count = info
            print(f"    {behavior}: {count}")

    # Prompt levels
    prompts = data.get("prompt_level_distribution", {})
    if prompts and any(v for v in prompts.values() if v):
        print("\n  Prompt Level Distribution:")
        for level, count in prompts.items():
            if count:
                bar = "█" * count
                print(f"    {level:20s} {count:3d} {bar}")

    # Event count
    events = data.get("events", [])
    if events:
        print(f"\n  Total Events Logged: {len(events)}")

    print("\n" + "=" * 60)


def cmd_analyze(args):
    """Run video analysis."""
    video_path = Path(args.video)
    if not video_path.exists():
        print(f"Error: Video file not found: {args.video}")
        sys.exit(1)

    # Load client config
    client_config = load_client_config(args.config)

    # Build prompt
    from prompts.aba_system import build_system_prompt
    system_prompt = build_system_prompt(client_config)

    # Try primary provider
    provider = get_provider(args.provider)
    fallback = get_provider(args.fallback) if args.fallback else None

    if not provider.is_available():
        if fallback and fallback.is_available():
            print(f"[main] Primary provider '{args.provider}' unavailable. Falling back to '{args.fallback}'.")
            provider = fallback
            fallback = None
        else:
            print(f"[main] Provider '{args.provider}' is not available and no fallback configured.")
            sys.exit(1)

    # Run analysis
    print(f"\n[main] Analyzing: {video_path.name}")
    print(f"[main] Provider: {provider.name}")
    print(f"[main] Client config: {args.config or 'none (generic observation)'}")
    print()

    try:
        data = provider.analyze_video(video_path, system_prompt)
    except Exception as e:
        print(f"\n[main] Error with {provider.name}: {e}")
        if fallback and fallback.is_available():
            print(f"[main] Trying fallback provider: {fallback.name}")
            data = fallback.analyze_video(video_path, system_prompt)
        else:
            raise

    # Check for parse errors
    if data.get("parse_error"):
        print("\n[main] Warning: Model returned unstructured output.")
        print("[main] Raw response saved to output file for review.")

    # Save and display
    out_path = save_output(data, video_path)
    print(f"\n[main] Full results saved to: {out_path}")

    print_summary(data)

    return data


def cmd_providers(args):
    """List available providers and their status."""
    print("\nAvailable Providers:")
    print("-" * 50)

    for name in ["gemini", "qwen"]:
        provider = get_provider(name)
        status = "READY" if provider.is_available() else "NOT AVAILABLE"
        icon = "✓" if status == "READY" else "✗"
        print(f"  {icon} {name:10s} — {status}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="ABA Observer — AI-powered behavioral data collection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py analyze --video session.mp4
  python main.py analyze --video session.mp4 --provider qwen
  python main.py analyze --video session.mp4 --config configs/example_client.json
  python main.py analyze --video session.mp4 --provider gemini --fallback qwen
  python main.py providers
        """,
    )
    subparsers = parser.add_subparsers(dest="command")

    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a video session")
    analyze_parser.add_argument("--video", "-v", required=True, help="Path to video file")
    analyze_parser.add_argument("--provider", "-p", default="gemini", choices=["gemini", "qwen"],
                                help="AI provider to use (default: gemini)")
    analyze_parser.add_argument("--fallback", "-f", choices=["gemini", "qwen"],
                                help="Fallback provider if primary fails")
    analyze_parser.add_argument("--config", "-c", help="Path to client behavior config JSON")
    analyze_parser.add_argument("--output", "-o", default="output", help="Output directory (default: output)")
    analyze_parser.set_defaults(func=cmd_analyze)

    # providers command
    providers_parser = subparsers.add_parser("providers", help="List available providers")
    providers_parser.set_defaults(func=cmd_providers)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
