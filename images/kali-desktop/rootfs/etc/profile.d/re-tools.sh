# Paths and settings for the reverse-engineering tools in this image. Read by login shells
# through /etc/profile, by every zsh through /etc/zsh/zshenv (so also by a command run over SSH),
# and by interactive bash through /etc/bash.bashrc. Safe to read more than once.

re_tools_path_prepend() {
    case ":${PATH}:" in
        *":$1:"*) ;;
        *) PATH="$1${PATH:+:${PATH}}" ;;
    esac
}
# Lowest priority first: each goes in front of the ones before it. The user's own tools
# (~/.local/bin, and `dotnet tool install -g` in ~/.dotnet/tools) persist with the home volume
# and win over the image's.
re_tools_path_prepend /opt/dotnet-tools
re_tools_path_prepend /opt/venvs/re/bin
re_tools_path_prepend "${HOME}/.dotnet/tools"
re_tools_path_prepend "${HOME}/.local/bin"
unset -f re_tools_path_prepend
export PATH

export VIRTUAL_ENV="${VIRTUAL_ENV:-/opt/venvs/re}"
export GHIDRA_INSTALL_DIR="${GHIDRA_INSTALL_DIR:-/usr/share/ghidra}"
export DOTNET_ROOT="${DOTNET_ROOT:-/usr/share/dotnet}"
export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1

# A command run over SSH gets no terminal type, and pwntools warns without one.
if [ -z "${TERM:-}" ]; then
    export TERM=xterm-256color
fi
