# Results redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Results and Responses pages with one Results page (Overview and Responses tabs per survey) as in the updated prototype, reusing the stacked PRs' backend ideas and rewriting the frontend.

**Architecture:** Eight pull requests, one per ticket, each on its own branch off fresh `origin/main`, merged in order. The data analyzer gets two per-survey endpoints (overview, responses) whose rules live in `domain.py`. The frontend rebuilds `src/features/results/` and removes `src/features/responses/`.

**Tech Stack:** Python 3.12, FastAPI, PostgreSQL (psycopg, row-level security), React 18, TypeScript, Vite, Vitest, Testing Library.

**Spec:** `docs/superpowers/specs/2026-11-19-results-redesign-design.md`

## Global Constraints

- One ticket per branch `feat/<short-name>` off fresh `origin/main`, one PR per ticket. Never commit to `main`.
- Commits have no `Co-Authored-By` trailer. PR bodies have `Closes #N`, then an **Acceptance criteria** checklist copied from the ticket with each item ticked and a short "how" (or unticked with the reason). Edit PR bodies with `gh api -X PATCH repos/thethtarzin111/liana-survey-tool/pulls/<n> -F "body=@file"` (`gh pr edit` fails on this repo).
- Backend: `domain.py` (plain rules) / `repo.py` (SQL) / `routes.py` (HTTP) in `backend/services/data-analyzer/data_analyzer/`. Every query through `tenant_db()` / `tenant_connection()`. `docs/api/openapi.yaml` changes in the same PR as the endpoint.
- Frontend: tokens from `src/styles/tokens.css` only (lint refuses hex colours), shared components from `src/components/ui`, charts as plain SVG and CSS, no chart library.
- Anonymity threshold: **5**. A segment with fewer than 5 responses is shown as **Other**; Other with fewer than 5 is not shown on its own. Stored `segment = 'all'` is shown as **No segment**, filter value `none`.
- Masking: each email address and phone number in comment text becomes `[hidden]`; the comment is tagged "Personal details hidden". Search, counts, paging and CSV run on masked text.
- Months for trends: calendar months in `Europe/Helsinki`.
- Copy fixed by the spec: "Fewer than 5 answers. Hidden to protect anonymity." · "People could pick more than one, so the percentages add up to more than 100%." · "Not available per segment" · "No responses yet" · "No responses match." / "Clear filters" · "Personal details hidden" · AI banner: "AI summary of comments is coming soon. It will group comments into themes."
- Verification before each PR: `make lint` and `make test` (Python with `.venv/bin/python`, frontend `npm test` in `frontend/`). Database tests run in CI's `db` job; locally only with `DATABASE_URL` and `REQUIRE_DB=1`. Vitest may exit 1 because of the known unhandled `TemplatesPage` rejection from `App.test.tsx`; read the "Tests" line, not only the exit code.

## Review Focus

- **A survey with no answers**: every card shows its empty state, no `NaN`, no division by zero, no "0%" donut. Pinned in Task 4 (`test_overview_of_survey_without_answers`) and Task 6 (`overview without answers shows empty states`).
- **A segment at the threshold**: 5 responses is shown, 4 becomes Other, and asking the API for a 4-response segment is refused. Pinned in Task 1 (`test_segment_groups_threshold`) and Task 4 (`test_small_segment_is_refused`).
- **An email inside a longer comment, then a search for it**: the comment shows with `[hidden]`, a search for the hidden address finds nothing, the CSV is masked too. Pinned in Task 5 (`test_search_does_not_reveal_masked_text`, `test_csv_is_masked`).
- **An answer at the month boundary**: 2026-10-31 22:30 UTC is November in Helsinki. Pinned in Task 1 (`test_month_uses_helsinki_time`).
- **A negative NPS**: shown with a minus sign and the negative colour, never as a filled positive bar. Pinned in Task 7 (`negative NPS keeps its sign and negative colour`).

---

### Task 0: Tickets, design PR and board

No code. Do it before Task 1.

- [ ] **Step 1: Open the design PR.** Push branch `docs/results-redesign` (it holds the spec and this plan) and open a PR "Design: one Results page with Overview and Responses". Body: summary, link to the spec, "No code changes".
- [ ] **Step 2: Rewrite the tickets** with `gh issue edit <n> --title … --body-file …`, keeping each number. Each body: one-line why, User Story, **Acceptance Criteria** copied from the spec section named here, `Spec:` link, `Depends on`.

