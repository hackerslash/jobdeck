<script lang="ts">
	import { Check, ChevronDown } from '@lucide/svelte';
	import { countryName, k, label, type Facets, type Filters, type ListKey } from './api';

	let { facets, filters, hasMatch = false, onchange }: { facets: Facets | null; filters: Filters; hasMatch?: boolean; onchange: (f: Filters) => void } = $props();

	type Group = { key: ListKey; title: string; facet: string; search?: boolean; show: number };
	const groups: Group[] = [
		{ key: 'role', title: 'Role', facet: 'role', show: 8 },
		{ key: 'seniority', title: 'Level', facet: 'seniority', show: 9 },
		{ key: 'remote', title: 'Workplace', facet: 'remote', show: 3 },
		{ key: 'region', title: 'Remote from', facet: 'region', show: 5 },
		{ key: 'skill', title: 'Stack', facet: 'skill', search: true, show: 10 },
		{ key: 'country', title: 'Country', facet: 'country', search: true, show: 8 },
		{ key: 'tag', title: 'Tags', facet: 'tag', show: 12 },
		{ key: 'employment', title: 'Type', facet: 'employment', show: 5 },
		{ key: 'lang', title: 'Posting language', facet: 'lang', show: 6 },
		{ key: 'source', title: 'Source', facet: 'source', search: true, show: 6 }
	];
	const DAYS = [
		[1, '24h'], [3, '3d'], [7, '7d'], [30, '30d'], [null, 'all']
	] as const;
	const PAY = [null, 80_000, 120_000, 160_000, 200_000, 250_000];
	const MATCH = [null, 50, 60, 70, 80, 90];

	let open = $state<Record<string, boolean>>({ region: false, employment: false, lang: false, source: false });
	let expanded = $state<Record<string, boolean>>({});
	let needle = $state<Record<string, string>>({});

	function toggle(key: ListKey, v: string) {
		const cur = filters[key];
		onchange({ ...filters, [key]: cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v] });
	}

	function rows(g: Group): [string, number][] {
		const all = facets?.[g.facet] ?? [];
		const sel = filters[g.key];
		// selected values stay visible even when the other filters push their count to zero
		const merged = [...all, ...sel.filter((s) => !all.some(([v]) => v === s)).map((s) => [s, 0] as [string, number])];
		const n = (needle[g.key] ?? '').toLowerCase();
		const hit = n ? merged.filter(([v]) => (g.key === 'country' ? countryName(v) : label(g.key, v)).toLowerCase().includes(n)) : merged;
		return expanded[g.key] || n ? hit : hit.slice(0, Math.max(g.show, sel.length));
	}
	const name = (g: Group, v: string) => (g.key === 'country' ? countryName(v) : label(g.key, v));
</script>

