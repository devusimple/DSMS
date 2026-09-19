# Project Context

## Purpose

This file serves as the single source of truth for understanding this project's structure, architecture, and conventions. It exists so that any AI/developer joining the project can quickly grasp the full scope of the codebase without reading every file line by line.

## How to Use This File

1. **Read this file first** — before exploring the codebase, read this document in full to understand the project's overall structure and intent.
2. **Follow the conventions** — all code written in this project must adhere to the standards and patterns described here.
3. **Keep it updated** — whenever you make changes that affect the project structure, add new modules, change dependencies, update the build process, or alter conventions, **update this file** to reflect those changes.

## Mandatory Rule

> **RULE: Keep this file current.** Any structural, architectural, or convention change made to the project MUST be reflected in this document in the same commit/PR. If you add, remove, or modify a component, update the relevant section below. If you introduce a new pattern, document it here. This file is a living document — treat it as part of the codebase, not as documentation that can drift out of date.

---

## Project Overview

_(Describe the project here: what it does, who it's for, and its primary goals.)_

## Tech Stack

_(List the core technologies, frameworks, languages, and tools used in this project.)_

## Project Structure

_(Provide a high-level directory tree or breakdown of the project's folders and what each contains.)_

```
project-root/
├── src/          # Source code
├── tests/        # Test files
├── config/       # Configuration files
├── docs/         # Additional documentation
└── scripts/      # Build/deployment scripts
```

## Key Modules & Components

_(List the main modules, services, or components and a brief description of each.)_

| Module   | Path     | Description      |
| -------- | -------- | ---------------- |
| _(name)_ | _(path)_ | _(what it does)_ |

## Architecture & Design Patterns

_(Describe the architectural style, design patterns used, data flow, and how components interact.)_

## Build, Run & Test Commands

_(Provide the commands needed to build, run, and test the project.)_

```bash
# Install dependencies
npm install   # or pip install, go mod tidy, etc.

# Run the project
npm start     # or equivalent

# Run tests
npm test      # or equivalent
```

## Environment & Configuration

_(List environment variables, configuration files, and any setup required to run the project locally.)_

## Conventions & Coding Standards

_(Document naming conventions, code style, linting rules, commit message format, branching strategy, etc.)_

## Dependencies

_(List key dependencies and why they are used.)_

## Known Issues / TODOs

_(Note any known limitations, technical debt, or planned improvements.)_

## Changelog

_(Track significant changes to the project. Each entry should reference the commit/PR that introduced the change.)_

| Date     | Change                    | Author/PR |
| -------- | ------------------------- | --------- |
| _(date)_ | _(description of change)_ | _(PR #)_  |

---

## Contribution Guidelines

1. Always read this file before starting any work.
2. Update this file when your changes affect the structure, architecture, or conventions.
3. Follow the existing patterns — do not introduce new patterns without updating this document.
4. Keep the changelog up to date with your changes.
