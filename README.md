# Claude Code Analytics

## Overview

This is a web application that indexes local Claude Code data (typically stored in ~/.claude) and provides a Web UI for exploring that data.


## Use cases

Primary use case will be search.

Examples:

- Show sessions that lasted more than 10 messages.
- Show sessions where total token usage is between A, B.
- Show sessions by git branch name.

For each session shown, user should be able to explore all associated data for that session.

## Design

Overarching priority is simplicity, and speed of implementation.  We will use the reflex framework (reflex.dev).  This allows the entire full stack application to be implemented in Python only.

### On data

We will NOT replicate the data from ~/.claude/.  Instead we will index it at application startup in memory.  This won't scale to large datasets, but it's good enough to start with.
