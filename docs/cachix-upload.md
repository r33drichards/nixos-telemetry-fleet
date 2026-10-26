# Upload-only workflow

Manual workflow `cachix-upload.yml` runs only on main with `expected_revision`
matching the workflow SHA. Protected environment `fleet-cache` supplies the
approved cache-only `CACHIX_AUTH_TOKEN` and variable
`CACHIX_UPLOAD_APPROVED=explicitly-approved`. Existing required-reviewer,
main-branch and no-bypass protections must be verified by the credential owner.
No environment/settings or credentials are created by this code.

CI rebuilds and validates the real node2 candidate and deployment specification
before exposing the token to the single upload step. The SHA256 digest binds that
step to the validated spec. Cachix pushes only that spec's runtime closure to the
approved public cache `r33drichards-nixos-fleet`; it does not push the whole store,
source archives or build outputs unrelated to that closure. Review the exact
revision for public data before approving the protected run.

The helper rejects other operations, non-main refs, wrong revisions/digests,
unapproved gates, missing tokens and broadened agent targets. It propagates push
failure. No activation token, agent credential, VM operation, Comin activation or
Cachix deployment command is present. A successful upload proves neither live
bootstrap nor activation. Preserve run revision/digest for a separate rollout.
