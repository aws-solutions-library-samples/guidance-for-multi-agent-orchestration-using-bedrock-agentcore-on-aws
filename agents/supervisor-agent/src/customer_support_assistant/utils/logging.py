"""Simple logging utilities for Customer Support Assistant."""

import logging
import json
from typing import Dict, Any

logger = logging.getLogger(__name__)


def log_agent_interaction(event_type: str, data: Dict[str, Any]) -> None:
    """Log agent interactions as structured JSON."""
    try:
        log_entry = {
            "event_type": event_type,
            **data
        }
        logger.info(json.dumps(log_entry))
    except Exception as e:
        logger.error(f"Failed to log agent interaction: {e}")


def setup_logging(log_level: str = "INFO") -> None:
    """Configure basic logging."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )