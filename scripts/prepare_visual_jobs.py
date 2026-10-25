#!/usr/bin/env python3
"""Compose illustration and icon jobs with one shared drawing style; no generation call."""
from prepare_icon_jobs import main


if __name__ == '__main__':
    raise SystemExit(main(allow_illustrations=True))
