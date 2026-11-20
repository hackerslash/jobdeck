export type Job = {
	id: string;
	source: string;
	company: string;
	title: string;
	role: string | null;
	seniority: string;
	posted: string;
	location: string | null;
	countries: string[];
	remote: string | null;
	remote_region: string | null;
	employment: string;
	salary_usd_min: number | null;
	salary_usd_max: number | null;
	salary_summary: string | null;
	skills: string[];
	years_min: number | null;
	visa: boolean | null;
	equity: boolean;
	relocation: boolean;
	lang: string;
	tags: string[];
	apply_url: string;
	match_pct: number | null;
	match_resume: string | null;
};

export type JobDetail = Job & {
	url: string | null;
	department: string | null;
	team: string | null;
	salary_currency: string | null;
	lang_required: string[];
	description: string | null;
};

export type Similar = Pick<Job, 'id' | 'title' | 'company' | 'role' | 'seniority' | 'location' | 'salary_usd_min' | 'salary_usd_max' | 'posted'> & { sim: number };

export type Facets = Record<string, [string, number][]>;

export type Resume = {
	id: number; name: string; filename: string; created: string; skills: string[]; roles: string[];
	years: number | null; seniority: string; chars: number; best_for: number;
};

export type MatchPart = {
	resume: string; pct: number; sem: number; skill: number; exp: number; role: number; matched: string[]; missing: string[];
};

export type Status = {
	state: string;
	last_run: string | null;
	last_error: string | null;
	log: string[];
	jobs: number;
	companies: number;
	newest: string | null;
	embedded: number;
	snapshot: string | null;
	sources: number;
	rule_errors: string[];
};

/** Filter state; every key maps 1:1 to an /api query param. */
export type Filters = {
	q: string;
	role: string[];
	seniority: string[];
	remote: string[];
	region: string[];
	employment: string[];
	source: string[];
	lang: string[];
	country: string[];
	skill: string[];
	tag: string[];
	exclude_tag: string[];
	eligible: string[];
	salary_min: number | null;
	match_min: number | null;
	days: number | null;
	years_max: number | null;
	visa: boolean;
	company: string;
	sort: string;
};

export const LIST_KEYS = ['role', 'seniority', 'remote', 'region', 'employment', 'source', 'lang', 'country', 'eligible', 'skill', 'tag', 'exclude_tag'] as const;
export type ListKey = (typeof LIST_KEYS)[number];

export const emptyFilters = (): Filters => ({
	q: '', role: [], seniority: [], remote: [], region: [], employment: [], source: [], lang: [], country: [],
	skill: [], tag: [], exclude_tag: [], eligible: [], match_min: null, salary_min: null, days: null, years_max: null, visa: false, company: '', sort: 'newest'
});

export function toParams(f: Filters): URLSearchParams {
	const p = new URLSearchParams();
	if (f.q.trim()) p.set('q', f.q.trim());
	for (const k of LIST_KEYS) for (const v of f[k]) p.append(k, v);
	if (f.salary_min) p.set('salary_min', String(f.salary_min));
	if (f.match_min) p.set('match_min', String(f.match_min));
	if (f.days) p.set('days', String(f.days));
	if (f.years_max != null) p.set('years_max', String(f.years_max));
	if (f.visa) p.set('visa', 'true');
	if (f.company) p.set('company', f.company);
	if (f.sort !== 'newest') p.set('sort', f.sort);
	return p;
}

export function fromParams(p: URLSearchParams): Filters {
	const f = emptyFilters();
	f.q = p.get('q') ?? '';
	for (const k of LIST_KEYS) f[k] = p.getAll(k);
	const n = (k: string) => (p.get(k) ? Number(p.get(k)) : null);
	f.salary_min = n('salary_min');
	f.match_min = n('match_min');
	f.days = n('days');
	f.years_max = n('years_max');
	f.visa = p.get('visa') === 'true';
	f.company = p.get('company') ?? '';
	f.sort = p.get('sort') ?? 'newest';
	return f;
}

/** `role:backend skill:rust remote:remote` typed in the query become filters. */
const TOKEN_KEYS: Record<string, ListKey> = {
	role: 'role', level: 'seniority', seniority: 'seniority', remote: 'remote', region: 'region', type: 'employment',
	source: 'source', lang: 'lang', country: 'country', eligible: 'eligible', skill: 'skill', tag: 'tag', '-tag': 'exclude_tag'
};

