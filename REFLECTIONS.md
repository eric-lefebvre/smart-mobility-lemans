## Before you build anything
> **Reflection 1.** Look at the business question's sub-questions in
> `project3_smart_mobility_lemans.md` (the section "The system should help answer").
> Before building anything: which one or two of these do you think today's guided
> build will already answer well, and which do you suspect will need real judgment
> calls from you later? You'll revisit this after the final section.

IGNORED

## Stage 1 — Acquisition, twice over
> **Reflection 2.** Before reading the workflow steps later in this document: the
> static feed will run on a monthly schedule, the real-time feed every 15 minutes.
> Both *could* technically run every 15 minutes. Write your own guess now for why the
> static one doesn't — you'll check it against Stage 5's reasoning.

The static feed does not run every 15 minutes because the informations it contains only changes every month so 99% of the refreshes would be pointless.

## Stage 2 — Cleaning & structuring
> **Reflection 3.** Before running anything: if a tool infers each file's column
> types automatically and independently (so one file's `stop_id` column becomes
> numbers, another file's `stop_id` column stays text, just because of what values
> happened to appear in each file), what goes wrong when you try to join those two
> files on `stop_id`? Write your prediction, then compare it to the comment in the
> script below explaining why every GTFS file is read with `dtype=str`.

It would probably silently fail, so strings would be converted to integers. If you're lucky you would have an error explaining you cannot convert a string into an int.

## Stage 3 — Storage & versioning
> **Reflection 4.** Before reading further: roughly how many individual stop-time
> update rows would a 12-week semester of 15-minute snapshots produce, if you logged
> every one of them? (Order of magnitude is the point, not exact math.) Now compare
> that to logging one row **per route** per snapshot instead (there are only 27-40
> routes). What real analytical question — something a transport planner might
> actually ask — becomes harder to answer with the per-route version? Keep your
> answer; you'll need it again in the final section.

One row per stop-time would produce about 40 000 000 lines.
One row per route: 275 000 lines.
If logging per route means we have a list of all the stop-time of the route per line, then answering a question like "What is the busiest stop ?" would be harder to code and longer to check by a computer but eventually give the same answer. 

## Stage 4 — KPI definition & visualization for decision support
> **Reflection 5.** Is that the right way to encode this KPI? A bus arriving very
> early can strand a waiting passenger just as effectively as a very late one — from
> a passenger's perspective, both extremes might be "bad." Propose an alternative
> color/encoding rule for this same chart, and explain what decision or conclusion a
> viewer would reach *differently* under your rule versus the one below.

It seems obvious that a bus running very early and very late are both bad outcomes. So we could change the color scale to:
the closer a bus is to the time it is supposed to arrive at, the greener the chart
the further a bus is to the time it is supposed to arrive at, the redder the chart
A viewer would more accurately identify a bus arriving precisely at the scheduled time and not confuse a bus arriving too early for a "good" bus.

### Step 9 — Add the snapshot collection workflow (`.github/workflows/collect_snapshot.yml`)
> **Reflection 6.** Now check your Reflection 2 guess against the real answer: why
> would a 15-minute schedule for the *static* GTFS reference be wasteful, and why
> would a monthly schedule for the *real-time* delay snapshots make the whole
> real-time picture useless? Answer both halves — the mismatch runs in both
> directions.
