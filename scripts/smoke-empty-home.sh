#!/usr/bin/env bash
# Run an image the way a workspace does, with an empty /home/coder, and check that its tools work.
#
# A workspace mounts its persistent home volume over /home/coder, and a Kubernetes volume is not
# seeded from the image, so anything the image put there is hidden. The home here is a tmpfs:
# Docker seeds an empty named volume from the image, which would hide exactly that bug, and bind
# mounts are unreliable on Docker-in-Docker CI runners. NET_RAW and MKNOD are dropped, as a
# hardened workspace pod would drop them.
# The checks run in a login zsh, the coder user's shell, so a profile that resets PATH fails too.
#
# Usage: scripts/smoke-empty-home.sh <image name> <image reference>
#        scripts/smoke-empty-home.sh --has <image name>    exit 0 if the image has checks here

set -euo pipefail

TESTED=" base cortex golang app infra ubuntu-desktop kali-desktop "
if [ "${1:-}" = --has ]; then
    [[ "$TESTED" == *" ${2:?usage: smoke-empty-home.sh --has <image name>} "* ]]
    exit
fi
NAME=${1:?usage: smoke-empty-home.sh <image name> <image reference>}
REF=${2:?usage: smoke-empty-home.sh <image name> <image reference>}

# Every image: the workspace user, passwordless sudo, and a home that really is empty.
COMMON='test "$(id -u):$(id -g)" = 1000:1000
test "$(id -un)" = coder
test "$HOME" = /home/coder
test -z "$(ls -A /home/coder)"
sudo -n true'
BASE='kubectl version --client
yq --version
uv --version
mc --version
fd --version
rg --version
psql --version
mysql --version
command -v nc
gh --version
tea --version
fj version
gitea-mcp -version'
GOLANG='go version
golangci-lint --version
goreleaser --version
air -v
echo "package p" | goimports
gopls version
dlv version'
# Both desktops: KasmVNC (configured and started by the template's kasmvnc module) and Xfce.
DESKTOP='command -v kasmvncserver
/usr/bin/Xkasmvnc -version 2>&1 | grep -i kasmvnc
id -nG | grep -qw ssl-cert
command -v startxfce4
# No screen locker: coder has no password, so a lock screen would lock the user out.
# (Kali keeps the xfce4-screensaver package, which its desktop metapackage needs, minus the daemon.)
for p in xfce4-screensaver light-locker xscreensaver; do if command -v $p || test -e /usr/bin/$p; then echo "screen locker $p can run" >&2; exit 1; fi; done
grep -qx "Pin-Priority: -1" /etc/apt/preferences.d/no-screen-locker'

case "$NAME" in
    base) CHECKS=$BASE ;;
    cortex) CHECKS='demisto-sdk --version
test "$(command -v python3)" = "$VIRTUAL_ENV/bin/python3"
# uv and uvx come from base; the venv keeps the demisto-sdk pinned uv for setup-env.
test "$(uv --version)" = "$(/usr/local/bin/uv --version)"
test "$(uvx --version)" = "$(/usr/local/bin/uvx --version)"
test -x "$VIRTUAL_ENV/bin/uv"
python3 -c "import demisto_sdk"
# The venv belongs to coder, so pip install into it works without sudo.
python3 -c "import os, site, sys; sys.exit(not os.access(site.getsitepackages()[0], os.W_OK))"' ;;
    golang) CHECKS=$GOLANG ;;
    app) CHECKS="$GOLANG"'
pnpm --version
node --version
helm version --short' ;;
    infra) CHECKS='ansible --version
ansible-playbook --version
test "$(command -v python3)" = "$VIRTUAL_ENV/bin/python3"
# The venv belongs to coder, so pip install into it works without sudo.
python3 -c "import os, site, sys; sys.exit(not os.access(site.getsitepackages()[0], os.W_OK))"
terraform version
terragrunt --version
helm version --short
kustomize version
flux --version
talosctl version --client --short
cilium version --client
kubeconform -v
kubectl version --client' ;;
    ubuntu-desktop) CHECKS="$BASE
$DESKTOP"'
firefox --version' ;;
    kali-desktop) CHECKS="$DESKTOP"'
test "$(dpkg-divert --truename /usr/bin/xfce4-screensaver)" = /usr/bin/xfce4-screensaver.disabled
git --version
firefox-esr --version
# ping has no file capability and NET_RAW is dropped here, so it uses an ICMP datagram socket,
# which works when net.ipv4.ping_group_range in the network namespace covers the user.
ping -V
cat /proc/sys/net/ipv4/ping_group_range
ping -c 1 -W 5 127.0.0.1
command -v ghidra
# Every Ghidra help module has a search index, so the help window opens.
java -Djava.awt.headless=true -cp /usr/share/ghidra/Ghidra/Framework/Help/lib/javahelp-*.jar /usr/local/lib/ghidra-help-index/GhidraHelpIndex.java --check /usr/share/ghidra
r2 -v
yara --version
python3 -c "import pefile"
PWNLIB_NOTERM=1 python3 -c "import pwn"' ;;
    *)
        echo "smoke-empty-home: no checks for $NAME" >&2
        exit 1 ;;
esac

echo "smoke-empty-home: $NAME ($REF) with an empty /home/coder"
# Layer sizes (uncompressed), oldest first, so a review can see what a change costs every node
# that pulls the image. The build-arg prefix BuildKit records on each RUN is dropped.
docker history --no-trunc --format '{{.Size}}\t{{.CreatedBy}}' "$REF" | tac |
    sed -E 's/\tRUN \|[0-9]+ ([A-Za-z_]+=[^ ]* )*/\tRUN /' | cut -c1-120 || true
docker run --rm \
    --tmpfs /home/coder:uid=1000,gid=1000,mode=0755 \
    --cap-drop NET_RAW --cap-drop MKNOD \
    "$REF" zsh -lc "set -ex
$COMMON
$CHECKS"
echo "smoke-empty-home: $NAME ok"
