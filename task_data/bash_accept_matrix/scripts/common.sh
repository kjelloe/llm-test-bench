# Shared helpers for scripts/*.sh (trimmed for this task: the real one also
# installs and starts Docker when it is missing).
ensure_docker() {
  command -v docker > /dev/null 2>&1 || [[ -n ${ACCEPT_NO_DOCKER:-} ]] || { echo "docker is not installed" >&2; exit 1; }
}
