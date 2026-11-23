// Small fetch wrapper. Later, generate typed calls from docs/api/openapi.yaml.

export type CurrentUser = {
  user_id: string;
  tenant_id: string;
  tenant_name: string;
  name: string;
  email: string;
};

/** A demo organisation the dev-auth gateway can switch to. */
export type DemoOrganization = {
  tenant_id: string;
  tenant_name: string;
  user_name: string;
  current: boolean;
};

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
    message: string,
  ) {
    super(message);
  }
}

async function responseBody(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

export async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new ApiError(res.status, await responseBody(res), `${res.status} ${res.statusText} for ${path}`);
  return (await res.json()) as T;
}

export const api = {
  me: () => getJson<CurrentUser>('/api/v1/me'),
  /** Dev auth only: the demo organisations. Real login has no such list. */
  demoOrganizations: () => getJson<DemoOrganization[]>('/api/v1/me/organizations'),
  /** Dev auth only: signs this browser in to another demo organisation. */
  switchOrganization: (tenantId: string) => send<CurrentUser>('PUT', '/api/v1/me/organizations', { tenant_id: tenantId }),
  survey: (id: string) => getJson<Survey>(`/api/v1/surveys/${encodeURIComponent(id)}`),
  createSurvey: async (type: SurveyType): Promise<Survey> => {
    const res = await fetch('/api/v1/surveys', {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ type }),
    });
    if (!res.ok) throw new Error('Could not save the survey draft.');
    return (await res.json()) as Survey;
  },
  updateSurvey: async (
    id: string,
    changes: Partial<
      Pick<Survey, 'title' | 'reader_title' | 'description' | 'thank_you' | keyof ReaderOptions | 'accent_color' | 'background_color'> &
        SurveySettings
    >,
  ): Promise<Survey> => {
    const res = await fetch(`/api/v1/surveys/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(changes),
    });
    if (!res.ok) {
      throw new ApiError(res.status, await responseBody(res), 'Could not save the survey draft.');
    }
    return (await res.json()) as Survey;
  },
  listSurveys: (filters: { q?: string; status?: SurveyStatus } = {}) => {
    const params = new URLSearchParams();
    if (filters.q) params.set('q', filters.q);
    if (filters.status) params.set('status', filters.status);
    const query = params.toString();
    return getJson<SurveyListItem[]>(`/api/v1/surveys${query ? `?${query}` : ''}`);
  },
  /** Everything the Results overview shows for one survey. 400 for an unknown segment, 404 for an unknown survey. */
  overview: (surveyId: string, segment = 'all') =>
    getJson<SurveyOverview>(
      `/api/v1/results/${encodeURIComponent(surveyId)}/overview?segment=${encodeURIComponent(segment)}`,
    ),
  /** One page of a survey's responses, newest first. Comments are masked by the server. */
  responses: (surveyId: string, filters: ResponseFilters & { limit?: number; offset?: number }) =>
    getJson<ResponsesPage>(
      `${resultsPath(surveyId)}/responses?${responseQuery(filters, { limit: filters.limit ?? 50, offset: filters.offset ?? 0 })}`,
    ),
  /** Every answer of one response. */
  responseDetail: (surveyId: string, responseId: string) =>
    getJson<ResponseDetail>(`${resultsPath(surveyId)}/responses/${encodeURIComponent(responseId)}`),
  /** Close (live → closed) or unpublish (live/scheduled → draft) a survey. */
  changeSurveyStatus: (id: string, action: 'close' | 'unpublish') =>
    send<Survey>('POST', `/api/v1/surveys/${encodeURIComponent(id)}/${action}`),
  deleteSurvey: (id: string) => send<void>('DELETE', `/api/v1/surveys/${encodeURIComponent(id)}`),
  /** Draft → live, with a public link (#5). 409 with a reason in `detail` when it isn't ready. */
  publishSurvey: (id: string) => send<Survey>('POST', `/api/v1/surveys/${encodeURIComponent(id)}/publish`),
  /**
   * The LianaMailer newsletter snippet, tagged with a campaign and a segment (#40). Without a
   * campaign the API uses the survey name as a slug. 409 with a reason in `detail` for custom surveys.
   */
  snippet: (id: string, tags: { campaign?: string; segment?: string } = {}) => {
    const params = new URLSearchParams();
    if (tags.campaign) params.set('campaign', tags.campaign);
    if (tags.segment) params.set('segment', tags.segment);
    const query = params.toString();
    return send<Snippet>('POST', `/api/v1/surveys/${encodeURIComponent(id)}/snippet${query ? `?${query}` : ''}`);
  },
  /** Signed answer links for made-up readers. Local development only: 404 elsewhere. */
  testLinks: (id: string, count = 3) =>
    send<{ links: string[] }>('POST', `/api/v1/surveys/${encodeURIComponent(id)}/test-links`, { count }),

  questions: (surveyId: string) => getJson<Question[]>(questionsPath(surveyId)),
  addQuestion: (surveyId: string, question: QuestionInput) =>
    send<Question>('POST', questionsPath(surveyId), question),
  updateQuestion: (surveyId: string, questionId: string, changes: Partial<QuestionInput>) =>
    send<Question>('PATCH', questionsPath(surveyId, questionId), changes),
  deleteQuestion: (surveyId: string, questionId: string) =>
    send<void>('DELETE', questionsPath(surveyId, questionId)),
  duplicateQuestion: (surveyId: string, questionId: string) =>
    send<Question>('POST', `${questionsPath(surveyId, questionId)}/duplicate`),
  reorderQuestions: (surveyId: string, questionIds: string[]) =>
    send<Question[]>('PUT', `${questionsPath(surveyId)}/order`, { question_ids: questionIds }),

  /** Uploads (or replaces) the logo and returns the survey with its new logo_url. */
  uploadLogo: async (surveyId: string, file: File): Promise<Survey> => {
    const path = `/api/v1/surveys/${encodeURIComponent(surveyId)}/logo`;
    const res = await fetch(path, {
      method: 'PUT',
      headers: { Accept: 'application/json', 'Content-Type': file.type },
      body: file,
    });
    if (!res.ok) throw new ApiError(res.status, await responseBody(res), `${res.status} ${res.statusText} for ${path}`);
    return (await res.json()) as Survey;
  },
  deleteLogo: (surveyId: string) => send<void>('DELETE', `/api/v1/surveys/${encodeURIComponent(surveyId)}/logo`),

  templates: (type?: SurveyType) =>
    getJson<Template[]>(`/api/v1/templates${type ? `?${new URLSearchParams({ type })}` : ''}`),
  /** Creates a draft survey from a template and returns it. */
  useTemplate: (templateId: string) =>
    send<Survey>('POST', `/api/v1/templates/${encodeURIComponent(templateId)}/surveys`),
  /** Saves a survey's type, questions and thank-you message as the organisation's own template. */
  saveAsTemplate: (surveyId: string, details: TemplateDetails) =>
    send<Template>('POST', '/api/v1/templates', { survey_id: surveyId, ...details }),
  /** Renames one of the organisation's own templates. Built-in ones get 403. */
  updateTemplate: (templateId: string, details: Partial<TemplateDetails>) =>
    send<Template>('PATCH', `/api/v1/templates/${encodeURIComponent(templateId)}`, details),
  deleteTemplate: (templateId: string) =>
    send<void>('DELETE', `/api/v1/templates/${encodeURIComponent(templateId)}`),
  /** Survey performance by channel, latest activity first. `limit` and `offset` count surveys, not rows. */
  performance: (page: { limit?: number; offset?: number } = {}) => {
    const params = new URLSearchParams();
    if (page.limit !== undefined) params.set('limit', String(page.limit));
    if (page.offset) params.set('offset', String(page.offset));
    const query = params.toString();
    return getJson<PerformanceRow[]>(`/api/v1/results/performance${query ? `?${query}` : ''}`);
  },
};

function questionsPath(surveyId: string, questionId?: string) {
  const base = `/api/v1/surveys/${encodeURIComponent(surveyId)}/questions`;
  return questionId ? `${base}/${encodeURIComponent(questionId)}` : base;
}

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body === undefined
      ? { Accept: 'application/json' }
      : { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status, await responseBody(res), `${res.status} ${res.statusText} for ${path}`);
  return (res.status === 204 ? undefined : await res.json()) as T;
}

/** Answer types (see docs/api/openapi.yaml, QuestionKind). */
export type QuestionKind =
  | 'single_choice'
  | 'multiple_choice'
  | 'dropdown'
  | 'text'
  | 'long_text'
  | 'rating'
  | 'nps'
  | 'reasons'
  | 'thumbs';

export type Question = {
  id: string;
  survey_id: string;
  position: number;
  kind: QuestionKind;
  prompt: string;
  options: string[];
  required: boolean;
};

export type QuestionInput = Pick<Question, 'kind' | 'prompt' | 'options' | 'required'>;

export type SurveyType = 'thumbs' | 'nps' | 'csat' | 'custom';

export type SurveyStatus = 'draft' | 'scheduled' | 'live' | 'closed';

export type Snippet = { campaign: string; segment: string; html: string };

export type Survey = {
  id: string;
  title: string;
  /** Template surveys: the title readers see on the survey link page (the name stays private). */
  reader_title?: string | null;
  description: string | null;
  /** Shown to readers after answering. */
  thank_you: string | null;
  type: SurveyType;
  status: SurveyStatus;
  /** The survey's public link, set when it is first published (#5). */
  public_url?: string | null;
  published_at?: string | null;
} & ReaderOptions & Branding & Partial<SurveySettings>;

/** Language of the fixed texts readers see: thank-you and closed pages, snippet buttons. */
export type SurveyLanguage = 'en' | 'fi' | 'sv';

/** Survey settings. null removes the close date or the limit. */
export type SurveySettings = {
  /** No answers tapped from this moment on (ISO date-time). */
  closes_at: string | null;
  /** No new readers once this many have answered. */
  response_limit: number | null;
  /** "Notify me of new responses by email". */
  notify_on_response: boolean;
  language: SurveyLanguage;
};

/** Branding: colours as "#RRGGBB", and where to load the logo (null when there is none). */
export type Branding = {
  accent_color: string;
  background_color: string;
  logo_url: string | null;
};

/** Reader options from "Edit and preview". All on by default. */
export type ReaderOptions = {
  /** Optional "Tell us more" field after any answer. */
  comment_field: boolean;
  /** Readers see the results after answering. */
  show_results: boolean;
  /** "Contact me about this by email" opt-in. */
  contact_opt_in: boolean;
};

export type SurveyListItem = Survey & {
  /** Answers per value of the main question, e.g. { '9': 12, '10': 30 }. */
  answer_counts?: Record<string, number>;
  opens_at: string | null;
  closes_at: string | null;
  /** Submitted responses so far. */
  answers: number;
  /** When the newest response arrived; null before the first. */
  last_answer_at: string | null;
  created_at: string;
  /** Last change to the survey's settings or texts. */
  updated_at: string;
  /** "Headline score", e.g. { score: 'NPS +42', note: 'scale −100 to +100' }; null before answers. */
  headline: { score: string; note: string } | null;
};

export type PerformanceRow = {
  survey_id: string;
  survey: string;
  channel: 'email' | 'link' | 'qr';
  views: number;
  responses: number;
  response_rate: number | null;
  main_result: string | null;
};

export type OverviewSegment = { value: string; label: string; answers: number };

/** The first nps, thumbs or rating question of a survey and how it scored. */
export type OverviewMain = {
  question_id: string;
  kind: 'nps' | 'thumbs' | 'rating';
  /** NPS, thumbs positive % or rating satisfied %; null before any answer. */
  score: number | null;
  /** Score now minus the score at the end of the previous month; null when there is none. */
  change: number | null;
  /** Answers per scale value. */
  counts: Record<string, number>;
};

export type OverviewQuestion = {
  id: string;
  kind: QuestionKind;
  prompt: string;
  required: boolean;
  answers: number;
  options: { label: string; count: number }[];
  /** Scale questions only, one decimal. */
  average: number | null;
};

export type SurveyOverview = {
  survey_id: string;
  title: string;
  type: SurveyType;
  status: SurveyStatus;
  closes_at: string | null;
  last_answer_at: string | null;
  /** Channels with views or answers. */
  channels: ('email' | 'link' | 'qr')[];
  /** The segment filter that was applied. */
  segment: string;
  /** Segments that can be chosen; empty when there are fewer than 2. */
  segments: OverviewSegment[];
  responses: number;
  views: number;
  /** Whole percent; null with a segment or without views. */
  response_rate: number | null;
  /** Percent of responses that answered every question; custom surveys only. */
  completed_all: number | null;
  main: OverviewMain | null;
  questions: OverviewQuestion[];
  reasons: { label: string; count: number; percent: number | null }[];
  trend: { month: string; score: number | null; answers: number }[];
  by_segment: { value: string; label: string; answers: number; score: number | null; counts: Record<string, number> }[];
};

export type ResponseFilters = { segment?: string; q?: string; group?: string };

export type ResponseRow = {
  id: string;
  display_id: string;
  submitted_at: string;
  answer: number | null;
  reason: string | null;
  comment: string | null;
  masked: boolean;
  /** Null when the survey has no segments to show. */
  segment_label: string | null;
};

export type ResponsesPage = { total: number; rows: ResponseRow[] };

export type ResponseDetail = {
  display_id: string;
  submitted_at: string;
  segment_label: string | null;
  answers: {
    question_id: string;
    prompt: string;
    kind: string;
    value: number | string | string[] | null;
    masked: boolean;
  }[];
};

const resultsPath = (surveyId: string) => `/api/v1/results/${encodeURIComponent(surveyId)}`;

function responseQuery(filters: ResponseFilters, paging?: { limit: number; offset: number }): string {
  const params = new URLSearchParams();
  if (paging) {
    params.set('limit', String(paging.limit));
    params.set('offset', String(paging.offset));
  }
  if (filters.segment && filters.segment !== 'all') params.set('segment', filters.segment);
  if (filters.q) params.set('q', filters.q);
  if (filters.group) params.set('group', filters.group);
  return params.toString();
}

/** Where the CSV of all matching responses is served; it carries the same filters. */
export function responsesCsvUrl(surveyId: string, filters: ResponseFilters = {}): string {
  const query = responseQuery(filters);
  return `${resultsPath(surveyId)}/responses.csv${query ? `?${query}` : ''}`;
}

export type Template = {
  id: string;
  name: string;
  type: SurveyType;
  description: string;
  thank_you: string;
  /** Shown as a card on the Templates page. */
  featured: boolean;
  /** Saved by the organisation. Built-in templates (false) are read-only. */
  own: boolean;
  /** The first is the main question; thumbs, NPS and CSAT templates follow it with reason bubbles. */
  questions: Pick<Question, 'kind' | 'prompt' | 'options' | 'required'>[];
  /** Own templates: the branding colours of the survey they were saved from. */
  accent_color?: string | null;
  background_color?: string | null;
};

/** The name and description a user gives their own template. */
export type TemplateDetails = { name: string; description: string };

/** The `detail` text of an API error (e.g. a 409 "Add a question before publishing."), if any. */
export function errorDetail(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null;
  const body = error.body as { detail?: unknown } | null;
  return typeof body?.detail === 'string' ? body.detail : null;
}
