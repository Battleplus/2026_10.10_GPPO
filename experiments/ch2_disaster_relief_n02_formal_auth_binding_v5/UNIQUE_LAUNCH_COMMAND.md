# v5 Unique Entry

The package has not been deployed. After independent review, publish the
complete package with the existing atomic no-overwrite publisher under a fresh
release directory. The canonical source entry after publication is:

```text
/home/user1/w1-pilot/packages/ch2_disaster_relief_n02_formal_auth_binding_v5/package/civilian/driver.py
```

Run the target-runtime preflight first, without `--authorization`:

```bash
/home/user1/w1-runtimes/w1-py31116-torch270cu128-v2/w1-light-repaired-fair-rerun-py31116/bin/python -B \
  /home/user1/w1-pilot/packages/ch2_disaster_relief_n02_formal_auth_binding_v5/package/civilian/driver.py \
  --preflight \
  --work-root /home/user1/w1-pilot/diagnostics/n02-v5-preflight-formal-auth-binding
```

The formal one-shot entry, after a separately created package-external
authorization has passed the v5 upgrade validator, is:

```bash
/home/user1/w1-runtimes/w1-py31116-torch270cu128-v2/w1-light-repaired-fair-rerun-py31116/bin/python -B \
  /home/user1/w1-pilot/packages/ch2_disaster_relief_n02_formal_auth_binding_v5/package/civilian/driver.py \
  --run \
  --authorization /home/user1/w1-pilot/authorizations/<formal-attempt-id>.json
```

The v5 formal authorization must bind Manifest `dc5755a2...7be6b1`, Hashes
`f5385457...3a561e5`, Request `bf81982f...d7ca79`, and Attempt
`778ca33f...5ff8b07`, with the exact formal scope and budget in
`FORMAL_AUTHORIZATION_CONTRACT.json`. A mismatch stops before systemd
submission.
