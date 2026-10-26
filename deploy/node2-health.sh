set -euo pipefail
systemctl is-active --quiet sshd
if systemctl is-active --quiet comin; then exit 1; fi
sshd -T | grep -qx 'permitrootlogin no'
sshd -T | grep -qx 'passwordauthentication no'
sshd -T | grep -qx 'kbdinteractiveauthentication no'
sshd -T | grep -qx 'allowusers operator'
sshd -T | grep -qx 'authorizedkeysfile /var/lib/fleet-access/authorized_keys'
test -s /var/lib/fleet-access/authorized_keys
ip -6 address show scope global | grep -q inet6
for service in prometheus grafana k3s spin; do
  if systemctl is-active --quiet "$service"; then exit 1; fi
done
