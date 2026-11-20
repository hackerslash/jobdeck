<script lang="ts">
	import { ArrowUpRight, X } from '@lucide/svelte';
	import DOMPurify from 'dompurify';
	import { marked } from 'marked';
	import { age, api, countryName, label, pay, type JobDetail, type MatchPart, type Similar } from './api';

	let { id, onclose, onopen }: { id: string; onclose: () => void; onopen: (id: string) => void } = $props();

	let job = $state<JobDetail | null>(null);
	let similar = $state<Similar[]>([]);
	let match = $state<MatchPart[]>([]);
	let error = $state('');
	let scroller: HTMLElement | undefined = $state();

	$effect(() => {
		const want = id;
		error = '';
		similar = [];
		match = [];
		api.match(want).then((m) => want === id && (match = m), () => {});
		api.job(want).then(
			(j) => {
				if (want === id) {
					job = j;
					scroller?.scrollTo({ top: 0 });
				}
			},
			(e) => (error = e.message)
		);
		api.similar(want).then((s) => want === id && (similar = s), () => {});
	});

	// third-party markdown: render, then sanitise; links open outside the app
	const html = $derived(
		job?.description
			? DOMPurify.sanitize(marked.parse(job.description, { async: false, breaks: true }) as string, {
					FORBID_TAGS: ['img', 'style', 'iframe', 'form'],
					FORBID_ATTR: ['style']
				})
			: ''
	);

	const meta = $derived.by(() => {
		if (!job) return [];
		const rows: [string, string][] = [
			['Pay', [pay(job) && `${pay(job)} USD / yr`, job.salary_currency && job.salary_currency !== 'USD' && job.salary_summary].filter(Boolean).join('   ·   ') || job.salary_summary || 'Not listed'],
			['Posted', `${age(job.posted)} ago · ${new Date(job.posted).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}`],
			['Where', [job.remote && label('remote', job.remote), job.remote_region && label('region', job.remote_region), job.location].filter(Boolean).join(' · ') || '—'],
			['Countries', job.countries.map(countryName).join(', ') || '—'],
			['Experience', job.years_min != null ? `${job.years_min}+ years` : 'Not stated'],
			['Visa', job.visa === true ? 'Sponsors' : job.visa === false ? 'No sponsorship' : 'Not stated'],
			['Type', label('employment', job.employment)],
			['Team', [job.department, job.team].filter((x, i, a) => x && a.indexOf(x) === i).join(' / ') || '—'],
			['Source', job.source]
		];
		if (job.lang_required.length) rows.push(['Requires', job.lang_required.map((l) => label('lang', l)).join(', ')]);
		return rows;
	});
</script>

