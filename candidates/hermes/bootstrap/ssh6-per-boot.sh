#!/bin/sh
# cloud-init runs this root-owned hook on every boot. No secrets or downloads.
set -eu
export PATH=/run/current-system/sw/bin:/run/wrappers/bin:$PATH
key=/var/lib/fleet-access/authorized_keys
test -s "$key" || { echo "SSH bootstrap: missing public key" >&2; exit 1; }
test "$(stat -c '%u:%a' "$key")" = 0:644 || { echo "SSH bootstrap: invalid key owner/mode" >&2; exit 1; }
ssh-keygen -lf "$key" >/dev/null
# This replacement is installed only by the reviewed root bootstrap after
# the tunnel-enabled Nix generation exists; Terraform custom_data is unchanged.
checker=/var/lib/fleet-bootstrap/check-ssh-policy.sh
test ! -L "$checker" && test "$(stat -c '%u:%a' "$checker")" = 0:700 || exit 1
tunnel_key=/var/lib/fleet-access/hermes-tunnel-authorized_keys
test ! -L "$tunnel_key" && test -s "$tunnel_key" || exit 1
test "$(stat -c '%u:%a' "$tunnel_key")" = 0:644 || exit 1
ssh-keygen -lf "$tunnel_key" >/dev/null
umask 077
policy_dir=$(mktemp -d)
trap 'rm -rf "$policy_dir"' EXIT HUP INT TERM
for account in operator hermes-tunnel; do
  # Fixed documentation addresses supply Match context; the approved config
  # contains only Match User, never Match Address/Host-dependent exceptions.
  sshd -T -f /etc/ssh/sshd_config -C "user=$account,host=policy-check,addr=2001:db8::1,laddr=2001:db8::2,lport=22" > "$policy_dir/$account.raw"
  awk '{ $1 = tolower($1); print }' "$policy_dir/$account.raw" > "$policy_dir/$account"
done
/bin/sh "$checker" "$policy_dir/operator" "$policy_dir/hermes-tunnel"
# /etc/systemd/system is Nix-managed. Only runtime drop-ins are written here;
# cloud-init recreates them on reboot. The firewall service supplies ip6tables.
install -d -m 755 /run/systemd/system/firewall.service.d
cat > /run/systemd/system/firewall.service.d/50-fleet-ssh6.conf <<'UNIT'
[Service]
ExecStartPost=/bin/sh -ec 'ip6tables -w -C nixos-fw -s ::/0 -p tcp --dport 22 -j ACCEPT || ip6tables -w -I nixos-fw 1 -s ::/0 -p tcp --dport 22 -j ACCEPT'
ExecReload=/bin/sh -ec 'ip6tables -w -C nixos-fw -s ::/0 -p tcp --dport 22 -j ACCEPT || ip6tables -w -I nixos-fw 1 -s ::/0 -p tcp --dport 22 -j ACCEPT'
UNIT
systemctl daemon-reload
systemctl restart firewall.service
# Deliberately do not create bootstrap-approved or start Comin.
