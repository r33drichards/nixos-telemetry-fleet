#!/usr/bin/env bash
set -euo pipefail
shopt -s inherit_errexit
# This script is never run with a publication credential.
[[ -z "${CACHIX_AUTH_TOKEN:-}" ]]
[[ "${GITHUB_REPOSITORY:-}" == r33drichards/nixos-telemetry-fleet ]]
case "${1:-}:${GITHUB_EVENT_NAME:-}" in
    qualify:pull_request)
        [[ "${GITHUB_REF:-}" =~ ^refs/pull/[1-9][0-9]*/merge$ ]]
        expected_revision="${HERMES_PR_HEAD_SHA:-}"
        ;;
    qualify:push|prepare:push)
        [[ "${GITHUB_REF:-}" == refs/heads/main ]]
        expected_revision="${GITHUB_SHA:-}"
        ;;
    *) exit 1 ;;
esac
[[ "$expected_revision" =~ ^[0-9a-f]{40}$ ]]
[[ "$(git rev-parse HEAD)" == "$expected_revision" ]]
git diff --quiet HEAD --
[[ -z "$(git ls-files --others --exclude-standard -- candidates/hermes)" ]]

readonly candidate=./candidates/hermes#default
readonly cachix_pin=github:NixOS/nixpkgs/da6dc0e7b26060f2f71ce3ef7088fb56ee44fa36#cachix
readonly store_path_re='^/nix/store/[0123456789abcdfghijklmnpqrsvwxyz]{32}-[a-zA-Z0-9+._?=-]+$'

runtime_identity() {
    local result="$1" root digest
    [[ -L "$result" ]]
    root=$(readlink -f -- "$result")
    [[ "$root" =~ $store_path_re && -d "$result" && -f "$result/command-map.json" && -d "$result/share/hermes-agent" ]]
    # Validate actual contents against the Nix database, not just display paths.
    # Trust/signatures are separate; this job is comparing independent builds.
    # Keep full closure paths and Nix verification diagnostics out of job logs.
    if ! nix store verify --recursive --no-trust "$root" >/dev/null 2>&1; then
        echo "Hermes runtime content verification failed." >&2
        return 1
    fi
    digest=$(nix path-info --recursive --json "$root" 2>/dev/null | python3 scripts/hermes-runtime-identity.py "$root")
    [[ "$digest" =~ ^[0-9a-f]{64}$ ]]
    printf 'root=%s\nclosure_sha256=%s\n' "$root" "$digest"
}

case "${1:-}" in
    qualify)
        runtime_identity result-hermes
        ;;
    prepare)
        [[ "${HERMES_RUNTIME_PUBLISH:-}" == enabled ]]
        [[ "${QUALIFIED_ROOT:-}" =~ $store_path_re ]]
        [[ "${QUALIFIED_CLOSURE_SHA256:-}" =~ ^[0-9a-f]{64}$ ]]
        [[ ! -e hermes-runtime-result && ! -L hermes-runtime-result ]]
        [[ ! -e hermes-runtime-cachix && ! -L hermes-runtime-cachix ]]
        nix build -L "$candidate" --no-update-lock-file --out-link hermes-runtime-result >&2
        git diff --quiet HEAD --
        identity=$(runtime_identity hermes-runtime-result)
        [[ "$identity" == "$(printf 'root=%s\nclosure_sha256=%s' "$QUALIFIED_ROOT" "$QUALIFIED_CLOSURE_SHA256")" ]]
        nix build -L "$cachix_pin" --no-update-lock-file --out-link hermes-runtime-cachix >&2
        [[ -L hermes-runtime-cachix ]]
        client=$(readlink -f -- hermes-runtime-cachix)
        [[ "$client" =~ $store_path_re && "$client" == *-cachix-* && -x hermes-runtime-cachix/bin/cachix ]]
        nix store verify --recursive --no-trust "$client" >&2
        # Freeze exact canonical paths, never raw path-info or package contents.
        printf '%s\nclient=%s/bin/cachix\n' "$identity" "$client"
        ;;
    *) exit 1 ;;
esac