<nav class="flex flex-col gap-1 pb-16 select-none" aria-label="Filters">
	<section class="border-b border-line px-3 pt-1 pb-3">
		<h3 class="mb-2 text-[11px] font-medium text-dim">Posted within</h3>
		<div class="grid grid-cols-5 gap-px overflow-hidden rounded-md bg-line">
			{#each DAYS as [d, t] (t)}
				<button
					class="num py-1 text-[11px] transition-colors duration-150 {filters.days === d
						? 'bg-paper text-ink'
						: 'bg-ink-2 text-muted hover:text-paper'}"
					onclick={() => onchange({ ...filters, days: d })}>{t}</button
				>
			{/each}
		</div>
		<h3 class="mt-3 mb-2 text-[11px] font-medium text-dim">Pay at least (USD / yr)</h3>
		<div class="grid grid-cols-6 gap-px overflow-hidden rounded-md bg-line">
			{#each PAY as p (p)}
				<button
					class="num py-1 text-[11px] transition-colors duration-150 {filters.salary_min === p
						? 'bg-paper text-ink'
						: 'bg-ink-2 text-muted hover:text-paper'}"
					onclick={() => onchange({ ...filters, salary_min: p })}>{p ? k(p) : 'any'}</button
				>
			{/each}
		</div>
		{#if hasMatch || filters.match_min}
			<h3 class="mt-3 mb-2 text-[11px] font-medium text-dim">Resume match at least</h3>
			<div class="grid grid-cols-6 gap-px overflow-hidden rounded-md bg-line">
				{#each MATCH as m (m)}
					<button
						class="num py-1 text-[11px] transition-colors duration-150 {filters.match_min === m
							? 'bg-resolve text-ink'
							: 'bg-ink-2 text-muted hover:text-paper'}"
						onclick={() => onchange({ ...filters, match_min: m })}>{m ? `${m}%` : 'any'}</button
					>
				{/each}
			</div>
		{/if}
		<div class="mt-3 flex items-center justify-between gap-2">
			<button
				class="group flex items-center gap-2 transition-colors {filters.visa ? 'text-paper' : 'text-muted hover:text-paper'}"
				aria-pressed={filters.visa}
				onclick={() => onchange({ ...filters, visa: !filters.visa })}
			>
				<span
					class="grid size-3.5 place-items-center rounded-[3px] border transition-colors {filters.visa
						? 'border-resolve bg-resolve text-ink'
						: 'border-line-2 group-hover:border-muted'}"
				>
					{#if filters.visa}<Check size={10} strokeWidth={3} />{/if}
				</span>
				Sponsors visa
			</button>
			<label class="flex items-center gap-1.5 text-muted" title="Hide roles asking for more years than this">
				<span class="text-[11px]">Max yrs</span>
				<input
					type="number"
					min="0"
					max="20"
					placeholder="any"
					class="num w-12 [appearance:textfield] rounded border border-line bg-ink-2 px-1.5 py-0.5 text-right text-[11px] text-paper [&::-webkit-inner-spin-button]:appearance-none"
					value={filters.years_max ?? ''}
					onchange={(e) => onchange({ ...filters, years_max: e.currentTarget.value === '' ? null : Number(e.currentTarget.value) })}
				/>
			</label>
		</div>
	</section>

	{#each groups as g (g.key)}
		{@const list = rows(g)}
		{@const isOpen = open[g.key] ?? true}
		{@const total = facets?.[g.facet]?.length ?? 0}
		<section class="border-b border-line px-3 py-2">
			<button
				class="flex w-full items-center justify-between py-1 text-[11px] font-medium text-dim hover:text-muted"
				aria-expanded={isOpen}
				onclick={() => (open[g.key] = !isOpen)}
			>
				<span>
					{g.title}
					{#if filters[g.key].length}<span class="ml-1 text-resolve">· {filters[g.key].length}</span>{/if}
				</span>
				<ChevronDown size={13} class="transition-transform duration-200 {isOpen ? '' : '-rotate-90'}" />
			</button>
			{#if isOpen}
				{#if g.search}
					<input
						class="mt-1 mb-1.5 w-full rounded-md border border-line bg-ink-2/80 px-2 py-1 text-[12px] placeholder:text-dim"
						placeholder="Filter {g.title.toLowerCase()}…"
						bind:value={needle[g.key]}
					/>
				{/if}
				<ul>
					{#each list as [v, n] (v)}
						{@const on = filters[g.key].includes(v)}
						<li>
							<button
								class="group flex w-full items-center gap-2 rounded px-1 py-[3px] text-left transition-colors duration-150 hover:bg-white/[0.04] {on
									? 'text-paper'
									: n
										? 'text-muted'
										: 'text-dim'}"
								onclick={() => toggle(g.key, v)}
								aria-pressed={on}
							>
								<span
									class="grid size-3.5 shrink-0 place-items-center rounded-[3px] border transition-colors {on
										? 'border-resolve bg-resolve text-ink'
										: 'border-line-2 group-hover:border-muted'}"
								>
									{#if on}<Check size={10} strokeWidth={3} />{/if}
								</span>
								<span class="truncate">{name(g, v)}</span>
								<span class="num ml-auto text-[11px] text-dim">{k(n)}</span>
							</button>
						</li>
					{/each}
				</ul>
				{#if !needle[g.key] && total > g.show}
					<button class="mt-0.5 px-1 text-[11px] text-dim hover:text-muted" onclick={() => (expanded[g.key] = !expanded[g.key])}>
						{expanded[g.key] ? 'Show fewer' : `Show all ${total}`}
					</button>
				{/if}
			{/if}
		</section>
	{/each}
</nav>
