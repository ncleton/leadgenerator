# Security policy

Report vulnerabilities privately to the repository owner rather than opening a
public issue with exploit details or credentials.

Never include API keys, access tokens, private profiles, browser sessions, scraped
datasets, or customer exports in a report. Describe the affected tool, expected
boundary, reproduction steps using test data, and potential impact.

Lead Generator never requests, extracts, exports, or persists LinkedIn credentials,
MFA codes, cookies, or authenticated browser sessions. It may keep a public
professional profile URL for human review, but all automated research must remain
available without authentication or access-control bypass.

The highest-risk boundaries are public URL validation, prompt-injection handling,
paid enrichment confirmation, HubSpot write confirmation, and secret redaction.
