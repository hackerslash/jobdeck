<script lang="ts">
	import { RefreshCw, Search, Settings, Sparkles, X } from '@lucide/svelte';
	import { onMount, tick } from 'svelte';
	import { flip } from 'svelte/animate';
	import { fade } from 'svelte/transition';
	import FacetRail from '#lib/FacetRail.svelte';
	import JobPane from '#lib/JobPane.svelte';
	import JobRow from '#lib/JobRow.svelte';
	import {
		absorbTokens, api, countryName, emptyFilters, fromParams, k, label, LIST_KEYS, toParams,
		type Facets, type Filters, type Job, type Status
	} from '#lib/api.ts';

	let filters = $state<Filters>(emptyFilters());
	let jobs = $state<Job[]>([]);
	let total = $state(0);
	let took = $state(0);
	let facets = $state<Facets | null>(null);
	let status = $state<Status | null>(null);
	let loading = $state(true);
	let loadingMore = $state(false);
	let error = $state<{ msg: string; warming: boolean } | null>(null);
	let selected = $state<string | null>(null);
	let showHelp = $state(false);
	let showFilters = $state(false);
	let understood = $state<string[]>([]);
	let lastVisit = 0;
	let seen = $state(new Set<string>());

	let queryEl: HTMLInputElement | undefined = $state();
	let listEl: HTMLElement | undefined = $state();
	let sentinel: HTMLElement | undefined = $state();
	let ctrl: AbortController | null = null;
	let debounce: ReturnType<typeof setTimeout>;

	const store = {
		get: (key: string) => {
			try {
				return localStorage.getItem(key);
			} catch {
				return null;
			}
		},
		set: (key: string, v: string) => {
			try {
				localStorage.setItem(key, v);
			} catch {
				/* private mode: marks just won't persist */
			}
		}
	};

	async function load(reset = true) {
		ctrl?.abort();
		ctrl = new AbortController();
		const signal = ctrl.signal;
		if (reset) loading = true;
		else loadingMore = true;
		try {
			const [r, fc] = await Promise.all([
				api.jobs(filters, reset ? 0 : jobs.length, signal),
				reset ? api.facets(filters, signal) : Promise.resolve(facets)
			]);
			jobs = reset ? r.jobs : [...jobs, ...r.jobs];
			total = r.total;
			took = r.took_ms;
			facets = fc;
			error = null;
			if (reset) listEl?.scrollTo({ top: 0 });
		} catch (e: any) {
			if (e.name === 'AbortError') return;
			error = { msg: e.message, warming: e.status === 503 };
			if (e.status === 503) setTimeout(() => load(true), 4000);
		} finally {
			if (!signal.aborted) loading = loadingMore = false;
		}
	}

	function apply(next: Filters, { debounced = false } = {}) {
		filters = next;
		const qs = toParams(filters).toString();
		history.replaceState(history.state, '', qs ? `?${qs}` : location.pathname);
		clearTimeout(debounce);
		if (debounced) debounce = setTimeout(() => load(true), 180);
		else load(true);
	}

	function onQueryInput(e: Event) {
		const q = (e.currentTarget as HTMLInputElement).value;
		apply({ ...filters, q, sort: q && filters.sort === 'newest' ? 'relevance' : !q && filters.sort === 'relevance' ? 'newest' : filters.sort }, { debounced: true });
	}

	function onQueryKey(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			understand();
		} else if (e.key === 'Escape') {
			queryEl?.blur();
		} else if (e.key === 'ArrowDown') {
			e.preventDefault();
			queryEl?.blur();
			if (jobs[0]) select(jobs[0].id);
		}
	}

	/** `key:value` tokens first, then plain language ("remote backend from india 2-4 years") via the local parser. */
	async function understand() {
		let next = absorbTokens({ ...filters });
		understood = [];
		if (next.q.trim().split(/\s+/).length >= 2) {
			try {
				const r = await api.parse(next.q);
				const pf = r.filters as any;
				for (const k of LIST_KEYS) if (pf[k]) next[k] = [...new Set([...next[k], ...pf[k]])];
				for (const k of ['salary_min', 'days', 'years_max', 'visa'] as const) if (pf[k] != null) (next as any)[k] = pf[k];
				next.q = pf.q ?? next.q;
				if (!next.q && next.sort === 'relevance') next.sort = hasMatch ? 'match' : 'newest';
				understood = r.understood;
			} catch {
				/* parser unavailable: keep the text query */
			}
		}
		apply(next);
	}

	async function select(id: string | null) {
		selected = id;
		if (!id) return;
		if (!seen.has(id)) {
			seen = new Set(seen).add(id);
			store.set('jobdeck.seen', JSON.stringify([...seen].slice(-5000)));
		}
		await tick();
		listEl?.querySelector(`[data-id="${CSS.escape(id)}"]`)?.scrollIntoView({ block: 'nearest' });
	}

	function move(d: number) {
		const i = jobs.findIndex((j) => j.id === selected);
		const next = jobs[Math.min(jobs.length - 1, Math.max(0, i + d))];
		if (next) select(next.id);
		if (i + d >= jobs.length - 5 && jobs.length < total && !loadingMore) load(false);
	}

	function onKey(e: KeyboardEvent) {
		const t = e.target as HTMLElement;
		if (t.matches('input, textarea, select') || e.metaKey || e.ctrlKey || e.altKey) return;
		if (e.key === 'Enter' && t.closest('button:not(.row), a')) return; // Enter activates the focused control, never apply
		const job = jobs.find((j) => j.id === selected);
		if (e.key === '/') {
			e.preventDefault();
			queryEl?.focus();
			queryEl?.select();
		} else if (e.key === 'j' || e.key === 'ArrowDown') {
			e.preventDefault();
			move(1);
		} else if (e.key === 'k' || e.key === 'ArrowUp') {
			e.preventDefault();
			move(-1);
		} else if (e.key === 'Escape') {
			if (showHelp) showHelp = false;
			else if (showFilters) showFilters = false;
			else select(null);
		} else if ((e.key === 'a' || e.key === 'Enter') && job) {
			window.open(job.apply_url, '_blank', 'noopener');
		} else if (e.key === '?') {
			showHelp = !showHelp;
		}
	}

	function chips(): { key: string; value: string; text: string }[] {
		const out = [];
		for (const key of LIST_KEYS)
			for (const value of filters[key])
				out.push({ key, value, text: `${key === 'exclude_tag' ? '-tag' : key}:${key === 'country' || key === 'eligible' ? value : label(key, value).toLowerCase().replace(/\s+/g, '-')}` });
		if (filters.salary_min) out.push({ key: 'salary_min', value: '', text: `pay>=${k(filters.salary_min)}` });
		if (filters.match_min) out.push({ key: 'match_min', value: '', text: `match>=${filters.match_min}%` });
		if (filters.days) out.push({ key: 'days', value: '', text: `posted<=${filters.days}d` });
		if (filters.years_max != null) out.push({ key: 'years_max', value: '', text: `years<=${filters.years_max}` });
		if (filters.visa) out.push({ key: 'visa', value: '', text: 'visa:yes' });
		if (filters.company) out.push({ key: 'company', value: '', text: `company:${filters.company}` });
		return out;
	}

	function removeChip(c: { key: string; value: string }) {
		const f: any = { ...filters };
		if ((LIST_KEYS as readonly string[]).includes(c.key)) f[c.key] = f[c.key].filter((v: string) => v !== c.value);
		else f[c.key] = c.key === 'visa' ? false : c.key === 'company' ? '' : null;
		apply(f);
	}

	async function refreshStatus() {
		try {
			status = await api.status();
		} catch {
			/* server restarting */
		}
	}

	async function syncNow() {
		await api.update();
		refreshStatus();
	}

	onMount(() => {
		filters = fromParams(new URLSearchParams(location.search));
		lastVisit = Number(store.get('jobdeck.lastVisit') ?? 0);
		store.set('jobdeck.lastVisit', String(Date.now()));
		try {
			seen = new Set(JSON.parse(store.get('jobdeck.seen') ?? '[]'));
		} catch {
			seen = new Set();
		}
		load(true);
		refreshStatus();
		const poll = setInterval(refreshStatus, 15000);
		const io = new IntersectionObserver((es) => {
			if (es[0].isIntersecting && !loading && !loadingMore && jobs.length < total) load(false);
		}, { root: listEl, rootMargin: '600px' });
		if (sentinel) io.observe(sentinel);
		return () => {
			clearInterval(poll);
			io.disconnect();
		};
	});

	const fresh = (j: Job) => lastVisit > 0 && new Date(j.posted).getTime() > lastVisit && !seen.has(j.id);
	const snapshotAge = $derived(status?.snapshot ? new Date(status.snapshot).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '');
	const busy = $derived(status && status.state !== 'idle');
	const hasMatch = $derived(jobs.some((j) => j.match_pct != null));
	const reduceMotion = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
