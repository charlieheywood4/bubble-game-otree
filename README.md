# Bubble Game study (oTree)

oTree version of the Bubble Game experiment: groups of 3–5, prices up to $36, plain / hedonic /
directive interfaces in six treatment groups, a financial literacy survey, and one paid game
per session that is the same for everyone.

## Run it on this computer

```bash
cd ~/bubble-game-otree
source .venv/bin/activate
otree devserver
```

Open http://localhost:8000, choose **Bubble Game study**, and open the 5 demo links.

## Test it with bots

```bash
.venv/bin/otree test bubble_study 30
```

Bots play a full 30-person session three times (with valid group codes, invalid codes, and no
codes) and check every payoff rule against an independent recomputation, the groups, the treatment rotation,
a timed-out decision, and the shared paid game.

## Session settings (Sessions → Create new session → Configure session)

- **Participants and groups:** 3 to 10 people. Each person types a code from their slip:
  `1A`–`1E` for group 1 and `2A`–`2E` for group 2, so you decide the groups by who gets which
  slip. Each group needs 3–5 people: 3–5 people use only group 1 codes; 6–10 split across both
  (e.g. 9 people: 1A–1E and 2A–2D). Groups are set once everyone has finished the welcome
  page and stay the same for every game, with a new random place in line each game.
  If a code has no group number or a group would end up outside 3–5, the computer falls back to
  random groups as equal in size as possible (6 → 3+3, 7 → 3+4, 9 → 4+5, 10 → 5+5).
- **Prices** shift with group size so the last trader can always be offered $36: groups of 5
  start at $2.25 ($2.25, $4.50, $9, $18, $36), groups of 4 at $4.50, groups of 3 at $9.
  Prices a group can't reach are not shown and stay blank in the data. Each round records
  `group_size`.
- **Comprehension check:** six questions, one at a time; after each answer the screen shows
  the correct answer and an explanation. Answers are recorded (first answer only) and scored
  in `cq_correct`; a wrong answer does not block the participant.
- **paid_game:** 0 draws the paid game at random (default). 1–10 fixes it, for testing only.
- **rotation_offset:** set to the number of participants already run in earlier sessions,
  so the six groups and price directions keep rotating evenly across sessions.
- **timers:** 45 seconds per decision (90 for practice).

## Running several sessions

Set **rotation_offset** to the total number of participants in all earlier sessions, so the
six groups stay balanced overall. Three sessions of 10, for example: 0, then 10, then 20.
With those offsets the 30 participants split exactly 5 per group.

Create each session in the **econ_lab** room with exactly the number of people who showed up
(at least 3). Groups are formed from the codes once everyone has joined and finished the
welcome page, so nobody gets past the first wait page until the last person arrives. A session
waiting for people who never arrive cannot finish: if someone doesn't show, delete the session
and create a new one for the right number.
Before the next session starts, go to **Rooms → econ_lab** and close the room's current session.

## When a participant gets stuck or leaves

- **Decision pages** have a timer. If someone stops responding or closes the browser, the
  server submits their page when time runs out (every price counts as "don't buy", and
  `timed_out` is recorded), so the group keeps going. For a closed browser this needs the
  production server's **worker** process: on Heroku, **Resources** must show both `web` and
  `worker` switched on. With the worker off (the current setup, to save cost), an open browser
  still submits at the timer, but a closed or frozen one leaves its group waiting: open the
  session's **Monitor** tab and click **Advance slowest participants**, which records that
  decision exactly as a timeout would.
- **Pages without a timer** (welcome, instructions, comprehension check, part intros, results,
  financial literacy): in the session's **Monitor** tab, click **Advance slowest participants**.
  Skipped answers are stored as blank, never as answers the participant did not give, and are
  flagged: `skipped` (demographics), `cq_skipped` (comprehension), `finlit_skipped`
  (financial literacy, with no score).
- A participant who closed the browser can reopen the room link and type the same code. They return to the page they were on.

## Structure

- `demographics/`: confirms the code, then asks gender and major (broad groups).
- `bubble/`: instructions, comprehension check, practice (round 1), part 1 (rounds 2–6),
  part 2 (rounds 7–11). Groups come from the room codes and stay fixed; places in line are re-randomized every round.
- `survey/`: financial literacy questions, then the paid-game reveal.
- Data export: each round records interface, treatment, price direction, choices at every
  price, position, price offered, outcome, and earnings.

## Paying in cash

- Each participant gets a paper slip with a code (`1A`–`1E` or `2A`–`2E`). When they open the
  room link, they type that code; `_rooms/econ_lab.txt` lists the 10 valid codes, and oTree
  rejects any other. **Payments** in the admin lists the cash owed by code.
- The last screen shows the code and the amount in large type. Call participants to the front
  one at a time by code and pay the envelope labeled with that code.
- Everyone gets a $3 show-up fee plus their earnings from the paid game ($0, $2, $2.25,
  $4.50, $9, or $18), so payments are $3, $5, $5.25, $7.50, $12, or $21. **Bring quarters**
  as well as $1 and $5 bills.
- A group costs the most when everyone in it buys: a group of 5 at most $48.75 ($33.75 +
  $15 in fees, $9.75 a person), a group of 4 at most $43.50 ($10.88 a person), a group of 3
  at most $36 ($12 a person). So 10 people (5+5) cost at most $97.50, and 9 people (4+5)
  at most $92.25.

For lab sessions, deploy to oTree Hub (https://www.otreehub.com) or Heroku, set
`OTREE_ADMIN_PASSWORD`, `OTREE_SECRET_KEY` (any long random string), `OTREE_PRODUCTION=1`, and
`OTREE_AUTH_LEVEL` (`STUDY` if you can; oTree Hub's free public projects only allow `DEMO`,
which still keeps the data and admin pages behind the password), and use the **econ_lab** room.
On Heroku, switch on both the `web` and `worker` dynos.
