---
type: wiki
title: AWS identity basics
status: draft
created: 2026-07-18
updated: 2026-07-18
tags:
  - tech/aws
  - security/identity
aliases: []
generated: true
generated_at: 2026-07-18
generator: codex-example
inputs:
  - "[[Knowledge/Examples/IAM role]]"
review_status: unreviewed
agent: codex
---

# AWS identity basics

> [!WARNING]
> Generated example. Verify important claims against the linked Knowledge and Source notes.

## Overview

AWS permissions can be attached to identities used by people or workloads. This small example currently covers only IAM roles and should not be treated as a complete identity guide.

## Roles

An [[Knowledge/Examples/IAM role|IAM role]] packages permissions for trusted identities to assume. Its temporary-credential model can reduce reliance on long-lived keys, while correct trust and permission policies remain essential.

<!-- human:start -->
## Human notes

Add your own framing here. A regeneration workflow must preserve this block exactly.
<!-- human:end -->

## Inputs

- [[Knowledge/Examples/IAM role]]
