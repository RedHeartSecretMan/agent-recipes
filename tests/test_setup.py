"""Black-box tests for setup using isolated targets and a simulated installer.

The fixture repositories contain real commits. Git network access and bunx are
replaced by explicit adapters; these tests do not claim live global installation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]
REAL_GIT = shutil.which("git")
CURRENT_BASH = next((candidate for candidate in (
    shutil.which("bash"), "/opt/homebrew/bin/bash", "/usr/local/bin/bash"
) if candidate and Path(candidate).is_file()
    and Path(candidate).resolve() != Path("/bin/bash").resolve()), shutil.which("bash"))
SOURCE = "https://github.com/agent-recipes-test/fixture"
SECOND_SOURCE = "https://github.com/agent-recipes-test/other"


def snapshot(root: Path):
    """Capture observable contents, including link identities, without following links."""
    result = {}
    if not root.exists():
        return result
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in list(dirs) + files:
            path = Path(directory) / name
            relative = str(path.relative_to(root))
            if path.is_symlink():
                result[relative] = ("link", os.readlink(path))
            elif path.is_file():
                result[relative] = ("file", path.read_bytes())
    return result


class SetupBehavior:
    shell = None

    def setUp(self):
        if not (PROJECT / "setup").is_file():
            self.fail("setup implementation is missing")
        self.temporary = tempfile.TemporaryDirectory(prefix="agent-recipes-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "recipes with spaces"
        self.repo.mkdir()
        shutil.copy2(PROJECT / "setup", self.repo / "setup")
        self.recipes = self.repo
        self.rules = "# Personal rules\n\nPreserve the user's work. 中文与 English 留空格。\n"
        (self.recipes / "AGENTS.md").write_text(self.rules)
        self.write_manifest([])
        self.home = self.root / "isolated home"
        self.home.mkdir()
        for name in (".codex", ".claude", ".dsh", ".cursor"):
            (self.home / name).mkdir()
        self.mcp_tripwire = self.root / "MCP must never execute"
        self.mcp_file = self.recipes / "mcps.json"
        self.mcp_file.write_text(json.dumps({"mcpServers": {
            "context7": {"type": "http", "url": "https://mcp.context7.com/mcp"},
            "tripwire": {"type": "stdio", "command": str(self.mcp_tripwire)}
        }}, indent=2) + "\n")
        self.mcp_tripwire.write_text("#!/bin/sh\ntouch '" + str(self.root / "MCP-RAN") + "'\n")
        self.mcp_tripwire.chmod(0o755)
        self.native_mcp = self.home / ".cursor/mcp.json"
        self.native_mcp.write_text('{"mcpServers":{"unrelated":{"url":"https://example.invalid/mcp"}}}\n')
        self.native_mcp_before = self.native_mcp.read_bytes()
        self.git_log = self.root / "git.calls"
        self.bunx_log = self.root / "bunx.calls"
        self.upstream = self.root / "upstream with spaces"
        self.upstream.mkdir()
        self.real_git("init", "-q", self.upstream)
        self.real_git("-C", self.upstream, "checkout", "-q", "-b", "main")
        self.put_skill(self.upstream, "skills/alpha", "alpha", "old")
        self.put_skill(self.upstream, "skills/beta", "beta", "beta")
        self.old = self.commit(self.upstream, "initial skills")
        self.put_skill(self.upstream, "skills/alpha", "alpha", "new")
        self.new = self.commit(self.upstream, "new alpha")
        self.other = self.root / "other upstream"
        self.other.mkdir()
        self.real_git("init", "-q", self.other)
        self.real_git("-C", self.other, "checkout", "-q", "-b", "main")
        self.put_skill(self.other, "plugins/alpha", "alpha", "other-source")
        self.other_ref = self.commit(self.other, "other source")
        self.env = os.environ.copy()
        self.env.update({
            "AGENT_RECIPES_HOME": str(self.home),
            "AGENT_RECIPES_BUNX": str(PROJECT / "tests/fake_bunx.py"),
            "AGENT_RECIPES_GIT": str(PROJECT / "tests/fake_git.py"),
            "TEST_REAL_GIT": REAL_GIT,
            "TEST_GIT_SOURCES": json.dumps({SOURCE: str(self.upstream), SECOND_SOURCE: str(self.other)}),
            "TEST_GIT_LOG": str(self.git_log),
            "TEST_BUNX_LOG": str(self.bunx_log),
            "TEST_MANIFEST": str(self.recipes / "skills.json"),
            "LC_ALL": "C",
        })

    def tearDown(self):
        if hasattr(self, "native_mcp"):
            if self.native_mcp_before is None:
                self.assertFalse(self.native_mcp.exists(), "Skills operations created client MCP configuration")
            else:
                self.assertEqual(self.native_mcp.read_bytes(), self.native_mcp_before,
                                 "Skills/rules operations changed client MCP configuration")
            self.assertFalse((self.root / "MCP-RAN").exists(), "setup executed an MCP command")

    def real_git(self, *args):
        process = subprocess.run([REAL_GIT, *map(str, args)], text=True, capture_output=True)
        if process.returncode:
            self.fail(process.stderr)
        return process.stdout.strip()

    def commit(self, repo, message):
        self.real_git("-C", repo, "add", ".")
        self.real_git("-C", repo, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                      "-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", message)
        return self.real_git("-C", repo, "rev-parse", "HEAD")

    def put_skill(self, repo, folder, name, version):
        location = repo / folder
        location.mkdir(parents=True, exist_ok=True)
        (location / "SKILL.md").write_text("---\nname: " + name + "\ndescription: Test fixture\n---\n" + version + "\n")
        (location / "resource.txt").write_text("resource: " + version + "\n")

    def write_manifest(self, skills):
        (self.recipes / "skills.json").write_text(json.dumps({"skills": skills}, indent=2) + "\n")

    def manifest(self):
        return json.loads((self.recipes / "skills.json").read_text())

    def entry(self, ref=None, source=SOURCE, path="skills/alpha", name="alpha"):
        return {"name": name, "source": source, "path": path, "ref": ref or self.old}

    def invoke(self, *args, ok=True, behavior=None, env=None):
        run_env = self.env.copy()
        if behavior:
            run_env["TEST_BUNX_BEHAVIOR"] = behavior
        if env:
            run_env.update(env)
        result = subprocess.run([self.shell, str(self.repo / "setup"), *args], cwd=self.repo,
                                env=run_env, text=True, capture_output=True, timeout=30)
        if ok is True:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        elif ok is False:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def add_alpha(self, ref=None):
        return self.invoke("skills", "add", SOURCE, "--skill", "alpha", "--path", "skills/alpha",
                           "--ref", ref or self.old)

    @property
    def installed(self):
        return self.home / ".agents/skills/alpha"

    def lock(self):
        return json.loads((self.home / ".agents/.skill-lock.json").read_text())

    def calls(self):
        return [json.loads(line) for line in self.bunx_log.read_text().splitlines()] if self.bunx_log.exists() else []

    def test_help_is_available(self):
        output = self.invoke("--help").stdout
        self.assertIn("skills", output)
        self.assertIn("./setup mcp", output)
        self.assertIn("--version", output)
        self.assertEqual(self.calls(), [])

    def test_version_is_read_only_and_independent_of_configuration_or_tools(self):
        before_home, before_repo = snapshot(self.home), snapshot(self.repo)
        output = self.invoke("--version").stdout
        self.assertEqual(output, "agent-recipes 0.1.0\n")
        self.assertEqual(snapshot(self.home), before_home)
        self.assertEqual(snapshot(self.repo), before_repo)
        self.assertEqual(self.calls(), [])
        (self.recipes / "AGENTS.md").unlink()
        (self.recipes / "skills.json").write_text("not valid JSON\n")
        self.mcp_file.write_text("not valid JSON\n")
        empty_path = self.root / "empty executable path"
        empty_path.mkdir()
        before_home, before_repo = snapshot(self.home), snapshot(self.repo)
        result = self.invoke("--version", env={
            "PATH": str(empty_path),
            "AGENT_RECIPES_HOME": "unused-relative-target",
            "AGENT_RECIPES_GIT": str(empty_path / "missing-git"),
            "AGENT_RECIPES_BUNX": str(empty_path / "missing-bunx"),
        })
        self.assertEqual(result.stdout, "agent-recipes 0.1.0\n")
        self.assertEqual(result.stderr, "")
        self.assertEqual(snapshot(self.home), before_home)
        self.assertEqual(snapshot(self.repo), before_repo)
        self.assertEqual(self.calls(), [])

    def test_mcp_guide_is_read_only_and_uses_current_records(self):
        data = json.loads(self.mcp_file.read_text())
        data["mcpServers"]["tripwire"]["env"] = {"API_KEY": "secret-must-not-print"}
        self.mcp_file.write_text(json.dumps(data) + "\n")
        before_home, before_repo = snapshot(self.home), snapshot(self.repo)
        output = self.invoke("mcp").stdout
        self.assertIn("context7 (http)", output)
        self.assertIn("tripwire (stdio)", output)
        self.assertIn(str(self.mcp_file), output)
        for number in range(1, 6):
            self.assertTrue(any(line.startswith(str(number) + ". ") for line in output.splitlines()))
        self.assertIn("保留其他 MCP", output)
        self.assertNotIn("secret-must-not-print", output)
        self.assertEqual(snapshot(self.home), before_home)
        self.assertEqual(snapshot(self.repo), before_repo)
        self.assertEqual(self.calls(), [])

    def test_mcp_guide_does_not_require_a_valid_skill_manifest(self):
        (self.recipes / "skills.json").write_text("not-json\n")
        output = self.invoke("mcp", env={"AGENT_RECIPES_HOME": "unused-relative-target"}).stdout
        self.assertIn("context7 (http)", output)
        self.assertEqual(self.calls(), [])
        self.assertFalse((self.home / ".local").exists())

    def test_invalid_mcp_guide_input_has_no_side_effects(self):
        self.mcp_file.write_text("not-json\n")
        before_home, before_repo = snapshot(self.home), snapshot(self.repo)
        result = self.invoke("mcp", ok=False)
        self.assertIn("mcps.json", result.stderr)
        self.assertEqual(snapshot(self.home), before_home)
        self.assertEqual(snapshot(self.repo), before_repo)
        self.assertEqual(self.calls(), [])

    def test_list_is_read_only(self):
        self.write_manifest([self.entry()])
        (self.home / "unrelated.txt").write_text("keep")
        before_home = snapshot(self.home)
        before_repo = snapshot(self.repo)
        output = self.invoke("skills", "list").stdout
        self.assertIn("alpha", output)
        self.assertEqual(snapshot(self.home), before_home)
        self.assertEqual(snapshot(self.repo), before_repo)
        self.assertEqual(self.calls(), [])

    def test_rules_sync_and_repeated_execution(self):
        output = self.invoke().stdout
        self.assertIn("./setup mcp", output)
        canonical = self.home / ".agents/AGENTS.md"
        self.assertEqual(canonical.read_text(), self.rules)
        for relative in (".codex/AGENTS.md", ".claude/CLAUDE.md", ".dsh/AGENTS.md"):
            path = self.home / relative
            self.assertEqual(path.read_text(), self.rules)
        cursor = self.home / ".cursor/rules/global-principles.mdc"
        self.assertIn("alwaysApply: true", cursor.read_text())
        self.assertIn(self.rules, cursor.read_text())
        before = snapshot(self.home)
        self.invoke()
        self.assertEqual(snapshot(self.home), before)
        self.assertEqual(self.calls(), [])

    def test_root_configuration_is_authoritative_and_agents_decoys_are_untouched(self):
        old_directory = self.repo / "agents"
        old_directory.mkdir()
        decoys = {
            old_directory / "AGENTS.md": b"outdated agents-directory rules: do not deploy\n",
            old_directory / "skills.json": b"not valid skill JSON\n",
            old_directory / "mcps.json": b"not valid MCP JSON\n",
        }
        for path, contents in decoys.items():
            path.write_bytes(contents)
        self.write_manifest([self.entry()])
        self.invoke()
        canonical = self.home / ".agents/AGENTS.md"
        self.assertEqual(canonical.read_text(), self.rules)
        self.assertEqual(canonical.resolve(), (self.recipes / "AGENTS.md").resolve())
        self.assertIn(self.rules, (self.home / ".cursor/rules/global-principles.mdc").read_text())
        self.assertIn("old", (self.installed / "SKILL.md").read_text())
        guide = self.invoke("mcp").stdout
        self.assertIn(str(self.mcp_file), guide)
        self.invoke("skills", "set", "alpha", "--ref", self.new)
        self.assertEqual(self.manifest()["skills"], [self.entry(self.new)])
        for path, contents in decoys.items():
            self.assertEqual(path.read_bytes(), contents, "An agents-directory decoy was read as writable configuration")

    def test_unknown_external_broken_rule_link_is_preserved(self):
        canonical = self.home / ".agents/AGENTS.md"
        canonical.parent.mkdir()
        for external in (self.root / "different missing global rules",
                         self.repo.resolve() / "agents/AGENTS.md"):
            with self.subTest(external=external):
                if canonical.is_symlink():
                    canonical.unlink()
                canonical.symlink_to(external)
                self.invoke(ok=False)
                self.assertTrue(canonical.is_symlink())
                self.assertEqual(os.readlink(canonical), str(external))
                self.assertFalse(canonical.exists())

    def test_rules_conflict_preserved_and_force_backed_up(self):
        canonical = self.home / ".agents/AGENTS.md"
        canonical.parent.mkdir()
        canonical.write_text("my existing rules\n")
        self.invoke(ok=False)
        self.assertEqual(canonical.read_text(), "my existing rules\n")
        self.invoke("--force")
        self.assertEqual(canonical.read_text(), self.rules)
        backups = self.home / ".local/state/agent-recipes"
        self.assertTrue(any(p.is_file() and not p.is_symlink() and p.read_bytes() == b"my existing rules\n"
                            for p in backups.rglob("*")))

    def check_rule_directory_refused(self, relative):
        target = self.home / relative
        target.mkdir(parents=True)
        (target / "keep.txt").write_text("directory content must remain in place\n")
        before = snapshot(target)
        for parameters in [(), ("--force",)]:
            with self.subTest(parameters=parameters):
                self.invoke(*parameters, ok=False)
                self.assertTrue(target.is_dir(), "A rule path that is a directory must be rejected")
                self.assertFalse(target.is_symlink())
                self.assertEqual(snapshot(target), before, "setup wrote inside or moved the directory")

    def test_canonical_rule_directory_is_refused_even_with_force(self):
        self.check_rule_directory_refused(".agents/AGENTS.md")

    def test_client_rule_directory_is_refused_even_with_force(self):
        self.check_rule_directory_refused(".codex/AGENTS.md")

    def test_cursor_rule_directory_is_refused_even_with_force(self):
        self.check_rule_directory_refused(".cursor/rules/global-principles.mdc")

    def check_rule_symlink_to_directory_refused(self, relative):
        referent = self.root / "outside target directory"
        referent.mkdir()
        (referent / "keep.txt").write_text("external directory must not receive rule files\n")
        target = self.home / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(referent, target_is_directory=True)
        before_contents = snapshot(referent)
        before_link = os.readlink(target)
        for parameters in [(), ("--force",)]:
            with self.subTest(parameters=parameters):
                self.invoke(*parameters, ok=False)
                self.assertTrue(target.is_symlink(), "A rule symlink to a directory must remain untouched")
                self.assertEqual(os.readlink(target), before_link)
                self.assertEqual(snapshot(referent), before_contents,
                                 "setup moved a temporary rule file into the symlink referent")

    def test_canonical_rule_symlink_to_directory_is_refused_even_with_force(self):
        self.check_rule_symlink_to_directory_refused(".agents/AGENTS.md")

    def test_client_rule_symlink_to_directory_is_refused_even_with_force(self):
        self.check_rule_symlink_to_directory_refused(".codex/AGENTS.md")

    def test_cursor_rule_symlink_to_directory_is_refused_even_with_force(self):
        self.check_rule_symlink_to_directory_refused(".cursor/rules/global-principles.mdc")

    def test_add_records_fixed_version_and_native_installer(self):
        self.add_alpha()
        self.assertEqual(self.manifest()["skills"], [self.entry()])
        self.assertIn("old", (self.installed / "SKILL.md").read_text())
        self.assertEqual(self.lock()["skills"]["alpha"]["ref"], self.old)
        additions = [call for call in self.calls() if call[:2] == ["skills@latest", "add"]]
        self.assertEqual(len(additions), 1)
        self.assertIn(self.old, additions[0][2])
        self.assertTrue(any(flag in additions[0] for flag in ("--global", "-g")))
        selector = next((flag for flag in ("--agent", "-a") if flag in additions[0]), None)
        self.assertIsNotNone(selector, "Use the shared universal target instead of auto-detection")
        self.assertEqual(additions[0][additions[0].index(selector) + 1], "universal")
        self.assertNotIn("--bun", additions[0])

    def test_manifest_key_order_does_not_trigger_reinstallation(self):
        self.add_alpha()
        manifest = self.recipes / "skills.json"
        manifest.write_text(json.dumps(self.manifest(), sort_keys=True, indent=2) + "\n")
        listing = self.invoke("skills", "list").stdout
        alpha_line = next(line for line in listing.splitlines() if line.split() and line.split()[0] == "alpha")
        self.assertIn("installed", alpha_line.lower().split())
        calls_before = self.calls()
        self.invoke()
        self.assertEqual(self.calls(), calls_before, "Object key order alone caused a native reinstall")
        self.assertIn("old", (self.installed / "SKILL.md").read_text())

    def test_add_resolves_default_branch_when_ref_omitted(self):
        self.invoke("skills", "add", SOURCE, "--skill", "alpha", "--path", "skills/alpha")
        self.assertEqual(self.manifest()["skills"][0]["ref"], self.new)
        self.assertIn("new", (self.installed / "SKILL.md").read_text())

    def test_add_succeeds_without_initialized_client_directories(self):
        for name in (".codex", ".claude", ".dsh", ".cursor"):
            shutil.rmtree(self.home / name)
        self.native_mcp_before = None
        self.add_alpha()
        self.assertEqual(self.manifest()["skills"], [self.entry()])
        self.assertIn("old", (self.installed / "SKILL.md").read_text())
        for name in (".codex", ".claude", ".dsh", ".cursor"):
            self.assertFalse((self.home / name).exists(), "Universal Skill installation should not initialize clients")

    def test_add_discovers_path_when_omitted(self):
        self.invoke("skills", "add", SOURCE, "--skill", "alpha", "--ref", self.old)
        self.assertEqual(self.manifest()["skills"][0], self.entry())

    def test_repository_root_skill_is_supported(self):
        self.put_skill(self.other, ".", "root-skill", "root package")
        ref = self.commit(self.other, "root-level Skill")
        self.invoke("skills", "add", SECOND_SOURCE, "--skill", "root-skill", "--path", ".", "--ref", ref)
        item = next(x for x in self.manifest()["skills"] if x["name"] == "root-skill")
        self.assertEqual(item["path"], ".")
        self.assertEqual(item["ref"], ref)
        self.assertIn("root package", (self.home / ".agents/skills/root-skill/SKILL.md").read_text())

    def test_replacing_development_link_preserves_source_checkout(self):
        checkout = self.root / "development checkout"
        checkout.mkdir()
        (checkout / "SKILL.md").write_text("uncommitted development content\n")
        self.installed.parent.mkdir(parents=True)
        self.installed.symlink_to(checkout, target_is_directory=True)
        before = snapshot(checkout)
        self.invoke("--force", "skills", "add", SOURCE, "--skill", "alpha",
                    "--path", "skills/alpha", "--ref", self.old)
        self.assertEqual(snapshot(checkout), before)
        self.assertNotEqual(self.installed.resolve(), checkout.resolve())
        self.assertIn("old", (self.installed / "SKILL.md").read_text())

    def test_set_ref_updates_configuration_and_installation(self):
        self.add_alpha()
        self.invoke("skills", "set", "alpha", "--ref", self.new)
        self.assertEqual(self.manifest()["skills"][0]["ref"], self.new)
        self.assertIn("new", (self.installed / "resource.txt").read_text())

    def test_set_changes_source_and_path(self):
        self.add_alpha()
        self.invoke("skills", "set", "alpha", "--source", SECOND_SOURCE,
                    "--path", "plugins/alpha", "--ref", self.other_ref)
        self.assertEqual(self.manifest()["skills"], [self.entry(self.other_ref, SECOND_SOURCE, "plugins/alpha")])
        self.assertIn("other-source", (self.installed / "SKILL.md").read_text())

    def test_set_ref_before_source_is_order_independent(self):
        self.add_alpha()
        self.invoke("skills", "set", "alpha", "--ref", self.other_ref,
                    "--source", SECOND_SOURCE, "--path", "plugins/alpha")
        self.assertEqual(self.manifest()["skills"], [self.entry(self.other_ref, SECOND_SOURCE, "plugins/alpha")])
        self.assertIn("other-source", (self.installed / "SKILL.md").read_text())

    def test_set_path_before_source_is_order_independent(self):
        self.add_alpha()
        self.invoke("skills", "set", "alpha", "--path", "plugins/alpha",
                    "--source", SECOND_SOURCE, "--ref", self.other_ref)
        self.assertEqual(self.manifest()["skills"], [self.entry(self.other_ref, SECOND_SOURCE, "plugins/alpha")])
        self.assertIn("other-source", (self.installed / "SKILL.md").read_text())

    def test_remove_only_managed_installation(self):
        self.add_alpha()
        unrelated = self.home / ".agents/skills/unrelated/SKILL.md"
        unrelated.parent.mkdir()
        unrelated.write_text("keep unrelated")
        self.invoke("skills", "remove", "alpha")
        self.assertEqual(self.manifest()["skills"], [])
        self.assertFalse(self.installed.exists())
        self.assertEqual(unrelated.read_text(), "keep unrelated")

    def test_remove_does_not_delete_unowned_directory(self):
        self.write_manifest([self.entry()])
        self.installed.mkdir(parents=True)
        (self.installed / "SKILL.md").write_text("unowned user content")
        self.invoke("skills", "remove", "alpha")
        self.assertEqual(self.manifest()["skills"], [])
        self.assertEqual((self.installed / "SKILL.md").read_text(), "unowned user content")
        self.assertEqual(self.calls(), [], "Removing only a declaration must not invoke bunx")

    def test_remove_missing_installation_only_updates_declaration(self):
        self.write_manifest([self.entry()])
        self.invoke("skills", "remove", "alpha")
        self.assertEqual(self.manifest()["skills"], [])
        self.assertFalse(self.installed.exists())
        self.assertEqual(self.calls(), [], "Removing a missing installation must not invoke bunx")

    def test_independent_same_named_copy_is_preserved_and_reported(self):
        self.add_alpha()
        external = self.home / ".claude/skills/alpha"
        external.mkdir(parents=True)
        (external / "SKILL.md").write_text("separately maintained alpha\n")
        (external / "custom.txt").write_text("keep this independent copy\n")
        before = snapshot(external)
        listing = self.invoke("skills", "list").stdout
        self.assertIn("external", listing.lower())
        self.invoke("skills", "set", "alpha", "--ref", self.new,
                    env={"TEST_BUNX_CREATE_ALIAS": "1"})
        self.assertEqual(snapshot(external), before)
        self.assertFalse(external.is_symlink())
        self.assertIn("new", (self.installed / "SKILL.md").read_text())
        calls_before_remove = self.calls()
        self.invoke("skills", "remove", "alpha", ok=False)
        self.assertEqual(snapshot(external), before)
        self.assertTrue(self.installed.is_dir())
        self.assertEqual(self.manifest()["skills"], [self.entry(self.new)])
        self.assertEqual(self.calls(), calls_before_remove, "Unsafe removal must not reach the native installer")

    def test_update_records_new_commit_after_installation(self):
        self.add_alpha()
        self.invoke("skills", "update", "alpha")
        self.assertEqual(self.manifest()["skills"][0]["ref"], self.new)
        self.assertEqual(self.lock()["skills"]["alpha"]["ref"], self.new)
        self.assertIn("new", (self.installed / "SKILL.md").read_text())

    def test_update_missing_upstream_skill_preserves_old_version(self):
        self.add_alpha()
        shutil.rmtree(self.upstream / "skills/alpha")
        self.commit(self.upstream, "remove upstream alpha")
        self.invoke("skills", "update", "alpha", ok=None)
        self.assertEqual(self.manifest()["skills"][0]["ref"], self.old)
        self.assertIn("old", (self.installed / "SKILL.md").read_text())

    def check_rejected_install_restores_old(self, behavior):
        self.add_alpha()
        lock_path = self.home / ".agents/.skill-lock.json"
        before_lock = self.lock()
        before_lock["skills"]["unrelated"] = {"source": "keep/me", "ref": "f" * 40}
        lock_path.write_text(json.dumps(before_lock) + "\n")
        previous_manifest = (self.recipes / "skills.json").read_bytes()
        previous_install = snapshot(self.installed)
        previous_lock_entry = self.lock()["skills"]["alpha"]
        self.invoke("skills", "set", "alpha", "--ref", self.new, behavior=behavior, ok=False)
        self.assertEqual((self.recipes / "skills.json").read_bytes(), previous_manifest)
        self.assertEqual(snapshot(self.installed), previous_install)
        self.assertEqual(self.lock()["skills"]["alpha"], previous_lock_entry)
        self.assertEqual(self.lock()["skills"]["unrelated"], before_lock["skills"]["unrelated"])

    def test_partial_installer_failure_is_rolled_back(self):
        self.check_rejected_install_restores_old("partial_failure")

    def test_exit_zero_with_wrong_lock_is_rejected(self):
        self.check_rejected_install_restores_old("bad_lock")

    def test_exit_zero_with_wrong_source_is_rejected(self):
        self.check_rejected_install_restores_old("bad_source")

    def test_exit_zero_with_wrong_path_is_rejected(self):
        self.check_rejected_install_restores_old("bad_path")

    def test_exit_zero_with_missing_files_is_rejected(self):
        self.check_rejected_install_restores_old("missing_files")

    def test_invalid_installer_json_is_rejected(self):
        self.check_rejected_install_restores_old("invalid_json")

    def test_modified_managed_skill_requires_force(self):
        self.add_alpha()
        modified = self.installed / "resource.txt"
        modified.write_text("manual change\n")
        self.invoke("skills", "set", "alpha", "--ref", self.new, ok=False)
        self.assertEqual(modified.read_text(), "manual change\n")
        self.invoke("--force", "skills", "set", "alpha", "--ref", self.new)
        self.assertIn("new", modified.read_text())
        backups = self.home / ".local/state/agent-recipes"
        self.assertTrue(any(p.is_file() and not p.is_symlink() and p.read_bytes() == b"manual change\n"
                            for p in backups.rglob("*")))

    def test_concurrent_manifest_edit_is_not_overwritten(self):
        self.add_alpha()
        self.invoke("skills", "set", "alpha", "--ref", self.new, behavior="mutate_manifest", ok=False)
        self.assertEqual(self.manifest().get("external_edit"), "preserve this concurrent change")

    def test_invalid_source_path_name_and_ref_are_rejected(self):
        marker = self.root / "INJECTION-RAN"
        bad_source = SOURCE + "; touch '" + str(marker) + "'"
        cases = [
            ("skills", "add", bad_source, "--skill", "alpha", "--path", "skills/alpha"),
            ("skills", "add", "file:///tmp/source", "--skill", "alpha"),
            ("skills", "add", SOURCE, "--skill", "../escape", "--path", "skills/alpha"),
            ("skills", "add", SOURCE, "--skill", "alpha", "--path", "../../escape"),
            ("skills", "add", SOURCE, "--skill", "alpha", "--ref", "--upload-pack=bad"),
        ]
        for parameters in cases:
            with self.subTest(parameters=parameters):
                self.invoke(*parameters, ok=False)
        self.assertFalse(marker.exists())
        self.assertEqual(self.manifest()["skills"], [])
        self.assertEqual(self.calls(), [])

    def test_duplicate_manifest_names_are_rejected(self):
        self.write_manifest([self.entry(), self.entry(self.new)])
        self.invoke("skills", "list", ok=False)
        self.assertEqual(self.calls(), [])

    def test_custom_home_requires_explicit_installer(self):
        run_env = self.env.copy()
        run_env.pop("AGENT_RECIPES_BUNX")
        self.write_manifest([self.entry()])
        result = subprocess.run([self.shell, str(self.repo / "setup")], cwd=self.repo, env=run_env,
                                text=True, capture_output=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.bunx_log.exists())


@unittest.skipUnless(Path("/bin/bash").is_file(), "System /bin/bash is unavailable")
class SystemBashTests(SetupBehavior, unittest.TestCase):
    shell = "/bin/bash"


@unittest.skipIf(CURRENT_BASH == "/bin/bash", "Current bash is the system bash")
class CurrentBashTests(SetupBehavior, unittest.TestCase):
    shell = CURRENT_BASH


if __name__ == "__main__":
    unittest.main()
