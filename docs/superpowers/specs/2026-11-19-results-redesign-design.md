# Results redesign: one Results page with Overview and Responses

Date: 2026-11-19
Prototype: [Campaign Feedback Loop](https://claude.ai/artifact/UFF9k3NRNRJoUHiHmyJqer), screen "Results" (version of 2026-11-19).

## Why

The Results page built in the stacked PRs #134 to #143 is hard to use:

- Every survey is a button, so with many surveys the picker fills the screen before any result shows.
- Charts show raw numbers instead of a message. NPS shows 11 bars, mostly "0 answers (0%)". A negative NPS (−33) is drawn as a green bar a third full, so a bad score looks good.
- Cards such as "Score by segment" and "Score by month" appear with a single row and nothing to compare.
- Results and Responses are two sidebar pages that answer one question: "how is this survey doing, and what did people say?"

The prototype was updated to fix this. This design rebuilds the Results area to match it.

## Goals

- One **Results** item in the sidebar, with two tabs for the chosen survey: **Overview** (visuals) and **Responses** (the anonymised answers).
- A survey picker that works with hundreds of surveys.
- Each question kind gets the visual that suits it (table below), for thumbs, NPS, CSAT and custom surveys.
- Cards only appear when they have something to show.
- Readers stay anonymous, including in free-text comments and small segments.

## Non-goals

- The **AI summary of comments**. The Overview shows a "Coming soon" banner in its place. Sending comments to an AI service needs Liana's data processing agreement first (`docs/gdpr.md`, "To decide with Liana").
- Results across several surveys at once. NPS, CSAT and thumbs scores cannot be combined into one chart.
- The cross-survey performance report (#154). It is closed: the front page card shows the 5 most active surveys, and each survey's response rate is a KPI on its Results page.
- Real authentication, the respondent screens, and the full public survey page (#105).

## Anti-goals

The work fails, even if it runs, if:

- a reader can be identified from the Results area: an email or phone number typed into a comment, or a segment so small that its score points to one person;
- a negative or bad score looks positive (colour, bar length or sign);
- the page shows an empty or one-row comparison card as if it meant something.

## Constraints

- Follow the repo rules in `CLAUDE.md`: backend in `data-analyzer` with `domain.py` / `repo.py` / `routes.py`, every query through `tenant_connection()`, `openapi.yaml` updated with every endpoint change, frontend uses the tokens in `src/styles/tokens.css` and the shared components in `src/components/ui`.
- Rebuild the screens in React from the prototype. Do not copy its code.
- Answers are anonymous by default (`docs/gdpr.md`). Only `contact_ref` links an answer to a person, and only after opt-in. The Results area never shows `contact_ref`. People who asked to be contacted are listed on the Contact requests page.
- Segments come from the `seg` parameter on answer links, stored as `responses.segment` (default `all`), from #134.

## Approaches

1. **Merge the stack as it is, then rework through new tickets.** It delivers the author's work quickly, but `main` ships the confusing page meanwhile, and the rework then rewrites most of that frontend. Rejected: reviewing 9 PRs of UI code that gets deleted.
2. **Keep the backend, redo the frontend.** (Chosen.) The backend tickets keep their numbers with updated criteria, and their code becomes backend-only PRs. The frontend tickets are rewritten to the new design in four slices. The stack's frontend PRs are closed. It keeps the tested backend and builds the frontend once. The cost: the stack's frontend work is discarded, and separating backend commits from mixed PRs takes effort. The project owner agreed to this on 2026-11-19.
3. **Rework each PR in place.** It keeps PR numbers and history, but every change to a lower PR has to be merged up through the whole stack again, and the PR boundaries do not match the new design's slices. Rejected.

## Design

### Page layout

```
Results
[ Member NPS 2026 ▾ ]  NPS survey · Live            (searchable survey picker)
● Collecting answers · last one 2 h ago · Closes Thu 31/12/2026 · Shared by link
[ Overview ] [ Responses 248 ]                      Segment [ All segments ▾ ]
```

- **Survey picker**: a button showing the chosen survey's name, type and status. It opens a panel with a search field and a list (name, type, number of answers, status, tick on the chosen one). "No surveys match …" when the search finds nothing. Keyboard: the search field has focus when the panel opens, arrow keys move, Enter picks, Escape closes.
- **Default survey**: the survey in the URL (`/results?survey=<id>`), otherwise the survey with the latest answer, otherwise the newest survey. Links from elsewhere ("See results" on the front page and the Surveys list) pass `survey`.
- **Status line**: collecting or closed, time of the last answer, close date, and how it was shared (from the survey's channels).
- **Tabs**: Overview and Responses. The Responses tab shows the number of responses. The URL keeps the tab (`&tab=responses`) and the segment (`&segment=members`), so a reload or a shared link opens the same view.
- **Segment filter**: shown only when the survey has answers from 2 or more segments. It applies to both tabs. It lists only segments with 5 or more answers (see Anonymity rules).
- The sidebar has one **Results** item. The old `/responses` route redirects to `/results?tab=responses`.

### Overview: KPI cards

| Survey type | KPI cards |
|---|---|
| Thumbs | Positive (Good + Loved it) %, Responses, Response rate, Loved it % |
| NPS | NPS (signed, e.g. −33), Responses, Response rate, Promoters % with "vs N% detractors" |
| CSAT | Satisfied (4–5) %, Responses, Response rate, Average rating "out of 5" |
| Custom | Responses, Response rate, Completed all questions %, plus the average of the first rating question if there is one |

- The score card shows the change since the previous month (arrow and "+5 since October") only when the previous month has answers.
- Response rate uses the survey performance data from #12: responses ÷ views, with "N of M viewed" as the note. "—" when there are no views.

### Overview: a visual per question kind

| Question kind | Visual | Numbers |
|---|---|---|
| `thumbs` | Donut Not for me / Good / Loved it, and a 3-column chart | Positive %, Loved it % |
| `nps` | Donut detractors / passives / promoters, and a 0–10 column chart coloured by group | NPS (signed), Promoters % vs detractors % |
| `rating` | Columns 1–5 coloured unsatisfied / neutral / satisfied. In a CSAT survey also a donut | Satisfied (4–5) %, average |
| `multiple_choice` | Horizontal bars, % of respondents per option | Note: "People could pick more than one, so the percentages add up to more than 100%." |
| `single_choice`, `dropdown` | Donut with legend (label, %, count). Horizontal bars when there are more than 6 options | — |
| `reasons` | "Top reasons" horizontal bars, ranked | — |
| `text`, `long_text` | Number of answers and "Read all answers →", which opens the Responses tab | — |

- Standard surveys (thumbs, NPS, CSAT) show the main question as "Answer split" (donut) and the distribution chart side by side, then Top reasons.
- Custom surveys show one card per question in question order, using the table above.
- Colours: the negative group always uses the striped negative token, neutral the mint border token, positive the positive token (`--color-chart-*`). A negative score is never drawn as a filled positive bar.
- Every chart has a text alternative (`role="img"` with an `aria-label` listing the values), and every bar has a tooltip with its count and %.
- Counts use correct plurals ("1 answer", "2 answers").

### Overview: cards that need something to compare

- **Trend**: a line chart of the main score by month. Shown only when 2 or more months have answers. Months are calendar months in the organisation's time zone (until there is one: Europe/Helsinki).
- **By segment**: one row per segment with its split bar and score. A segment with fewer than 5 answers shows "Fewer than 5 answers. Hidden to protect anonymity." instead of its numbers. The card is shown only when there are 2 or more segments.
- **Close the loop** (standard surveys only): the prototype's banner linking to the follow-up options.
- **AI summary**: a "Coming soon" banner in the AI summary's place, for example "AI summary of comments is coming soon. It will group comments into themes." No data is sent anywhere.
- **In short** (custom surveys): a one-sentence takeaway built from the numbers, for example "Most students found the information easy to find (72% rated it 4–5)." It is generated by rules, not AI.

### Responses tab

```
[ Search comments… ]  [All answers] [Detractors] [Passives] [Promoters]   [Export CSV]
🛡 Anonymised. No names or emails are shown. Emails and phone numbers typed into
   comments are hidden automatically. People who asked to be contacted are in Contact requests.
ID      Received        Answer   Reason          Comment                     Segment
R-5337  Today 09:12     3        Too long        "Personal details hidden"   Members
…
Showing 50 of 248 responses, newest first                       [Load more]
```

- One row per response to the chosen survey, newest first, 50 at a time with "Load more".
- **Columns**: ID, Received, Answer (main question), Reason, Comment, Segment. For custom surveys the Answer and Reason columns use the survey's first scale question and first reasons question, and Comment shows the first text question's answer.
- **All answers of one response**: clicking a row opens a side panel with every question and its answer, masked the same way. This is where custom surveys with several text or choice questions show the rest. *(My call.)*
- **ID**: a short display id derived from the response id (for example `R-` and the first 6 characters of a hash). It never contains the link key or `contact_ref`.
- **Filters**: free-text search in comments, and chips by answer group (thumbs: Not for me / Good / Loved it; NPS: detractors / passives / promoters; CSAT and scales: 1–2 / 3 / 4–5). The segment filter from the page header also applies.
- **Masking**: the server replaces each email address and phone number in a comment with `[hidden]` before sending it, and keeps the rest of the comment. A comment with a replacement is tagged "Personal details hidden". The original text stays in the database; masking happens when reading (see Anonymity rules for search).
- **Segment rule**: segments with fewer than 5 responses show as "Other" (see Anonymity rules).
- **Export CSV**: all matching responses (not only the loaded 50), with the same masking and filters. Columns: ID, Received, Segment, then one column per question in question order. *(My call: a CSV is for analysis, so every question gets its own column.)*
- **Empty states**: "No responses yet" for a survey without answers, and "No responses match. Clear filters" when the filters hide everything.

### Anonymity rules (settled in review, my calls)

- **Small segments.** A segment with fewer than 5 responses is never shown on its own. Its responses are grouped into **Other**. Other is shown only when it has 5 or more responses; otherwise those responses count only in All. The segment list for the filter, the By segment card and the Responses column all use this grouping, and the API refuses a `segment` value for a small segment (400). This also covers search and answer-group filters, because they run inside an allowed segment.
- **No segment.** Responses stored with `segment = 'all'` (no `seg` on the link) are labelled **No segment**, with the filter value `none`. They count as a segment for the "2 or more segments" rule and follow the same fewer-than-5 rule. No migration: the API maps the stored value.
- **Search matches masked text.** The masking is done in SQL (`regexp_replace` with the email and phone patterns) in the same query, and search, counts, paging and the CSV all run on the masked text. A search for "@gmail" finds nothing that is hidden.

### Numbers (settled in review, my calls)

- **Headline score** is all-time for the chosen segment, like the Responses count next to it.
- **Change since last month** is the all-time score now minus the all-time score at the end of the previous calendar month. Hidden when the survey had no answers before this month.
- **Main score of a custom survey** (for Trend, By segment and the change) is its first `nps`, `thumbs` or `rating` question, scored by that kind's rule. A custom survey without one shows no Trend, By segment or change.
- **Response rate with a segment selected** shows "—" with the note "Not available per segment", because views are counted per channel, not per segment.
- **Completed all questions** means the response has an answer to every question, required or optional, matching the prototype's note "the rest skipped optional ones".
- **Survey picker data** comes from the existing `GET /api/v1/surveys` list (name, type, status, answers, `closes_at`), with a new `last_answer_at` field. The list is searched in the browser; hundreds of surveys are fine. "Shared by …" in the status line lists the channels that have views or responses in survey performance (#12), not the publish settings.

### Backend

All endpoints live in the data analyzer under `/api/v1/results`, filtered by tenant. Existing code from the stack is kept where it fits:

| Endpoint | Status |
|---|---|
| `GET /results/{survey_id}?segment=` | From #134/#136/#143. Extend: KPIs per survey type, previous-month change, one aggregate per question in the shape of the visual table, trend by month, per-segment scores with the fewer-than-5 rule, response rate from #12. |
| `GET /results/{survey_id}/responses?segment=&q=&group=&limit=&offset=` | Replaces the cross-survey `/results/responses` from #140/#141. Adds search, answer-group filter, masking, short IDs, total count. |
| `GET /results/{survey_id}/responses.csv` | New. Same filters and masking, streamed as CSV. |
| `GET /results/{survey_id}/reasons`, `/comments` | From #138. Folded into the two endpoints above, then removed. |
| `GET /results/performance` | From #12, unchanged. |

- Masking and the fewer-than-5 rule live in `domain.py` with unit tests, so the PHP port can reuse them.
- `question_charts` currently runs one query per question. Replace it with one grouped query.
- The new rules get database tests, and CI's `db` job also runs when `backend/services/data-analyzer/**` changes (it does not today).

### Frontend

- `src/features/results/` holds the page, the picker, both tabs and one component per visual kind. `src/features/responses/` is removed.
- Charts are plain SVG and CSS from the shared components, no chart library, as on the front page.
- **Demo data**: on `main` the answer link only records the main question, and the full public survey page is #105. Reasons, text answers and custom surveys therefore need the demo seed data from #20 to be built, tested and demoed. #20 comes first.
- The front page "View responses" and "See results" links open the right survey and tab.

## Tickets

| Ticket | Change |
|---|---|
| #15 [Frontend] Results page | Rewrite: page shell, survey picker, tabs, status line, KPI cards, segment filter, URL state. Includes `last_answer_at` on the survey list. |
| #16 [Frontend] Charts | Rewrite: one component per question kind (visual table), colours, plurals, text alternatives. |
| #49 Results: Reasons and Comments tabs | Close as replaced by this design. Reasons move into the Overview; comments into the Responses tab. |
| #50 [Backend] reasons and comments API | Rewrite: the extended `GET /results/{survey_id}` (aggregates per question, KPIs, trend, segments with the fewer-than-5 rule). |
| #51 [Frontend] Reasons and Comments tabs | Rewrite: trend, by segment, close the loop, AI "Coming soon" banner, In short takeaway. |
| #52 Responses page | Close as replaced by this design. |
| #53 [Backend] responses API with filters | Rewrite: per-survey responses endpoint with search, groups, masking, short IDs, CSV export. |
| #54 [Frontend] responses table and filters | Rewrite: the Responses tab. |
| #71 [Data] segments and trend | Keep, re-scoped to the backend parts: segment storage (done in #134), trend by month and per-segment scores. |
| #154 Full performance report | Close. The front page Survey performance card's "View all →" links to the Surveys list instead of `/results`. |

The stack's PRs: their backend code is reused in new backend-only branches off `main`, one per rewritten backend ticket, starting with #134's segment storage (migration, respondent and worker), which the others need. *(My call: new branches instead of rewriting the stacked ones, so nothing has to be merged up the stack again.)* The stack's PRs are closed once their backend code has a new home, each with a comment linking this design and the ticket that replaces it.

## Left to the builder

- Exact wording of empty states, the AI banner and the In short sentences, within the prototype's tone.
- The hash used for short response IDs.
- The regular expressions for masking emails and phone numbers (Finnish and international formats), with tests for the common cases.
- Component names and file layout inside `src/features/results/`.
- Loading and error states, following the front page's pattern.
