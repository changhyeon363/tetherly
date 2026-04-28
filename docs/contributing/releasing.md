---
icon: lucide/package
---

# Releasing

Tetherly's release flow is one command: push a `vX.Y.Z` git tag. The `Publish` workflow handles PyPI upload **and** GitHub Release creation from there. PyPI auth uses [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC), so there is no API token to rotate.

## Cutting a release

```bash
git tag v0.1.1
git push --tags
```

That's it. The `Publish` workflow runs three jobs in sequence:

1. **build** — checks out the repo with full history (so `setuptools-scm` can resolve the tag → version) and builds sdist + wheel with `python -m build`.
2. **publish** — uploads the artifacts to PyPI via `pypa/gh-action-pypi-publish` using OIDC.
3. **github-release** — creates a GitHub Release for the tag, attaches the sdist/wheel, and auto-generates release notes from commit messages and merged PRs since the previous tag.

Watch the run under **Actions → Publish**. On success:

- New version live at <https://pypi.org/project/tetherly/>
- New release at <https://github.com/changhyeon363/tetherly/releases>

If you want to tweak the auto-generated notes, edit the release on GitHub afterwards.

## How versioning works

The package version is **derived from the git tag** by [`setuptools-scm`](https://setuptools-scm.readthedocs.io/) — `pyproject.toml` declares `version` as `dynamic` and there is no hardcoded version number.

| Build context | Resulting version |
| --- | --- |
| Tag `v0.1.1` checked out | `0.1.1` |
| Commits past a tag | `0.1.2.dev3+g<sha>` |
| No tags yet (fresh clone) | `0.0.0+g<sha>` |

So **the only source of truth for the version is the git tag**. Don't edit a version field in `pyproject.toml` — there isn't one. To bump, just push a new `vX.Y.Z` tag.

## One-time PyPI setup (already done; here for the record)

If the trusted publisher relationship ever needs to be re-established (new project, repo rename, etc.):

1. Sign in at <https://pypi.org/manage/account/publishing/>.
2. Add a new "pending" or existing-project trusted publisher with:
    - **PyPI Project Name**: `tetherly`
    - **Owner**: `changhyeon363`
    - **Repository name**: `tetherly`
    - **Workflow name**: `publish.yml`
    - **Environment name**: `pypi`
3. In GitHub: **Settings → Environments → New environment → `pypi`**. (Optional: add required reviewers as a manual gate before each publish.)

After that, `git push --tags` is the entire release flow.

## Troubleshooting

- **`No matching distributions found` after publish** — PyPI's CDN can lag for a minute or two. Wait, then retry `pipx install tetherly`.
- **Workflow fails with `invalid-publisher` from PyPI** — the trusted publisher form on PyPI doesn't match the workflow. Recheck the four fields above (case-sensitive) and the environment name.
- **`setuptools-scm` writes version `0.0.0+...`** — the runner didn't fetch tags. Confirm `actions/checkout@v4` has `fetch-depth: 0`.
