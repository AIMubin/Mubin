# Synchronous engine adapter timeout semantics

Status: operational containment of blocking workers; **not** a kill guarantee.

The orchestration kernel accepts async and synchronous engine adapters. A
synchronous adapter runs in a process-wide, bounded thread pool with eight
worker permits. Admission is non-blocking on the event loop; waiting for a
permit consumes the caller's regular request deadline. A permit remains held
until the synchronous function **actually returns or raises**, not merely
until the request gives up waiting. Concurrent cases therefore cannot create
an unbounded number of still-running synchronous engine handlers.

A request that exceeds its deadline reports `UNAVAILABLE` with
`ENGINE_TIMEOUT`. If the synchronous handler was already submitted and
had not yet returned at receipt creation, the receipt also includes
`SYNC_WORKER_TERMINATION_NOT_CONFIRMED` in `uncertainties`.
The eventual worker result is never published as success for that request.
Late exceptions are observed without including their contents in logs or
public receipts. A request that expires while waiting for a worker permit
has not submitted a worker and receives only `ENGINE_TIMEOUT`.

**Hard limitation:** Python threads cannot be forcibly terminated safely.
A blocked worker may continue running and perform side effects after its
request times out. Eight indefinitely blocked handlers can prevent further
synchronous engine work in that process. These limits prevent uncontrolled
worker fan-out but do not ensure process liveness, rollback, or cancellation.
Only service-owned cooperative cancellation or a separately reviewed,
killable process boundary can provide a stronger termination contract.
Adapter authors must make side effects idempotent and honor request deadlines
on every external I/O operation.

The research-only, source-rights, human-review, and scholarly-qualification
gates remain unchanged.
