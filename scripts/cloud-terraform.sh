#!/usr/bin/env bash
set -euo pipefail
test "${GITHUB_REF:-}" = refs/heads/main
test "${FLEET_ENABLED:-}" = explicitly-approved
TF_ROOT=${TF_ROOT:-terraform}
case "$TF_ROOT" in
  terraform) preflight=scripts/azure-sku-preflight.py ;;
  terraform/amd-canary) preflight=scripts/amd-canary-preflight.py ;;
  *) echo 'Unsupported Terraform root' >&2; exit 1 ;;
esac
umask 077
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
printf '%s' "$BACKEND_CONFIG" > "$work/backend.hcl"
printf '%s' "$TOPOLOGY" > "$work/topology.tfvars.json"
backend_scope=()
if [ "$TF_ROOT" = terraform/amd-canary ]; then
  # Last backend argument binds this root to its dedicated state, even if a
  # stale private backend file contains the legacy fleet key.
  backend_scope=(-backend-config=key=fleet/amd-canary/terraform.tfstate)
fi
# Private inventory and plan output must never enter public Actions logs/artifacts.
if ! terraform -chdir="$TF_ROOT" init -input=false -lockfile=readonly -backend-config="$work/backend.hcl" "${backend_scope[@]}" >"$work/init.log" 2>&1; then
  echo 'Backend init failed; inspect via approved private diagnostics.' >&2; exit 1
fi
if [ "$OPERATION" = plan ]; then
  python3 "$preflight" "$work/topology.tfvars.json"
  if ! terraform -chdir="$TF_ROOT" plan -input=false -lock-timeout=60s -var-file="$work/topology.tfvars.json" -out="$work/plan" >"$work/plan.log" 2>&1; then
    echo 'Cloud plan failed; inspect via approved private diagnostics.' >&2; exit 1
  fi
  if [ "$TF_ROOT" = terraform/amd-canary ]; then
    terraform -chdir="$TF_ROOT" show -json "$work/plan" > "$work/plan.json" 2>"$work/show.log"
    python3 "$preflight" --check-plan-json "$work/plan.json"
  fi
  printf '%s' "$GITHUB_SHA" > "$work/revision"
  sha256sum "$work/plan" | cut -d' ' -f1 > "$work/sha256"
  printf '%s' "$TF_ROOT" > "$work/root"
  for item in plan revision sha256 root; do
    az storage blob upload --auth-mode login --account-name "$PLAN_STORAGE_ACCOUNT" --container-name "$PLAN_CONTAINER" --name "$GITHUB_RUN_ID/$item" --file "$work/$item" --overwrite false --only-show-errors > /dev/null 2>&1
  done
  echo "Private plan saved for run $GITHUB_RUN_ID. Review it privately before requesting apply."
elif [ "$OPERATION" = apply ]; then
  [[ "$PLAN_RUN_ID" =~ ^[0-9]+$ ]] && [[ "$APPROVED_PLAN_SHA256" =~ ^[a-f0-9]{64}$ ]]
  for item in plan revision root; do
    az storage blob download --auth-mode login --account-name "$PLAN_STORAGE_ACCOUNT" --container-name "$PLAN_CONTAINER" --name "$PLAN_RUN_ID/$item" --file "$work/$item" --only-show-errors > /dev/null 2>&1
  done
  test "$(cat "$work/revision")" = "$GITHUB_SHA"
  test "$(cat "$work/root")" = "$TF_ROOT"
  test "$(sha256sum "$work/plan" | cut -d' ' -f1)" = "$APPROVED_PLAN_SHA256"
  terraform -chdir="$TF_ROOT" show -json "$work/plan" > "$work/plan.json" 2>"$work/show.log"
  python3 "$preflight" --plan-json "$work/plan.json"
  if ! terraform -chdir="$TF_ROOT" apply -input=false -lock-timeout=60s "$work/plan" >"$work/apply.log" 2>&1; then
    echo 'Apply failed or partially completed. Inspect private state before any retry.' >&2; exit 1
  fi
  echo 'Approved saved plan applied; cloud E2E is still required.'
else
  echo 'Unsupported operation' >&2; exit 1
fi
