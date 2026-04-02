"""
SuperAI V11 — backend/skills/skill_loader.py

Loads and parses SKILL.md files (YAML frontmatter + markdown body).
Extracts: name, description, trigger keywords, activation conditions,
and the full skill prompt content.

Inspired by Superpowers' composable skills architecture.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger


@dataclass
class Skill:
    name: str
    description: str
    trigger_keywords: List[str] = field(default_factory=list)
    category: str = "general"
    content: str = ""                 # full markdown body
    auto_activate: bool = True
    priority: int = 0                 # higher = preferred
    source_path: str = ""

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "trigger_keywords": self.trigger_keywords,
            "category": self.category,
            "auto_activate": self.auto_activate,
            "priority": self.priority,
        }


class SkillLoader:
    """Parses SKILL.md files from a directory."""

    def load_directory(self, directory: str) -> List[Skill]:
        """Load all SKILL.md files from a directory tree."""
        skills: List[Skill] = []
        base = Path(directory)
        if not base.exists():
            logger.warning("Skills directory not found", path=directory)
            return skills

        for skill_file in base.rglob("SKILL.md"):
            try:
                skill = self.load_file(str(skill_file))
                if skill:
                    skills.append(skill)
            except Exception as e:
                logger.warning("Failed to load skill", file=str(skill_file), error=str(e))

        logger.info(f"Loaded {len(skills)} skills from {directory}")
        return skills

    def load_file(self, filepath: str) -> Optional[Skill]:
        """Parse a single SKILL.md file."""
        path = Path(filepath)
        if not path.exists():
            return None

        text = path.read_text(encoding="utf-8", errors="ignore")
        frontmatter, body = self._split_frontmatter(text)

        name = frontmatter.get("name", path.parent.name)
        description = frontmatter.get("description", "")
        keywords = frontmatter.get("triggers", frontmatter.get("keywords", []))
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",")]
        category = frontmatter.get("category", "general")
        auto = frontmatter.get("auto_activate", True)
        priority = int(frontmatter.get("priority", 0))

        return Skill(
            name=name,
            description=description,
            trigger_keywords=keywords,
            category=category,
            content=body.strip(),
            auto_activate=auto if isinstance(auto, bool) else str(auto).lower() == "true",
            priority=priority,
            source_path=str(path),
        )

    def create_skill_file(
        self, directory: str, name: str, description: str,
        triggers: List[str], content: str, category: str = "custom",
    ) -> str:
        """Create a new SKILL.md file."""
        skill_dir = Path(directory) / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_path = skill_dir / "SKILL.md"

        triggers_yaml = ", ".join(triggers)
        file_content = (
            f"---\n"
            f"name: {name}\n"
            f"description: {description}\n"
            f"triggers: [{triggers_yaml}]\n"
            f"category: {category}\n"
            f"auto_activate: true\n"
            f"priority: 0\n"
            f"---\n\n"
            f"{content}\n"
        )
        skill_path.write_text(file_content, encoding="utf-8")
        return str(skill_path)

    # ── Frontmatter parser ────────────────────────────────────────

    @staticmethod
    def _split_frontmatter(text: str) -> tuple[Dict, str]:
        """Split YAML frontmatter from markdown body."""
        frontmatter: Dict = {}

        match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", text, re.DOTALL)
        if not match:
            return frontmatter, text

        yaml_block = match.group(1)
        body = match.group(2)

        # Simple YAML parser (avoids PyYAML dependency in this module)
        for line in yaml_block.splitlines():
            line = line.strip()
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()

            # Handle lists: [a, b, c]
            if value.startswith("[") and value.endswith("]"):
                items = value[1:-1].split(",")
                frontmatter[key] = [i.strip().strip("'\"") for i in items if i.strip()]
            elif value.lower() in ("true", "false"):
                frontmatter[key] = value.lower() == "true"
            else:
                frontmatter[key] = value.strip("'\"")

        return frontmatter, body