| Ticket | New title | Criteria from the spec | Depends on |
|---|---|---|---|
| #71 | [Backend] Segments: store the segment and anonymity rules | Anonymity rules; segment storage | — |
| #20 | (keep title) | add: a custom survey, a 4-response segment, comments with an email and a phone number, answers in 3 months, channel views | #71 |
| #50 | [Backend] Results: survey overview endpoint | Overview: KPI cards, visual per question kind (data), cards that need something to compare (data), Numbers | #71 |
| #53 | [Backend] Results: responses endpoint, search, masking and CSV | Responses tab (data), Anonymity rules | #71 |
| #15 | [Frontend] Results page: survey picker, tabs and KPI cards | Page layout, Overview: KPI cards, `last_answer_at` | #50 |
| #16 | [Frontend] Results: a visual per question kind | Overview: a visual per question kind | #15 |
| #51 | [Frontend] Results: trend, segments, close the loop and AI banner | Overview: cards that need something to compare | #16 |
| #54 | [Frontend] Results: Responses tab | Responses tab | #15, #53 |

- [ ] **Step 3: Close** #49, #52 and #154 with `gh issue close <n> --reason "not planned" --comment "Replaced by the Results redesign: <spec link>. See #15/#16/#51/#54."` (#154: "Each survey's response rate is now a KPI on its Results page; the front page card links to the Surveys list.")
- [ ] **Step 4: Comment on stack PRs #134, #136–#143**: "This PR will be closed: the Results redesign (<spec link>) replaces it. Its backend ideas move to #71 / #50 / #53." Do not close them yet (Task 9).
- [ ] **Step 5: Board.** Set #71, #20, #50, #53, #15, #16, #51, #54 to **Todo** on project 1 (`gh project item-edit …`, Status field `PVTSSF_lAHOCDFGqs4BkQsOzhjB5rM`, Todo `f75ad846`), and each to **In Progress** when its task starts.

### Task 1: Segment storage and anonymity rules (#71)

Branch `feat/segment-storage`. Reuse #134's code (`git show origin/feat/results-in-short:<path>`) for the migration, message, respondent and worker parts.

