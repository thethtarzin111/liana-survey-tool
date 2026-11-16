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
    changes: Partial<Pick<Survey, 'title' | 'description'>>,
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
  | 'reasons';

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
  type: SurveyType;
  status: SurveyStatus;
};

export type SurveyListItem = Survey & {
  opens_at: string | null;
  /** Submitted responses so far. */
  answers: number;
};
