#!/usr/bin/env python3
import sys
from functools import partial
from pathlib import Path
from subprocess import PIPE, run

HERE = Path(__file__).parent

runhere = partial(run, cwd=HERE)


def main() -> None:
    # FIXME: ideally there would be some sanity-checking of `tagname`
    tagname = sys.argv[1]

    # verify we have a clean repo
    changed = runhere(['git', 'status', '--short'], check=True, stdout=PIPE).stdout
    assert not len(changed), "Repo must be clean"

    # verify we are on branch master
    branch = runhere(
        ['git', 'branch', '--show-current'],
        check=True,
        stdout=PIPE,
        encoding='utf-8',
    ).stdout.strip()
    assert branch == "master", f"Incorrect branch {branch!r}"

    # update pyproject.toml
    pyproject = HERE / 'pyproject.toml'
    tmpfile = HERE / 'pyproject.toml.new'
    with pyproject.open() as f_in, tmpfile.open('w') as f_out:
        for line in f_in:
            if line.startswith('version = '):
                f_out.write(f'version = "{tagname}"\n')
            else:
                f_out.write(line)
    tmpfile.replace(pyproject)

    sys.stderr.write("Updating version inside pyproject.toml ...\n")
    runhere(['git', 'add', 'pyproject.toml'], check=True)
    runhere(['git', 'commit', '-m', 'Updated version in pyproject.toml'], check=True)
    sys.stderr.write(f"Tagging {tagname!r} ...\n")
    runhere(['git', 'tag', tagname], check=True)
    sys.stderr.write("Pushing ...\n")
    runhere(['git', 'push'], check=True)
    sys.stderr.write(f"Pushing tag {tagname} ...\n")
    runhere(['git', 'push', '--tags'], check=True)


if __name__ == "__main__":
    main()
