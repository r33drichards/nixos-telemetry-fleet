# ChatGPT account sign-in: proposed, not executed

Audited upstream revision: 05d7b5af1c42d524762c7ffce991c1fe1aa2adb1.
`hermes auth add openai-codex` calls the fresh OAuth login directly through
hermes_cli/auth_commands.py. Use this path rather than importing an existing
Codex credential or the model-selection flow that offers credential reuse.

Run only after approval, as the dedicated hermes user with its own clean HOME
and HERMES_HOME. Do not inherit operator/root authentication environment or
mount their home directories. Do not copy any existing Codex auth.json.

Default login is headless device-code authentication:

1. Hermes requests a code from auth.openai.com/api/accounts/deviceauth/usercode.
2. Robert opens https://auth.openai.com/codex/device in his browser and confirms
   the intended ChatGPT account/workspace and displayed consent.
3. Hermes polls the device token endpoint, then exchanges the authorization
   code at auth.openai.com/oauth/token. No inbound callback port is needed.
4. Hermes stores and refreshes its own session in
   /var/lib/hermes/.hermes/auth.json, owner hermes, mode0600, parent0700.

The device request sends a public client ID but no explicit scope field;
server consent determines that grant. The optional browser PKCE flow requests
openid profile email offline_access and uses localhost:1455, but is not the
proposed headless flow. Inference uses chatgpt.com/backend-api/codex. HTTPS
access to both auth.openai.com and chatgpt.com must work from node2.

The runtime file contains access and refresh credentials. It must remain outside
Git, Nix derivations, Cachix closures, Terraform state, CI artifacts and logs.
It must be writable by hermes for token refresh. Backups, if approved later,
need private host-secret handling; do not put encrypted payloads in Git either.
The upstream writer uses atomic0600 writes and tightens the parent to0700.

Next security approval: start one fresh Hermes device-code login for Robert's
chosen ChatGPT account/workspace and retain that session under the dedicated
node2 service account. This does not authorize copying existing tokens, changing
account security settings, or falling back to a paid API key. If device login
is disabled or the account/model lacks entitlement, stop and report it.
Package publication/build, privileged bootstrap, tunnel credentials/access,
and service activation remain separate pending steps. No login has been run.

Source evidence: hermes_cli/auth_commands.py (_codex_login, _OAUTH_ADD_SPECS),
auth_codex_browser.py (codex_oauth_login), auth_codex.py (device request/poll/
exchange and independent token store), auth.py (_save_auth_store), and
https://developers.openai.com/codex/auth .
