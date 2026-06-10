from setuptools import setup, find_packages

setup(
    name="logwatch",
    version="1.0.0",
    description="DevOps Log Monitoring Tool",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        'tomli>=2.0.0;python_version<"3.11"',
        'python-dotenv>=1.0.0',
    ],
    entry_points={
        "console_scripts": [
            "logwatch = logwatch.cli:main",
        ],
    },
)
