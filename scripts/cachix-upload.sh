#!/usr/bin/env bash
set -euo pipefail
# No tracing: the token is an environment-only capability.
[[ "${GITHUB_REF:-}" == refs/heads/main ]]
[[ "${GITHUB_SHA:-}" =~ ^[0-9a-f]{40}$ ]]
[[ "${EXPECTED_REVISION:-}" == "$GITHUB_SHA" ]]
[[ "${UPLOAD_APPROVED:-}" == explicitly-approved ]]
case "${1:-}" in
  prepare)
    nix build -L .#checks.x86_64-linux.node2-cachix-contract
    nix build -L .#node2-deploy --out-link deploy-result
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
    nix shell github:NixOS/nixpkgs/da6dc0e7b26060f2f71ce3ef7088fb56ee44fa36#cachix -c cachix push r33drichards-nixos-fleet "$spec_path"
    ;;
  *) exit 1 ;;
esac
