# Manage the node2 Hermes IRC gateway

## Overview

Update and recover the live Hermes gateway without losing SSH access, runtime credentials, or the owner's toolset preferences.

## Requirements

- **Permissions:** SSH as `operator`; `sudo -n id` must report root. Azure control-plane access is needed only for access recovery.
- **Tools:** SSH with IPv6 connectivity; Nix for local dependencies; the installed Hermes Python for remote validation.
- **Network:** IPv6 SSH to the target, HTTPS to model/MCP providers, and the existing IRC reverse tunnel on localhost port 16667.
- **Operator/decision maker:** the repository and VM owner. No separate on-call roster is configured.

## Constraints

- This runbook records live observations as of **2026-11-13**. Recheck identity, service definitions, limits, and tool availability before changes.
- Restarting `hermes-irc` interrupts agent turns and briefly disconnects IRC. Avoid restarting during an active task; capture evidence before recovery.
- The VM has one vCPU, about 894 MiB usable RAM, no swap, and a 64 GiB OS disk. Its hosted model and Computer Use desktop run elsewhere.
- Never commit secrets, secret-bearing backups, Terraform state, or environment-file contents. Do not put secrets in a Nix expression, command argument, shell history, or Azure Run Command script. Logs and session records can contain private task content; extract only the evidence needed.
- Do not run `hermes gateway install --force` as a general repair: it may replace the deliberately hardened/custom service. Preserve existing IRC access, authentication, and service isolation.

### Target identity

| Field | Value |
|---|---|
| SSH | `ssh -F /dev/null -6 -p 22 operator@2603:1020:1601:8::136` |
| Hostname / Azure VM | `node2` / `nixos-node2` |
| Subscription | `38d8d92f-3e84-4ef5-b3da-2788a843aa70` |
| Tenant | `0e4545fd-804f-4acb-ad41-f955e53645c1` |
| Resource group / region | `RG-NIXOS-FLEET-WEST` / `denmarkeast` |
| Service / IRC | `hermes-irc.service` / nickname `hermes`, channel `#hermes` |
| Model | `openai-codex`, `gpt-6-sol` at observation time |

### Configuration map

| Path | Role |
|---|---|
| `/var/lib/fleet-access/hermes-config.json` | Authoritative runtime config, JSON |
| `/etc/hermes-policy/validate-config.py` | Exact config allowlist; edits must match intended config |
| `/etc/hermes-policy/hermes-irc-pre-start` | Validates and installs the systemd credential as Hermes's config |
| `/var/lib/hermes/.hermes/config.yaml` | Generated copy, currently JSON syntax despite filename; overwritten at startup |
| `/var/lib/fleet-access/hermes.env` | Root-owned mode 0600; includes Computer Use token variable |
| `/var/lib/fleet-access/hermes-modal.env` | Existing Modal credentials; terminal toolset is disabled |
| `/etc/hermes-policy/hermes-run` | Actual custom launcher; exports installed Python/package paths |
| `/etc/hermes-policy/plugins/` | Custom IRC/channel-intake plugins |
| `/etc/systemd/system.control/hermes-irc.service.d/` | Persistent launcher, transport, environment, and resource overrides |
| `/var/lib/hermes/.hermes/` | Writable Hermes state, auth, sessions, skills, memory, and logs |
| `/etc/sudoers.d/operator` | Validated `operator ALL=(ALL:ALL) NOPASSWD: ALL` rule |
| `/var/lib/hermes-config-backups/` | Root-only matching config/validator backups; some also include environment files |

`memories/MEMORY.md` and `memories/USER.md` are created as native memory is used. The native memory and skills tools must be enabled to make their writable storage agent-editable. Computer Use `/data/memory/` is on a different machine and disk.

### Live tool policy

The current runtime config includes:

```yaml
platform_toolsets:
  irc:
    - computeruse
    - skills
    - memory
    - todo
    - session_search
    - cronjob
    - web
    - search
    - image_gen
    - video_gen
    - delegation
    - clarify
    - debugging
tools:
  tool_search:
    enabled: "off"
agent:
  disabled_toolsets: [terminal]
```

`computeruse` is the alias of the configured MCP server, not Hermes's native `computer_use`. It exposes `mcp__computeruse__run_js`, browser/desktop/exec wrappers, and artifact/resource helpers (12 tools at observation time). Keep the existing `agent.environment_hint` describing these capabilities and the remote-host boundary. `debugging` is a composite of terminal, web, and file tools: the explicit terminal exclusion retains web/file functionality without exposing `terminal` or `process_manage`.

