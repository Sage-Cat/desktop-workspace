# Development and releases

## Working with the pins

The parent Git tree records an exact commit for each submodule. `make pins`
prints those commits; `make check` verifies the checkout matches them. It rejects
missing modules, unexpected URLs, symlinks and modified component worktrees.
Ignored local files are not part of a component commit or the source bundle.

A recursive clone checks out component commits in detached HEAD state. Before
editing a component, create a branch there or switch to its normal development
branch. Commit and push the component before recording its pin in the parent.

```sh
git -C gnome-winctl switch -c improve-placement
# Edit and test the component, then commit and push it.
git add gnome-winctl
make check
make integration
git commit -m 'update: advance window-control component'
git push
```

This example does not merge the component branch. Follow that repository's normal
branch workflow. Parent pins do not automatically follow changing child branches;
a pointer update is a reviewed change with combined checks.

To adopt a parent update in a clean checkout:

```sh
git pull --ff-only
git submodule update --init --recursive
```

Keep uncommitted component work on a branch before changing pins. The parent
never resets component branches or runs `submodule update --remote` during builds.

## Checks

See [validation](validation.md) for the real VM procedure, recorded results and
coverage limits.

- `make test`: parent pin, packaging and privacy regression tests.
- `make check`: pin/privacy checks and all component source suites.
- `make integration`: real placement and HUD cancellation in isolated GNOME.
- `make check-source`: component suites without parent Git metadata; for release archives.

Enable the local staged privacy check after cloning:

```sh
git config core.hooksPath .githooks
```

CI checks out the exact submodule commits, runs source and integration checks,
and only then publishes `build-<parent SHA>`. Latest promotion is serialized.
Every release includes a complete source archive, a component commit lock file
and checksums. Child source comes from the pinned Git commits, never untracked
files or the working directory contents. Tags and published assets are not replaced.

Use the generated release source asset for a complete checkout without Git.
GitHub's automatic parent-only source ZIP does not include submodule contents.
After extracting the complete asset, install the documented build dependencies,
run `npm --prefix login-hud ci`, then `make check-source`. Git-based installation
and pin changes require a recursive clone.

## Installation boundary

`make stage` and `make install` pass a filtered public-component manifest to
Workspace State. Its existing release installer handles atomic packaging,
rollback and next-login activation. The parent does not install or enable tasks
from unlisted repositories. Staging and scheduling leave running applications
and GNOME modules untouched.
