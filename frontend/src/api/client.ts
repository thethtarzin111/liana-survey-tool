// Small fetch wrapper. Later, generate typed calls from docs/api/openapi.yaml.

export type CurrentUser = {
  user_id: string;
  tenant_id: string;
  tenant_name: string;
  name: string;
  email: string;
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
    changes: Partial<Pick<Survey, 'title' | 'description' | 'thank_you' | keyof ReaderOptions | 'accent_color' | 'background_color'>>,
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
  /** Close (live → closed) or unpublish (live/scheduled → draft) a survey. */
  changeSurveyStatus: (id: string, action: 'close' | 'unpublish') =>
    send<Survey>('POST', `/api/v1/surveys/${encodeURIComponent(id)}/${action}`),
  deleteSurvey: (id: string) => send<void>('DELETE', `/api/v1/surveys/${encodeURIComponent(id)}`),
  /** Draft → live, with a public link (#5). 409 with a reason in `detail` when it isn't ready. */
  publishSurvey: (id: string) => send<Survey>('POST', `/api/v1/surveys/${encodeURIComponent(id)}/publish`),
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
  result: (surveyId: string, segment = 'all') =>
    getJson<SurveyResult>(`/api/v1/results/${encodeURIComponent(surveyId)}?${new URLSearchParams({ segment })}`),
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

export type Survey = {
  id: string;
  title: string;
  description: string | null;
  /** Shown to readers after answering. */
  thank_you: string | null;
  type: SurveyType;
  status: SurveyStatus;
  /** The survey's public link, set when it is first published (#5). */
  public_url?: string | null;
  published_at?: string | null;
} & ReaderOptions & Branding;

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
  opens_at: string | null;
  /** Submitted responses so far. */
  answers: number;
  /** "Headline score", e.g. { score: 'NPS +42', note: 'scale −100 to +100' }; null before answers. */
  headline: { score: string; note: string } | null;
};

export type SurveyResult = {
  survey_id: string;
  title: string;
  type: SurveyType;
  status: SurveyStatus;
  answers: number;
  segment: string;
  segments: string[];
  headline: { score: string; note: string } | null;
  split: { value: number; count: number; percent: number | null }[];
};

export type Template = {
  id: string;
  name: string;
  type: SurveyType;
  description: string;
  thank_you: string;
  /** Shown as a card on the Templates page. */
  featured: boolean;
  /** The first is the main question; thumbs, NPS and CSAT templates follow it with reason bubbles. */
  questions: Pick<Question, 'kind' | 'prompt' | 'options' | 'required'>[];
};

/** The `detail` text of an API error (e.g. a 409 "Add a question before publishing."), if any. */
export function errorDetail(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null;
  const body = error.body as { detail?: unknown } | null;
  return typeof body?.detail === 'string' ? body.detail : null;
}