Image/video generation are enabled in policy but were unavailable because their provider checks returned false. Selecting a toolset does not configure credentials or prove a provider works. Native cron tools require messaging-session context; a standalone Python check without `HERMES_GATEWAY_SESSION=1` can incorrectly suggest they are unavailable. `web` already contains search; specifying `search` as well does not create duplicate tools.

## Procedure

### Step 1: Verify access and capture health

**Action:** Connect with the SSH command above. Verify `hostname`, `sudo -n id`, and `systemctl is-active hermes-irc`. Inspect only the relevant service properties:

```sh
sudo -n systemctl show hermes-irc \
  -p ActiveState -p SubState -p MainPID -p NRestarts -p Result \
  -p MemoryCurrent -p MemoryPeak -p MemoryHigh -p MemoryMax
ss -tn | grep 16667
```

Follow the journal from a local terminal:

```sh
ssh -F /dev/null -6 -p 22 -t operator@2603:1020:1601:8::136 \
  'sudo -n journalctl -u hermes-irc -f -n 100'
```

**Expected outcome:** correct host, root through sudo, running service, and an established IRC socket. Application logs are under `/var/lib/hermes/.hermes/logs/agent.log` and `gateway.log`; inspect relevant timestamps rather than publishing entire files.

**If failed:** use the incident/recovery sections below. Do not treat `active` alone as proof of a connected IRC adapter.

### Step 2: Back up the matching configuration

**Action:** In the remote shell:

```sh
backup="/var/lib/hermes-config-backups/$(date -u +%Y%m%dT%H%M%SZ)-manual"
sudo -n install -d -m 0700 /var/lib/hermes-config-backups "$backup"
sudo -n cp -p /var/lib/fleet-access/hermes-config.json "$backup/config.json"
sudo -n cp -p /etc/hermes-policy/validate-config.py "$backup/validate-config.py"
sudo -n cp -p /var/lib/fleet-access/hermes.env "$backup/hermes.env"
sudo -n cp -a /etc/systemd/system.control/hermes-irc.service.d "$backup/service-dropins"
printf 'Backup directory: %s\n' "$backup"
```

**Expected outcome:** root-owned backup directory, mode 0700, containing the pre-change files. Record its path; do not copy it into the repository.

**If failed:** stop before editing. Keep disk space for a rollback and retained Nix generations.

### Step 3: Change and validate runtime configuration

**Action:** Edit the JSON source and its validator together using a root-capable editor, preserving unrelated settings. The validator intentionally compares exact keys/toolsets/MCP details; extend it narrowly for the owner's requested change. Do not remove validation to make a restart pass.

Resolve the installed interpreter from the launcher, then validate:

```sh
hermes_python=$(sed -n "s/^export HERMES_PYTHON='\([^']*\)'$/\1/p" /etc/hermes-policy/hermes-run)
test -x "$hermes_python"
sudo -n "$hermes_python" /etc/hermes-policy/validate-config.py \
  /var/lib/fleet-access/hermes-config.json --transport ssh-loopback
```

Preserve root ownership and mode 0600 on config/environment files. Token values go only into runtime environment files; the config references them:

```yaml
mcp_servers:
  computeruse:
    url: https://api.computeruse.site/s-mnwl4/mcp
    headers:
      Authorization: "Bearer ${COMPUTERUSE_API_TOKEN}"
```

The token needs `sessions:connect`. `https://sessions.computeruse.site/s-mnwl4/mcp` is for browser OAuth, not this service's API-token flow. Deliver credentials through a private file/stdin transfer over verified SSH, never a literal token in a command. Remove any staging copy after installing it root-only. Do not assume a token exists at an old local path or read it just to document the setup.

**Expected outcome:** validator exits zero without printing config values. For validator changes, also check rejection of an unintended endpoint, literal auth header, and an additional MCP server using copies in memory.

**If failed:** correct the intended config/validator pair before restarting, or restore the matching backup. Editing the generated `config.yaml` will not fix the source.

### Step 4: Restart once and verify

**Action:** Restart after checking whether a turn is active:

```sh
sudo -n systemctl restart hermes-irc
sudo -n systemctl show hermes-irc -p ActiveState -p SubState -p NRestarts -p Result
```

**Expected outcome:** service starts, the pre-start validator accepts the credential, MCP tools register, and IRC logs report connection/join to `#hermes`. Allow normal startup time before concluding it failed.

**If failed:** inspect the bounded journal. Several rapid restarts can hit `StartLimitBurst=3` within 300 seconds. Fix the cause first, then `sudo -n systemctl reset-failed hermes-irc` and `sudo -n systemctl start hermes-irc`. Stop retrying after one failed corrected start; capture evidence and restore the backup.

