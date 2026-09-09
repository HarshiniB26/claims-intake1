# Tool comparison

I only worked with **one agent**: Cursor. I did not use Claude, ChatGPT, or
anything else for Day 4. The piece I asked it to do was the README — how to run
the service, how to run the tests, and why the Docker build uses
`--platform linux/amd64`.

What I can compare is the **Cursor agent** against **me in Cursor** without it
(opening files, running commands, clicking GitHub myself).

## What the agent made easy

It was already in this repo. It picked `claims.api.routes:app` out of
`routes.py` instead of guessing. It saw `Linux aarch64` and
`docker: command not found` in the terminal, so the README could say: this FDE
box is ARM, it has no Docker, build on the Mac, do not apt-install Docker here.

It started uvicorn and a POST came back **201**. I did not have to wire that
check by hand.

## What the agent made awkward

It tried `docker buildx` **here**, which fails. I had to say stop, use the Mac.
Because it can run the terminal, that wrong command looked like the next step.

It cannot click GitHub. Compare branches, Checks, merge blocked vs marked — I
did those in the browser. It also over-explained commands I already knew. Faster
to type `uv run pytest` myself.

## What I made easy and awkward without the agent

Easy: `/docs` in the browser, killing uvicorn with Ctrl+C, `git status` so I do
not commit `pythonApp/`. Awkward: the linux/amd64 paragraph. Left to me I would
have written “the flag sets the platform” and skipped *why* this ARM lab is not
the server CPU.

## What I would take where

For files that have to match this tree — README, `routes.py`, tests, Dockerfile —
I would use the **Cursor agent**. It can read the repo and hit a real missing
`docker`.

For GitHub, for watching the merge button, and for opening terminals, I would
not. I do that myself.

I would not add a second agent for this lab. I already had Cursor, and a chat
window with no repo would have told me to run Docker inside FDE.
