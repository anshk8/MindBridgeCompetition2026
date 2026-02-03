"""
Setup configuration for Carleton Competition SQL Query Agent
"""

from setuptools import setup, find_packages

setup(
    name="carleton-sql-agent",
    version="0.1.0",
    description="Multi-agent system for SQL query generation",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "ollama>=0.4.7",
        "duckdb>=1.1.3",
        "sqlalchemy>=2.0.36",
    ],
)
