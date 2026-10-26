# Local-only SSH bootstrap compatibility patch

These files are not imported by node2, installed, published or executed as root.
They do not change Terraform custom_data: doing so could replace the existing VM.
PR16 remains unchanged/unmerged. This is a proposed follow-up to its restricted
`tunnel.nix`, not an instruction to enable Hermes, Cachix or Comin.

The replacement `ssh6-per-boot.sh` preserves the existing IPv6 TCP22 firewall
drop-in exactly. Before any firewall write/restart it checks both effective
policies using `sshd -T -C user=...`, checks the operator and dedicated tunnel
public-key file ownership/modes, and invokes the root-owned policy checker.
The approved Nix configuration has only Match User, no address/host-dependent
exceptions; sampled Match contexts do not prove arbitrary future configurations.

The checker accepts exactly operator and hermes-tunnel (either order, including
OpenSSH's repeated AllowUsers output), rejecting extra/duplicate users and
ambiguous scalar directives. It preserves operator's root/password/keyboard
login bans, custom key path and usable interactive sessions. Tunnel must have
publickey-only auth, its own key file, remote TCP forwarding only, loopback
127.0.0.1:16667 listener, no destination-open/local forwarding, no public
GatewayPorts, sessions, PTY, agent/X11/streamlocal/tun forwarding. A global
DisableForwarding=yes also rejects because it would break the approved tunnel.
MaxSessions=0 denies shell/exec/subsystem sessions despite the valid login shell
required for sshd account checks. No sudo membership/rule is added.

Installation belongs in the still-pending, reviewed self-disarming root
bootstrap: preserve the original hook; stage this checker root:root0700 at
/var/lib/fleet-bootstrap/check-ssh-policy.sh; verify the worker-provided public
key (no key creation here); test the exact tunnel-enabled generation; install
this replacement over the existing /var/lib/cloud/scripts/per-boot/fleet-ssh6
root:root0700 only after its effective policies pass. Do not add a second
per-boot script or any recurring root debug/recovery hook. This is the existing
firewall bootstrap's policy update. On failed activation restore both original
hook and old generation before reboot. Keep an already working operator SSH
session open and independently verify a new one.

Local validation:

    python3 candidates/hermes/bootstrap/test_policy.py
    sh -n candidates/hermes/bootstrap/check-ssh-policy.sh candidates/hermes/bootstrap/ssh6-per-boot.sh

Eleven test methods cover valid/reordered/repeated-list output, each missing
tunnel restriction, broadening, unexpected users, operator regressions,
duplicate scalars, denies, directive casing and public-key parameter shape. The final test parses the actual tunnel.nix Match
block with local OpenSSH sshd -T for both users and feeds both results to the
checker. Its temporary host key is an isolated test fixture, removed afterwards;
no listener starts, real host key is read, or deployment credential is created.
These tests do not prove live key authentication, root installation, reboot
persistence or the Railway forwarding path. NixOS integration/VM testing of
this follow-up remains pending publication approval.
