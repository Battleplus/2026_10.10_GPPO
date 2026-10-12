# N01 R2 Formal Evaluation Stop Record

Status: **STOPPED_FIRST_ERROR / NOT_READY**

The single authorized SSH session exited during remote preflight with a
submission-script shell-quoting error in the reader assertion. The Python
dictionary key quotes were consumed by the outer shell, producing
`x[evaluation_identity]` and a `SyntaxError` before the preflight completed.

No approval was uploaded. No `systemctl start` was executed. No InvocationID,
run, admission record, trajectory, evaluation event, export, or resource
settlement was created. The formal evaluation therefore has zero measured
episodes and is not a model-evaluation failure.

The stop is final for this identity under the one-session authorization:
do not reconnect, resubmit, repair and retry, or start N2/N3 from this state.

## Recorded hashes

- Sanitized first-error report SHA-256: `98c2728160f7c03117e9f02cb4184565e94297d7eea186dfbcaa723156cda4a`
- Transcript SHA-256: `fc25e4cb80d729cc5b5a4324ba0bc9ad51d477d8d08e464565b32005381e8e9f`
- Submission script SHA-256: `9e5ccfaf1dbfc563cadd11c31e9cfb9ccd128095e6e8eab691e51bd2e661047f`
- Independent review SHA-256: `0fca1b724a77cc29f08632e74d20739437b392ba5476df270bb68b6512a38b29`

The transcript itself and all credentials, keys, raw remote paths, and runtime
artifacts are intentionally excluded from this archive.
