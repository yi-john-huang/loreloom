---
type: concept
title: IAM role
status: draft
created: 2026-07-18
updated: 2026-07-18
tags:
  - tech/aws
  - security/identity
aliases:
  - AWS IAM role
confidence: high
reviewed: null
sources:
  - "[[Sources/Examples/AWS IAM roles - AWS docs]]"
agent: codex
---

# IAM role

An IAM role is an AWS identity whose permission policies can be used by trusted identities that assume it.

## Explanation

A role separates the permissions needed for a task from a long-lived identity associated with a particular person. The assuming identity receives temporary credentials, while the role's trust configuration controls who or what may assume it.

## Implications and limits

- Role permissions and the ability to assume the role are separate concerns.
- Temporary credentials reduce the need to distribute long-lived access keys, but they do not make an overly broad policy safe.

## Related

- Appears in the generated [[Wiki/Examples/AWS identity basics|AWS identity basics]] guide.
- Navigated from [[MOCs/Examples/Technology]].

## Sources

- [[Sources/Examples/AWS IAM roles - AWS docs]]
