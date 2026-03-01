"""Build system and language detection for scanned repos."""
from __future__ import annotations

from pathlib import Path


def detect_build_system(repo_path: str) -> dict:
    """Auto-detect project type from build files in the repo."""
    p = Path(repo_path)
    detected: dict = {"languages": [], "build_systems": [], "package_managers": []}

    # Python
    if (p / "pyproject.toml").exists() or (p / "setup.py").exists() or (p / "setup.cfg").exists():
        detected["languages"].append("python")
        if (p / "poetry.lock").exists():
            detected["package_managers"].append("poetry")
        elif (p / "Pipfile.lock").exists():
            detected["package_managers"].append("pipenv")
        else:
            detected["package_managers"].append("pip")
        detected["build_systems"].append("python")

    # JavaScript / TypeScript
    if (p / "package.json").exists():
        lang = "typescript" if (p / "tsconfig.json").exists() else "javascript"
        detected["languages"].append(lang)
        if (p / "pnpm-lock.yaml").exists():
            detected["package_managers"].append("pnpm")
        elif (p / "yarn.lock").exists():
            detected["package_managers"].append("yarn")
        elif (p / "bun.lockb").exists():
            detected["package_managers"].append("bun")
        else:
            detected["package_managers"].append("npm")
        detected["build_systems"].append("node")

    # Go
    if (p / "go.mod").exists():
        detected["languages"].append("go")
        detected["build_systems"].append("go")
        detected["package_managers"].append("go-modules")

    # Rust
    if (p / "Cargo.toml").exists():
        detected["languages"].append("rust")
        detected["build_systems"].append("cargo")
        detected["package_managers"].append("cargo")

    # Java / Kotlin
    if (p / "pom.xml").exists():
        detected["languages"].append("java")
        detected["build_systems"].append("maven")
        detected["package_managers"].append("maven")
    elif (p / "build.gradle").exists() or (p / "build.gradle.kts").exists():
        lang = "kotlin" if (p / "build.gradle.kts").exists() else "java"
        detected["languages"].append(lang)
        detected["build_systems"].append("gradle")
        detected["package_managers"].append("gradle")

    # PHP
    if (p / "composer.json").exists():
        detected["languages"].append("php")
        detected["build_systems"].append("composer")
        detected["package_managers"].append("composer")

    # Ruby
    if (p / "Gemfile").exists():
        detected["languages"].append("ruby")
        detected["build_systems"].append("bundler")
        detected["package_managers"].append("bundler")

    # .NET
    for ext in ("*.csproj", "*.fsproj", "*.sln"):
        if list(p.glob(ext)):
            detected["languages"].append("dotnet")
            detected["build_systems"].append("dotnet")
            detected["package_managers"].append("nuget")
            break

    # Docker
    if (p / "Dockerfile").exists() or (p / "docker-compose.yml").exists():
        detected["build_systems"].append("docker")

    return detected
