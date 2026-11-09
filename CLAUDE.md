# CLAUDE.md

This file guides Claude Code (claude.ai/code) in this repository. It says what the tree **is**, in
the present tense; a decision that outlives an issue is recorded here as a bullet.

## What this is

`dofjson` is the client for SIDOF's undocumented JSON open-data service (`sidof.segob.gob.mx`),
the Secretaría de Gobernación's system for the *Diario Oficial de la Federación* (DOF), Mexico's
official gazette, plus a fallback onto the DOF's own website (`www.dof.gob.mx`) for the days SIDOF
loses, and the reader of the `notas-archivo` release: the compact `codNota`+`titulo`+`fecha`
record of every legal provision ever published (over 1.2 million since 1917). A DOF *nota* is a
legal provision. The DOF is the official source of legal text.

It is one package of the Legistlan project (the `legistlan` organization), the one every other
reaches the DOF through: `nota2md` requires `dofjson>=0.5.0` and re-exports
`fetch_daily_legal_provisions` and `legal_provisions_titles`; `dofjson` itself imports no sibling.
It was `packages/dofjson` of a monorepo until 8 November 2026 (monorepo commit `f403872b1`); this
repository is that history filtered to the package's files, so `git log` and `git blame` reach the
first commit. A `#N` in a commit message, a comment or a docstring is an issue of that monorepo,
where those issues live.

## The package

- **One entry point.** Everything is reachable off `dofjson` (`dofjson.get_nota`,
  `dofjson.get_notas`, `dofjson.download_nota_pdf`, `dofjson.legal_provisions_titles`, ...);
  `tests/test_dofjson.py` pins `__all__`. Another package never imports `dofjson.sidof` or
  `dofjson.dofweb` directly: `dofjson.api` is the one module that decides between SIDOF and the
  website, and the only one allowed to depend on both.
- **The days SIDOF loses.** SIDOF reports a day it is missing as `200 OK` with empty note lists,
  exactly as it reports a Sunday. `dofjson.dofweb` recovers such a day from `www.dof.gob.mx`
  (verifying it with `dofjson/certs/dof-gob-mx-chain.pem`, because the server omits the
  intermediate that signs it), and a caller never needs to know which source answered: the
  `fuente` field says (`FUENTE_PREDETERMINADA` is `sidof`, `dofjson.FUENTE_WEB` the website).
