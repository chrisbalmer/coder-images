# coder-images

Container images for [Coder](https://coder.com) workspaces, published to
`ghcr.io/chrisbalmer/coder-images-<name>`. Each image is versioned and released on its own, and
built for amd64 and arm64.

**Changing one image builds one image.** Nothing else is rebuilt, re-tagged or renumbered.

## Images

| Image | Base | Purpose |
|-------|------|---------|
| `base` | Ubuntu | Foundation image with common tools |
| `golang` | `base` | Go, delve, gopls, goimports, golangci-lint, goreleaser, air |
| `app` | `golang` | Go and React apps: `golang` plus pnpm and Helm (Node.js 22 comes from `base`) |
| `infra` | `base` | Infrastructure tools: Terraform, Terragrunt, Ansible, Helm, kustomize, Flux, talosctl, Cilium CLI, kubeconform |
| `cortex` | `base` | Palo Alto Cortex (XSOAR/XSIAM) development |
| `ubuntu-desktop` | `base` | Xfce desktop with KasmVNC and Firefox (KasmVNC's Ubuntu 24.04 build until it ships one for 26.04) |
| `podman` | Fedora | Podman container runtime |
| `kali-desktop` | Kali | Xfce desktop with KasmVNC, plus a security-lab toolset: reverse engineering, forensics, crypto/stego, web, exploitation, passwords, Ghidra, YARA, pefile, pwntools |
| `terraform` | `base` | **Deprecated**, replaced by `infra`. No new tags are published; existing tags stay published for workspaces that still use them |

Every image ends as the `coder` user (uid/gid 1000). `golang`, `app`, `infra` and `cortex` run
each of their tools' `--version` as that user during the build, on every architecture, so a tool
that needs root or ships the wrong binary fails the build.

### Nothing under `/home/coder`

A workspace mounts its persistent home volume at `/home/coder`. A Kubernetes volume is not seeded
from the image, so anything an image installs or configures there is hidden. Tools go under
`/usr/local` or `/opt` (Python venvs live in `/opt/venvs/<image>`, owned by `coder` so
`pip install` needs no sudo), and shell or tool configuration goes under `/etc` (`/etc/profile.d/`,
`/etc/gitconfig`). Two checks enforce this:

- `ci-graph.py check` (the validate job) fails a `RUN`, `COPY`, `ADD` or `WORKDIR` that names
  `/home/coder`, `~` or `$HOME`, an `ENV` that points into it, and, as `coder`, installers that
  default into the home directory (`pip --user`, `pipx`, `uv tool`, `npm -g`, `git config
  --global`). Runtime defaults for user data are allowed by name: `GOPATH` and `GOBIN`
  (`HOME_ALLOWED` in the script).
- `scripts/smoke-empty-home.sh` runs `base`, `golang`, `app`, `infra`, `cortex` and both desktops with an empty
  tmpfs at `/home/coder` and checks the user, sudo and every tool. The build action runs it on
  the amd64 image before anything is pushed, and a release runs it on the image it just
  published, pulled fresh. It uses a tmpfs because Docker seeds an empty named volume from the
  image, which would hide exactly this bug. It also prints the image's layer sizes, since every
  node that runs a workspace pulls each changed layer.

### Image or template module?

Not everything a workspace needs belongs in an image. Agents, editors, dotfiles, git identity and
repository clones come from modules in the Coder template instead. The rule:

> **An image holds what every user of it needs, pinned and slow to change. A module holds whatever
> depends on the user or the workspace, needs wiring into Coder, is meant to be shared with other
> templates or other people, or changes faster than an image release is worth.**

For a tool that could go either way:

| Question | Image | Module |
|---|---|---|
| When is the value known? | At build time | At workspace creation: owner, repository, parameters, secrets |
| How often does it change? | Rarely: a base change means a release of every child | Often: a module version bump is one line in the template |
| Where must it live? | `/usr/local`, `/opt`, `/etc` | Under `/home/coder`, which hides anything an image puts there |
| What does it cost per start? | Nothing; it is already in the image | Its install, on every start (the root filesystem is not persistent) |
| What does start-up depend on? | Nothing; the image is pinned by digest and checksums are verified | The tool's download source being up and reachable |
| Who uses it? | Everyone on that image | A per-user choice or an optional toggle |
| Where must it run? | Workspaces on this image family | Any template, including ones that don't use these images |
| Does it need `coder_app`, `coder_script` or `coder_env`? | No | Yes |

A tool can be split across both: the binary in the image, its configuration and credentials from
a module. A module meant for sharing should skip its install when the tool is already present, so
an image can pre-install it to save start time without the module depending on that. It should
install under the home directory, which persists across restarts, rather than `/usr/local`, which
doesn't. These images are public, so nothing specific to one deployment (hostnames, tokens,
personal configuration) goes in them; that comes from the template.

## How it works

| Event | What happens |
|---|---|
| Push to `main` | Images whose inputs changed are built and published as `main`, `main-<sha>` and `src-<key>` |
| Push tag `cortex-v2.1.0` | Nothing is built: main's `cortex` image is tagged `2.1.0`, and `2.1`, `2` and `latest` where it is the highest version |
| Push tag `cortex-v2.1.0-rc.1` | `cortex` is built from the tagged commit, on any branch, and published as `2.1.0-rc.1` only |
| Pull request | Changed images are built, never pushed |
| Docs, scripts, workflows only | Nothing is built |

`latest` is the highest released version, never an unreleased main build. `X.Y` and `X` likewise
follow the highest release in their line, so a fix for an older line (`2.0.1` after `2.1.0`)
moves only `2.0`.

**Releases promote; they never rebuild.** `src-<key>` is a hash of an image's build inputs: its
`images/<name>/` and `src/<name>/` directories plus the shared catch-alls
(`scripts/ci-graph.py key <name>`). A release computes the key at the tagged commit and tags that
exact image (`scripts/promote.sh`), so what ships is what main built. The release also records
its version as an `org.opencontainers.image.version` annotation on the image index. The image's
own `version` label stays `ci/main-<sha>`, because changing a label needs a rebuild.

### The image graph

[`.ci/graph.json`](.ci/graph.json) is the only place images are listed. Each image lives in
`images/<name>/Dockerfile`, and rebuilds when anything under `images/<name>/` or `src/<name>/`
changes (plus optional `extra_paths`). `from` names its base; `apt_upgrade` is explained under
[Refreshing packages](#refreshing-packages).

| `defaults` key | Meaning |
|---|---|
| `publish_repositories` | `owner/name` whose runs may publish; this is what stops a fork, which also reports `ghcr.io` |
| `consumers` | Paths that never change image content; changing only these builds nothing |
| `catch_all` | Shared build inputs (`.dockerignore`, the graph, the build action); changing one rebuilds every image |

Any tracked file that is not owned by an image, a consumer or a catch-all fails
`ci-graph.py check`, so an accidental "rebuild everything" path is caught in review.

## Releasing

```bash
./scripts/release.sh cortex 2.1.0 --dry-run    # check everything, push nothing
./scripts/release.sh cortex 2.1.0
```

`release.sh` refuses unless all of these hold:

- HEAD is the tip of the remote's `main` and the tree is clean.
- Main has already published the image as it is at HEAD. Right after pushing a change, wait for
  main's build to finish.
- The version is `X.Y.Z`, at least `2.0.0`, and not already published.

CI repeats the "not already published" check and requires the tagged commit to be on `main`, so a
hand-pushed or moved tag cannot overwrite a release. **Re-run jobs** on a failed release run is
allowed to find its own version already published: if it holds the same images as `src-<key>`,
only the floating tags are re-applied; if `src-<key>` has moved since, the re-run fails rather
than move the version.

Protect release tags too: add a tag ruleset for `*-v*.*.*` that blocks updates and deletions
(GitHub: **Settings → Rules → Rulesets → New tag ruleset**; the equivalent on any other forge
you release from).

### Release candidates

To try an image before merging, tag the branch commit by hand:

```bash
git tag cortex-v2.1.0-rc.1 && git push origin cortex-v2.1.0-rc.1
```

A candidate builds that one image at the tagged commit and publishes only `2.1.0-rc.1`: never
`latest`, `2.1`, `2` or `src-<key>`. CI refuses a candidate version that is already published.
A candidate of a dependent builds against the base version its Dockerfile pins.

### Choosing a version number

| Change | Version |
|---|---|
| A fix that changes nothing a workspace relies on | patch, `2.0.1` |
| Moves something a workspace could never use, such as content its home volume hid | patch, `2.0.1` |
| Additive: a new tool or package, nothing removed or renamed | minor, `2.1.0` |
| Removes or changes something a workspace relies on: a package, a path, the `coder` user or uid, the OS release | major, `3.0.0` |

For `base`, judge the change by what the dependents inherit: dropping a package from base is a
major change for every image built on it.

## The base pin

A dependent names the base version it builds on in its own Dockerfile. `app` pins `golang` the
same way, with `BASE_NAME=.../coder-images-golang`: everything below applies to it with golang in
the place of base.

```dockerfile
ARG BASE_NAME=ghcr.io/chrisbalmer/coder-images-base
ARG BASE_VERSION=2.0.0
ARG BASE_REF=${BASE_NAME}:${BASE_VERSION}
FROM ${BASE_REF}
```

CI resolves `BASE_VERSION` to a digest in the registry it builds for, and builds `FROM` that
digest. The digest is recorded as the `org.opencontainers.image.base.digest` label. Never edit
`BASE_REF`; CI overrides it.

### Rolling out a new base

A base change reaches a dependent only when that dependent's pin changes, so a base release never
rebuilds anything by surprise:

```bash
# 1. Release the base (after main has built it).
./scripts/release.sh base 2.1.0

# 2. Adopt it: one line per image that should move.
for i in golang cortex infra ubuntu-desktop; do
  sed -i 's/^ARG BASE_VERSION=.*/ARG BASE_VERSION=2.1.0/' "images/$i/Dockerfile"
done
git commit -am 'adopt base 2.1.0' && git push origin main   # builds only those images
```

`app` is one level further down: to move it, release `golang`, then change `ARG BASE_VERSION` in
`images/app/Dockerfile`.

Always release the base before merging pins that adopt it: main cannot build a dependent whose
pinned base is unpublished, and that dependent's job fails. If that happens, release the base,
then **re-run all jobs** of that run. Re-running only the failed job reuses the lookup that
found no base.

## Forcing a build

**Build and Publish Images → Run workflow**:

| Input | Effect |
|---|---|
| `images` | Build these images regardless of what changed, e.g. `cortex,golang` |
| `all` | Build every image |
| `upgrade_base` | Refresh apt packages. On its own it builds every image that allows a refresh (`base`, `kali-desktop`); with `images` or `all` it refreshes those of them selected |

## Architectures

Images are built for `linux/amd64` and `linux/arm64`. Set the repository variable
`BUILD_ARM64` to `false` (GitHub: **Settings → Secrets and variables → Actions → Variables**) to build `linux/amd64`
only. arm64 is emulated on amd64 runners, which makes it most of the build time.

The flag applies to what a run *builds*. A release re-tags main's build, so it carries whatever
architectures main was built with; a release candidate follows the flag at the time it is built.

## Refreshing packages

`apt upgrade` depends on what the mirrors serve today, so an unconditional one changes an image's
digest with no commit. It runs only when a dispatch run sets `upgrade_base`, and only for images
with `"apt_upgrade": true` in the graph: `base`, and `kali-desktop` (whose upstream is a rolling
tag). Dependents never upgrade; they inherit a patched base. `ci-graph.py check` rejects an
`apt upgrade` that is not behind `ARG APT_UPGRADE=false`.

## Registries

By default the workflow publishes to **`ghcr.io/<repository owner>`** with the workflow's own
token. Images land at `<registry>/<owner>/coder-images-<name>`.

To publish somewhere else, set these on the repository (no workflow edit needed):

| Name | Kind | Default |
|---|---|---|
| `REGISTRY` | variable | `ghcr.io` |
| `IMAGE_OWNER` | variable | the repository owner (lowercased, as registry paths must be) |
| `REGISTRY_USERNAME` | secret | the workflow actor |
| `REGISTRY_PASSWORD` | secret | the workflow token |

`publish_repositories` in `.ci/graph.json` decides whether a run may publish at all, so a fork
(which still reports `ghcr.io`) builds but never pushes.

### Publishing to your own registry as well

Forgejo and Gitea Actions run `.github/workflows/` when a repository has no `.forgejo/` or
`.gitea/` directory, so a mirror of this repo on a self-hosted forge can build straight into a
private registry (Harbor, for example):

1. Mirror the repository to your forge under the same `owner/name` (or add it to
   `publish_repositories`), and set the four settings above there.
2. Push `main` to both remotes; each forge builds and publishes to its own registry.
3. Release on each: the scripts read the same names, and `--remote` picks the forge.

```bash
./scripts/release.sh cortex 2.1.0                                   # ghcr.io, remote "origin"
REGISTRY=registry.example.com IMAGE_OWNER=library \
REGISTRY_USERNAME=... REGISTRY_PASSWORD=... \
  ./scripts/release.sh cortex 2.1.0 --remote forge                 # your registry
```

Each forge promotes its own build of the same commit, so the two registries carry the same
versions without replicating between them. Unset, `IMAGE_OWNER` in `release.sh` and
`get-digest.sh` is the owner in the URL of the `github` remote, else `origin` (lowercased); set it
whenever the registry owner differs from that, as for `library` above.

## Consuming images

Pin by digest, not by a moving tag:

```bash
./scripts/get-digest.sh cortex 2.1.0            # digest and pinned reference
./scripts/get-digest.sh --pins                  # every base pin, resolved
docker pull ghcr.io/chrisbalmer/coder-images-cortex@sha256:...
```

Only `<version>` tags never move; `2.1`, `2` and `latest` follow the highest release they cover.

## Local builds

```bash
docker build -f images/cortex/Dockerfile .      # uses the pinned base from ghcr.io
docker build -f images/cortex/Dockerfile \
  --build-arg BASE_NAME=registry.example.com/library/coder-images-base .
```

The build context is the repo root; `.dockerignore` keeps CI files out of it.

## Scripts

| Script | Purpose |
|---|---|
| `release.sh <image> <version>` | Cut one release |
| `get-digest.sh` | Digest of a published image; `--pins` for all base pins |
| `ci-graph.py` | The graph: `check`, `key`, `plan`, `pins`, `images` |
| `ci-resolve.sh` | The resolve job: what to build or release, base digests |
| `promote.sh` | The release job: tags main's `src-<key>` image with a version |
| `validate-release-tag.sh` | CI's refusal of reused or off-main release tags |
| `plan-release.py` | The release decision and next-version hint |
| `base-digest.py` | Resolves `image:version` to a digest over the registry API |
| `validate-ci.sh` | The validate job: graph check, lint, tests |
| `test_ci.py` | Offline tests for all of the above |

## Starting in an empty registry

A dependent can't build until the base version it pins is **released** in the registry it builds
from, so a registry with none of these images yet (a new fork, a private mirror) fills in order:

1. Build every image on `main`. A repository's first commit does this by itself; a fork or a
   mirror arrives with history, and pushing it builds nothing, so run the workflow on `main` by
   hand with **all** checked. Every image publishes its `src-<key>` tags except the dependents,
   which fail with "not in <registry>"; `base` and the standalone images still build.
2. `./scripts/release.sh base <version>` at the version the dependents pin.
3. Re-run **all jobs** of step 1's run; `cortex`, `infra`, `golang` and `ubuntu-desktop` now
   build.
4. Release `golang`, then re-run again so `app` builds on it. Release the rest.

## The 1.x images

The old pipeline released all images under one repo-wide version (last: `1.1.5`; `ubuntu-desktop`
`1.1.9`, `podman` `1.0.2`). Those tags stay in `ghcr.io`, but every image now has its own line,
starting at `2.0.0`, and the 1.x images get no fixes.
