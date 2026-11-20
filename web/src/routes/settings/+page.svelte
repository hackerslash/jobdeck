<script lang="ts">
	import { ArrowLeft, FileUp, Trash2 } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { api, k, label, type Resume } from '#lib/api.ts';

	let resumes = $state<Resume[]>([]);
	let loaded = $state(false);
	let blocked = $state(false);
	let name = $state('');
	let file = $state<File | null>(null);
	let busy = $state(false);
	let error = $state('');
	let fileInput: HTMLInputElement | undefined = $state();

	async function refresh() {
		try {
			resumes = await api.resumes();
		} catch (e: any) {
			blocked = e.status === 403;
			error = blocked ? '' : e.message;
		}
		loaded = true;
	}

	async function upload(e: SubmitEvent) {
		e.preventDefault();
		if (!file) return;
		busy = true;
		error = '';
		try {
			await api.addResume(file, name || file.name.replace(/\.[^.]+$/, ''));
			name = '';
			file = null;
			if (fileInput) fileInput.value = '';
			await refresh();
		} catch (err: any) {
			error = err.message;
		} finally {
			busy = false;
		}
	}

	async function remove(r: Resume) {
		if (!confirm(`Delete “${r.name}”? Its match scores go with it.`)) return;
		await api.deleteResume(r.id);
		await refresh();
	}

	onMount(refresh);
</script>

<svelte:head><title>Resumes · jobdeck</title></svelte:head>

<div class="mx-auto max-w-3xl px-5 py-8">
	<a href="/" class="inline-flex items-center gap-1.5 text-muted hover:text-paper"><ArrowLeft size={14} /> Jobs</a>
	<h1 class="mt-5 text-[1.375rem] font-semibold tracking-[-0.02em]">Resumes</h1>
	<p class="mt-1.5 max-w-[60ch] text-muted">
		Add one or more versions. Each is parsed and embedded on this machine; every job shows its best match and which version earned it.
		Nothing leaves your computer.
	</p>

	{#if blocked}
		<p class="mt-8 rounded-xl border border-line p-5 text-muted">Resumes can only be managed on the machine running jobdeck (open it at localhost:8700).</p>
	{:else}
		<form class="glass mt-6 grid gap-3 rounded-2xl p-5 sm:grid-cols-[1fr_1fr_auto] sm:items-end" onsubmit={upload}>
			<label class="grid gap-1.5">
				<span class="text-[11px] font-medium text-dim">Version name</span>
				<input bind:value={name} placeholder="e.g. Backend, Go-focused" class="rounded-lg border border-line bg-ink-2/80 px-3 py-2 placeholder:text-dim" />
			</label>
			<label class="grid gap-1.5">
				<span class="text-[11px] font-medium text-dim">File (PDF, DOCX, TXT)</span>
				<span class="relative flex items-center gap-2 rounded-lg border border-dashed border-line-2 bg-ink-2/50 px-3 py-2 text-muted hover:border-muted">
					<FileUp size={14} class="shrink-0" />
					<span class="truncate">{file ? file.name : 'Choose a file'}</span>
					<input
						bind:this={fileInput}
						type="file"
						accept=".pdf,.docx,.txt,.md"
						class="absolute inset-0 cursor-pointer opacity-0"
						onchange={(e) => (file = e.currentTarget.files?.[0] ?? null)}
					/>
				</span>
			</label>
			<button
				type="submit"
				disabled={!file || busy}
				class="rounded-lg bg-resolve px-4 py-2 font-medium text-ink transition-[filter,opacity] hover:brightness-110 disabled:opacity-40"
			>
				{busy ? 'Parsing & scoring…' : 'Add version'}
			</button>
			{#if error}<p class="text-conflict sm:col-span-3">{error}</p>{/if}
		</form>

		<ul class="mt-6 space-y-3">
			{#each resumes as r (r.id)}
				<li class="rounded-2xl border border-line bg-ink-2/40 p-5">
					<div class="flex items-start justify-between gap-4">
						<div class="min-w-0">
							<h2 class="font-medium text-paper">{r.name}</h2>
							<p class="mt-0.5 text-[12px] text-dim">
								{r.filename} · added {new Date(r.created).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })} · best match for
								<span class="num text-muted">{k(r.best_for)}</span> jobs
							</p>
						</div>
						<button class="rounded-md p-1.5 text-dim hover:bg-conflict/10 hover:text-conflict" onclick={() => remove(r)} aria-label="Delete {r.name}">
							<Trash2 size={15} />
						</button>
					</div>
					<dl class="mt-4 grid grid-cols-[96px_1fr] gap-x-4 gap-y-1.5">
						<dt class="text-dim">Level</dt>
						<dd class="font-mono text-[12px]">@{r.seniority}</dd>
						<dt class="text-dim">Experience</dt>
						<dd>{r.years != null ? `${r.years} years (from dated roles)` : 'No dated roles found'}</dd>
						<dt class="text-dim">Roles</dt>
						<dd>{r.roles.map((x) => label('role', x)).join(', ') || '—'}</dd>
						<dt class="text-dim">Stack</dt>
						<dd class="flex flex-wrap gap-1.5">
							{#each r.skills as s (s)}<span class="rounded-[5px] bg-white/[0.06] px-1.5 py-0.5 font-mono text-[11px] text-paper/85">{s}</span>{:else}—{/each}
						</dd>
					</dl>
				</li>
			{:else}
				{#if loaded}
					<li class="rounded-2xl border border-dashed border-line-2 p-6 text-muted">
						No resumes yet. Add one above and the job list gains a match column and a “match” sort.
					</li>
				{/if}
			{/each}
		</ul>

		<p class="mt-8 text-[12px] leading-relaxed text-dim">
			Match = 45% meaning (local embedding, calibrated against all jobs) + 30% stack coverage + 15% level & years + 10% role family.
		</p>
	{/if}
</div>
