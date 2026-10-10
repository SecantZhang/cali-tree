# CaliTree TLS diagnostics

At the time of TLS debugging, the twelve-case experiment was stopped at 1,413 total model calls, 17 frozen case-arm outcomes, and zero final-verification calls. Diagnostic probes did not resume the experiment or change its ledgers. A later separately authorized continuation completed at 2,364 combined model calls; see [the experiment report](calitree_typed_twelve.md). The TLS root cause remains unconfirmed.

## Saved observations

All 49 recorded experiment transport failures contain BAD_RECORD_MAC and occur on requests with images. All 258 text-only requests completed; 49 of 1,155 image-bearing requests failed. This is association, not proof of a particular cause.

External probes sent synthetic JSON only, without authorization, source images, reference labels or model completions. HTTP 401 is an expected completed TLS exchange. Authentication rejection may close an upload early, so these probes do not reproduce every condition of an authenticated model request.

| Diagnostic cell | Attempts | TLS MAC failures | Other transport failures |
|---|---:|---:|---:|
| 261008-tls-diagnostic-client-matrix / httpx / TLS 1.2 / 1500000 bytes | 16 | 0 | 0 |
| 261008-tls-diagnostic-client-matrix / httpx / TLS default / 1500000 bytes | 16 | 1 | 0 |
| 261008-tls-diagnostic-client-matrix / requests / TLS 1.2 / 1500000 bytes | 16 | 1 | 0 |
| 261008-tls-diagnostic-client-matrix / requests / TLS default / 1500000 bytes | 16 | 0 | 0 |
| 261008-tls-diagnostic-requests / requests / TLS default / 1024 bytes | 24 | 0 | 0 |
| 261008-tls-diagnostic-requests / requests / TLS default / 1500000 bytes | 24 | 3 | 0 |
| 261008-tls-diagnostic-upload-writes / curl / TLS default / 1500000 bytes | 24 | 0 | 1 |
| 261008-tls-diagnostic-upload-writes / requests / TLS default / 1500000 bytes | 24 | 0 | 0 |
| 261008-tls-diagnostic-upload-writes / requests-16k / TLS default / 1500000 bytes | 24 | 2 | 0 |

Total: 184 unauthenticated external probes; 7 TLS MAC failures and 1 other transport failures.

## Local and environment checks

- Python 3.13.2, OpenSSL 3.4.1; Requests 2.34.2, urllib3 2.8.0, HTTPX 0.28.1.
- No explicit proxy or certificate-override environment variables. The macOS proxy dictionary is empty; OpenAI and default routing use en0. This does not rule out transparent filtering or endpoint software.
- The public OpenAI certificate validated with Google Trust Services WE1 as issuer, TLS 1.3 and TLS_AES_256_GCM_SHA384. Certificate and hostname checks stayed enabled.
- All 32 local 1.5 MB TLS uploads succeeded and matched their complete body hashes, with one and two workers. The generated localhost certificate was explicitly trusted; its temporary private key was removed after the test.

## Interpretation

The failure is reproducible without model execution. Concurrency is not required. HTTPX, forced TLS 1.2 and 16 KiB body writes did not consistently eliminate it. System curl also encountered a broken pipe; that is a different error and does not establish the same TLS fault. A shared Requests Session is unlikely to explain production failures because each call creates its own session.

These checks narrow the investigation toward the external path or edge-server behavior, while leaving client/peer interactions possible. They do not identify the faulty component or prove a mitigation. No certificate verification was disabled, no dependencies or network settings were changed, and no experiment failure was retried.

## Next controlled comparison

Repeat synthetic large-upload probes from a second network, such as a phone hotspot, then compare failure rates. The user has been asked to confirm when that network is connected. Keep model settings, optimizer selections and the stopped experiment unchanged.

```bash
.venv/bin/python -m run.calitree_tls_probe --output-dir logs/exps/NEW-NETWORK-TLS-CHECK --clients requests --tls default --samples 12
```

For API guidance, see [official OpenAI connection-error troubleshooting](https://developers.openai.com/api/docs/guides/error-codes).
