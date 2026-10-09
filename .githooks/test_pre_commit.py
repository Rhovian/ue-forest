import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).with_name("pre-commit").resolve()
POINTER = b"version https://git-lfs.github.com/spec/v1\noid sha256:" + b"0" * 64 + b"\nsize 10\n"
PROJECT = "MyProject/MyProject.uproject"


class PreCommitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.env = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1", GIT_CONFIG_NOSYSTEM="1",
                        GIT_CONFIG_GLOBAL=os.devnull)
        for key in list(self.env):
            if key.startswith(("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_",
                               "GIT_CONFIG_VALUE_", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES")):
                del self.env[key]
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "core.hooksPath", "/dev/null")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, env=self.env, check=True, capture_output=True)

    def stage(self, path, blob):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
        self.git("add", "--", path)

    def check(self, path, code):
        result = subprocess.run([str(HOOK)], check=False, cwd=self.repo, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        if code:
            self.assertIn(path, result.stdout + result.stderr)

    def test_raw_asset(self):
        path = "MyProject/Content/SM_Tree.uasset"
        self.stage(path, b"raw asset")
        self.check(path, 1)

    def test_pointer_asset(self):
        path = "MyProject/Content/SM_Tree.uasset"
        self.stage(path, POINTER)
        self.check(path, 0)

    def test_large_binary(self):
        self.stage("large.bin", b"x" * (1024 * 1024 + 1))
        self.check("large.bin", 1)

    def test_invalid_project(self):
        self.stage(PROJECT, b"{")
        self.check(PROJECT, 1)

    def test_enabled_mcp(self):
        self.stage(PROJECT, b'{"Plugins": [{"Name": "MCPClientToolset", "Enabled": true}]}')
        self.check(PROJECT, 1)

    def test_bad_name(self):
        path = "MyProject/Content/Tree.uasset"
        self.stage(path, POINTER)
        self.check(path, 1)

    def test_library_name(self):
        path = "MyProject/Content/Megaplant_Library/Tree.uasset"
        self.stage(path, POINTER)
        self.check(path, 0)

    def test_modified_name(self):
        path = "MyProject/Content/Tree.uasset"
        self.stage(path, POINTER)
        self.git("commit", "-qm", "existing asset")
        self.stage(path, POINTER.replace(b"size 10", b"size 11"))
        self.check(path, 0)

    def test_staged_blob_not_worktree(self):
        path = "MyProject/Content/SM_Tree.uasset"
        self.stage(path, b"raw asset")
        (self.repo / path).write_bytes(POINTER)
        self.check(path, 1)
        self.stage(path, POINTER)
        (self.repo / path).write_bytes(b"raw asset")
        self.check(path, 0)

    def test_renamed_name(self):
        old, new = "MyProject/Content/SM_Tree.uasset", "MyProject/Content/Tree.uasset"
        self.stage(old, POINTER)
        self.git("commit", "-qm", "existing asset")
        self.git("mv", old, new)
        self.check(new, 1)

    def test_all_failures(self):
        self.stage(PROJECT, b'{"Plugins": [{"Name": "AllToolsets", "Enabled": true}]}')
        self.stage("MyProject/Content/Tree.umap", b"raw map")
        result = subprocess.run([str(HOOK)], check=False, cwd=self.repo, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        for reason in (PROJECT, "AllToolsets", "Tree.umap", "LFS pointer", "basename"):
            self.assertIn(reason, result.stderr)


if __name__ == "__main__":
    unittest.main()
