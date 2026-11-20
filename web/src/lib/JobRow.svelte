<script lang="ts">
	import { age, countryName, label, pay, type Job } from './api';

	let { job, selected, fresh, narrow = false, onselect }: { job: Job; selected: boolean; fresh: boolean; narrow?: boolean; onselect: () => void } = $props();

	const where = $derived(
		job.remote === 'remote'
			? `Remote${job.remote_region ? ' · ' + label('region', job.remote_region) : job.countries[0] ? ' · ' + job.countries[0] : ''}`
			: job.location || (job.countries[0] ? countryName(job.countries[0]) : '')
	);
	const salary = $derived(pay(job));
	// whole chips only: fewer when the detail pane narrows the list
	const shown = $derived(job.skills.slice(0, selected || narrow ? 4 : 6));
</script>

<button
	class="row group grid w-full grid-cols-[6px_minmax(0,1fr)_auto] items-start gap-x-3 border-b border-line px-4 py-2.5 text-left transition-colors duration-100
	{selected ? 'bg-paper text-ink' : 'hover:bg-white/[0.035]'}"
	onclick={onselect}
	data-id={job.id}
	aria-current={selected}
>
	<span class="mt-[7px] size-1.5 rounded-full {fresh ? 'bg-amber' : 'bg-transparent'}" title={fresh ? 'New since your last visit' : undefined}></span>

	<span class="min-w-0">
		<span class="flex min-w-0 items-baseline gap-1.5">
			<span class="hidden max-w-[45%] shrink-0 truncate sm:inline {selected ? 'text-ink/60' : 'text-muted'}">{job.company}</span>
			<span class="hidden sm:inline {selected ? 'text-ink/40' : 'text-dim'}">/</span>
			<span class="line-clamp-2 font-medium sm:truncate">{job.title}</span>
		</span>
		<span class="mt-1 flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-1 whitespace-nowrap sm:flex-nowrap">
			<span class="truncate text-[11px] sm:hidden {selected ? 'text-ink/60' : 'text-muted'}">{job.company}</span>
			<span class="font-mono text-[11px] {selected ? 'text-ink/70' : 'text-muted'}">@{job.seniority}</span>
			{#if job.role}<span class="text-[11px] {selected ? 'text-ink/60' : 'text-dim'}">{label('role', job.role)}</span>{/if}
			<span class="mx-0.5 hidden h-3 w-px sm:inline {selected ? 'bg-ink/20' : 'bg-line-2'}"></span>
			<!-- phones: chips on their own line, 3 max -->
			<span class="flex min-w-0 basis-full items-center gap-1.5 overflow-hidden sm:basis-auto">
			{#each shown as s, i (s)}
				<span
					class="rounded-[4px] px-1.5 font-mono text-[11px] leading-[18px] {i >= 3 ? 'hidden sm:inline' : ''} {selected
						? 'bg-ink/10 text-ink/80'
						: 'bg-white/[0.05] text-muted'}">{s}</span
				>
			{/each}
			{#if job.skills.length > 3}<span class="num shrink-0 text-[11px] sm:hidden {selected ? 'text-ink/50' : 'text-dim'}">+{job.skills.length - 3}</span>{/if}
			</span>
			{#if job.skills.length > shown.length}<span class="num hidden shrink-0 text-[11px] sm:inline {selected ? 'text-ink/50' : 'text-dim'}">+{job.skills.length - shown.length}</span>{/if}
		</span>
	</span>

	<span class="flex flex-col items-end gap-1 text-right whitespace-nowrap">
		<span class="flex items-baseline gap-2">
		{#if job.match_pct != null}
			<span
				class="num rounded px-1 text-[11px] {selected
					? 'bg-ink/10 text-ink'
					: job.match_pct >= 75
						? 'bg-resolve/15 text-resolve'
						: 'text-dim'}"
				title="Best match: {job.match_resume}">{job.match_pct}%</span
			>
		{/if}
		<span class="num {salary ? (selected ? 'text-ink' : 'text-paper') : selected ? 'text-ink/40' : 'text-dim'}">{salary || '—'}</span>
		</span>
		<span class="flex items-center gap-2 text-[11px] {selected ? 'text-ink/60' : 'text-dim'}">
			<span class="max-w-44 truncate">{where}</span>
			<span class="num w-8 text-right">{age(job.posted)}</span>
		</span>
	</span>
</button>
