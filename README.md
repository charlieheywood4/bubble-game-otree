# Bubble Game study (oTree)

oTree version of the Bubble Game experiment: groups of 5, prices $3–$48, plain / hedonic /
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

Bots play a full 30-person session and check every payoff rule, the treatment rotation,
a timed-out decision, and the shared paid game.

## Session settings (Sessions → Create new session → Configure session)

- **Participants:** must be a multiple of 5.
- **paid_game:** 0 draws the paid game at random (default). 1–10 fixes it, for testing only.
- **rotation_offset:** set to the number of participants already run in earlier sessions,
  so the six groups and price directions keep rotating evenly across sessions.
- **timers:** 45 seconds per decision (90 for practice).

## Running several sessions

Set **rotation_offset** to the total number of participants in all earlier sessions, so the
six groups stay balanced overall. Three sessions of 10, for example: 0, then 10, then 20.
With those offsets the 30 participants split exactly 5 per group.

Create each session in the **econ_lab** room with exactly the number of people who showed up,
rounded down to a multiple of 5. A session waiting for people who never arrive cannot finish.
Before the next session starts, go to **Rooms → econ_lab** and close the room's current session.

## When a participant gets stuck or leaves

- **Decision pages** have a timer. If someone stops responding or closes the browser, the
  server submits their page when time runs out (every price counts as "don't buy", and
  `timed_out` is recorded), so the group keeps going. This needs the production server.
- **Pages without a timer** (welcome, instructions, comprehension check, part intros, results,
  financial literacy): in the session's **Monitor** tab, click **Advance slowest participants**.
  Skipped answers are stored as blank, never as answers the participant did not give, and are
  flagged: `skipped` (demographics), `cq_skipped` (comprehension), `finlit_skipped`
  (financial literacy, with no score).
- A participant who closed the browser can reopen the room link and type the same station
  number. They return to the page they were on.

## Structure

- `demographics/`: confirms the station number, then asks gender and major (broad groups).
- `bubble/`: instructions, comprehension check, practice (round 1), part 1 (rounds 2–6),
  part 2 (rounds 7–11). Groups and positions are re-randomized every round.
- `survey/`: financial literacy questions, then the paid-game reveal.
- Data export: each round records interface, treatment, price direction, choices at every
  price, position, price offered, outcome, and earnings.

## Paying in cash

- Each participant draws a paper slip with a random station number. When they open the room
  link, they type that number; `_rooms/econ_lab.txt` lists the 36 valid numbers, and oTree
  rejects any other. **Payments** in the admin lists the cash owed by station number.
- The last screen shows the station number and the amount in large type. Call participants
  to the front one at a time by station number and pay the envelope labeled with that number.
- Payments are whole dollars from $0 to $24 ($3, $5, $6, $12, or $24). The most a full group
  of 5 can cost is $45, so 30 participants cost at most $270. Bring mostly $1 and $5 bills.

For lab sessions, deploy to oTree Hub (https://www.otreehub.com) or Heroku, set
`OTREE_ADMIN_PASSWORD`, `OTREE_SECRET_KEY` (any long random string), `OTREE_PRODUCTION=1`, and
`OTREE_AUTH_LEVEL=STUDY`, and use the **econ_lab** room.
