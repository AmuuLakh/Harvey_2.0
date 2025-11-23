"""
Harvey - Autonomous OSINT Reconnaissance Agent
==============================================

A powerful OSINT tool for gathering public information from LinkedIn,
GitHub, and other sources.

Usage:
    $ harvey                    # Start interactive CLI
    $ harvey-config            # Configure GitHub token

API Usage:
    from harvey import HarveyAgent
    
    agent = HarveyAgent()
    messages = []
    messages, response = agent.process_message(messages, "investigate John Doe")
"""

__version__ = "0.1.0"
__author__ = "Amisha Lakhani & Ariel Mbingui"
__license__ = "MIT"

from harvey.agent import HarveyAgent
from harvey.config import setup_github_token, load_github_token

__all__ = [
    "HarveyAgent",
    "setup_github_token",
    "load_github_token",
]