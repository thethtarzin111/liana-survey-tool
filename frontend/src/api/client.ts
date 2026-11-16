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
};

export type SurveyType = 'thumbs' | 'nps' | 'csat' | 'custom';

export type Survey = {
  id: string;
  title: string;
  description: string | null;
  type: SurveyType;
  status: 'draft' | 'scheduled' | 'live' | 'closed';
};
