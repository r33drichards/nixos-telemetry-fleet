#!/bin/sh
# cloud-init runs this root-owned hook on every boot. No secrets or downloads.
set -eu
export PATH=/run/current-system/sw/bin:/run/wrappers/bin:$PATH
key=/var/lib/fleet-access/authorized_keys
test -s "$key" || { echo "SSH bootstrap: missing public key" >&2; exit 1; }
test "$(stat -c '%u:%a' "$key")" = 0:644 || { echo "SSH bootstrap: invalid key owner/mode" >&2; exit 1; }
ssh-keygen -lf "$key" >/dev/null
policy=$(sshd -T -f /etc/ssh/sshd_config)
# OpenSSH versions differ in directive-name casing; values/paths stay exact.
policy=$(printf '%s\n' "$policy" | awk '{ $1 = tolower($1); print }')
for setting in 'permitrootlogin no' 'passwordauthentication no' 'kbdinteractiveauthentication no' 'allowusers operator' 'authorizedkeysfile /var/lib/fleet-access/authorized_keys'; do
  printf '%s\n' "$policy" | grep -Fx "$setting" >/dev/null || { echo "SSH bootstrap: required policy missing: $setting" >&2; exit 1; }
done
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
