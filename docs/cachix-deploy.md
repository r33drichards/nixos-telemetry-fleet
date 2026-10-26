# Cachix Deploy candidate (not activated)

Build `nix build .#node2-deploy` on CI. The result references the complete
node2 system and health-check closures, so both must be uploaded to the approved
signed cache before `cachix deploy activate ./deploy-result`. The current
workflow builds only; it cannot upload or activate. The approved public cache is `r33drichards-nixos-fleet`; the workspace is
`azure-denmark-node2`. Its verified public signing key is declared in the module.

The separate `node2-cachix` target preserves the tested Azure/SSH leaf while
explicitly disabling Comin. Do not activate the Comin bootstrap marker. The
Cachix agent requires root-owned host-local files under `/var/lib/fleet-access`:
`cachix-agent.env` (0600, CACHIX_AGENT_TOKEN) and
`cachix-approved` (0600). No token or encrypted secret belongs in Git or the
Nix store. Nix signature checks stay enabled; local builders are disabled.

Before enabling uploads, review closure contents for the selected public cache. Public repository visibility does not authorize publishing
all built closures. CI needs separately scoped cache-write and deploy-activate
credentials in a protected GitHub environment. Host agent credentials are a
separate capability. Do not print tokens or run shell tracing around them.

The documented rollback script returns nonzero on failed local SSH policy,
missing keys/IPv6, running Comin or unwanted services. This is not proof of
external SSH reachability or reboot health. Test an actual key-authenticated
IPv6 connection independently before/after activation and after an approved
reboot; retain the previous generation and console recovery access.

Privileged bootstrap remains unresolved: the existing operator cannot sudo.
Installing the prebuilt closure, runtime credentials and enabling the agent
needs a separately reviewed administrator path. No RunCommand, extension,
GRUB recovery, credential delivery or reboot is authorized by this source patch.
First test the separately approved shared-default-outbound path, including
GitHub and Cachix HTTPS/WebSocket reachability; no paid network fallback.

References: https://docs.cachix.org/deploy/running-an-agent/nixos and
https://docs.cachix.org/deploy/reference . A nonzero rollback script requests
rollback; this has not yet been qualified on the live VM.