## Verification

- Check both systemd and the IRC connected/joined log entry, plus an established localhost socket. A successful restart is not an end-to-end tool check.
- Confirm MCP HTTP initialization and registration logs, without exposing auth headers. The initial Computer Use integration registered 12 tools.
- Inspect actual model-visible schemas through the installed `model_tools.get_tool_definitions`, using `_get_platform_tools(config, 'irc')` and `config['agent']['disabled_toolsets']`. Use the Hermes UID/home, its runtime environment, and gateway session context. On the pinned installed package, MCP discovery and cleanup are in `tools.mcp_tool_discovery.discover_mcp_tools` and `tools.mcp_tool_lifecycle.shutdown_mcp_servers`; imports from `tools.mcp_tool` itself may fail.
- Expected native tools include `memory`, `skills_list`, `skill_view`, `skill_manage`, `todo_list`, `session_search`, `cronjob_manage`, `web_search`, `web_extract`, `delegate_task`, and `clarify`. `debugging` also adds file tools. `terminal` and `process_manage` must remain absent. Check generation-provider availability separately.
- Tool Search is off, so the model sees Computer Use schemas directly rather than only search/describe/call wrappers. For an old conversation repeating a stale tool inventory, ask the owner to start `/new`; do not silently reset their session.
- Do not execute external-account tasks or paid generation calls just to verify registration. Report registration versus tested execution separately.

## Rollback

Choose the recorded **matching** backup directory. Inspect which files it contains; not every historical backup has an environment file or service drop-ins. Restore only components changed in the attempted rollout. For a config/validator change:

```sh
# Set backup to the recorded pre-change directory, not an arbitrary newest directory.
sudo -n install -o root -g root -m 0600 "$backup/config.json" /var/lib/fleet-access/hermes-config.json
sudo -n install -o root -g root -m 0644 "$backup/validate-config.py" /etc/hermes-policy/validate-config.py
# If credentials changed and this backup contains the previous environment:
# sudo -n install -o root -g root -m 0600 "$backup/hermes.env" /var/lib/fleet-access/hermes.env
sudo -n "$hermes_python" /etc/hermes-policy/validate-config.py \
  /var/lib/fleet-access/hermes-config.json --transport ssh-loopback
sudo -n systemctl reset-failed hermes-irc
sudo -n systemctl restart hermes-irc
```

Restore changed drop-ins as a matching set and run `systemctl daemon-reload` before restarting. Do not use `systemctl revert hermes-irc` indiscriminately: existing custom transport/launcher overrides are required. Recheck MCP/IRC health. NixOS generation rollback alone does not restore these host-local credentials or overrides.

## Incident: IRC ping timeout while taking a screenshot

On 2026-11-13, Hermes accepted a desktop task at 18:20:03 UTC. It stopped responding during an MCP image result at 18:21:15; IRC eventually reported a two-minute ping timeout. Systemd still reported running, with no restart or OOM kill. A `vision-encode_0` thread was in `mem_cgroup_handle_over_high` while other Python threads waited. `memory.events` recorded tens of thousands of `high` events and zero `oom`/`oom_kill` events.

Collect evidence before restarting:

```sh
sudo -n cat /sys/fs/cgroup/system.slice/hermes-irc.service/memory.events
sudo -n systemctl show hermes-irc -p MainPID -p MemoryCurrent -p MemoryPeak -p MemoryHigh -p MemoryMax
pid=$(systemctl show hermes-irc -p MainPID --value)
sudo -n ps -L -p "$pid" -o tid,stat,wchan:28,comm
free -h
```

The cgroup path assumes the current system slice; use `systemctl show -p ControlGroup --value hermes-irc` if placement changes. If the same soft-limit throttle is confirmed and host headroom permits, the measured recovery was:

```sh
sudo -n systemctl set-property --runtime hermes-irc.service MemoryHigh=480M
```

The previously blocked MCP call completed after 331 seconds, housekeeping resumed, and IRC reconnected at 18:26:47 UTC without a process restart. Its turn was nevertheless interrupted with `session_turn_lease_lost`; recovery did not complete the owner's external-account task. Ask the owner to retry it rather than automatically repeating account actions.

After confirming recovery, the same soft limit was persisted with:

```sh
sudo -n systemctl set-property hermes-irc.service MemoryHigh=480M
```

