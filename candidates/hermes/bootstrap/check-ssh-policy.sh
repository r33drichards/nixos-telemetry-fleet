#!/bin/sh
# Effective sshd -T output for operator and hermes-tunnel, never config text.
set -eu
reject() { echo 'SSH bootstrap: effective policy rejected' >&2; exit 1; }
[ "$#" -eq 2 ] || reject
# OpenSSH versions vary directive-name casing. Preserve values exactly while
# normalizing the names, as the existing cloud-init bootstrap already does.
umask 077
normalized=$(mktemp -d)
trap 'rm -rf "$normalized"' EXIT HUP INT TERM
awk '{ $1=tolower($1); print }' "$1" > "$normalized/operator"
awk '{ $1=tolower($1); print }' "$2" > "$normalized/tunnel"
set -- "$normalized/operator" "$normalized/tunnel"
for policy in "$1" "$2"; do
  # OpenSSH repeats list-valued entries (AllowUsers, ListenAddress). Reject
  # duplicates of security scalars; aggregate AllowUsers below instead.
  awk '$1 ~ /^(permitrootlogin|passwordauthentication|kbdinteractiveauthentication|authorizedkeysfile|authenticationmethods|allowtcpforwarding|permitlisten|permitopen|gatewayports|maxsessions|permittty|allowagentforwarding|x11forwarding|allowstreamlocalforwarding|permittunnel|disableforwarding)$/ { if (seen[$1]++) exit 1 }' "$policy" || reject
  for expected in 'permitrootlogin no' 'passwordauthentication no' 'kbdinteractiveauthentication no'; do
    grep -Fx "$expected" "$policy" >/dev/null || reject
  done
  users=$(awk '$1 == "allowusers" { for(i=2;i<=NF;i++) print $i }' "$policy" | LC_ALL=C sort)
  [ "$users" = "$(printf 'hermes-tunnel\noperator')" ] || reject
  # A user/group deny can make approved accounts unusable. No such controls
  # exist in this candidate; changes need explicit review.
  ! grep -Eq '^(denyusers|denygroups|allowgroups) ' "$policy" || reject
done
grep -Fx 'authorizedkeysfile /var/lib/fleet-access/authorized_keys' "$1" >/dev/null || reject
# Prevent a misplaced Match block from silently turning operator into a tunnel-only account.
grep -Fx 'permittty yes' "$1" >/dev/null || reject
sessions=$(awk '$1 == "maxsessions" {print $2}' "$1")
case "$sessions" in ''|*[!0-9]*) reject;; esac
[ "$sessions" -gt 0 ] || reject
for expected in \
  'authenticationmethods publickey' \
  'authorizedkeysfile /var/lib/fleet-access/hermes-tunnel-authorized_keys' \
  'allowtcpforwarding remote' 'permitlisten 127.0.0.1:16667' \
  'permitopen none' 'gatewayports no' 'maxsessions 0' 'permittty no' \
  'allowagentforwarding no' 'x11forwarding no' \
  'allowstreamlocalforwarding no' 'permittunnel no' 'disableforwarding no'; do
  grep -Fx "$expected" "$2" >/dev/null || reject
done
