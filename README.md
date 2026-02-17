# coder-images

Container images for [Coder](https://coder.com) workspaces. Supports dual-platform CI/CD — develop on Gitea (`gitea.labgophers.com`), release publicly on GitHub (`ghcr.io`).

## Images

| Image | Base | Purpose |
|-------|------|---------|
| `base` | Ubuntu | Foundation image with common tools |
| `golang` | `base` | Go development environment |
| `cortex` | `base` | Palo Alto Cortex (XSOAR/XSIAM) development |
| `terraform` | `base` | Terraform and Terragrunt |
| `ubuntu-desktop` | `base` | Ubuntu with desktop environment |
| `podman` | Fedora | Podman container runtime |
| `kali-desktop` | Kali | Kali Linux desktop |

## Versioning

Versions are generated automatically from git tags — no manual version files.

| Git Action | Tags Created |
|------------|-------------|
| Push to `main` | `latest`, `main-<sha>` |
| Tag `v1.2.3` | `1.2.3`, `1.2`, `1`, `latest` |
| Pull request | `pr-<number>` (no push) |

## Usage

### Development (Gitea)

```bash
git push gitea main
# → Builds on Gitea, pushes to gitea.labgophers.com
```

### Release (GitHub)

```bash
./scripts/release-to-github.sh
# Syncs to GitHub and optionally creates a version tag

# Or manually:
git tag v1.2.0
git push github v1.2.0
# → Pushes to ghcr.io/chrisbalmer/coder-images-*
```

### Pull Images

```bash
# Development
docker pull gitea.labgophers.com/chrisbalmer/coder-images-golang:latest

# Production (always use digest)
docker pull ghcr.io/chrisbalmer/coder-images-golang@sha256:...
./scripts/get-digest.sh golang 1.2.0  # get the digest for a tag
```

### Local Build

```bash
# Default (uses ghcr.io base)
docker build -f images/golang/Dockerfile .

# With specific base tag or registry
docker build -f images/golang/Dockerfile \
  --build-arg REGISTRY=gitea.labgophers.com \
  --build-arg IMAGE_OWNER=chrisbalmer \
  --build-arg BASE_TAG=latest .
```

## CI/CD Pipeline

Three jobs run in order:

1. **`build-base`** — Builds the `base` image, outputs its digest
2. **`build-independent`** — Builds `podman` and `kali-desktop` in parallel
3. **`build-dependent`** — Waits for `build-base`, then builds `golang`, `cortex`, `terraform`, `ubuntu-desktop` in parallel using the base digest

Dependent images reference `base` by digest (not tag) to guarantee consistency and avoid race conditions.

## Workflow Files

| File | Platform | Purpose |
|------|----------|---------|
| `.github/workflows/publish.yml` | GitHub Actions | Production builds → `ghcr.io` |
| `.gitea/workflows/publish.yml` | Gitea Actions | Dev builds → `gitea.labgophers.com` |
| `.github/workflows/publish-unified.yml` | Either | Auto-detects platform |

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/release-to-github.sh` | Sync Gitea → GitHub with optional version tag |
| `scripts/get-digest.sh` | Get digest of a published image |
| `scripts/test-dockerfile-args.sh` | Validate Dockerfiles support both registries |
