# 🤝 Contributing to Apprise

Thank you for your interest in contributing to Apprise!

We welcome bug reports, feature requests, documentation improvements, and new
notification plugins. Please follow the guidelines below to help us review and
merge your contributions smoothly.

---

## ✅ Quick Checklist Before You Submit

- ✔️ Your code passes all lint and style checks:
  ```bash
  tox -e lint
  ```
  If it reports issues, auto-fix them with:
  ```bash
  tox -e format
  ```

- ✔️ Your changes are covered by tests:
  ```bash
  tox -e qa
  ```


- ✔️ You followed the plugin template (if adding a new plugin).
- ✔️ A new or changed multi-target plugin records each success with
  `mark_delivered()`.
- ✔️ You included inline docstrings and respected the BSD 2-Clause license.
- ✔️ Your commit message is descriptive.

---

## 📦 Local Development Setup

To get started with development:

### 🧰 System Requirements

- Python >= 3.9
- `pip`
- `git`
- Optional: `VS Code` with the Python extension

### 🚀 One-Time Setup

```bash
git clone https://github.com/caronc/apprise.git
cd apprise

# Install all runtime + dev dependencies
pip install '.[dev]'
```

(Optional, but recommended if actively developing):
```bash
pip install -e '.[dev]'
```

If you use [uv](https://docs.astral.sh/uv/), one command sets up a `.venv`
with every dev tool and plugin dependency:
```bash
uv sync
uv run pytest
```

`tox` also works through uv:
```bash
uvx --with tox-uv tox -e qa
```

---

## 🧪 Running Tests

```bash
pytest               # Run all tests
pytest tests/foo.py  # Run a specific test file
```

Run with coverage:
```bash
pytest --cov=apprise --cov-report=term
```

---

## 🧹 Linting & Formatting

Use `tox` to run through the same toolchain as CI:

```bash
tox -e lint    # Check for lint violations and style issues (read-only)
tox -e format  # Auto-fix lint violations and apply consistent code style
```

If you prefer to call ruff directly:

```bash
ruff check .              # Check lint violations
ruff check . --fix        # Auto-fix lint violations
ruff format --check .     # Check code style
ruff format .             # Apply code style
```

---

## 🌍 Translations

Apprise presents its human readable strings (the names of the settings each
service accepts) in the language of whoever is running it. Every language
lives in its own directory under `apprise/i18n/`.

Start by seeing where help is needed:

```bash
python packaging/i18n_status.py
```

Each language is listed with how much of it is translated, followed by a
bullet for every string still waiting on someone. The report also names the
exact file to edit.

To improve an existing translation:

1. Open `apprise/i18n/<language>/LC_MESSAGES/apprise.po` for your language.
2. Fill in the `msgstr ""` under each `msgid` you want to translate. Leave
   the `msgid` lines alone; they are the English source text.
3. Remove any `#, fuzzy` comment once you have confirmed the translation
   below it. A fuzzy entry is a machine guess and Apprise ignores it.
4. Rebuild and check your work:

```bash
tox -e i18n            # refresh the .pot and every .po file
tox -e compile         # build the .mo files Apprise loads
tox -e i18n-status     # confirm nothing is left behind
```

To start a brand new language, let Babel create the catalog for you so its
header carries the right `Language`, `Language-Team`, and `Plural-Forms`
values for that language:

```bash
tox -e i18n            # build apprise/i18n/apprise.pot first
pybabel init --domain=apprise -i apprise/i18n/apprise.pot \
    -d apprise/i18n -l <language>
```

Name the directory after the language code, such as `de` or `ja`. A region
may be added when a language needs one (`pt_BR`), and Apprise falls back to
the plain language when no catalog exists for the region. Then translate it
the same way as above.

Only text a person reads gets translated. Anything a program reads, such as
a status code or a key in a JSON response, stays in English.

---

## 🧰 Optional: Using VS Code

1. Open the repo: `code .`
2. Press `Ctrl+Shift+P -> Python: Select Interpreter`
3. Choose the same interpreter you used for `pip install .[dev]`
4. Press `Ctrl+Shift+P -> Python: Discover Tests`

`.vscode/settings.json` is pre-configured with:

- pytest as the test runner
- ruff for linting
- PYTHONPATH set to project root

No `.venv` is required unless you choose to use one.

---

## 📌 How to Contribute

1. **Fork the repository** and create a new branch.
2. Make your changes.
3. Run the checks listed above.
4. Submit a pull request (PR) to the `main` branch.

GitHub Actions will run tests and lint checks on your PR automatically.

---

## 🧪 Need Help with Testing or Plugins?

See [DEVELOPMENT.md](./DEVELOPMENT.md) for:
- Full setup instructions
- Tox environment descriptions
- RPM testing
- Plugin development guidance

---

## 🙏 Thank You

Your contributions make Apprise better for everyone — thank you!

📝 See [ACKNOWLEDGEMENTS.md](./ACKNOWLEDGEMENTS.md) for a list of contributors.
