# N02 v5 Formal Authorization Binding Repair

## Scope

This package is an independent repair of the v4 formal entry gate. The v4
package, its published directory, static identities, and all failure evidence
remain unchanged. No server connection, deployment, authorization, token,
formal attempt, model forward, or training was performed for v5.

## Defect

The v4 static Request intentionally records a preflight candidate:

```text
authorized=false
request_frozen=false
request_scope=candidate_target_runtime_preflight_only
budget=null
```

`load_release_binding()` correctly returned those values, but
`validate_authorization_document()` required the same binding to already be
formally authorized, frozen, scoped, and budgeted. A valid package-external
authorization therefore could never pass the gate.

## Repair

The v5 gate keeps the static candidate values unchanged. A one-time external
authorization must contain a `formal_upgrade` object with schema
`n02-v5-formal-authorization-upgrade/1`. That object supplies the formal scope
and budget and binds the release manifest, hash bundle, candidate Request
identity, and candidate Attempt identity. The top-level request and attempt
records must repeat the same bindings. The validator returns effective formal
fields only after all comparisons pass.

The package release is `ch2_disaster_relief_n02_formal_auth_binding_v5`.
The new static identities are:

```yaml
Manifest: dc5755a2cb7ecb6c82599ae9297155f1b9fd6cce256ca24050b0dad5127be6b1
Manifest file: 99aa0fc40c2147594dcc4e37629b067247b992779aabd04b40952fdbf35cf34a
Hashes: f53854570c452b9e8d21badcf3e72ee1d5747a193c28a7e66d63779103a561e5
Hashes file: 9baf58894f7b3c7108e5b7b61664988a14402a6edf860f66536263d68fa91e98
Request: bf81982fafa28ebf84224fd610b978cadb89ff938739d1519af18a210cd7ca79
Attempt: 778ca33f3347d3afc1e01beb520c099d564e524ffe3639fbd4f9601615ff8b07
```

## Verification

The new tests cover a valid upgrade, manifest/hash mismatch, scope mismatch,
budget mismatch, and mutation of the static candidate flags. They passed:

```text
5 passed in 0.10s
```

`load_release_binding()` was also run against the assembled v5 package and
returned the expected candidate state. Python compilation passed; generated
`__pycache__`, `.pyc`, and `.pyo` files were removed before the final package
identity was computed.

## Next gate

The v5 package still requires an independently reviewed server publication and
no-authorization preflight before any external formal authorization is made.
The preflight must not create a token, attempt directory, checkpoint, or run.
