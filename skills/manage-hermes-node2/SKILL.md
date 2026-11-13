---
name: manage-hermes-node2
description: Manage and troubleshoot the Hermes IRC gateway on the node2 Azure NixOS VM, including toolsets, Computer Use MCP, runtime credentials, sudo access, service health, and rollback. Use for this instance rather than unrelated Hermes installations.
---

# Manage Hermes on node2

Read [the operational runbook](../../docs/runbooks/hermes-node2.md) before changing the live gateway. It contains the target identity, exact paths, backup/apply/rollback commands, and known failures. Check live state rather than treating the dated snapshot as current desired state.

- Target: `operator@2603:1020:1601:8::136`, hostname `node2`, Azure VM `nixos-node2` in `RG-NIXOS-FLEET-WEST`, Denmark East. Use `ssh -F /dev/null -6 -p 22` and verify the target before mutation. Do not disable SSH host-key checks.
- Use Nix for dependency management and Cargo. Prefer the installed service's Python interpreter for configuration validation. Resolve its current store path from `/etc/hermes-policy/hermes-run`; store hashes change with deployments.
- The active service is `hermes-irc`. `/etc/nixos/configuration.nix` is an Azure bootstrap file. The running service includes host-local overrides that the repository's Nix flake does not yet reproduce. A push to this repository is not a live deployment.
- Change `/var/lib/fleet-access/hermes-config.json` together with the exact allowlist in `/etc/hermes-policy/validate-config.py`. Validate before restarting. The generated `/var/lib/hermes/.hermes/config.yaml` is replaced on every start.
- Preserve the owner's explicit terminal exclusion. `debugging` includes terminal and process tools; keep `agent.disabled_toolsets: [terminal]` when enabling it. Native `computer_use` is different from the configured MCP alias `computeruse` (`mcp-computeruse`).
- Keep MCP tools directly visible with `tools.tool_search.enabled: "off"` unless the owner changes this preference. Keep the environment hint explaining the remote desktop and its separation from the Azure host.
- Computer Use API tokens use `https://api.computeruse.site/<session>/mcp`, `Authorization: Bearer ${COMPUTERUSE_API_TOKEN}`, and `sessions:connect`. `sessions.computeruse.site` is the browser-OAuth endpoint. Keep token values in root-only runtime files, outside Git and Nix derivations; never print tokens or credential-bearing logs.
- Back up the config, validator, changed environment files, and relevant systemd drop-ins as a matching set. Root-only backups can contain secrets. Verify model-visible tools, service state, IRC connection, and absence of terminal tools after applying changes.
- A running process is not proof of IRC health. For ping timeouts, inspect cgroup memory events and thread wait channels before restarting. The first 2026-11-13 stall recovered when `MemoryHigh` increased from 384 MiB to 480 MiB. A later stall reached that soft limit again: a 1 GiB swap file was added and `MemorySwapMax=512M` allowed reclaim, followed by one automatic gateway restart. The RAM hard limit remains 512 MiB. See the runbook's second incident and swap rollback; do not repeatedly raise RAM limits on this roughly 1 GiB VM.
- `operator` currently has passwordless sudo through `/etc/sudoers.d/operator`. Verify with `sudo -n id`; do not assume this survives host replacement. Azure extension operations are normally disabled. The runbook describes the one-time recovery used previously, not standing authorization to change access controls or repeat recovery.

When finished, report what changed on the VM versus in Git, what was actually verified, unavailable provider-backed tools, and any interrupted agent task. Do not retry an interrupted external-account operation merely because the gateway recovered.
