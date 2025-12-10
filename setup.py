"""Setup script for voice AI bot."""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="voice-ai-bot",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Production-ready voice AI bot with Twilio, Pipecat, and Sarvam AI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/voice-ai-bot",
    packages=find_packages(exclude=["tests", "docs"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Communications :: Telephony",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.7.0",
            "flake8>=6.1.0",
            "mypy>=1.5.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "voice-bot=app.main:main",
        ],
    },
)