- **Read order inside the package**, the way data flows: `dofjson.api` (entry points),
  `dofjson.sidof` (the raw REST client), `dofjson.dofweb` (the HTML fallback), `dofjson.notas`
  (pure helpers over a fetched day: page inference, the editions' note lists), `dofjson.titulos`
  (the release and the titles stream), `dofjson.archivo` (the resumable whole-history downloader
  behind `dofjson --archivo`), `dofjson.cli`.
- The package writes no dataset of its own; NOM codes and `codNota` values are opaque strings.

## Data: the release and the cache

- **`notas-archivo`** is the one release a workflow publishes: `notas-YYYY.tgz` per closed year
  and `notas-YYYY-MM.tgz` per month of the current year, each holding one `DDMMYYYY-notas.json`
  per day. `.github/workflows/notas-archivo.yml` builds the previous month on the 1st and folds a
  closed year on 1 January; `scripts/reparar_notas_archivo.py` refills the days SIDOF lost from
  the website and uploads nothing (a human runs `gh release upload ... --clobber`).
- **The release's owner.** This repository owns the release:
  `dofjson.titulos.DEFAULT_RELEASE_REPOSITORY` is `legistlan/dofjson`, and the environment
  variable `DOFJSON_RELEASE_REPOSITORY` (`<owner>/<name>`, read on every call by
  `release_repository`) points the lookup at a mirror of the release held elsewhere. The release
  was copied here once, byte for byte, with `scripts/copiar_notas_archivo.py` (the source is a
  required argument; the script names no repository), and the workflow's `schedule:` is on
  (`0 9 1 * *`). Changing the default is a release of `dofjson`.
- **The cache.** `dofjson.titulos.CACHE_DIR` (platformdirs: `~/.cache/dofjson` on Linux) is where
  `download_dof_assets` writes and every reader reads; it is this package's alone, never shared
  with `nota2md`'s. `cache_dir=None` skips it for one call; `SIN_CACHE_DIR` is the sentinel that
  tells "nothing passed" from "skip". `tests/conftest.py` points it at an empty per-test directory,
  so a cache hit in a test only ever happens when the test asks for one.
- The release listing is one request to `api.github.com`, sent with `GH_TOKEN` or
  `GITHUB_TOKEN` when set (`_github_api_headers`); the asset downloads are outside that quota.

## Documentation

One GitHub Pages site, `https://legistlan.github.io/dofjson/`, built and deployed by
`.github/workflows/website.yml` (the official Pages artifact flow, Pages source "GitHub Actions",
no `gh-pages` branch; pull requests only build, a push to `main` deploys). It has two halves with
no overlapping page:

- `docs/source/index.rst`, published under `/dev/`, is the **developer reference**: every name in
  `__all__`, every public method of an exported class and every CLI option gets a verified example,
  a live doctest run by the `docs` job of `test.yml` (network allowed); an exception is written on
  the page itself, naming the pytest suite that verifies the behaviour instead. Private helpers
  (leading underscore) get a full docstring and appear through `:private-members:` but need no
  example. The HTML build is strict (`-n -W`). The strict build and the doctest stay in `test.yml`'s
  `docs` job as the pull request gate; `website.yml` builds HTML only and never touches the network.
- `website/` is the Quarto **user site** at the root, in English, written from the README:
  install, command line, Python, archive, titles. `execute.enabled: false` (every example would
  hit SIDOF), no API reference; its code blocks are illustrative and the developer reference holds
  the verified ones. `tests/test_docs.py` keeps `website/pages/cli.qmd` naming every CLI option and
  every `dofjson/*.py` module documented by exactly one `automodule`.

Nothing in the tree names the former organization or the monorepo this package was extracted from:
provenance is said without naming, and links point at legistlan (never at Read the Docs).
`tests/test_docs.py` guards it, case-insensitively, on every tracked file.

## Commands

```bash
pip install -e ".[test]"
pytest tests                                                              # no test touches the network
python -m sphinx -n -W --keep-going -b html docs/source docs/build/html   # the strict build
python -m sphinx -b doctest docs/source docs/build/doctest                # network: SIDOF, the website, the release
quarto render website                                                     # the user site, into website/_site
python scripts/check_package_versions.py                                  # one step ahead of PyPI
```

## Releases to PyPI

- The version is dynamic (`dofjson.__version__`) and at most one step ahead of PyPI (the next
  patch, or the next minor with patch 0): `check-package-versions` in `test.yml` is the gate.
- A tag `vX.Y.Z` on `main` runs `publish-pypi.yml`, which refuses a tag that does not match
  `__version__`, builds, checks and uploads with the organization's `TWINE` secret.
- Publish order across repositories: `dofjson` before the `nota2md` release that raises its
  floor. A published package never carries a URL dependency.

## Git workflow: branches, issues and PRs

- A branch is created to work on one particular issue, only at the moment, while on `main`, an
  issue is read and about to be implemented.
- A secondary issue that turns out necessary is done on the working branch; no new branch.
- A pull request is opened only when the user explicitly asks for it, after the main issue and
  every secondary one are done. `main` takes changes only through a pull request (ruleset).

## Language policy

- The implementation is in English: identifiers, comments, docstrings, commit messages and new
  documentation, whatever language the instructions were given in.
- The codebase still mixes Spanish identifiers (`notas_del_dia`, `quita_notas_sin_titulo`,
  `descarga_*`, the Spanish help of the CLI and of `notas-archivo.yml`). Leave existing Spanish
  as it is when touching unrelated lines, no drive-by renames; new code, and code rewritten
  anyway, is English.
- Domain terms that are proper nouns or established Mexican legal vocabulary (`DOF`, `codNota`,
  `SIDOF`, `codDiario`, `NOM-...` codes) are names, not translated.

## Working conventions

- Naming favours precision over brevity: `codNota`, `legal_provisions_titles`,
  `download_nota_imagen_o_pdf` are the domain's vocabulary.
- Comments record the incident or the numeric check that justified a design choice (why a day is
  recovered from the website, why the certificate chain is shipped, why a token is sent); read
  them before "simplifying" the code they are attached to.
- No test touches the network: SIDOF, `www.dof.gob.mx` and GitHub are mocked.
