from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="agenticqa",
    version="1.0.0",
    author="Nicholas Homyk",
    author_email="nicholas@agenticqa.dev",
    description="Intelligent autonomous QA platform with learning agents, secure data store, and real-time insights",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/nhomyk/AgenticQA",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Quality Assurance",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[],
    extras_require={
        "quality": [
            "great-expectations>=0.14.0",
            "pydantic>=1.8.0",
            "requests>=2.25.0",
        ],
        "graph": [
            "neo4j>=5.15.0",
            "rich>=13.0.0",
        ],
        "dashboard": [
            "streamlit>=1.28.0",
            "plotly>=5.17.0",
            "pandas>=2.0.0",
        ],
        "rag": [
            "weaviate-client>=4.0.0",
            "qdrant-client>=1.7.0",
            "sentence-transformers>=2.0.0",
            "ragas>=0.4.0",
        ],
        "test": [
            "pytest>=6.0",
            "pytest-cov>=2.12.0",
            "neo4j>=5.15.0",
            "streamlit>=1.28.0",
            "plotly>=5.17.0",
            "pandas>=2.0.0",
            "rich>=13.0.0",
            "great-expectations>=0.14.0",
            "pydantic>=1.8.0",
            "requests>=2.25.0",
            "weaviate-client>=4.0.0",
            "qdrant-client>=1.7.0",
            "numpy>=1.21.0",
            "ragas>=0.4.0",
            "sentence-transformers>=2.0.0",
        ],
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.12.0",
            "black>=21.0",
            "flake8>=3.9",
            "mypy>=0.910",
        ],
    },
    entry_points={
        "console_scripts": [
            "agenticqa=agenticqa.cli:main",
        ],
    },
)
