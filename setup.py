from setuptools import setup, find_packages
from setuptools.command.install import install
import os
import sys

class PostInstallCommand(install):
    """Post-installation for installation mode."""
    def run(self):
        install.run(self)
        # Run post-install configuration
        try:
            from harvey.config import setup_github_token
            setup_github_token()
        except Exception as e:
            print(f"\nNote: You can configure GitHub token later by running: harvey-config")
            print(f"Error during configuration: {e}")

try:
    with open("README.md", "r", encoding="utf-16 LE") as fh:
        long_description = fh.read()
except UnicodeDecodeError:
    with open("README.md", "r", encoding="utf-16 LE", errors="ignore") as fh:
        long_description = fh.read()
except FileNotFoundError:
    long_description = "Harvey - Autonomous OSINT Reconnaissance Agent"

setup(
    name="harvey-osint",
    version="0.1.0",
    author="Amisha Lakhani & Ariel Mbingui",
    description="Harvey - Autonomous OSINT Reconnaissance Agent for LinkedIn and GitHub profiling",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/AmuuLakh/Harvey_2.0",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Topic :: Security",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    install_requires=[
        "requests>=2.28.0",
        "beautifulsoup4>=4.11.0",
        "lxml>=4.9.0",
        "pandas>=1.5.0",
        "pyyaml>=6.0",
        "rich>=13.0.0",
    ],
    entry_points={
        "console_scripts": [
            "harvey=harvey.cli:main",
            "harvey-config=harvey.config:configure_token_cli",
        ],
    },
    package_data={
        "harvey": ["data/*.json", "data/*.yaml"],
    },
    include_package_data=True,
    cmdclass={
        'install': PostInstallCommand,
    },
)