The persistent systemd override is under `/etc/systemd/system.control/hermes-irc.service.d/`; the runtime override is under `/run/systemd/system.control/`. **MemoryMax remained 512 MiB and CPUQuota remained 50%.** This is a measured mitigation, not proof that arbitrary image workloads fit. Check host headroom and whether the `high` counter continues increasing. If pressure recurs, investigate image sizing/provider behavior or an owner-approved capacity change; do not repeatedly increase limits on the 1 GiB host.

For an unsuccessful runtime-only experiment, restore the recorded prior property with `systemctl set-property --runtime`. If changing the persistent value, inspect/remove the corresponding runtime override or set both scopes consistently. Do not roll back to 384 MiB during an active image workload merely to match the repository baseline.

## Access recovery

Current access uses `/etc/sudoers.d/operator` (root-owned, 0440). The NixOS sudoers file contains `#includedir /etc/sudoers.d`—a valid sudo directive despite the leading `#`. Validate with the installed `visudo -c`. Keep the rule in the include directory rather than appending to generated `/etc/sudoers`. The repository's Nix source has not yet declared this host-local rule.

The successful one-time bootstrap used Azure CLI, supplied through Nix, and the Browserjs account that owns this subscription. Existing cached CLI accounts were different; confirm the exact subscription instead of trusting the default:

```sh
nix shell nixpkgs#azure-cli -c az account show --subscription 38d8d92f-3e84-4ef5-b3da-2788a843aa70
```

The observed Nix Azure CLI 2.80.0 device-code login failed with `Session.request() got an unexpected keyword argument 'claims_challenge'`; normal browser login to this tenant succeeded. Use the Browserjs profile and verify completion. Do not extract browser cookies or tokens.

`osProfile.allowExtensionOperations` is normally false. With the owner's explicit recovery authorization, it was temporarily enabled on this VM, then `az vm run-command invoke --command-id RunShellScript` ran a `visudo`-validated operator rule as root. No reboot or password change was needed. This recovery broadens administrative execution and is not part of ordinary config updates now that sudo works.

Cleanup matters: Azure rejects disabling extension operations while the hidden action Run Command extension is installed, even if `az vm extension list` is empty. Use `az vm run-command invoke --command-id RemoveRunCommandLinuxExtension` for this exact VM, then restore `osProfile.allowExtensionOperations=false` with `az vm update`. The observed CLI raised an output-deserialization error after removal; a subsequent successful update/read confirmed the platform state. Verify state rather than assuming either CLI error or empty extension list proves cleanup. Never remove unrelated extensions or operate on another VM.

## Repository and deployment boundaries

- Root `flake.nix` defines `nixosConfigurations.node2-hermes` and `node2-hermes-deploy`. `deploy/node2-hermes.nix` imports the access, Cachix, Hermes service, and tunnel modules and explicitly disables Comin. `candidates/hermes/service.nix` supplies the original service and resource limits.
- The live installation has later host-local validator, tool-policy, provider, launcher, sudo, and memory-limit changes. The image provenance identifies repository revision `ba51125b3d367b8326b357023a5ad5812239b7a9` and leaf `nodes/node2`; that image stamp is not proof of the complete current configuration.
- The Cachix agent is installed but inactive: its approval/credential files were absent. Comin is masked. Do not assume a Git push activates the VM.
- `.github/workflows/hermes-build.yml` qualifies/builds the Hermes candidate without activation. `cachix-deploy.yml` builds the base candidate only. `cachix-upload.yml` manually uploads a reviewed base/Hermes closure on main with the exact revision and protected cache environment; it does not activate. `cloud.yml` handles separately gated Azure operations. See [Cachix upload](../cachix-upload.md) and [Cachix deployment](../cachix-deploy.md).
- A future Nix rollout must first reconcile live overrides and runtime files with the intended closure. Do not activate the baseline leaf or install a stock gateway unit just because CI passed.

## Escalation

- **Escalate to:** the VM/repository owner when SSH/sudo fails, a corrected start fails, host memory is exhausted, or the runbook no longer matches the installed service.
- **Escalate after:** one failed corrected restart/rollback, or immediately for loss of access, an OOM kill, or an unexpected credential/config change.
- **Decision makers:** the owner decides host resizing, privileged recovery, credential rotation, enabling deployment controllers, and retrying interrupted external-account actions.
- **Third-party support:** [Azure Run Command](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/run-command), [extension-operation controls](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/disable-provisioning), [Hermes Tool Search](https://hermes-agent.nousresearch.com/docs/user-guide/features/tool-search), [Computer Use token authentication](https://computeruse.site/guides/use-from-code), and [Computer Use source](https://github.com/r33drichards/computer-use/blob/main/backend/internal/auth/apihost.go).
