# Automatic Hermes runtime cache publication (not a deployment)

This optional pipeline publishes only the pinned
`./candidates/hermes#default` x86_64-linux package and its runtime references to
a dedicated Cachix cache. It does not build or publish a fleet system closure in
the credentialed job, upload node2 deployment/health/bootstrap roots, update
substituters, restart services, or run any activation command. The protected
`fleet-cache` and production rollout paths are unchanged. This pipeline neither
replaces nor completes an outstanding protected upload or any production gate.

A matching push to the canonical repository's **main** branch triggers the
workflow. Both jobs are skipped unless the nonsecret repository variable
`HERMES_RUNTIME_PUBLISH_ARMED` is exactly `enabled`. Unarmed runs do not
request or implicitly create the publish environment, or access its secret.
Once armed, the existing credential-free native/installed checks and integrated
node2 contract, bootstrap/spec and tunnel VM checks qualify the exact push SHA.
The publisher re-checks that SHA, requires a second environment-level enable
flag, builds the locked
candidate and pinned Cachix client before the token is available, and binds the
single runtime root to the identity from the separate qualification runner.
Identity is the SHA-256 of canonical sorted JSON over the root, every reachable
store path, its NAR SHA-256 and size, and its sorted direct reference set.
Both runners check actual NAR bytes against the Nix database before computing
identity; malformed, missing, extra, or forbidden paths fail closed. The client
and runtime out-links pin those store objects for the job. Only the validated
root, identity digest and canonical pinned client path are passed as outputs;
no NAR, full path-info inventory or operational artifacts go to GitHub artifact
storage. The credential-bearing step runs the pinned client directly from an
empty home, without evaluating the flake or running worktree scripts. Ordinary PR/fork checks cannot enter the publish job. Rapid
pushes may coalesce queued qualification runs; there is no promise to cache
every intermediate commit.

## Isolation boundary

The two builds use separate fresh GitHub-hosted runners, but the second build
and final upload share one protected runner. This is a **step-level secret
boundary**, not isolation from previously executed reviewed code in that job.
The repository is public; moving package data between jobs using its artifact
store is out of scope. Keep the gate disabled until the owner approves that
trust boundary, or use a separately approved private, authenticated staging
transport and a fresh upload-only runner instead. Never transfer the private
closure through public Actions artifacts to achieve isolation.

## One-time configuration (not performed by this change)

1. Review the exact workflow, helper, candidate and lock changes on protected
   main before enabling automatic publication. Ensure those paths and trusted
   actions require review, no untrusted users can push to main, and no less
   trusted workflow can use the same environment on main. GitHub's environment
   branch filter alone does **not** authorize one particular workflow name.
2. Create a distinct cache named `r33drichards-hermes-runtime`. Prefer a
   **private** cache unless the owner has separately authorized its contents
   for public distribution. Check what the exact Nix closure includes first:
   a store-path allow/deny check is not a content or privacy audit. Do not
   put credentials, fleet configuration, operator records, or private sources
   into the candidate or its runtime references.
3. Create GitHub environment `hermes-runtime-cache` in this repository.
   Configure selected deployment branches to allow **main only** and no tags;
   do not reuse the protected `fleet-cache` environment. Add only the
   environment secret `HERMES_RUNTIME_CACHE_WRITE_TOKEN`, issued for write
   access to this one dedicated cache (not an account-wide or fleet-cache
   token). GitHub exposes the selected token as `CACHIX_AUTH_TOKEN` in one
   step. Do not add it at repository/organization scope. Do not add a manual
   reviewer to this new environment if unattended publication is intended;
   the stricter existing fleet-cache approval remains in place. This
   configuration is still a trust grant to reviewed main code. If this
   scoping cannot be provided, leave the workflow disabled.
4. Once reviewed, set the environment variable
   `HERMES_RUNTIME_PUBLISH=enabled`. Last, and only after the environment
   and token are configured, set the nonsecret **repository** variable
   `HERMES_RUNTIME_PUBLISH_ARMED=enabled`. Missing repository arming skips
   both jobs; missing environment enablement or token fails closed.
   Publication begins on a subsequent matching push to main; there is no
   manual dispatch, deploy, consumer, or production switch in this workflow.
   To stop new uploads, clear the repository arming variable. To stop or
   prevent a run already started, cancel it and revoke the dedicated write
   token as appropriate.

## Verification

Run `python3 -m unittest discover -s tests -p test_hermes_runtime_publish.py -v`.
The local harness uses synthetic commands and cannot publish. In GitHub, require
the qualified exact revision, verify that an unarmed main push skips both jobs
without creating the environment, and test that a PR/fork/other branch cannot
reach the publish job. Confirm that missing environment enablement, a
mismatched closure, and the wrong token scope fail without a write. Verify the
first qualified and independently rebuilt identities agree; a non-reproducible
closure intentionally blocks publication. Verify the dedicated cache with an
isolated read-only client, not by changing any fleet host or cache settings.