export function absorbTokens(f: Filters): Filters {
	const rest: string[] = [];
	for (const word of f.q.split(/\s+/)) {
		const m = word.match(/^(-?[a-z]+):(.+)$/i);
		const key = m && TOKEN_KEYS[m[1].toLowerCase()];
		if (key && m) {
			const v = key === 'country' || key === 'eligible' ? m[2].toUpperCase() : m[2];
			if (!f[key].includes(v)) f[key] = [...f[key], v];
		} else if (word) rest.push(word);
	}
	f.q = rest.join(' ');
	return f;
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
	const r = await fetch(path, { signal });
	if (!r.ok) throw Object.assign(new Error((await r.json().catch(() => null))?.detail ?? r.statusText), { status: r.status });
	return r.json();
}

export const api = {
	jobs: (f: Filters, offset: number, signal?: AbortSignal) => {
		const p = toParams(f);
		p.set('offset', String(offset));
		p.set('limit', '60');
		return get<{ total: number; took_ms: number; jobs: Job[] }>(`/api/jobs?${p}`, signal);
	},
	facets: (f: Filters, signal?: AbortSignal) => get<Facets>(`/api/facets?${toParams(f)}`, signal),
	job: (id: string) => get<JobDetail>(`/api/job/${encodeURIComponent(id)}`),
	similar: (id: string) => get<Similar[]>(`/api/job/${encodeURIComponent(id)}/similar`),
	status: () => get<Status>('/api/status'),
	parse: (q: string) => get<{ filters: Partial<Filters>; understood: string[] }>(`/api/parse?q=${encodeURIComponent(q)}`),
	match: (id: string) => get<MatchPart[]>(`/api/job/${encodeURIComponent(id)}/match`),
	resumes: () => get<Resume[]>('/api/resumes'),
	addResume: async (file: File, name: string) => {
		const body = new FormData();
		body.set('file', file);
		body.set('name', name);
		const r = await fetch('/api/resumes', { method: 'POST', body });
		if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? r.statusText);
		return (await r.json()) as Resume;
	},
	deleteResume: (id: number) => fetch(`/api/resumes/${id}`, { method: 'DELETE' }),
	update: () => fetch('/api/update', { method: 'POST' }).then((r) => r.json())
};

// ---------- formatting ----------

export const ROLE_LABEL: Record<string, string> = {
	software: 'Software', backend: 'Backend', frontend: 'Frontend', fullstack: 'Full-stack', mobile: 'Mobile',
	ml_ai: 'ML / AI', data_eng: 'Data eng', data_analytics: 'Data & analytics', devops: 'DevOps / SRE', security: 'Security',
	embedded: 'Embedded / HW', qa: 'QA / test', gamedev: 'Games', blockchain: 'Blockchain', devrel: 'DevRel',
	solutions: 'Solutions eng', architect: 'Architect', tech_writing: 'Tech writing', support_eng: 'Support eng',
	product: 'Product', design: 'Design', it_ops: 'IT / ops', eng_mgmt: 'Eng management'
};
export const LABELS: Record<string, Record<string, string>> = {
	role: ROLE_LABEL,
	remote: { remote: 'Remote', hybrid: 'Hybrid', onsite: 'On-site' },
	region: { global: 'Anywhere', americas: 'Americas', europe: 'Europe', apac: 'APAC', latam: 'LatAm' },
	employment: { full_time: 'Full-time', part_time: 'Part-time', contract: 'Contract', internship: 'Internship', temporary: 'Temporary' },
	lang: { en: 'English', de: 'German', fr: 'French', es: 'Spanish', nl: 'Dutch', pt: 'Portuguese' }
};
export const label = (key: string, v: string) => LABELS[key]?.[v] ?? (key === 'seniority' ? v[0].toUpperCase() + v.slice(1) : v);

const regionNames = new Intl.DisplayNames(['en'], { type: 'region' });
export const countryName = (cc: string) => {
	try {
		return regionNames.of(cc) ?? cc;
	} catch {
		return cc;
	}
};

export const k = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1000 ? `${Math.round(n / 1000)}k` : String(n));

export function pay(j: Pick<Job, 'salary_usd_min' | 'salary_usd_max'>): string {
	const { salary_usd_min: lo, salary_usd_max: hi } = j;
	if (!lo && !hi) return '';
	if (lo && hi && Math.abs(hi - lo) > 500) return `$${k(lo)}–${k(hi)}`;
	return `$${k((hi ?? lo)!)}`;
}

export function age(iso: string): string {
	const h = (Date.now() - new Date(iso).getTime()) / 3.6e6;
	if (h < 1) return 'now';
	if (h < 24) return `${Math.floor(h)}h`;
	const d = h / 24;
	if (d < 60) return `${Math.floor(d)}d`;
	return `${Math.floor(d / 30)}mo`;
}