<aside class="glass flex h-full flex-col overflow-hidden rounded-2xl shadow-[0_24px_60px_-20px_rgb(0_0_0/0.7)]" aria-label="Job details">
	{#if error}
		<p class="p-6 text-conflict">Couldn't load this job: {error}</p>
	{:else if !job}
		<div class="space-y-3 p-6" aria-busy="true">
			<div class="h-3 w-24 animate-pulse rounded bg-white/[0.06]"></div>
			<div class="h-5 w-3/4 animate-pulse rounded bg-white/[0.08]"></div>
			<div class="h-3 w-1/2 animate-pulse rounded bg-white/[0.05]"></div>
		</div>
	{:else}
		<header class="border-b border-line px-6 pt-5 pb-4">
			<div class="flex items-start justify-between gap-4">
				<div class="min-w-0">
					<h2 class="text-[1.125rem] leading-snug font-semibold tracking-[-0.015em] text-balance text-paper">
						<span class="font-normal text-muted">{job.company}</span> <span class="font-normal text-dim">/</span> {job.title}
					</h2>
					<p class="mt-1.5 font-mono text-[12px] text-muted">
						@{job.seniority}{#if job.role}<span class="text-dim">&nbsp;· {label('role', job.role)}</span>{/if}
					</p>
				</div>
				<button class="-mr-2 rounded-md p-1.5 text-dim hover:bg-white/[0.06] hover:text-paper" onclick={onclose} aria-label="Close details (Esc)">
					<X size={16} />
				</button>
			</div>
			<div class="mt-4 flex gap-2">
				<a
					href={job.apply_url}
					target="_blank"
					rel="noopener noreferrer"
					class="inline-flex items-center gap-1.5 rounded-lg bg-resolve px-3.5 py-1.5 font-medium text-ink transition-[filter] duration-150 hover:brightness-110"
				>
					Apply <ArrowUpRight size={14} />
				</a>
				{#if job.url && job.url !== job.apply_url}
					<a
						href={job.url}
						target="_blank"
						rel="noopener noreferrer"
						class="inline-flex items-center gap-1.5 rounded-lg border border-line-2 px-3.5 py-1.5 text-muted transition-colors hover:text-paper"
						>Posting <ArrowUpRight size={14} /></a
					>
				{/if}
				<span class="ml-auto self-center text-[11px] text-dim"><kbd class="font-mono">a</kbd> to apply</span>
			</div>
		</header>

		<div class="min-h-0 flex-1 overflow-y-auto" bind:this={scroller}>
			{#if match.length}
				{@const best = match[0]}
				<section class="border-b border-line px-6 py-4" aria-label="Resume match">
					<div class="flex items-baseline gap-3">
						<span class="num text-[1.5rem] leading-none font-semibold {best.pct >= 75 ? 'text-resolve' : 'text-paper'}">{best.pct}%</span>
						<span class="text-muted">match with <span class="text-paper">{best.resume}</span></span>
					</div>
					<div class="mt-3 grid grid-cols-4 gap-3">
						{#each [['Meaning', best.sem], ['Stack', best.skill], ['Level', best.exp], ['Role', best.role]] as [k, v] (k)}
							<div>
								<div class="mb-1 flex justify-between text-[11px]"><span class="text-dim">{k}</span><span class="num text-muted">{Math.round(Number(v) * 100)}</span></div>
								<div class="h-1 overflow-hidden rounded-full bg-white/[0.06]"><div class="h-full rounded-full bg-resolve/80" style="width: {Number(v) * 100}%"></div></div>
							</div>
						{/each}
					</div>
					{#if best.matched.length || best.missing.length}
						<div class="mt-3 flex flex-wrap gap-1.5">
							{#each best.matched as s (s)}<span class="rounded-[5px] bg-resolve/15 px-1.5 py-0.5 font-mono text-[11px] text-resolve">{s}</span>{/each}
							{#each best.missing as s (s)}<span class="rounded-[5px] border border-dashed border-line-2 px-1.5 py-0.5 font-mono text-[11px] text-dim" title="In the job, not in this resume">{s}</span>{/each}
						</div>
					{/if}
					{#if match.length > 1}
						<ul class="mt-3 space-y-0.5 text-[12px]">
							{#each match.slice(1) as m (m.resume)}
								<li class="flex justify-between text-dim"><span class="truncate">{m.resume}</span><span class="num">{m.pct}%</span></li>
							{/each}
						</ul>
					{/if}
				</section>
			{/if}
			<dl class="grid grid-cols-[88px_1fr] gap-x-4 gap-y-1.5 border-b border-line px-6 py-4">
				{#each meta as [k, v] (k)}
					<dt class="text-dim">{k}</dt>
					<dd class="min-w-0 text-paper/90 {k === 'Pay' ? 'num' : ''} {k === 'Visa' && job.visa ? 'text-resolve' : ''}">{v}</dd>
				{/each}
			</dl>

			{#if job.skills.length || job.tags.length}
				<div class="space-y-3 border-b border-line px-6 py-4">
					{#if job.skills.length}
						<div class="flex flex-wrap gap-1.5">
							{#each job.skills as s (s)}
								<span class="rounded-[5px] bg-white/[0.06] px-2 py-0.5 font-mono text-[12px] text-paper/85">{s}</span>
							{/each}
						</div>
					{/if}
					{#if job.tags.length}
						<div class="flex flex-wrap gap-1.5">
							{#each job.tags as t (t)}
								<span class="rounded-full border border-resolve/30 px-2 py-0.5 font-mono text-[11px] text-resolve">#{t}</span>
							{/each}
						</div>
					{/if}
				</div>
			{/if}

			<article class="readme px-6 py-5">
				{#if html}{@html html}{:else}<p class="text-dim">No description in the snapshot.</p>{/if}
			</article>

			{#if similar.length}
				<section class="border-t border-line px-6 py-5">
					<h3 class="mb-2 text-[11px] font-medium text-dim">Closest roles by description</h3>
					<ul class="-mx-2">
						{#each similar as s (s.id)}
							<li>
								<button class="flex w-full items-baseline gap-2 rounded-md px-2 py-1.5 text-left hover:bg-white/[0.04]" onclick={() => onopen(s.id)}>
									<span class="num w-9 shrink-0 text-[11px] text-resolve">{Math.round(s.sim * 100)}%</span>
									<span class="min-w-0 truncate"><span class="text-muted">{s.company}</span> <span class="text-dim">/</span> {s.title}</span>
									<span class="num ml-auto shrink-0 text-[11px] text-dim">{pay(s)}</span>
								</button>
							</li>
						{/each}
					</ul>
				</section>
			{/if}
		</div>
	{/if}
</aside>
