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

- ✔️ All tests pass locally.

- ✔️ Your code is clean and consistently formatted:
  ```bash
  tox -e format
  ```

- ✔️ You followed the plugin template (if adding a new plugin).
- ✔️ You included inline docstrings and respected the BSD 2-Clause license.
- ✔️ Your commit message is descriptive.

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
