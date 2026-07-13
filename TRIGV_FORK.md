# Trigv fork — Apprise upstream PR

This repository is a **fork of [caronc/apprise](https://github.com/caronc/apprise)** used to develop and submit the Trigv notification plugin.

| Item | Value |
|------|-------|
| Upstream | https://github.com/caronc/apprise |
| Branch | `feature/trigv-plugin` |
| Plugin | `apprise/plugins/trigv.py` (`NotifyTrigv`) |
| Tests | `tests/test_plugin_trigv.py` |
| Trigv API docs | https://trigv.com/docs/learn/api-keys |

## URL syntax

| URL | Use |
|-----|-----|
| `trigvs://trgv_…` | Production (`https://api.trigv.com/api/v1/events`), channel `general` |
| `trigvs://trgv_…/deploys` | Production, channel slug `deploys` |
| `trigv://trgv_…@trigv-platform.test/general` | Local Herd dev (HTTP) |

Query parameters: `channel`, `url`, `image_url`, `delivery_urgency` (`standard` \| `time_sensitive`), `event_type`, `priority` (Pushover compatibility).

## Local test

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
tox -e lint,qa -- tests/test_plugin_trigv.py
```

Live send (uses real API key + bills one event):

```bash
apprise -vv -t "Apprise test" -b "Hello from Apprise" -n failure \
  "trigvs://trgv_YOUR_KEY/general"
```

## Open upstream PR

1. Fork `caronc/apprise` on GitHub (if not already).
2. Add remote: `git remote add trigv git@github.com:Trigv/trigv-apprise.git`
3. Push branch: `git push -u trigv feature/trigv-plugin`
4. Open PR to `caronc/apprise:master` from `Trigv/trigv-apprise:feature/trigv-plugin`.
5. Use the [Apprise PR template](.github/PULL_REQUEST_TEMPLATE.md) — fill the **Trigv** plugin section.
6. Optional: docs PR at https://github.com/caronc/apprise-docs

## Sync with upstream

```bash
git fetch origin
git merge origin/master
```

`origin` points at `caronc/apprise`.
