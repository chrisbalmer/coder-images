#!/usr/bin/env python3
"""Tests for the pipeline scripts: change one image, build one image; release by promotion.

Every test runs in a throwaway git copy of the working tree, so uncommitted changes are tested
and the real history is never touched. Nothing reaches a registry: published tags come from
fixture files, and the "unreachable registry" cases use host.invalid.

Usage: python3 scripts/test_ci.py [-v]
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES = ["base", "golang", "app", "cortex", "infra", "ubuntu-desktop", "podman", "kali-desktop"]
# app is built on golang, the rest on base.
DEPENDENTS = ["app", "cortex", "golang", "infra", "ubuntu-desktop"]
CANONICAL = "chrisbalmer/coder-images"

_spec = importlib.util.spec_from_file_location("plan_release", os.path.join(ROOT, "scripts", "plan-release.py"))
plan_release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plan_release)


class Repo:
    """A throwaway git repository seeded from the working tree."""

    def __init__(self, tmp: str):
        self.path = os.path.join(tmp, "repo")
        shutil.copytree(ROOT, self.path, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "ci@example.com")
        self.git("config", "user.name", "CI")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "seed")

    def run(self, *cmd: str, env: dict | None = None) -> subprocess.CompletedProcess:
        full_env = {**os.environ, "GITHUB_STEP_SUMMARY": "", **(env or {})}
        return subprocess.run(cmd, cwd=self.path, capture_output=True, text=True, env=full_env)

    def git(self, *args: str) -> str:
        out = self.run("git", *args)
        if out.returncode != 0:
            raise AssertionError(f"git {' '.join(args)}: {out.stderr}")
        return out.stdout.strip()

    def commit(self, path: str, text: str = "# changed\n") -> None:
        full = os.path.join(self.path, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "a", encoding="utf-8") as handle:
            handle.write(text)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", f"change {path}")

    def graph(self, *args: str) -> subprocess.CompletedProcess:
        return self.run("python3", "scripts/ci-graph.py", *args)

    def plan(self, *args: str, registry: str = "ghcr.io", repository: str = CANONICAL) -> dict:
        out = self.graph("plan", "--registry", registry, "--repository", repository, *args)
        if out.returncode != 0:
            raise AssertionError(f"plan failed: {out.stderr}")
        return json.loads(out.stdout)

    def key(self, image: str, rev: str = "HEAD") -> str:
        return self.graph("key", image, "--rev", rev).stdout.strip()

    def pin(self, parent: str = "base") -> str:
        pins = dict(p.split(":", 1) for p in json.loads(self.graph("pins").stdout))
        return pins[parent]

    def repin(self, image: str, version: str) -> None:
        """Point an image's ARG BASE_VERSION at another version of its parent, and commit it."""
        path = os.path.join(self.path, f"images/{image}/Dockerfile")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        pinned = [l for l in text.splitlines() if l.startswith("ARG BASE_VERSION=")]
        assert len(pinned) == 1, pinned
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text.replace(pinned[0], f"ARG BASE_VERSION={version}"))
        self.git("commit", "-qam", f"pin {image} to {version}")


def names(plan: dict) -> list[str]:
    return sorted(e["name"] for e in plan["build"])


class RepoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo = Repo(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def main_push(self, **kw) -> dict:
        return self.repo.plan("--event", "push", "--ref-name", "main", "--changed-base", "HEAD^", **kw)


class PlanTests(RepoTest):
    def test_a_dependent_change_builds_only_that_dependent(self):
        self.repo.commit("src/cortex/requirements.txt")
        plan = self.main_push()
        self.assertEqual(names(plan), ["cortex"])
        self.assertIsNone(plan["base"])
        self.assertEqual(plan["digest_refs"], [f"base:{self.repo.pin()}"])
        entry = plan["dependent"][0]
        self.assertEqual(entry["inputs_key"], self.repo.key("cortex"))
        self.assertEqual((entry["tag_source"], entry["publish"]), ("branch", "true"))

    def test_a_base_change_builds_only_base(self):
        self.repo.commit("images/base/Dockerfile")
        plan = self.main_push()
        self.assertEqual(names(plan), ["base"])
        self.assertEqual(plan["dependent"], [])

    def test_a_parent_change_never_rebuilds_the_images_pinned_to_it(self):
        # app pins golang exactly, as golang pins base: a golang change builds golang alone, and
        # app moves only when its own pin does.
        self.repo.commit("images/golang/Dockerfile")
        self.assertEqual(names(self.main_push()), ["golang"])
        self.repo.repin("app", "9.9.9")
        plan = self.main_push()
        self.assertEqual(names(plan), ["app"])
        self.assertEqual(plan["digest_refs"], ["golang:9.9.9"])
        self.assertEqual(plan["dependent"][0]["from"], "golang")

    def test_consumer_changes_build_nothing(self):
        for path in ("README.md", ".github/workflows/publish.yml", "scripts/release.sh", ".ci/smoke/Dockerfile"):
            self.repo.commit(path)
        plan = self.repo.plan("--event", "push", "--ref-name", "main", "--changed-base", "HEAD~4")
        self.assertTrue(plan["empty"])

    def test_catch_alls_rebuild_every_image(self):
        for path in (".dockerignore", ".ci/graph.json", ".github/actions/build-image/action.yml"):
            plan = self.repo.plan("--ref-name", "main", "--changed-file", path)
            self.assertEqual(plan["count"], len(IMAGES), path)
            self.assertEqual(plan["reasons"]["base"], f"shared:{path}")

    def test_a_pull_request_builds_but_never_publishes(self):
        plan = self.repo.plan("--event", "pull_request", "--ref-name", "feature",
                              "--changed-file", "src/cortex/requirements.txt")
        self.assertEqual(names(plan), ["cortex"])
        self.assertEqual((plan["build"][0]["tag_source"], plan["build"][0]["publish"]), ("skip", "false"))

    def test_only_the_canonical_repository_publishes(self):
        change = ("--ref-name", "main", "--changed-file", "src/cortex/requirements.txt")
        publish = lambda **kw: self.repo.plan(*change, **kw)["build"][0]["publish"]
        self.assertEqual(publish(), "true")
        self.assertEqual(publish(registry="registry.internal.example"), "true")
        self.assertEqual(publish(repository="someone-else/coder-images"), "false")
        self.assertEqual(publish(repository="Someone-Else/Coder-Images"), "false")
        # A platform that supplies no repository is unknown, not denied.
        self.assertEqual(publish(repository=""), "true")

    def test_a_release_tag_promotes_one_image_and_builds_nothing(self):
        plan = self.repo.plan("--event", "tag", "--ref", "refs/tags/cortex-v2.1.0")
        self.assertEqual(plan["count"], 0)
        self.assertEqual(plan["release"], {"image": "cortex", "version": "2.1.0",
                                           "key": self.repo.key("cortex"), "publish": "true"})
        # A base release touches no dependent, not even one pinned to that version. The pin is set
        # here, not read from the tree, which may pin a release candidate while one is tested.
        self.repo.repin("cortex", "9.9.9")
        plan = self.repo.plan("--event", "tag", "--ref", "refs/tags/base-v9.9.9")
        self.assertEqual((plan["count"], plan["release"]["image"]), (0, "base"))
        fork = self.repo.plan("--event", "tag", "--ref", "refs/tags/cortex-v2.1.0",
                              repository="someone-else/coder-images")
        self.assertEqual(fork["release"]["publish"], "false")

    def test_a_release_candidate_builds_its_image_from_the_tagged_commit(self):
        plan = self.repo.plan("--event", "tag", "--ref", "refs/tags/cortex-v2.0.0-rc.1")
        self.assertIsNone(plan["release"])
        self.assertEqual(names(plan), ["cortex"])
        entry = plan["build"][0]
        self.assertEqual((entry["tag_source"], entry["version"], entry["publish"]),
                         ("rc", "2.0.0-rc.1", "true"))
        self.assertEqual(plan["digest_refs"], [f"base:{self.repo.pin()}"])
        # A base candidate builds base alone.
        plan = self.repo.plan("--event", "tag", "--ref", "refs/tags/base-v2.0.0-rc.1")
        self.assertEqual((names(plan), plan["base"]["version"]), (["base"], "2.0.0-rc.1"))

    def test_every_image_can_be_released_on_its_own(self):
        for image in IMAGES:
            release = self.repo.plan("--event", "tag", "--ref", f"refs/tags/{image}-v2.0.0")["release"]
            self.assertEqual((release["image"], release["version"]), (image, "2.0.0"))

    def test_a_push_on_a_tag_ref_is_not_a_release(self):
        # CI must classify from the ref: a tag push reports event_name=push.
        plan = self.repo.plan("--event", "push", "--ref", "refs/tags/cortex-v2.1.0",
                              "--ref-name", "cortex-v2.1.0")
        self.assertTrue(plan["empty"])
        self.assertIsNone(plan["release"])

    def test_malformed_input_fails_loudly(self):
        for args in (("--event", "tag", "--ref", "refs/tags/not-a-release"),
                     ("--event", "tag", "--ref", "refs/tags/nope-v1.0.0"),
                     ("--event", "tag", "--ref", "refs/tags/cortex-v2.0.0-rc1"),
                     ("--images", "nope"),
                     ("--ref-name", "main", "--changed-base", "0" * 40)):
            self.assertEqual(self.repo.graph("plan", "--registry", "ghcr.io", *args).returncode, 2, args)

    def test_dispatch_overrides(self):
        self.assertEqual(names(self.repo.plan("--ref-name", "main", "--images", "golang,podman")),
                         ["golang", "podman"])
        plan = self.repo.plan("--all", "--ref-name", "main")
        self.assertEqual(plan["count"], len(IMAGES))
        # One digest per distinct parent pin: dependents may pin different versions of the
        # same parent (ubuntu-desktop can lag base), so derive the expectation from the graph.
        pins = sorted(set(json.loads(self.repo.graph("pins").stdout)))
        self.assertEqual(plan["digest_refs"], pins)
        self.assertEqual(plan["base"]["name"], "base")
        self.assertEqual(sorted(e["name"] for e in plan["standalone"]), ["kali-desktop", "podman"])
        self.assertEqual(sorted(e["name"] for e in plan["dependent"]), sorted(DEPENDENTS))

    def test_a_force_push_that_reverts_a_change_rebuilds_it(self):
        base = self.repo.git("rev-parse", "HEAD")
        self.repo.commit("src/cortex/requirements.txt")
        pushed = self.repo.git("rev-parse", "HEAD")
        self.repo.git("tag", "keep", pushed)  # the old tip stays in the clone
        self.repo.git("reset", "-q", "--hard", base)
        self.repo.commit("README.md")
        plan = self.repo.plan("--event", "push", "--ref-name", "main", "--changed-base", pushed)
        self.assertEqual(names(plan), ["cortex"])

    def test_upgrade_base_alone_refreshes_the_images_that_allow_it(self):
        plan = self.repo.plan("--event", "workflow_dispatch", "--ref-name", "main",
                              "--upgrade-base", "true", "--changed-base", "HEAD")
        self.assertEqual({e["name"]: e["apt_upgrade_arg"] for e in plan["build"]},
                         {"base": "true", "kali-desktop": "true"})

    def test_no_compare_ref_builds_nothing(self):
        self.assertTrue(self.repo.plan("--event", "push", "--ref-name", "main")["empty"])

    def test_the_package_refresh_is_opt_in_and_per_image(self):
        args = lambda plan: {e["name"]: e["apt_upgrade_arg"] for e in plan["build"]}
        refreshed = args(self.repo.plan("--all", "--ref-name", "main", "--upgrade-base", "true"))
        self.assertEqual({n for n, v in refreshed.items() if v == "true"}, {"base", "kali-desktop"})
        self.assertTrue(all(v == "" for n, v in refreshed.items() if n not in ("base", "kali-desktop")))
        default = args(self.repo.plan("--all", "--ref-name", "main"))
        self.assertEqual((default["base"], default["kali-desktop"]), ("false", "false"))


class KeyTests(RepoTest):
    def test_the_key_follows_exactly_the_inputs_that_rebuild_an_image(self):
        cortex, golang = self.repo.key("cortex"), self.repo.key("golang")
        self.repo.commit("README.md")
        self.assertEqual(self.repo.key("cortex"), cortex)
        self.repo.commit("src/cortex/requirements.txt")
        self.assertNotEqual(self.repo.key("cortex"), cortex)
        self.assertEqual(self.repo.key("golang"), golang)
        self.assertEqual(self.repo.key("cortex", "HEAD^"), cortex)
        self.repo.commit(".ci/graph.json", "\n")
        self.assertNotEqual(self.repo.key("golang"), golang)


class CheckTests(RepoTest):
    def check(self) -> subprocess.CompletedProcess:
        return self.repo.graph("check")

    def test_the_tree_satisfies_the_graph(self):
        self.assertEqual(self.check().returncode, 0, self.check().stderr)

    def test_an_unclassified_file_fails_by_its_real_name(self):
        for path in ("Makefile", "docs/notes.md", "café.md"):
            self.repo.commit(path)
            out = self.check()
            self.assertEqual(out.returncode, 1, path)
            self.assertIn(f"{path}: no image owns it", out.stderr)
            self.repo.git("rm", "-q", path)
            self.repo.git("commit", "-q", "-m", "remove")

    def test_an_ungated_apt_upgrade_fails(self):
        self.repo.commit("images/podman/Dockerfile", "RUN apt-get -y upgrade\n")
        self.assertIn("podman: apt upgrade must sit behind", self.check().stderr)

    def test_a_build_step_after_the_provenance_args_fails(self):
        self.repo.commit("images/podman/Dockerfile", "RUN true\n")
        self.assertIn("podman: declare ARG VERSION/GIT_SHA/BUILD_CREATED after", self.check().stderr)

    def test_a_dependent_must_pin_a_real_base_version(self):
        path = os.path.join(self.repo.path, "images/cortex/Dockerfile")
        pin = f"ARG BASE_VERSION={self.repo.pin()}"
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn(pin, text)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text.replace(pin, "ARG BASE_VERSION=latest"))
        self.assertIn("cortex: needs ARG BASE_VERSION", self.check().stderr)

    def check_with(self, image: str, text: str) -> str:
        """check's errors with `text` appended to an image's Dockerfile, which is then restored."""
        path = os.path.join(self.repo.path, f"images/{image}/Dockerfile")
        with open(path, encoding="utf-8") as handle:
            original = handle.read()
        try:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(text)
            return self.check().stderr
        finally:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(original)

    def test_image_content_under_the_home_directory_fails(self):
        # A workspace's home volume hides /home/coder, so nothing the image puts there survives.
        cases = [
            ("cortex", "RUN python3 -m venv /home/coder/.venv\n", "RUN writes or reads under /home/coder"),
            ("cortex", "RUN mkdir -p \\\n    ~/.config\n", "RUN writes or reads under"),
            ("infra", "RUN echo 'x' >> $HOME/.zshrc\n", "RUN writes or reads under"),
            ("infra", "COPY src/infra/requirements.txt ${HOME}/r.txt\n", "COPY writes or reads under"),
            ("base", "WORKDIR /home/coder\n", "WORKDIR writes or reads under"),
            ("cortex", "ENV VIRTUAL_ENV=/home/coder/.venv\n", "ENV VIRTUAL_ENV points into /home/coder"),
            ("cortex", 'ENV PATH="/home/coder/.local/bin:$PATH"\n', "ENV PATH points into"),
            ("golang", "ENV GOPATH=/home/coder/gopath\n", "ENV GOPATH points into"),
            ("podman", "RUN pipx install black\n", "RUN as coder installs or configures under"),
            ("base", "RUN git config --global init.defaultBranch main\n", "RUN as coder installs"),
            # golang ends with GOPATH in the home directory; app inherits it.
            ("golang", "RUN go install example.com/x@v1.0.0\n", "RUN runs go with GOPATH or GOBIN"),
            ("app", "USER root\nRUN go install example.com/x@v1.0.0\n", "app: images/app/Dockerfile"),
        ]
        for image, text, message in cases:
            with self.subTest(image=image, text=text):
                self.assertIn(message, self.check_with(image, text))

    def test_runtime_defaults_and_other_homes_pass(self):
        for image, text in [
            ("golang", "ENV GOPATH=/home/coder/go GOBIN=/home/coder/go/bin\n"),
            ("golang", "RUN GOBIN=/usr/local/bin GOPATH=/tmp/gopath go install example.com/x@v1.0.0\n"),
            ("podman", "USER root\nRUN pipx install black && npm install -g pnpm\n"),
            ("base", "RUN apt-get install -y foo=1.2~rc1 && echo ~root\n"),
        ]:
            with self.subTest(image=image, text=text):
                self.assertNotIn("/home/coder", self.check_with(image, text))

    def test_a_from_chain_must_end_at_a_real_image(self):
        path = os.path.join(self.repo.path, ".ci/graph.json")
        with open(path, encoding="utf-8") as handle:
            graph = json.load(handle)
        graph["images"]["golang"]["from"] = "app"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(graph, handle)
        self.assertIn("golang: its from chain leads back to itself", self.check().stderr)
        graph["images"]["golang"]["from"] = "nope"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(graph, handle)
        self.assertIn("golang: from 'nope' must name an image in the graph", self.check().stderr)


