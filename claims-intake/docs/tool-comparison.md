# Tool comparison

I used one agent for this work: Cursor. I did not use another product.

The task I did with the agent was the README: how to run the service, how to
run the tests, and why the image is built with `--platform linux/amd64`.

What I can compare is the Cursor **agent** against doing the same work **myself**
in Cursor (files, terminal, GitHub).

## What the agent made easy

It was already in this repository. It took `claims.api.routes:app` from
`routes.py` instead of inventing a path. It saw `Linux aarch64` and
`docker: command not found`, so the README could say this environment is ARM,
has no Docker, and the image should be built on a machine that does.

It ran uvicorn and a `POST /notifications` that returned `201`, which is the
check a new joiner needs.

## What the agent made awkward

It tried `docker buildx` inside this container, where Docker is not installed.
I had to stop that and keep the command for a host that has Docker. Because the
agent can run the terminal, a failing command looked like the next step.

It cannot operate GitHub. Opening a pull request, reading Checks, and seeing
whether merge is blocked are browser work. It also spelled out commands I
already knew; `uv run pytest` is faster typed.

## What I did myself

GitHub, `/docs`, stopping uvicorn, and `git status` before a commit were easier by hand. Writing the platform
paragraph without the agent would have been weaker: I would have restated the
flag instead of explaining host CPU versus the CPU the image must run on.

## Preference

I use the agent for work that has to match this tree: README commands, HTTP
mapping, tests, Dockerfile. It can read the files and hit a missing `docker`
binary.

I do not use it for GitHub clicks, for watching the merge button, or for
opening terminals. I do those myself.

I did not add a second agent. A chat window with no checkout would not have
seen `aarch64` or the missing CLI, and would have told me to build an image
here anyway.
