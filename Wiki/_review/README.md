# Wiki review queue

Optional queue for pages that failed the auto-accept rule and that the agent did not place in their final section. Every page here keeps `status: draft` and has a `Needs review:` line in `log.md`.

To accept a page, the owner moves it to its final section with Obsidian, sets `status: reviewed` and `reviewed_by: owner`, and asks the agent to add it to `index.md` and to add a `review` entry to `log.md`.