class ReleaseDecisionTests(unittest.TestCase):
    decide = staticmethod(plan_release.decide)

    def code(self, image, version, tags=(), source=""):
        return self.decide(image, version, IMAGES, list(tags), source)["code"]

    def test_decisions(self):
        self.assertEqual(self.code("nope", "2.0.0"), "unknown_image")
        self.assertEqual(self.code("cortex", "2.0"), "bad_version")
        self.assertEqual(self.code("cortex", "2.0.0", ["2.0.0"]), "already_published")
        self.assertEqual(self.code("cortex", "1.1.6"), "below_minimum")
        self.assertEqual(self.code("cortex", "2.1.0", ["src-abc"], "src-def"), "not_built")
        self.assertEqual(self.code("cortex", "2.1.0", ["2.0.0", "src-abc"], "src-abc"), "ok")
        self.assertEqual(self.code("cortex", "2.0.0-rc.1"), "ok")
        self.assertEqual(self.code("cortex", "2.0.0-rc.1", ["2.0.0-rc.1"]), "already_published")
        self.assertEqual(self.code("cortex", "1.2.0-rc.1"), "below_minimum")
        self.assertEqual(self.code("cortex", "2.0.0-beta"), "bad_version")

    def test_only_full_versions_count_as_published(self):
        noise = ["latest", "main", "main-f94ffb5", "buildcache", "src-abc", "pr-3", "2.0", "2", "10.0.0", "2.0.0"]
        self.assertEqual(plan_release.published_versions(noise), ["2.0.0", "10.0.0"])

    def test_floating_tags_move_only_for_the_highest_version(self):
        tags = ["2.0.0", "2.1.0", "2.1", "2", "latest", "src-abc", "3.0.0-rc.1"]
        floating = plan_release.floating_tags
        self.assertEqual(floating("2.1.1", tags), ["2.1", "2", "latest"])
        self.assertEqual(floating("2.0.1", tags), ["2.0"])  # a fix for an older line
        self.assertEqual(floating("3.0.0", tags), ["3.0", "3", "latest"])  # candidates don't count
        self.assertEqual(floating("2.0.0", []), ["2.0", "2", "latest"])  # first release

    def test_numbering_suggestions(self):
        self.assertEqual(plan_release.suggest_next(["1.1.5", "latest"])["next"], ["2.0.0"])
        self.assertEqual(plan_release.suggest_next(["1.1.5", "2.1.0"])["next"], ["2.1.1", "2.2.0", "3.0.0"])


