set -euo pipefail
systemctl is-active --quiet sshd
if systemctl is-active --quiet comin; then exit 1; fi
umask 077
policy_dir=$(mktemp -d)
trap 'rm -rf "$policy_dir"' EXIT
for account in operator hermes-tunnel; do
  sshd -T -f /etc/ssh/sshd_config -C "user=$account,host=policy-check,addr=2001:db8::1,laddr=2001:db8::2,lport=22" |
    awk '{ $1 = tolower($1); print }' > "$policy_dir/$account"
done
fleet-check-ssh-policy "$policy_dir/operator" "$policy_dir/hermes-tunnel"
for key in /var/lib/fleet-access/authorized_keys /var/lib/fleet-access/hermes-tunnel-authorized_keys; do
  test ! -L "$key" && test -s "$key"
  test "$(stat -c '%u:%a' "$key")" = 0:644
  ssh-keygen -lf "$key" >/dev/null
done
# Controller may not be connected during initial bootstrap. If its listener
# exists, it must never be public or wildcard-bound.
ss -H -lnt '( sport = :16667 )' | awk '$4 != "127.0.0.1:16667" { exit 1 }'
ip -6 address show scope global | grep -q inet6
for service in prometheus grafana k3s spin; do
  if systemctl is-active --quiet "$service"; then exit 1; fi
done
# Initial closure health is not model/tunnel end-to-end health. Missing any
# gate must prevent Hermes startup; this check never creates those gates.
for gate in /var/lib/fleet-access/hermes-irc-policy-qualified /var/lib/fleet-access/hermes-approved /var/lib/fleet-access/hermes.env /var/lib/fleet-access/hermes-config.json /var/lib/hermes/.hermes/auth.json; do
  if ! test -e "$gate" && systemctl is-active --quiet hermes-irc; then exit 1; fi
done
