# 2. Avoid Nested Templates

Date: 2019-07-25

## Status

Accepted

## Context

Nested Cloudformation templates offer "1-click" deployment of managed  templates, simplifying operations. However, nested templates obfuscate Cloudformation change-set detail, making review of changes hard.

## Decision

We will not use nested templates for this project because we feel the value of visibility into change set effects is of greater importance than 1-click deployment.

## Consequences

The feature for 1-click deployment will require an alternate orchestrator or will need to be reviewed for business necessity.
