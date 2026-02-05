from setuptools import setup, find_packages

setup(
    name="rcsclient",
    version="0.1.0",
    description="Command-line client for sending RCS messages",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.28",
        "google-auth>=2.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "responses>=0.22",
        ],
    },
    entry_points={
        "console_scripts": [
            "rcsclient=rcsclient.cli:cli_main",
        ],
    },
)
