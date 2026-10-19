#!/usr/bin/env python3
"""Zero-install entry point; also available as python -m stage_agent.cli after installation."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from stage_agent.cli import main

if __name__ == '__main__':
    main()