class ReleaseScriptTests(RepoTest):
    """scripts/release.sh end to end, against a local bare remote and fixture tag lists."""

    def setUp(self):
        super().setUp()
        self.remote = os.path.join(self.tmp, "remote.git")
        self.repo.git("clone", "-q", "--bare", self.repo.path, self.remote)
        self.repo.git("remote", "add", "origin", self.remote)
        self.repo.git("fetch", "-q", "origin")
        self.tags = os.path.join(self.tmp, "tags")

    def published(self, *tags: str) -> None:
        with open(self.tags, "w", encoding="utf-8") as handle:
            handle.write("".join(f"{t}\n" for t in tags))

    def built(self, image: str) -> str:
        return f"src-{self.repo.key(image)}"

    def release(self, image: str, version: str, **env) -> subprocess.CompletedProcess:
        return self.repo.run("bash", "scripts/release.sh", image, version, "--dry-run",
                             env={"RELEASE_TAGS_FILE": self.tags, **env})

    def assertRefused(self, out, text):
        self.assertNotEqual(out.returncode, 0, out.stdout)
        self.assertIn(text, out.stderr)

    def test_a_release_needs_main_to_have_built_the_image(self):
        self.published("2.0.0")
        self.assertRefused(self.release("cortex", "2.1.0"), "main has not published cortex")
        self.published("2.0.0", self.built("cortex"))
        out = self.release("cortex", "2.1.0")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("Would run: git tag cortex-v2.1.0", out.stdout)

    def test_version_rules(self):
        self.published("2.0.0", self.built("cortex"))
        self.assertRefused(self.release("cortex", "2.0.0"), "already published")
        self.assertRefused(self.release("cortex", "1.0.3"), "releases start at 2.0.0")

    def test_a_candidate_is_not_cut_with_release_sh(self):
        self.published(self.built("cortex"))
        self.assertRefused(self.release("cortex", "2.0.0-rc.1"), "push a tag by hand")

    def test_an_unreachable_registry_refuses(self):
        out = self.release("cortex", "9.9.9", RELEASE_TAGS_FILE="", REGISTRY="host.invalid")
        self.assertRefused(out, "could not check")

    def test_the_owner_defaults_to_the_remote_s_owner(self):
        # The github remote wins over origin, as it does for the push; IMAGE_OWNER overrides both.
        remote = os.path.join(self.tmp, "Some-Owner", "coder-images.git")
        self.repo.git("clone", "-q", "--bare", self.repo.path, remote)
        self.repo.git("remote", "add", "github", remote)
        self.published(self.built("cortex"))
        out = self.release("cortex", "2.1.0", IMAGE_OWNER="")  # CI's workflow env sets it
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn(f"promotes ghcr.io/some-owner/coder-images-cortex:{self.built('cortex')}", out.stdout)
        out = self.release("cortex", "2.1.0", IMAGE_OWNER="Other")
        self.assertIn("promotes ghcr.io/other/coder-images-cortex:", out.stdout)

    def test_only_the_tip_of_main_is_released(self):
        self.published(self.built("base"))
        self.repo.git("checkout", "-q", "-b", "side")
        self.assertRefused(self.release("base", "9.9.9"), "releases are cut from main")
        self.repo.git("checkout", "-q", "main")
        self.repo.commit("images/base/Dockerfile")
        self.repo.git("push", "-q", "origin", "main")
        self.repo.git("reset", "-q", "--hard", "HEAD~1")
        self.assertRefused(self.release("base", "9.9.9"), "is not the tip of origin/main")
        self.repo.git("pull", "-q", "--ff-only", "origin", "main")
        self.published(self.built("base"))
        self.assertEqual(self.release("base", "9.9.9").returncode, 0)


