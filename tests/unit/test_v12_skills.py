"""
SuperAI V12 — tests/unit/test_v12_skills.py
Unit tests for Step 5: Skills/Plugin System
"""
import pytest
import sys
import os
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ── Skill Loader ──────────────────────────────────────────────────

class TestSkillLoader:

    def setup_method(self):
        from backend.skills.skill_loader import SkillLoader
        self.loader = SkillLoader()

    def test_split_frontmatter(self):
        text = "---\nname: test\ndescription: A test skill\n---\nBody content here."
        fm, body = self.loader._split_frontmatter(text)
        assert fm["name"] == "test"
        assert fm["description"] == "A test skill"
        assert "Body content" in body

    def test_split_frontmatter_with_list(self):
        text = "---\nname: test\ntriggers: [code, debug, fix]\n---\nContent"
        fm, body = self.loader._split_frontmatter(text)
        assert isinstance(fm["triggers"], list)
        assert "code" in fm["triggers"]
        assert len(fm["triggers"]) == 3

    def test_split_frontmatter_boolean(self):
        text = "---\nauto_activate: true\n---\nBody"
        fm, _ = self.loader._split_frontmatter(text)
        assert fm["auto_activate"] is True

    def test_load_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(
                "---\nname: my-skill\ndescription: Test\n"
                "triggers: [test, demo]\ncategory: testing\n---\n"
                "# My Skill\nDo the thing.\n"
            )
            skill = self.loader.load_file(str(skill_file))
            assert skill is not None
            assert skill.name == "my-skill"
            assert skill.category == "testing"
            assert "test" in skill.trigger_keywords
            assert "My Skill" in skill.content

    def test_load_nonexistent_returns_none(self):
        assert self.loader.load_file("/nonexistent/SKILL.md") is None

    def test_load_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two skills
            for name in ["skill-a", "skill-b"]:
                d = Path(tmpdir) / name
                d.mkdir()
                (d / "SKILL.md").write_text(f"---\nname: {name}\n---\nContent")

            skills = self.loader.load_directory(tmpdir)
            assert len(skills) == 2

    def test_create_skill_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self.loader.create_skill_file(
                tmpdir, "new-skill", "A new skill",
                ["trigger1", "trigger2"], "Do X then Y.",
            )
            assert Path(path).exists()
            content = Path(path).read_text()
            assert "name: new-skill" in content
            assert "Do X then Y." in content


# ── Skill Registry ────────────────────────────────────────────────

class TestSkillRegistry:

    def setup_method(self):
        from backend.skills.skill_registry import SkillRegistry
        from backend.skills.skill_loader import Skill
        self.registry = SkillRegistry(auto_load=False)
        # Register some test skills
        self.registry.register(Skill(
            name="code-review", description="Review code",
            trigger_keywords=["review", "code quality", "check"],
            category="quality",
        ))
        self.registry.register(Skill(
            name="debugging", description="Debug issues",
            trigger_keywords=["debug", "error", "fix bug"],
            category="debugging",
        ))
        self.registry.register(Skill(
            name="tdd", description="Test-driven development",
            trigger_keywords=["test", "tdd", "unit test"],
            category="testing",
        ))

    def test_list_all(self):
        assert len(self.registry.list_all()) == 3

    def test_get_existing(self):
        skill = self.registry.get("code-review")
        assert skill is not None
        assert skill.category == "quality"

    def test_get_nonexistent(self):
        assert self.registry.get("nonexistent") is None

    def test_list_by_category(self):
        debug_skills = self.registry.list_by_category("debugging")
        assert len(debug_skills) == 1
        assert debug_skills[0].name == "debugging"

    def test_match_by_keywords(self):
        matched = self.registry.match("review my code quality")
        assert any(s.name == "code-review" for s in matched)

    def test_match_debug_keywords(self):
        matched = self.registry.match("I have an error, help me debug")
        assert any(s.name == "debugging" for s in matched)

    def test_match_returns_empty_for_no_match(self):
        matched = self.registry.match("hello world")
        assert len(matched) == 0

    def test_match_respects_max_skills(self):
        matched = self.registry.match("review code debug test fix", max_skills=2)
        assert len(matched) <= 2

    def test_match_uses_name_and_description_overlap(self):
        from backend.skills.skill_loader import Skill
        from backend.skills.skill_registry import SkillRegistry
        registry = SkillRegistry(auto_load=False)
        registry.register(Skill(
            name="react-patterns",
            description="React dashboard components and hooks",
            trigger_keywords=["hooks"],
            category="frontend",
            priority=3,
        ))
        registry.register(Skill(
            name="docker-expert",
            description="Docker containers and deployment pipelines",
            trigger_keywords=["container"],
            category="devops",
            priority=3,
        ))

        matched = registry.match("Build a React dashboard for analytics", max_skills=2)
        assert matched
        assert matched[0].name == "react-patterns"

    def test_enrich_prompt(self):
        enriched = self.registry.enrich_prompt(
            "You are an AI.", "debug this error please",
        )
        assert "Active Skills" in enriched
        assert "debugging" in enriched.lower()

    def test_enrich_prompt_no_match(self):
        enriched = self.registry.enrich_prompt(
            "You are an AI.", "hello world",
        )
        # No skills matched, should return original
        assert enriched == "You are an AI."
