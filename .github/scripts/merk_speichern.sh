#!/bin/bash
# Merkzettel fb/gepostet.json speichern (18.11.2026, aus facebook-post.yml übernommen) – darf nie verloren gehen,
# sonst wird doppelt gepostet. Erst normal mit pull --rebase, sonst Notfall-Sicherung über die GitHub-Schnittstelle.
git add fb/gepostet.json 2>/dev/null || true
git diff --cached --quiet && exit 0
git commit -q -m "Facebook: gepostet $(TZ=Europe/Berlin date +'%d.%m. %H:%M')"
ok=0; for i in 1 2 3 4 5 6; do git pull --rebase -X theirs -q && git push -q && ok=1 && break; git rebase --abort 2>/dev/null; sleep $((i*5)); done
if [ "$ok" != 1 ]; then python .github/scripts/merk_sichern.py || python .github/scripts/fb_senden.py merkfehler || true; fi
exit 0
