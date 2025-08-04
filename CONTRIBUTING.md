# 🤝 Contributing to Apprise

Thank you for your interest in contributing to Apprise!

We welcome bug reports, feature requests, documentation improvements, and new
notification plugins. Please follow the guidelines below to help us review and
merge your contributions smoothly.

---

## ✅ Quick Checklist Before You Submit

- ✔️ Your code passes all lint checks:
  ```bash
  tox -e lint
  ```

- ✔️ Your changes are covered by tests:
  ```bash
  tox -e qa
  ```

- ✔️ Your code is clean and consistently formatted:
  ```bash
  tox -e format
  ```


- ✔️ You followed the plugin template (if adding a new plugin).
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
pip install .[dev]
```

(Optional, but recommended if actively developing):
```bash
pip install -e .[dev]
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

## 🧹 Linting & Formatting with ruff

```bash
ruff check apprise tests           # Check linting
ruff check apprise tests --fix     # Auto-fix
ruff format apprise tests          # Format files
```

---

## 🧰 Optional: Using VS Code

1. Open the repo: `code .`
2. Press `Ctrl+Shift+P → Python: Select Interpreter`
3. Choose the same interpreter you used for `pip install .[dev]`
4. Press `Ctrl+Shift+P → Python: Discover Tests`

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
