#!/usr/bin/env python3
"""
Setup script for ThinkingSDK Client

Install locally with:
    pip install -e .

Or build and install:
    python setup.py sdist bdist_wheel
    pip install dist/thinkingsdk-*.whl
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="thinkingsdk",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="AI-powered runtime insight client for Python applications",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/thinkingsdk",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Debuggers",
        "Topic :: System :: Monitoring",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.31.0",
        "urllib3>=2.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "thinking-sdk=thinkingsdk.cli:main",
        ],
    },
    package_data={
        "thinkingsdk": ["*.json", "*.yaml", "*.yml"],
    },
    include_package_data=True,
    zip_safe=False,
)