class PromoteTests(RepoTest):
    """scripts/promote.sh, with a stand-in docker that records what it was asked to do."""

    def promote(self, version: str, published: list[str],
                manifests: dict[str, list[str]] | None = None) -> tuple[subprocess.CompletedProcess, str]:
        """Run promote.sh; `manifests` maps a tag to the platform digests its index lists."""
        bin_dir = os.path.join(self.tmp, "bin")
        index_dir = os.path.join(self.tmp, "indexes")
        os.makedirs(bin_dir, exist_ok=True)
        os.makedirs(index_dir, exist_ok=True)
        for tag, digests in (manifests or {}).items():
            with open(os.path.join(index_dir, f"{tag}.json"), "w", encoding="utf-8") as handle:
                json.dump({"manifests": [{"digest": d} for d in digests]}, handle)
        log = os.path.join(self.tmp, "docker.log")
        with open(log, "w", encoding="utf-8"):
            pass
        with open(os.path.join(bin_dir, "docker"), "w", encoding="utf-8") as handle:
            # --raw answers from indexes/<tag>.json; the reference is the last argument.
            handle.write(f'#!/bin/sh\necho "$*" >> {log}\n'
                         'case "$*" in\n'
                         f'  *--raw*) for arg; do ref=$arg; done; cat "{index_dir}/${{ref##*:}}.json" || exit 1 ;;\n'
                         '  *--format*) echo sha256:abc ;;\n'
                         'esac\n')
        os.chmod(os.path.join(bin_dir, "docker"), 0o755)
        tags = os.path.join(self.tmp, "tags")
        with open(tags, "w", encoding="utf-8") as handle:
            handle.write("".join(f"{t}\n" for t in published))
        out = self.repo.run("bash", "scripts/promote.sh", "registry.example/o/coder-images", "cortex",
                            version, "abc", env={"PATH": f"{bin_dir}:{os.environ['PATH']}",
                                                 "RELEASE_TAGS_FILE": tags})
        with open(log, encoding="utf-8") as handle:
            return out, handle.read()

    def test_a_re_run_of_the_same_release_only_re_applies_the_floating_tags(self):
        published = ["2.0.0", "2.1.0", "2.1", "2", "latest", "src-abc"]
        out, log = self.promote("2.1.0", published,
                                {"2.1.0": ["sha256:arm", "sha256:amd"], "src-abc": ["sha256:amd", "sha256:arm"]})
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("re-applying only its floating tags", out.stdout)
        create = next(line for line in log.splitlines() if " create " in line)
        self.assertNotIn("--annotation", create)
        self.assertNotIn("--tag registry.example/o/coder-images-cortex:2.1.0", create)
        self.assertIn("--tag registry.example/o/coder-images-cortex:latest", create)
        self.assertTrue(create.endswith("coder-images-cortex:2.1.0"), create)

    def test_a_published_version_is_never_repointed_at_a_moved_source(self):
        # src-<key> can move under the same key (an upgrade_base rebuild); the version must not.
        out, log = self.promote("2.1.0", ["2.1.0", "latest", "src-abc"],
                                {"2.1.0": ["sha256:old"], "src-abc": ["sha256:new"]})
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("already published with different images", out.stdout)
        self.assertNotIn(" create ", log)

    def test_a_release_moves_only_the_floating_tags_it_heads(self):
        out, log = self.promote("2.0.1", ["2.0.0", "2.1.0", "src-abc"])
        self.assertEqual(out.returncode, 0, out.stderr)
        create = next(line for line in log.splitlines() if " create " in line)
        self.assertIn("coder-images-cortex:2.0.1 ", create)
        self.assertIn("coder-images-cortex:2.0 ", create)
        self.assertNotIn(":latest", create)
        self.assertNotIn("coder-images-cortex:2 ", create)
        self.assertTrue(create.endswith("coder-images-cortex:src-abc"))
        out, log = self.promote("2.2.0", ["2.0.0", "2.1.0", "src-abc"])
        self.assertIn(":latest", log)


