# Contributing

Thanks for helping! Issues and pull requests are welcome in English or Portuguese.

1. Fork and create a branch from `main`.
2. Backend: `cd backend && pip install -e ".[dev]" && ruff check app tests && ruff format app tests && pytest`.
3. Frontend: `cd frontend && npm install && npm run build`.
4. New user-facing text goes in the locale files (`backend/app/locales`, `frontend/src/locales`),
   with at least `en` and `pt-BR`.
5. Open a pull request describing the change.

By contributing you agree that your contributions are licensed under the Apache License 2.0.
