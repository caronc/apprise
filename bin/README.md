# 🛠️ Apprise Development Guide

Welcome! This guide helps you contribute to Apprise with confidence. It outlines
how to set up your local environment, run tests, lint your code, and build 
packages — all using modern tools like [Tox](https://tox.readthedocs.io/) and 
[Ruff](https://docs.astral.sh/ruff/).

---

## 🚀 Getting Started

Set up your local development environment using Tox:

```bash
# Install Tox
python -m pip install tox
```

Tox manages dependencies, linting, testing, and builds — no need to manually 
install `requirements-dev.txt`.

---

## 🧪 Running Tests

Use the `qa` environment for full testing and plugin coverage:

```bash
tox -e qa
```

To focus on specific tests (e.g., email-related):

```bash
tox -e qa -- -k email
```

To run a minimal dependency test set:

```bash
tox -e minimal
```

---

## 🧹 Linting and Formatting

Apprise uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting.
This is configured via `pyproject.toml`.

Run linting:

```bash
tox -e lint
```

Fix formatting automatically (where possible):

```bash
tox -e format
```

> Linting runs automatically on all PRs that touch Python files via GitHub 
> Actions and will fail builds on violation.

---

## ✅ Pre-Commit Check (Recommended)

Before pushing or creating a PR, validate your work with:

```bash
tox -e lint,qa
```

Or use a combined check shortcut (if defined):

```bash
tox -e checkdone
```

This ensures your changes are linted, tested, and PR-ready.

---

## 📨 CLI Testing

You can run the `apprise` CLI using your local code without installation or run within docker containers:

```bash
# From the root of the repo
./bin/apprise -t "Title" -b "Body" mailto://user:pass@example.com
```

Alternatively you can continue to use the `tox` environment:


```bash
# syntax tox -e apprise -- [options], e.g.:
tox -e apprise -- -vv -b "test body" -t "test title" mailto://credentials
```

Optionally, add the `bin/` directory to your PATH:

```bash
export PATH="$(pwd)/bin:$PATH"
```

---

## 📦 RPM Build & Verification

Apprise supports RPM packaging for Fedora and RHEL-based systems. Use Docker 
to safely test builds:

```bash
# Build RPM for EL9
docker-compose run --rm rpmbuild.el9 build-rpm.sh

# Build RPM for Fedora 42
docker-compose run --rm rpmbuild.f42 build-rpm.sh
```

---

## 🧪 GitHub Actions

GitHub Actions runs:
- ✅ Full test suite with coverage
- ✅ Linting (using Ruff)
- ✅ Packaging and validation

Linting **must pass** before PRs can be merged.

---

## 🧠 Developer Tips

- Add new plugins by following [`demo.py`](https://github.com/caronc/apprise/blob/master/apprise/plugins/demo.py) as a template.
- Write unit tests under `tests/` using the `AppriseURLTester` pattern.
- All new plugins must include test coverage and pass linting.
