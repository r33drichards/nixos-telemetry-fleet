import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REV = "a" * 40
RUNTIME = "/nix/store/" + "a" * 32 + "-hermes-agent"
DEP = "/nix/store/" + "b" * 32 + "-python"
CLIENT = "/nix/store/" + "c" * 32 + "-cachix-1.0"
TOKEN = "synthetic-hermes-token"
SRI = "sha256-" + "A" * 43 + "="
BASE = {
    RUNTIME: {"narHash": SRI, "narSize": 1, "references": [DEP, RUNTIME]},
    DEP: {"narHash": SRI, "narSize": 2, "references": []},
}


def identity(info, *, raw=False):
    return subprocess.run(
        ["python3", ROOT / "scripts/hermes-runtime-identity.py", RUNTIME],
        input=info if raw else json.dumps(info), capture_output=True, text=True,
    )


class ClosureIdentityTests(unittest.TestCase):
    def test_path_reference_and_metadata_order_is_not_significant(self):
        reordered = {DEP: BASE[DEP], RUNTIME: {
            **BASE[RUNTIME], "references": [RUNTIME, DEP], "registrationTime": 500
        }}
        a, b = identity(BASE), identity(reordered)
        self.assertEqual((a.returncode, b.returncode), (0, 0))
        self.assertEqual(a.stdout, b.stdout)

    def test_same_store_path_changed_bytes_size_and_edges_change_digest(self):
        base = identity(BASE).stdout
        for field, value in (
            ("narHash", "sha256-B" + "A" * 42 + "="),
            ("narSize", 12345),
            ("references", [DEP]),
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(BASE)
                changed[RUNTIME][field] = value
                result = identity(changed)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotEqual(result.stdout, base)

    def test_missing_unreachable_and_prohibited_references_fail(self):
        extra = "/nix/store/" + "d" * 32 + "-extra"
        for info in (
            {DEP: BASE[DEP]},
            {RUNTIME: BASE[RUNTIME]},
            {**BASE, extra: BASE[DEP]},
            {**BASE, DEP: {**BASE[DEP], "narHash": "wrong"}},
            {**BASE, DEP: {**BASE[DEP], "narSize": True}},
            {**BASE, DEP: {**BASE[DEP], "references": [DEP, DEP]}},
            *(
                {RUNTIME: {**BASE[RUNTIME], "references": [p]}, p: BASE[DEP]}
                for p in ("/tmp/path", *(extra + suffix for suffix in (
                    ".drv", "-deploy.json", "-nixos-system-node2", "-node2-health",
                    "-node2-hermes-bootstrap-assets",
                )))
            ),
        ):
            with self.subTest(info=info):
                self.assertNotEqual(identity(info).returncode, 0)

    def test_duplicate_json_keys_fail(self):
        valid = json.dumps(BASE)
        duplicate = valid[:-1] + ", " + json.dumps(DEP) + ": {}}"
        self.assertNotEqual(identity(duplicate, raw=True).returncode, 0)


class PublishWorkflowTests(unittest.TestCase):
    def test_workflow_must_be_armed_before_jobs_and_still_checks_environment(self):
        workflow = (ROOT / ".github/workflows/hermes-runtime-publish.yml").read_text()
        qualify, publish = workflow.split("  qualify:\n", 1)[1].split("\n  publish:\n", 1)
        gate = "    if: >-\n      vars.HERMES_RUNTIME_PUBLISH_ARMED == 'enabled' &&"
        for job in (qualify, publish):
            self.assertIn(gate, job)
        self.assertLess(publish.index(gate), publish.index("    environment: hermes-runtime-cache"))
        self.assertNotIn("environment:", qualify)
        self.assertNotIn("secrets.", qualify)
        self.assertIn("HERMES_RUNTIME_PUBLISH: ${{ vars.HERMES_RUNTIME_PUBLISH }}", publish)
        self.assertIn('[[ "$HERMES_RUNTIME_PUBLISH" == enabled && -n "$CACHIX_AUTH_TOKEN" ]]', publish)

    def test_token_step_uses_absolute_shell_and_ignores_bash_startup_file(self):
        workflow = (ROOT / ".github/workflows/hermes-runtime-publish.yml").read_text()
        token_step = workflow.split(
            "      - name: Submit only the verified Hermes runtime closure\n", 1
        )[1].split("\n      - name:", 1)[0]
        self.assertIn(
            "        shell: /usr/bin/bash --noprofile --norc -e -o pipefail {0}\n",
            token_step,
        )
        self.assertIn("          BASH_ENV: /dev/null\n", token_step)
        self.assertIn("          CACHIX_AUTH_TOKEN: ${{ secrets.HERMES_RUNTIME_CACHE_WRITE_TOKEN }}", token_step)
        self.assertEqual(workflow.count("secrets."), 1)


class HermesPublishTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        (self.root / "scripts").mkdir()
        (self.root / "bin").mkdir()
        (self.root / "runtime/share/hermes-agent").mkdir(parents=True)
        (self.root / "runtime/command-map.json").touch()
        (self.root / "client/bin").mkdir(parents=True)
        self.calls = self.root / "calls"
        self.env = {
            **os.environ,
            "PATH": f"{self.root / 'bin'}:{os.environ['PATH']}",
            "GITHUB_REPOSITORY": "r33drichards/nixos-telemetry-fleet",
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": REV,
            "MOCK_HEAD": REV,
            "MOCK_RUNTIME": RUNTIME,
            "MOCK_CLIENT": CLIENT,
            "MOCK_CLOSURE": json.dumps(BASE),
            "HERMES_RUNTIME_PUBLISH": "enabled",
            "CACHIX_AUTH_TOKEN": "",
            "MOCK_LOG": str(self.calls),
        }
        for file in ("hermes-runtime-publish.sh", "hermes-runtime-identity.py"):
            shutil.copyfile(ROOT / "scripts" / file, self.root / "scripts" / file)
        self.mock("bin/git", """
[[ -z "${CACHIX_AUTH_TOKEN:-}" ]]
case "$1" in
  rev-parse) echo "$MOCK_HEAD" ;;
  diff) [[ "${MOCK_DIRTY:-}" != yes ]] ;;
  ls-files) printf %s "${MOCK_UNTRACKED:-}" ;;
  *) exit 9 ;;
esac
""")
        self.mock("bin/readlink", """
case "${*: -1}" in
  result-hermes|hermes-runtime-result) echo "$MOCK_RUNTIME" ;;
  hermes-runtime-cachix) echo "$MOCK_CLIENT" ;;
  *) exit 9 ;;
esac
""")
        self.mock("bin/nix", """
[[ -z "${CACHIX_AUTH_TOKEN:-}" ]]
printf 'nix %s\n' "$*" >>"$MOCK_LOG"
case "$1" in
  build)
    case "${*: -1}" in
      hermes-runtime-result) ln -s runtime hermes-runtime-result ;;
      hermes-runtime-cachix) ln -s client hermes-runtime-cachix ;;
      *) exit 9 ;;
    esac ;;
  path-info) printf '%s\n' "$MOCK_CLOSURE"; exit "${MOCK_NIX_EXIT:-0}" ;;
  store) [[ "$2 $3 $4" == "verify --recursive --no-trust" ]]; exit "${MOCK_VERIFY_EXIT:-0}" ;;
  *) exit 9 ;;
esac
""")
        self.mock("client/bin/cachix", "exit 99")  # Prepare must not execute it.

    def mock(self, name, code):
        file = self.root / name
        file.write_text("#!/bin/bash\nset -eu\n" + code)
        file.chmod(0o755)

    def run_phase(self, phase, **env):
        result = subprocess.run(
            ["bash", "scripts/hermes-runtime-publish.sh", phase],
            cwd=self.root, env={**self.env, **env}, capture_output=True, text=True,
        )
        self.assertNotIn(TOKEN, result.stdout + result.stderr)
        return result

    def call_log(self):
        return self.calls.read_text() if self.calls.exists() else ""

    def qualify(self):
        (self.root / "result-hermes").symlink_to("runtime")
        result = self.run_phase("qualify")
        self.assertEqual(result.returncode, 0, result.stderr)
        vals = dict(line.split("=", 1) for line in result.stdout.splitlines())
        self.assertEqual(set(vals), {"root", "closure_sha256"})
        return {"QUALIFIED_ROOT": vals["root"], "QUALIFIED_CLOSURE_SHA256": vals["closure_sha256"]}

    def test_independent_build_must_match_and_pin_client(self):
        env = self.qualify()
        result = self.run_phase("prepare", **env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            f"root={RUNTIME}",
            f"closure_sha256={env['QUALIFIED_CLOSURE_SHA256']}",
            f"client={CLIENT}/bin/cachix",
        ])
        self.assertIn("build -L ./candidates/hermes#default --no-update-lock-file", self.call_log())
        self.assertEqual(self.call_log().count("store verify --recursive --no-trust"), 3)
        self.assertNotIn("cachix push ", self.call_log())

    def test_wrong_context_fails_before_nix(self):
        for key, value in (
            ("GITHUB_REPOSITORY", "fork/nixos-telemetry-fleet"),
            ("GITHUB_REF", "refs/heads/feature"),
            ("GITHUB_EVENT_NAME", "pull_request_target"),
            ("GITHUB_EVENT_NAME", "workflow_dispatch"),
            ("GITHUB_SHA", "not-a-sha"),
            ("MOCK_HEAD", "b" * 40),
            ("MOCK_DIRTY", "yes"),
            ("MOCK_UNTRACKED", "candidates/hermes/.env"),
            ("HERMES_RUNTIME_PUBLISH", ""),
            ("CACHIX_AUTH_TOKEN", TOKEN),
        ):
            with self.subTest(key=key, value=value):
                self.assertNotEqual(self.run_phase("prepare", **{key: value}).returncode, 0)
        self.assertEqual(self.call_log(), "")

    def test_runtime_shape_and_contents_verification_fail_closed(self):
        for phase in ("qualify", "prepare"):
            for env in (
                {"MOCK_VERIFY_EXIT": "1"}, {"MOCK_NIX_EXIT": "17"},
                {"MOCK_RUNTIME": "/tmp/runtime"},
            ):
                with self.subTest(phase=phase, overrides=env):
                    if phase == "qualify":
                        p = self.root / "result-hermes"
                        if not p.is_symlink():
                            p.symlink_to("runtime")
                    result = self.run_phase(phase, **{
                        "QUALIFIED_ROOT": RUNTIME,
                        "QUALIFIED_CLOSURE_SHA256": identity(BASE).stdout.strip(),
                        **env,
                    })
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, "")
                    outgoing = self.root / "hermes-runtime-result"
                    if outgoing.is_symlink():
                        outgoing.unlink()
        self.assertNotIn("github:NixOS/nixpkgs", self.call_log())

    def test_changed_contents_at_same_root_rejected_before_client_build(self):
        env = self.qualify()
        changed = copy.deepcopy(BASE)
        changed[DEP]["narHash"] = "sha256-B" + "A" * 42 + "="
        result = self.run_phase("prepare", **env, MOCK_CLOSURE=json.dumps(changed))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("github:NixOS/nixpkgs", self.call_log())

    def test_rejects_preexisting_outlinks_and_unknown_operations(self):
        env = self.qualify()
        (self.root / "hermes-runtime-cachix").symlink_to("missing")
        for phase in ("prepare", "upload", "activate"):
            with self.subTest(phase=phase):
                self.assertNotEqual(self.run_phase(phase, **env).returncode, 0)
        self.assertNotIn("build -L", self.call_log())


if __name__ == "__main__":
    unittest.main()