class ReleaseTagGateTests(RepoTest):
    """scripts/validate-release-tag.sh: CI's backstop when a tag is pushed."""

    def setUp(self):
        super().setUp()
        self.tags = os.path.join(self.tmp, "tags")
        with open(self.tags, "w", encoding="utf-8") as handle:
            handle.write("2.0.0\nlatest\n")
        self.tagged = self.repo.git("rev-parse", "HEAD")
        self.repo.commit("README.md")  # main moves on after the tag is pushed
        self.repo.git("update-ref", "refs/remotes/test/main", "HEAD")
        self.repo.git("checkout", "-q", "--detach", self.tagged)

    def gate(self, tag: str, attempt: str = "1") -> int:
        return self.repo.run("bash", "scripts/validate-release-tag.sh", "ghcr.io", "o",
                             f"refs/tags/{tag}", "test/main",
                             env={"RELEASE_TAGS_FILE": self.tags, "RUN_ATTEMPT": attempt}).returncode

    def test_the_gate(self):
        self.assertEqual(self.gate("cortex-v2.1.0"), 0, "a tag behind main's tip is on main")
        self.assertEqual(self.gate("cortex-v2.0.0"), 1, "a published version is refused")
        self.assertEqual(self.gate("cortex-v2.0.0", "2"), 0, "a re-run may find its own version")
        self.repo.commit("LICENSE")  # a commit main never had (README would recreate main's commit)
        self.assertEqual(self.gate("cortex-v2.1.0"), 1, "a tag off main is refused")
        self.assertEqual(self.gate("cortex-v2.1.0", "2"), 1, "a re-run does not excuse that")
        self.assertEqual(self.gate("cortex-v2.1.0-rc.1"), 0, "a release candidate may come from any branch")
        with open(self.tags, "a", encoding="utf-8") as handle:
            handle.write("2.1.0-rc.1\n")
        self.assertEqual(self.gate("cortex-v2.1.0-rc.1"), 1, "but may not reuse a published candidate")