</script>

<svelte:window onkeydown={onKey} />
<svelte:head><title>jobdeck{total ? ` · ${total.toLocaleString()}` : ''}</title></svelte:head>

<div class="grid h-dvh grid-rows-[auto_1fr] overflow-hidden">
	<!-- query bar -->
	<header class="flex items-center gap-4 border-b border-line px-4 py-2.5">
		<a href="/" class="flex shrink-0 items-center gap-2 font-mono text-[13px] font-medium tracking-tight text-paper" onclick={(e) => { e.preventDefault(); apply(emptyFilters()); }}>
			<span class="grid size-5 place-items-center rounded-[5px] bg-resolve text-[11px] font-bold text-ink">j</span>
			jobdeck
		</a>
		<label class="group relative flex max-w-2xl flex-1 items-center">
			<Search size={15} class="pointer-events-none absolute left-3 text-dim group-focus-within:text-resolve" />
			<input
				bind:this={queryEl}
				value={filters.q}
				oninput={onQueryInput}
				onkeydown={onQueryKey}
				class="w-full rounded-lg border border-line bg-ink-2/70 py-2 pr-16 pl-9 text-[14px] text-paper transition-colors placeholder:text-dim focus:border-resolve/40 focus:bg-ink-2 focus:outline-none"
				placeholder="Search {status?.jobs ? status.jobs.toLocaleString() : ''} jobs… try  remote backend from india 2-4 years"
				spellcheck="false"
				autocomplete="off"
				aria-label="Search jobs"
			/>
			<kbd class="pointer-events-none absolute right-3 rounded border border-line-2 px-1.5 font-mono text-[11px] text-dim">/</kbd>
		</label>
		<div class="ml-auto flex items-center gap-3 text-[12px] text-dim">
			{#if status}
				<span class="hidden items-center gap-1.5 lg:flex" title={status.log.at(-1) ?? ''}>
					<span class="size-1.5 rounded-full {status.last_error ? 'bg-conflict' : busy ? 'animate-pulse bg-amber' : 'bg-resolve'}"></span>
					{busy ? `${status.state}…` : `snapshot ${snapshotAge}`}
				</span>
				<button class="rounded-md p-1.5 hover:bg-white/[0.06] hover:text-paper disabled:opacity-40" onclick={syncNow} disabled={!!busy} title="Check for a new snapshot now">
					<RefreshCw size={14} class={busy ? 'animate-spin' : ''} />
				</button>
			{/if}
			<button class="rounded-md border border-line-2 px-2 py-0.5 text-[12px] text-muted hover:text-paper md:hidden" onclick={() => (showFilters = true)}>
				Filters{#if chips().length}<span class="num ml-1 text-resolve">{chips().length}</span>{/if}
			</button>
			<a href="/settings" class="rounded-md p-1.5 hover:bg-white/[0.06] hover:text-paper" title="Resumes & matching" aria-label="Resumes and matching settings"><Settings size={15} /></a>
			<button class="hidden rounded-md border border-line-2 px-1.5 font-mono text-[11px] hover:text-paper md:block" onclick={() => (showHelp = !showHelp)} aria-label="Keyboard shortcuts">?</button>
		</div>
	</header>

	<div class="grid min-h-0 grid-cols-1 md:grid-cols-[248px_minmax(0,1fr)] {selected ? 'xl:grid-cols-[248px_minmax(0,1fr)_minmax(460px,42%)]' : ''}">
		<div class="hidden min-h-0 overflow-y-auto border-r border-line pt-2 md:block">
			<FacetRail {facets} {filters} {hasMatch} onchange={(f) => apply(f)} />
		</div>

		<!-- results -->
		<main class="relative min-h-0 overflow-y-auto" bind:this={listEl}>
			<div class="glass sticky top-0 z-10 flex min-h-11 flex-wrap items-center gap-x-3 gap-y-1.5 border-x-0 border-t-0 px-4 py-2">
				<span class="num text-[12px] text-muted">
					{#if loading && !jobs.length}<span class="text-dim">loading…</span>{:else}{total.toLocaleString()} <span class="text-dim">jobs · {took}ms</span>{/if}
				</span>
				{#if understood.length}
					<span class="inline-flex items-center gap-1 text-[11px] text-dim" title="Parsed locally from your search">
						<Sparkles size={11} class="text-amber" />{understood.join(' · ')}
					</span>
				{/if}
				{#each chips() as c (c.key + c.value)}
					<button
						class="group inline-flex items-center gap-1 rounded-md bg-resolve/10 px-1.5 py-0.5 font-mono text-[11px] text-resolve transition-colors hover:bg-conflict/15 hover:text-conflict"
						onclick={() => removeChip(c)}
						title="Remove filter"
						transition:fade={{ duration: 120 }}
					>
						{c.text}<X size={11} class="opacity-50 group-hover:opacity-100" />
					</button>
				{/each}
				<div class="ml-auto flex overflow-hidden rounded-md border border-line text-[11px]">
					{#each [['match', 'match'], ['relevance', 'relevance'], ['newest', 'newest'], ['salary', 'pay'], ['company', 'company']] as [v, t] (v)}
						<button
							class="px-2 py-1 transition-colors {filters.sort === v ? 'bg-paper text-ink' : 'text-muted hover:text-paper'} disabled:opacity-30"
							disabled={(v === 'relevance' && !filters.q) || (v === 'match' && !hasMatch)}
							title={v === 'match' && !hasMatch ? 'Add a resume in settings to rank by match' : undefined}
							onclick={() => apply({ ...filters, sort: v })}>{t}</button
						>
					{/each}
				</div>
			</div>

			{#if error}
				<div class="mx-auto max-w-md px-6 py-20 text-center">
					{#if error.warming}
						<p class="text-paper">Building the job index for the first time…</p>
						<p class="mt-2 text-muted">Downloading the snapshot, enriching and embedding jobs. This page fills in by itself.</p>
						{#if status?.log.length}<pre class="mt-4 text-left font-mono text-[11px] whitespace-pre-wrap text-dim">{status.log.slice(-6).join('\n')}</pre>{/if}
					{:else}
						<p class="text-conflict">Search failed: {error.msg}</p>
						<button class="mt-3 text-muted underline hover:text-paper" onclick={() => load(true)}>Try again</button>
					{/if}
				</div>
			{:else if loading && !jobs.length}
				{#each Array(14) as _, i (i)}
					<div class="grid grid-cols-[6px_1fr_auto] gap-x-3 border-b border-line px-4 py-3">
						<span></span>
						<span class="space-y-2"><span class="block h-3 w-2/3 animate-pulse rounded bg-white/[0.06]"></span><span class="block h-2.5 w-1/3 animate-pulse rounded bg-white/[0.04]"></span></span>
						<span class="h-3 w-14 animate-pulse rounded bg-white/[0.05]"></span>
					</div>
				{/each}
			{:else if !jobs.length}
				<div class="mx-auto max-w-md px-6 py-20 text-center">
					<p class="text-paper">No jobs match all of these.</p>
					<p class="mt-2 text-muted">Drop a filter above, or widen “Posted within”. {filters.q ? 'Every search word has to appear in the posting.' : ''}</p>
				</div>
			{:else}
				<div class:opacity-60={loading} class="transition-opacity duration-150">
					{#each jobs as job (job.id)}
						<div animate:flip={{ duration: reduceMotion ? 0 : 220 }}>
							<JobRow {job} selected={job.id === selected} narrow={!!selected} fresh={fresh(job)} onselect={() => select(job.id)} />
						</div>
					{/each}
				</div>
			{/if}
			<div bind:this={sentinel} class="h-px"></div>
			{#if loadingMore}<p class="py-4 text-center text-[12px] text-dim">Loading more…</p>{/if}
			{#if !loading && jobs.length && jobs.length >= total}<p class="py-6 text-center text-[11px] text-dim">End of results</p>{/if}
		</main>

		{#if selected}
			<div class="fixed inset-0 z-30 min-h-0 bg-ink/60 p-2 md:absolute md:inset-auto md:top-14 md:right-3 md:bottom-3 md:w-[min(560px,calc(100vw-280px))] md:bg-transparent md:p-0 xl:static xl:w-auto xl:p-3 xl:pl-0" transition:fade={{ duration: 120 }}>
				<JobPane id={selected} onclose={() => select(null)} onopen={(id) => select(id)} />
			</div>
		{/if}
	</div>
</div>

{#if showFilters}
	<div class="fixed inset-0 z-40 bg-ink/50 md:hidden" role="presentation" onclick={() => (showFilters = false)} transition:fade={{ duration: 120 }}>
		<div class="absolute inset-y-0 left-0 w-[86vw] max-w-80 overflow-y-auto rounded-r-2xl border-r border-line bg-ink-2/[0.97] pt-3 shadow-[0_24px_60px_-20px_rgb(0_0_0/0.8)]" role="dialog" aria-label="Filters" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={() => {}}>
			<div class="flex items-center justify-between px-4 pb-2">
				<span class="font-medium">Filters</span>
				<button class="rounded-md p-1 text-dim hover:text-paper" onclick={() => (showFilters = false)} aria-label="Close filters"><X size={16} /></button>
			</div>
			<FacetRail {facets} {filters} {hasMatch} onchange={(f) => apply(f)} />
		</div>
	</div>
{/if}

{#if showHelp}
	<div class="fixed inset-0 z-40" role="presentation" onclick={() => (showHelp = false)}>
		<div class="glass absolute top-14 right-4 w-72 rounded-xl p-4 shadow-[0_24px_60px_-20px_rgb(0_0_0/0.7)]" role="dialog" aria-label="Keyboard shortcuts" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={() => {}}>
			<dl class="grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-2 text-[12px]">
				{#each [['/', 'Search'], ['j  k', 'Next / previous job'], ['↵  a', 'Apply on the employer site'], ['esc', 'Close details'], ['?', 'This list']] as [key, what] (key)}
					<dt><kbd class="rounded border border-line-2 px-1.5 py-0.5 font-mono text-[11px] text-paper">{key}</kbd></dt>
					<dd class="text-muted">{what}</dd>
				{/each}
			</dl>
			<p class="mt-4 border-t border-line pt-3 text-[11px] leading-relaxed text-dim">
				Type filters into search and press ↵: <span class="font-mono text-muted">role:backend skill:Rust remote:remote region:europe country:DE level:senior tag:visa -tag:big-tech</span>
			</p>
		</div>
	</div>
{/if}