**Files:**
- Create: `backend/db/migrations/20261119090000_response_segments.sql` (content of #134's `20261118230000_response_segments.sql`)
- Modify: `backend/packages/shared-py/src/liana_survey_shared/messages.py` (`AnswerSubmitted.segment`), `backend/services/respondent/respondent_service/routes.py` (`seg` query parameter), `backend/services/worker/survey_worker/handlers.py` (insert `segment`), `docs/integrations.md`, `docs/data-model.md`, `docs/api/openapi.yaml` (`seg` on `/r/{link_token}` already listed; check pattern)
- Modify: `backend/services/data-analyzer/data_analyzer/domain.py`, `.github/workflows/ci.yml` (add `'backend/services/data-analyzer/**'` to the `db` paths filter)
- Test: `backend/services/data-analyzer/tests/test_domain.py`, `backend/services/respondent/tests/test_answers.py`, `backend/services/worker/tests/test_handlers.py`

**Interfaces:**
- Produces in `data_analyzer/domain.py`:
  - `MIN_GROUP = 5`, `TIME_ZONE = ZoneInfo("Europe/Helsinki")`
  - `segment_label(stored: str) -> str` (`"all"` → `"No segment"`, else the stored value capitalised: `"members"` → `"Members"`)
  - `segment_groups(counts: dict[str, int]) -> list[SegmentGroup]` where `SegmentGroup(value: str, label: str, answers: int, members: tuple[str, ...])`; `value` is the stored value, `"none"` for `all`, or `"other"`; sorted by answers, most first, Other last; Other omitted when its total is below 5
  - `stored_segments(groups: list[SegmentGroup], value: str) -> tuple[str, ...] | None` — the stored values a filter value stands for, `None` for an unknown or small segment
  - `score(kind: str, counts: Counts) -> int | None` — NPS score, thumbs positive %, rating satisfied (4–5) %, else `None`
  - `month_of(ts: datetime) -> str` → `"2026-11"` in Helsinki time

- [ ] **Step 1: Write the failing domain tests**

```python
def test_segment_groups_threshold():
    groups = segment_groups({"members": 5, "partners": 4, "volunteers": 3, "all": 6})
    assert [(g.value, g.label, g.answers) for g in groups] == [
        ("none", "No segment", 6), ("members", "Members", 5), ("other", "Other", 7)]
    assert stored_segments(groups, "other") == ("partners", "volunteers")
    assert stored_segments(groups, "partners") is None

def test_small_other_is_not_shown():
    assert [g.value for g in segment_groups({"members": 9, "partners": 2})] == ["members"]

def test_score_per_kind():
    assert score("nps", {"0": 2, "10": 1}) == -33
    assert score("thumbs", {"0": 1, "1": 1, "2": 2}) == 75
    assert score("rating", {"2": 1, "4": 1, "5": 2}) == 75
    assert score("single_choice", {"a": 1}) is None

def test_month_uses_helsinki_time():
    assert month_of(datetime(2026, 10, 31, 22, 30, tzinfo=UTC)) == "2026-11"
```

- [ ] **Step 2:** Run `cd backend/services/data-analyzer && ../../../.venv/bin/python -m pytest tests/test_domain.py -q` — expect ImportError.
- [ ] **Step 3:** Implement the five functions and `SegmentGroup` (frozen dataclass) in `domain.py`. `score` reuses `nps_score`, `thumbs_score`, `csat_score` from `liana_survey_shared.scoring`.
- [ ] **Step 4:** Run the same command — expect PASS.
- [ ] **Step 5: Port segment storage from #134** (migration with the new timestamp, message field with the `^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$` pattern and default `"all"`, respondent `seg` parameter next to `ch`, worker insert of `channel` and `segment`). Add DB tests: `test_the_segment_from_the_link_is_queued` (respondent: `link(...)+"&seg=members"` → `message.segment == "members"`; `&seg=Bad!` → 422 page) and `test_the_worker_stores_the_segment` (worker: saved response has `segment == "members"`; no segment → `"all"`).
- [ ] **Step 6:** Update `docs/integrations.md` (AnswerSubmitted.segment paragraph from the stack merge), `docs/data-model.md` (`responses.segment`), CI paths filter.
- [ ] **Step 7:** `make lint`, Python tests — expect PASS. Commit "Segments: store the link's segment and add anonymity rules (#71)". Open the PR.

### Task 2: Demo seed data (#20)

Branch `feat/demo-seed`. Depends on Task 1 being merged.

**Files:** Modify `backend/db/seed/seed.sql`. Test: CI's seed-twice check (already in `.github/workflows/ci.yml`) and `backend/db/tests/rls_check.sql` still passing.

- [ ] **Step 1:** Add, with fixed UUIDs and `on conflict do nothing` so a second run changes nothing:
  - "May newsletter" (thumbs, live), "Member NPS 2026" (nps, live), "Spring course feedback" (csat, closed), "Student services survey" (custom: `multiple_choice`, `rating`, `dropdown`, `long_text`).
  - About 40 responses per standard survey over September–November 2026, segments `members`, `volunteers` and `all`, plus exactly 4 `partners` responses on Member NPS.
  - A `reasons` question on each standard survey with answers in `value_choices`; comments as `value_text`, two of them containing `anna.virtanen@example.org` and `+358 40 123 4567`.
  - `survey_aggregates` rows matching the answers, and `survey_channel_views` for email, link and qr.
  - Contact requests in each status (`new`, `contacted`, `done`).
- [ ] **Step 2:** Run the seed twice on the local database and compare row counts; run `rls_check.sql`. Expect identical counts and "RLS check passed".
- [ ] **Step 3:** Commit "Demo seed data for the Results redesign (#20)". Open the PR.

### Task 3: Survey list `last_answer_at` (part of #15, backend)

Branch `feat/results-shell` (shared with Task 6; this task is its first commit).

**Files:** Modify `backend/services/survey-manager/survey_manager/surveys/repo.py` (`list_all`), `schemas.py` (`SurveyListItem.last_answer_at: datetime | None`), `docs/api/openapi.yaml`; Test `backend/services/survey-manager/tests/test_surveys.py`.

- [ ] **Step 1:** DB test `test_list_shows_the_last_answer_time`: a survey with responses at two times lists the later one; a survey without responses lists `None`.
- [ ] **Step 2:** Run it — FAIL (`KeyError`/missing field).
- [ ] **Step 3:** Add `(select max(r.submitted_at) from responses r where r.survey_id = s.id) as last_answer_at` to `list_all`, the schema field and the OpenAPI property.
- [ ] **Step 4:** Run — PASS. Commit "Survey list: time of the last answer (#15)".

### Task 4: Survey overview endpoint (#50)

Branch `feat/results-overview-api`. Depends on Task 1.

**Files:** Modify `data_analyzer/repo.py`, `routes.py`, `schemas.py`, `domain.py`, `docs/api/openapi.yaml`; Create `backend/services/data-analyzer/tests/test_overview_api.py`.

**Interfaces:**
- Consumes: Task 1's `segment_groups`, `stored_segments`, `score`, `month_of`, `MIN_GROUP`; `liana_survey_shared.scoring.top_reasons`.
- Produces: `GET /api/v1/results/{survey_id}/overview?segment=` (default `all` = no filter; other values from `segments[].value`) → `SurveyOverview`, registered after `/performance`. Fields (snake_case JSON):
  - `survey_id`, `title`, `type`, `status`, `closes_at`, `last_answer_at`, `channels: list[Literal["email","link","qr"]]` (channels with views or responses)
  - `segment: str`, `segments: list[{value, label, answers}]` (from `segment_groups`; empty when fewer than 2 groups)
  - `responses: int`, `views: int`, `response_rate: int | None` (None when a segment is chosen or `views == 0`), `completed_all: int | None` (percent, custom surveys only)
  - `main: {question_id, kind, score: int | None, change: int | None, counts: dict[str, int]} | None` — first `nps`/`thumbs`/`rating` question; `change` = all-time score now minus all-time score at the end of the previous Helsinki month, `None` when there were no answers before this month
  - `questions: list[{id, kind, prompt, required, answers, options: list[{label, count}], average: float | None}]` — every question in order; scale kinds list every scale value; `multiple_choice` counts each picked option once per response; text kinds have `options: []`
  - `reasons: list[{label, count, percent}]` — from the first `reasons` question, via `top_reasons`
  - `trend: list[{month, score, answers}]` — main score per Helsinki month, oldest first; empty when fewer than 2 months
  - `by_segment: list[{value, label, answers, score, counts}]` — one per group from `segment_groups`; empty when fewer than 2 groups
- Errors: 404 "Survey not found"; 400 "Segment not available" when `stored_segments(...) is None` for a value other than `all`.

- [ ] **Step 1: Write the failing DB tests** in `test_overview_api.py` (fixture creates an NPS survey with a `reasons` and a `text` question, responses in two Helsinki months across `members` ×5, `partners` ×4, `all` ×3; deletes it afterwards):

```python
def test_overview_scores_the_main_question(survey): ...      # main.score == score("nps", all counts); responses == 12
def test_change_since_last_month(survey): ...                # main.change == score(now) - score(before this month)
def test_segments_follow_the_anonymity_rules(survey): ...     # segments values == ["none"?/"members", ...]; partners not listed alone
def test_small_segment_is_refused(survey): ...               # ?segment=partners -> 400
def test_segment_filter_limits_every_number(survey): ...     # ?segment=members -> responses == 5, response_rate is None
def test_trend_by_helsinki_month(survey): ...                # two months, oldest first, answers add up to responses
def test_reasons_and_questions_in_order(survey): ...         # questions[*].kind == ["nps", "reasons", "text"]; reasons ranked
def test_overview_of_survey_without_answers(empty_survey): ... # responses == 0, main.score is None, trend == [], by_segment == []
def test_other_tenant_survey_is_not_found(survey): ...       # X-Tenant-Id other tenant -> 404
```

- [ ] **Step 2:** Run with `REQUIRE_DB=1` — FAIL (404 route missing). Without a database they skip; CI runs them.
- [ ] **Step 3:** Implement `repo.overview_rows(conn, survey_id, stored: tuple[str, ...] | None) -> dict` with one query per concern (survey + channels, answers grouped by question/value/segment/month, response completion) — no query per question. Build `SurveyOverview` in `domain.overview(rows, segment) -> dict`; `routes.py` only resolves the segment and calls them.
- [ ] **Step 4:** Unit-test `domain.overview` for the custom-survey rules: `test_custom_survey_main_is_first_scale_question`, `test_custom_survey_without_scale_has_no_main` (`main is None`, `trend == []`), `test_completed_all_counts_optional_questions`.
- [ ] **Step 5:** Run all data-analyzer tests — PASS. Update `openapi.yaml` (path, `SurveyOverview` schema, 400/404). Commit "Results: survey overview endpoint (#50)". Open the PR.

### Task 5: Responses endpoint, masking and CSV (#53)

Branch `feat/results-responses-api`. Depends on Task 1.

**Files:** Modify `data_analyzer/domain.py`, `repo.py`, `routes.py`, `schemas.py`, `docs/api/openapi.yaml`; Create `backend/services/data-analyzer/tests/test_masking.py`, `tests/test_responses_api.py`.

**Interfaces:**
- Produces in `domain.py`: `EMAIL_PATTERN: str`, `PHONE_PATTERN: str` (POSIX-compatible, used both in SQL `regexp_replace(..., 'g')` and in Python `re`), `mask(text: str) -> tuple[str, bool]`, `display_id(response_id: UUID) -> str` (`"R-"` + first 6 hex characters of SHA-256 of the UUID string, upper case), `GROUPS: dict[str, dict[str, tuple[int, ...]]]` — thumbs `not-for-me` (0) / `good` (1) / `loved-it` (2); nps `detractors` (0–6) / `passives` (7–8) / `promoters` (9–10); rating `low` (1–2) / `neutral` (3) / `high` (4–5).
- Produces endpoints (after `/performance`, before any `/{survey_id}` catch-all):
  - `GET /api/v1/results/{survey_id}/responses?segment=&q=&group=&limit=50&offset=0` → `{total: int, rows: list[{id, display_id, submitted_at, answer: int | None, reason: str | None, comment: str | None, masked: bool, segment_label: str}]}`, newest first, `limit` 1–200.
  - `GET /api/v1/results/{survey_id}/responses/{response_id}` → `{display_id, submitted_at, segment_label, answers: list[{question_id, prompt, kind, value: int | str | list[str] | None, masked: bool}]}` in question order.
  - `GET /api/v1/results/{survey_id}/responses.csv?segment=&q=&group=` → `text/csv`, header `ID,Received,Segment,<one column per question prompt>`, multi-choice joined with `; `.
- Segment handling and errors as in Task 4 (shared helper in `routes.py`: `resolve_segment(conn, survey_id, value) -> tuple[str, ...] | None`, raising 400/404). Segment labels use `segment_groups`, so small segments show "Other".

- [ ] **Step 1: Failing masking tests**

```python
def test_mask_keeps_the_rest_of_the_comment():
    assert mask("Mail me at anna.virtanen@example.org thanks") == ("Mail me at [hidden] thanks", True)
    assert mask("Call +358 40 123 4567 or 040-1234567") == ("Call [hidden] or [hidden]", True)
    assert mask("Room 12, 3 people, 2026") == ("Room 12, 3 people, 2026", False)

def test_display_id_is_short_and_stable():
    rid = UUID("11111111-2222-4333-8444-555555555555")
    assert display_id(rid) == display_id(rid) and re.fullmatch(r"R-[0-9A-F]{6}", display_id(rid))
```

- [ ] **Step 2:** Run — FAIL. Implement `mask`, the patterns and `display_id`. Run — PASS.
- [ ] **Step 3: Failing DB tests** in `test_responses_api.py`: `test_rows_newest_first_with_masking`, `test_search_does_not_reveal_masked_text` (`q=example.org` → `total == 0`; `q=thanks` finds the masked comment), `test_group_filter` (`group=detractors` → only answers 0–6; unknown group → 422), `test_small_segment_is_refused` (400), `test_segment_label_other_for_small_segments`, `test_detail_lists_every_answer_masked`, `test_csv_is_masked` (body contains `[hidden]`, not the address; one column per question), `test_no_contact_ref_anywhere` (a response with `contact_ref='C-1'` → `"C-1"` not in any response body or CSV).
- [ ] **Step 4:** Implement `repo.responses(conn, survey_id, stored, q, group_values, limit, offset)`, `repo.response_detail(...)`, `repo.responses_csv_rows(...)` with masking in SQL so `q` (`ILIKE`) runs on the masked text. Stream the CSV with `StreamingResponse` and `csv.writer`.
- [ ] **Step 5:** Run all data-analyzer tests — PASS. OpenAPI for three paths. Commit "Results: responses endpoint with search, masking and CSV (#53)". Open the PR.

### Task 6: Results page shell (#15, frontend)

Branch `feat/results-shell` (after Task 3's commit). Depends on Task 4 merged.

**Files:**
- Modify: `frontend/src/api/client.ts` (`SurveyListItem.last_answer_at`, `SurveyOverview` type mirroring Task 4, `api.overview(surveyId: string, segment = 'all'): Promise<SurveyOverview>`), `frontend/src/app/nav.ts` (remove Responses), `frontend/src/app/App.tsx` (`/responses` → `<Navigate to="/results?tab=responses" replace />`), `frontend/src/features/front/FrontPage.tsx` ("View responses" → `/results?tab=responses`), `frontend/src/features/front/PerformancePanel.tsx` ("View all →" → `/surveys`)
- Delete: `frontend/src/features/responses/`
- Create in `frontend/src/features/results/`: `ResultsPage.tsx` (rewrite), `SurveyPicker.tsx`, `useResultsParams.ts`, `KpiCards.tsx`, `StatusLine.tsx`, `format.ts`, `results.css`
- Test: `ResultsPage.test.tsx`, `SurveyPicker.test.tsx`, `format.test.ts`, and update `App.test.tsx`, `FrontPage.test.tsx`, `PerformancePanel.test.tsx`

**Interfaces:**
- Produces: `useResultsParams(): { survey: string | null; tab: 'overview' | 'responses'; segment: string; set(changes: Partial<{survey: string; tab: 'overview' | 'responses'; segment: string}>): void }` (URL query `survey`, `tab`, `segment`; changing `survey` resets `segment`).
- Produces in `format.ts`: `plural(n: number, one: string, many: string): string` (`plural(1,'answer','answers') === '1 answer'`), `signed(n: number): string` (`'+40'`, `'−33'` with U+2212, `'0'`), `dayDate(iso)` (moved from FrontPage, `"Mon 01/12/2026"`).
- Produces `<ResultsPage>` slots for later tasks: `<OverviewTab overview={...} />` (Task 7/8 fill it; this task renders KPI cards only) and `<ResponsesTab surveyId segment />` (Task 9; this task renders a placeholder card "Responses arrive with #54").

- [ ] **Step 1: Failing tests**
  - `format.test.ts`: `plural` and `signed` cases above.
  - `SurveyPicker.test.tsx`: `lists surveys with type, answers and status`; `search filters and shows "No surveys match “x”."`; `arrow keys and Enter pick, Escape closes`; `focus moves to the search field when opened`.
  - `ResultsPage.test.tsx`: `defaults to the survey in the URL, else the latest answer, else the newest`; `tabs and segment live in the URL`; `segment filter hidden with fewer than 2 segments`; `KPI cards per survey type` (NPS: "NPS", signed score, "Promoters"; thumbs: "Positive (Good + Loved it)"; CSAT: "Satisfied (4–5)", "out of 5"; custom: "Completed all questions"); `response rate shows "—" and "Not available per segment" with a segment`; `overview without answers shows empty states`; `unknown survey shows "Survey not found" and the picker`.
  - `App.test.tsx`: sidebar has no Responses; `/responses` lands on Results with the Responses tab.
- [ ] **Step 2:** `cd frontend && npx vitest run src/features/results src/app` — FAIL.
- [ ] **Step 3:** Implement. The picker uses `api.listSurveys()` and searches in the browser; the status line uses `last_answer_at`, `closes_at`, `status` and `channels` ("Sent by email", "Shared by link", "QR code").
- [ ] **Step 4:** Run the tests — PASS. `npm run typecheck && npm run lint`, `npm test` — PASS.
- [ ] **Step 5:** Commit "Results page: survey picker, tabs and KPI cards (#15)". Open the PR.

### Task 7: A visual per question kind (#16)

Branch `feat/results-visuals`. Depends on Task 6.

**Files:** Create in `frontend/src/features/results/`: `charts/Donut.tsx`, `charts/Columns.tsx`, `charts/BarList.tsx`, `QuestionCard.tsx`, `AnswerSplit.tsx` (standard surveys: donut + distribution side by side, then Top reasons); Modify `OverviewTab.tsx`, `results.css`. Test: `charts/charts.test.tsx`, `QuestionCard.test.tsx`.

**Interfaces:**
- Consumes: `SurveyOverview.main`, `.questions`, `.reasons` (Task 4 shapes), `plural`, `signed`.
- Produces: `Donut({ label: string; center: string; centerNote: string; slices: {label: string; count: number; tone: 'negative' | 'neutral' | 'positive' | number}[] })`, `Columns({ label: string; bars: {label: string; count: number; tone: …}[]; note?: string })`, `BarList({ label: string; rows: {label: string; count: number; percent: number}[]; note?: string })`, `QuestionCard({ question, onReadAll })` choosing the visual by `kind` as in the spec table (`single_choice`/`dropdown` with more than 6 options → `BarList`).

- [ ] **Step 1: Failing tests**: `each chart has a text alternative listing every value` (`role="img"` with aria-label "Detractors 67%, Passives 0%, Promoters 33%"); `negative NPS keeps its sign and negative colour` (center text "−33", detractor slice has class `tone-negative`); `nps columns 0–10 coloured by group`; `multiple choice shows the more-than-100% note`; `dropdown with 7 options uses bars`; `text question shows count and "Read all answers →" which switches to Responses`; `plurals: "1 answer"`.
- [ ] **Step 2:** Run — FAIL. Implement with SVG (`Donut` arcs via `stroke-dasharray` on circles) and CSS bars, colours only from `--color-chart-*` and mint tokens.
- [ ] **Step 3:** Run — PASS. Full frontend checks. Commit "Results: a visual per question kind (#16)". Open the PR.

### Task 8: Trend, segments, close the loop, AI banner, In short (#51)

Branch `feat/results-compare`. Depends on Task 7.

**Files:** Create `TrendCard.tsx`, `SegmentCard.tsx`, `CloseTheLoop.tsx`, `AiComingSoon.tsx`, `takeaway.ts`; Modify `OverviewTab.tsx`, `results.css`. Test: `TrendCard.test.tsx`, `SegmentCard.test.tsx`, `takeaway.test.ts`, `OverviewTab.test.tsx`.

**Interfaces:**
- Consumes: `SurveyOverview.trend`, `.by_segment`, `.main`, `.questions`, `.type`.
- Produces: `takeaway(overview: SurveyOverview): string | null` (custom surveys; e.g. first rating question → "Most respondents rated <prompt> 4–5 (72%)." when ≥ 50%, else "Ratings for <prompt> are mixed: 48% gave 4–5."; `null` without a rating question).

- [ ] **Step 1: Failing tests**: `trend hidden with one month, line with labels from two months`; `segment card hidden with fewer than 2 groups`; `small groups never appear by name` (renders only labels from `by_segment`); `close the loop only on standard surveys` (links to `/contact-requests`); `AI banner text is exact and sends nothing` (no `fetch` call besides overview); `takeaway sentences` (the two cases above and `null`).
- [ ] **Step 2:** Run — FAIL. Implement. The trend is an SVG polyline with points labelled by month ("Sep", "Oct", "Nov") and value via `signed`.
- [ ] **Step 3:** Run — PASS. Full checks. Commit "Results: trend, segments, close the loop and AI banner (#51)". Open the PR.

### Task 9: Responses tab (#54) and closing the stack

Branch `feat/results-responses-tab`. Depends on Tasks 5 and 6.

**Files:** Modify `client.ts` (`api.responses(surveyId, {segment, q, group, limit, offset})`, `api.responseDetail(surveyId, id)`, `responsesCsvUrl(surveyId, {segment, q, group}): string`); Create `ResponsesTab.tsx`, `ResponseDetail.tsx`; Modify `ResultsPage.tsx`, `results.css`. Test: `ResponsesTab.test.tsx`.

- [ ] **Step 1: Failing tests**: `rows newest first with ID, Received, Answer, Reason, Comment, Segment`; `masked comment shows "Personal details hidden"`; `search and group chips filter and update the URL`; `chips per survey type` (NPS: All answers / Detractors / Passives / Promoters); `Load more appends the next 50`; `"No responses yet"` and `"No responses match." with "Clear filters"`; `row click opens every answer in a side panel, Escape closes and returns focus`; `Export CSV link carries the filters`; `the anonymised notice links to Contact requests`.
- [ ] **Step 2:** Run — FAIL. Implement; the side panel uses the shared `Dialog` pattern.
- [ ] **Step 3:** Run — PASS. Full checks. Commit "Results: Responses tab (#54)". Open the PR.
- [ ] **Step 4: Close the stack** once Tasks 1, 4 and 5 are merged: `gh pr close <n> --comment "Replaced by the Results redesign: <spec link>; backend moved to #<new PR>."` for #134, #136–#143, and delete their branches. Move the redesign tickets to Done as their PRs merge.
