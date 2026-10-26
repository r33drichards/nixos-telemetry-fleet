#!/usr/bin/env bash
set -euo pipefail
# No tracing: the token is an environment-only capability.
[[ "${GITHUB_REF:-}" == refs/heads/main ]]
[[ "${GITHUB_SHA:-}" =~ ^[0-9a-f]{40}$ ]]
[[ "${EXPECTED_REVISION:-}" == "$GITHUB_SHA" ]]
[[ "${UPLOAD_APPROVED:-}" == explicitly-approved ]]
case "${UPLOAD_CANDIDATE:-node2}" in
  node2) contract=node2-cachix-contract; target=node2-deploy ;;
  hermes) contract=node2-hermes-contract; target=node2-hermes-deploy ;;
  *) exit 1 ;;
esac
case "${1:-}" in
  prepare)
    nix build -L ".#checks.x86_64-linux.$contract" --no-update-lock-file
    nix build -L ".#$target" --no-update-lock-file --out-link deploy-result
    if [[ "$target" == node2-hermes-deploy ]]; then
      nix build -L .#node2-hermes-bootstrap --no-update-lock-file --out-link bootstrap-result
    fi
    python3 scripts/check-cachix-spec.py deploy-result
    sha256sum deploy-result
    ;;
  upload)
    [[ -n "${CACHIX_AUTH_TOKEN:-}" ]]
    [[ "${EXPECTED_SPEC_SHA256:-}" =~ ^[0-9a-f]{64}$ ]]
    python3 scripts/check-cachix-spec.py deploy-result
    [[ "$(sha256sum deploy-result | cut -d' ' -f1)" == "$EXPECTED_SPEC_SHA256" ]]
    spec_path=$(readlink -f deploy-result)
    [[ "$spec_path" =~ ^/nix/store/[0-9a-z]{32}-deploy.json$ ]]
    roots=("$spec_path")
    if [[ "$target" == node2-hermes-deploy ]]; then
      bootstrap_path=$(readlink -f bootstrap-result)
      [[ "$bootstrap_path" =~ ^/nix/store/[0-9a-z]{32}-node2-hermes-bootstrap-assets$ ]]
      [[ "$bootstrap_path" == "${EXPECTED_BOOTSTRAP_PATH:-}" ]]
      roots+=("$bootstrap_path")
    fi
    nix shell github:NixOS/nixpkgs/da6dc0e7b26060f2f71ce3ef7088fb56ee44fa36#cachix -c cachix push r33drichards-nixos-fleet "${roots[@]}"
    ;;
  *) exit 1 ;;
esac
