#!/usr/bin/env python
"""
Script to manually trigger pool check for testing.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tasks.pool_dispatcher import check_pool
from utils.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main():
    """Manually trigger pool check."""
    logger.info("Manually triggering pool check...")
    
    try:
        check_pool()
        logger.info("Pool check completed!")
    except Exception as e:
        logger.error(f"Error during pool check: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
