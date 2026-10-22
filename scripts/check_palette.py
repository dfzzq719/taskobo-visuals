#!/usr/bin/env python3
"""Check selected opaque sRGB color pairs; no image or file mutation."""

import argparse
import json
import math
import re
import sys
from pathlib import Path


def normalize_color(value):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError("Color must be an opaque #RRGGBB sRGB value.")
    return value.upper()


def luminance(color):
    color = normalize_color(color)
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def threshold(value):
    if isinstance(value, bool):
        raise ValueError("Minimum contrast must be a number from 1 to 21.")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Minimum contrast must be a number from 1 to 21.") from error
    if not math.isfinite(number) or not 1 <= number <= 21:
        raise ValueError("Minimum contrast must be a number from 1 to 21.")
    return number


def evaluate_pair(name, foreground, background, minimum):
    foreground, background = normalize_color(foreground), normalize_color(background)
    minimum = threshold(minimum)
    first, second = luminance(foreground), luminance(background)
    ratio = (max(first, second) + 0.05) / (min(first, second) + 0.05)
    return {
        "name": name,
        "foreground": foreground,
        "background": background,
        "ratio": ratio,
        "minimum": minimum,
        "passes": ratio >= minimum,
    }


def evaluate_palette(payload):
    if not isinstance(payload, dict):
        raise ValueError("Palette must be an object with colors and checks.")
    colors, checks = payload.get("colors"), payload.get("checks")
    if not isinstance(colors, dict) or not colors:
        raise ValueError("colors must be a nonempty object of named #RRGGBB values.")
    normalized = {name: normalize_color(value) for name, value in colors.items()}
    if not isinstance(checks, list) or not checks:
        raise ValueError("checks must be a nonempty list of foreground/background role pairs.")
    results = []
    for index, check in enumerate(checks, 1):
        if not isinstance(check, dict):
            raise ValueError(f"Check {index} must be an object.")
        foreground, background = check.get("foreground"), check.get("background")
        if not isinstance(foreground, str) or foreground not in normalized:
            raise ValueError(f"Check {index} refers to an unknown foreground role.")
        if not isinstance(background, str) or background not in normalized:
            raise ValueError(f"Check {index} refers to an unknown background role.")
        if "minimum" not in check:
            raise ValueError(f"Check {index} requires an explicit minimum.")
        name = check.get("name", f"check {index}")
        if not isinstance(name, str):
            raise ValueError(f"Check {index} name must be a string.")
        results.append(evaluate_pair(name, normalized[foreground], normalized[background], check["minimum"]))
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--palette", type=Path, help="JSON containing colors and explicit role-pair checks")
    parser.add_argument("--foreground", help="Opaque sRGB #RRGGBB")
    parser.add_argument("--background", help="Opaque sRGB #RRGGBB")
    parser.add_argument("--minimum", default=None, type=float, help="Contrast threshold; single-pair default 4.5")
    args = parser.parse_args(argv)
    try:
        if args.palette:
            if args.foreground is not None or args.background is not None or args.minimum is not None:
                raise ValueError("Use either --palette or a single foreground/background pair.")
            results = evaluate_palette(json.loads(args.palette.read_text(encoding="utf-8")))
        else:
            if args.foreground is None or args.background is None:
                raise ValueError("Provide --palette or both --foreground and --background.")
            results = [evaluate_pair("single pair", args.foreground, args.background, 4.5 if args.minimum is None else args.minimum)]
        passed = all(result["passes"] for result in results)
        print(json.dumps({"all_pass": passed, "checks": results, "scope": "selected opaque sRGB pairs only"}, ensure_ascii=False, indent=2))
        return 0 if passed else 1
    except (ValueError, OSError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