class ResolveTests(RepoTest):
    """scripts/ci-resolve.sh, the resolve job both platforms run."""

    def setUp(self):
        super().setUp()
        self.repo.commit("LICENSE")  # a parent commit to compare against

    def resolve(self, **env) -> tuple[subprocess.CompletedProcess, dict]:
        output = os.path.join(self.tmp, "output")
        open(output, "w").close()
        base = {"EVENT": "push", "PR_BASE_SHA": "",
                "REF": "refs/heads/main", "REF_NAME": "main", "DEFAULT_BRANCH": "main",
                "REGISTRY": "host.invalid", "OWNER": "o", "REPOSITORY": CANONICAL,
                "GITHUB_OUTPUT": output}
        if "BEFORE" not in env:  # a root commit has no HEAD^
            base["BEFORE"] = self.repo.git("rev-parse", "HEAD^")
        out = self.repo.run("bash", "scripts/ci-resolve.sh", env={**base, **env})
        with open(output, encoding="utf-8") as handle:
            values = dict(line.split("=", 1) for line in handle.read().splitlines() if "=" in line)
        return out, values

    def test_a_docs_push_builds_nothing(self):
        self.repo.commit("README.md")
        out, values = self.resolve()
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual((values["base"], values["dependent"], values["release"]), ("", "[]", ""))

    def test_an_unresolvable_base_pin_blocks_only_its_dependents(self):
        # base and the standalone images must still build, or a first base release is impossible.
        self.repo.commit("src/cortex/requirements.txt")
        self.repo.commit("images/podman/Dockerfile")
        out, values = self.resolve(BEFORE=self.repo.git("rev-parse", "HEAD~2"))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("will not build", out.stdout)
        self.assertEqual([e["name"] for e in json.loads(values["standalone"])], ["podman"])
        dependent = json.loads(values["dependent"])
        self.assertEqual([(d["name"], d["base_digest"]) for d in dependent], [("cortex", "")])

    def test_an_image_built_on_golang_resolves_golang_s_pin(self):
        self.repo.commit("images/app/Dockerfile")
        out, values = self.resolve()
        self.assertEqual(out.returncode, 0, out.stderr)
        [app] = json.loads(values["dependent"])
        self.assertEqual(app["base_name"], f"host.invalid/o/coder-images-golang:{self.repo.pin('golang')}")

    def test_a_pull_request_skips_a_dependent_whose_base_is_unreleased(self):
        self.repo.commit("src/cortex/requirements.txt")
        out, values = self.resolve(EVENT="pull_request", PR_BASE_SHA=self.repo.git("rev-parse", "HEAD^"),
                                   REF="refs/pull/1/merge", REF_NAME="1/merge")
        self.assertEqual(out.returncode, 0, out.stderr)
        dependent = json.loads(values["dependent"])
        self.assertEqual([(d["name"], d["base_digest"]) for d in dependent], [("cortex", "")])

    def test_a_repository_s_first_commit_on_main_builds_every_image(self):
        # A new branch, or main pushed with history, has no diff and builds nothing; a root commit
        # on the default branch has nothing published yet either, so it builds everything.
        new_branch = {"BEFORE": "0" * 40}
        for env in ({"REF": "refs/heads/feature", "REF_NAME": "feature"}, {}):
            out, values = self.resolve(**new_branch, **env)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual((values["base"], values["standalone"], values["dependent"]), ("", "[]", "[]"), env)
        self.repo.git("checkout", "-q", "--orphan", "first")
        self.repo.git("commit", "-q", "-m", "first")
        out, values = self.resolve(**new_branch)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(values["base"])["name"], "base")
        self.assertEqual(sorted(e["name"] for e in json.loads(values["standalone"])), ["kali-desktop", "podman"])
        self.assertEqual(sorted(e["name"] for e in json.loads(values["dependent"])), sorted(DEPENDENTS))
        # ...but only on the default branch.
        out, values = self.resolve(**new_branch, REF="refs/heads/feature", REF_NAME="feature")
        self.assertEqual(values["base"], "")

    def test_a_mixed_case_owner_publishes_under_a_lowercase_prefix(self):
        self.repo.commit("images/app/Dockerfile")
        out, values = self.resolve(OWNER="Some-Owner")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(values["image_prefix"], "host.invalid/some-owner/coder-images")
        [app] = json.loads(values["dependent"])
        self.assertTrue(app["base_name"].startswith("host.invalid/some-owner/coder-images-golang:"))

    def test_a_tag_push_is_a_release(self):
        tags = os.path.join(self.tmp, "tags")
        open(tags, "w").close()
        self.repo.git("update-ref", "refs/remotes/origin/main", "HEAD")
        out, values = self.resolve(REF="refs/tags/cortex-v2.1.0", REF_NAME="cortex-v2.1.0",
                                   BEFORE="0" * 40, RELEASE_TAGS_FILE=tags, REGISTRY="ghcr.io")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(values["release"])["image"], "cortex")
        self.assertEqual(values["dependent"], "[]")

    def test_a_release_candidate_tag_builds_off_main(self):
        tags = os.path.join(self.tmp, "tags")
        open(tags, "w").close()
        out, values = self.resolve(REF="refs/tags/podman-v2.0.0-rc.1", REF_NAME="podman-v2.0.0-rc.1",
                                   BEFORE="0" * 40, RELEASE_TAGS_FILE=tags, REGISTRY="ghcr.io")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(values["release"], "")
        standalone = json.loads(values["standalone"])
        self.assertEqual([(e["name"], e["version"]) for e in standalone], [("podman", "2.0.0-rc.1")])

    def test_a_tag_that_cannot_publish_fails(self):
        tags = os.path.join(self.tmp, "tags")
        open(tags, "w").close()
        out, _ = self.resolve(REF="refs/tags/podman-v2.0.0-rc.1", REF_NAME="podman-v2.0.0-rc.1",
                              BEFORE="0" * 40, RELEASE_TAGS_FILE=tags, REPOSITORY="someone-else/coder-images")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("would build without publishing", out.stdout)

    def test_an_empty_context_is_refused(self):
        out, _ = self.resolve(OWNER="")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("OWNER is empty", out.stdout)


class BuildActionTests(unittest.TestCase):
    # Inputs of the actions the build action uses. Gitea and Forgejo runners pass a composite action's
    # inputs on to the actions nested in it, so a shared name silently overrides theirs: an
    # input called `image` made setup-qemu pull the image being built as its QEMU helper.
    NESTED = {"image", "platforms", "cache-image", "version", "name", "driver", "driver-opts",
              "endpoint", "install", "use", "config", "config-inline", "append", "cleanup",
              "context", "file", "tags", "push", "load", "labels", "target", "outputs",
              "build-args", "cache-from", "cache-to", "provenance", "github-token", "ecr",
              "logout"}

    def test_no_input_shares_a_name_with_a_nested_action_input(self):
        with open(os.path.join(ROOT, ".github/actions/build-image/action.yml"), encoding="utf-8") as f:
            text = f.read()
        block = text.split("\ninputs:\n", 1)[1].split("\noutputs:\n", 1)[0]
        names = {line.split(":")[0].strip() for line in block.splitlines()
                 if line.startswith("  ") and not line.startswith("   ") and line.strip().endswith(":")}
        self.assertIn("image_name", names)
        self.assertEqual(names & self.NESTED, set())


if __name__ == "__main__":
    unittest.main()
