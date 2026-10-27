import { useEffect, useState } from 'react'
import { api, enc } from '../api.js'
import {
  Async, ConfirmDialog, EntityLink, ErrorBox, MultiPicker, Picker, Table, invalidatePickers, useApi, useToast,
} from '../components/ui.jsx'
import { Pager } from './Researchers.jsx'

// Field definitions drive both the create and the edit form.
// type: text | number | textarea | picker | multi ; createOnly: only editable when creating
const ENTITIES = {
  researchers: {
    title: 'Researchers', singular: 'researcher', idKey: 'researcherId', link: 'Researcher',
    fields: [
      { key: 'researcherId', label: 'Researcher ID (blank = next free ID)', createOnly: true, optional: true },
      { key: 'name', label: 'Name', required: true },
      { key: 'email', label: 'E-mail', required: true, inputType: 'email' },
      { key: 'specialization', label: 'Specialization', required: true },
      { key: 'experienceYears', label: 'Experience (years)', type: 'number', required: true, min: 0, max: 70 },
      { key: 'institutionId', label: 'Institution', type: 'picker', kind: 'institutions', optional: true },
      { key: 'departmentId', label: 'Department', type: 'picker', kind: 'departments', optional: true, dependsOn: 'institutionId' },
      { key: 'role', label: 'Role at institution', optional: true },
    ],
    columns: ['researcherId', 'name', 'specialization', 'institution', 'paperCount'],
    toForm: (d) => ({ ...d.researcher }),
  },
  papers: {
    title: 'Papers', singular: 'paper', idKey: 'paperId', link: 'Paper',
    fields: [
      { key: 'paperId', label: 'Paper ID (blank = next free ID)', createOnly: true, optional: true },
      { key: 'title', label: 'Title', required: true },
      { key: 'publicationYear', label: 'Publication year', type: 'number', required: true, min: 1900, max: 2100 },
      { key: 'doi', label: 'DOI (e.g. 10.5555/acn.2026.x)', optional: true, clearable: true },
      { key: 'abstract', label: 'Abstract', type: 'textarea', optional: true },
      { key: 'authorIds', label: 'Authors (in order of selection)', type: 'multi', kind: 'researchers', required: true },
      { key: 'topicIds', label: 'Topics', type: 'multi', kind: 'topics' },
      { key: 'conferenceId', label: 'Presented at conference', type: 'picker', kind: 'conferences', optional: true, clearable: true },
      { key: 'journalId', label: 'Published in journal', type: 'picker', kind: 'journals', optional: true, clearable: true },
      { key: 'citedPaperIds', label: 'Cites these papers', type: 'multi', kind: 'papers' },
    ],
    columns: ['paperId', 'title', 'publicationYear', 'citationCount'],
    toForm: (d) => ({
      ...d.paper,
      authorIds: d.paper.authors.map((a) => a.researcherId),
      topicIds: d.paper.topics.map((t) => t.topicId),
      conferenceId: d.paper.conference?.conferenceId || '',
      journalId: d.paper.journal?.journalId || '',
      citedPaperIds: d.references.map((r) => r.paperId),
    }),
  },
  institutions: {
    title: 'Institutions', singular: 'institution', idKey: 'institutionId', link: 'Institution',
    fields: [
      { key: 'institutionId', label: 'Institution ID (blank = next free ID)', createOnly: true, optional: true },
      { key: 'name', label: 'Name', required: true },
      { key: 'location', label: 'Location', required: true },
      { key: 'type', label: 'Type (e.g. Public Institute)', required: true },
    ],
    columns: ['institutionId', 'name', 'location', 'researcherCount'],
    toForm: (d) => ({ ...d.institution }),
  },
  departments: {
    title: 'Departments', singular: 'department', idKey: 'departmentId', link: 'Department',
    fields: [
      { key: 'departmentId', label: 'Department ID (e.g. VIT-SMEC)', createOnly: true, optional: true },
      { key: 'name', label: 'Name', required: true },
      { key: 'institutionId', label: 'Institution', type: 'picker', kind: 'institutions', required: true, createOnly: true },
    ],
    columns: ['departmentId', 'name', 'institution', 'researcherCount'],
    toForm: (d) => ({ ...d.department }),
  },
  topics: {
    title: 'Topics', singular: 'topic', idKey: 'topicId', link: 'Topic',
    fields: [
      { key: 'topicId', label: 'Topic ID (blank = next free ID)', createOnly: true, optional: true },
      { key: 'name', label: 'Name', required: true },
      { key: 'description', label: 'Description', type: 'textarea', optional: true },
    ],
    columns: ['topicId', 'name', 'paperCount'],
    toForm: (d) => ({ ...d.topic }),
  },
  conferences: {
    title: 'Conferences', singular: 'conference', idKey: 'conferenceId', link: 'Conference',
    fields: [
      { key: 'conferenceId', label: 'Conference ID (blank = next free ID)', createOnly: true, optional: true },
      { key: 'name', label: 'Name', required: true },
      { key: 'year', label: 'Year', type: 'number', required: true, min: 1900, max: 2100 },
      { key: 'location', label: 'Location', required: true },
    ],
    columns: ['conferenceId', 'name', 'year', 'location', 'paperCount'],
    toForm: (d) => ({ ...d.venue }),
  },
  journals: {
    title: 'Journals', singular: 'journal', idKey: 'journalId', link: 'Journal',
    fields: [
      { key: 'journalId', label: 'Journal ID (blank = next free ID)', createOnly: true, optional: true },
      { key: 'name', label: 'Name', required: true },
      { key: 'publisher', label: 'Publisher', required: true },
      { key: 'field', label: 'Field', optional: true },
    ],
    columns: ['journalId', 'name', 'publisher', 'paperCount'],
    toForm: (d) => ({ ...d.venue }),
  },
}

function buildPayload(cfg, form, mode) {
  const out = {}
  cfg.fields.forEach((f) => {
    if (mode === 'edit' && f.createOnly) return
    let v = form[f.key]
    if (f.type === 'number') v = v === '' || v === undefined || v === null ? undefined : Number(v)
    if (f.type === 'multi') v = v || []
    if (typeof v === 'string') v = v.trim()
    if (v === '' || v === undefined) {
      // In edit mode an emptied clearable field means "remove the link / value".
      v = mode === 'edit' && f.clearable ? '' : undefined
    }
    if (v !== undefined) out[f.key] = v
  })
  return out
}

function EntityForm({ cfg, mode, initial, onSaved, onCancel }) {
  const [form, setForm] = useState(initial)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v, ...(k === 'institutionId' ? { departmentId: '' } : {}) }))

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const payload = buildPayload(cfg, form, mode)
      const res =
        mode === 'create'
          ? await api.post(`/api/${cfg.key}`, payload)
          : await api.put(`/api/${cfg.key}/${enc(initial[cfg.idKey])}`, payload)
      invalidatePickers()
      onSaved(res, mode)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="panel entity-form" onSubmit={submit} noValidate={false}>
      <h2>{mode === 'create' ? `New ${cfg.singular}` : `Edit ${cfg.singular} ${initial[cfg.idKey]}`}</h2>
      <div className="form-grid">
        {cfg.fields.map((f) => {
          if (mode === 'edit' && f.createOnly) return null
          const value = form[f.key] ?? (f.type === 'multi' ? [] : '')
          if (f.type === 'picker') {
            return (
              <Picker
                key={f.key + (f.dependsOn ? form[f.dependsOn] : '')}
                kind={f.kind}
                label={f.label + (f.required ? ' *' : '')}
                value={value}
                onChange={(v) => set(f.key, v)}
                placeholder={f.required ? 'Choose…' : 'None'}
                params={f.dependsOn && form[f.dependsOn] ? { institutionId: form[f.dependsOn] } : undefined}
                id={`f-${cfg.key}-${f.key}`}
              />
            )
          }
          if (f.type === 'multi') {
            return (
              <div className="span-2" key={f.key}>
                <MultiPicker kind={f.kind} label={f.label + (f.required ? ' *' : '')} values={value} onChange={(v) => set(f.key, v)} />
              </div>
            )
          }
          const common = {
            id: `f-${cfg.key}-${f.key}`,
            value,
            required: !!f.required,
            onChange: (e) => set(f.key, e.target.value),
          }
          return (
            <label key={f.key} className={`field ${f.type === 'textarea' ? 'span-2' : ''}`} htmlFor={common.id}>
              <span className="field-label">{f.label}{f.required ? ' *' : ''}</span>
              {f.type === 'textarea' ? (
                <textarea rows={3} maxLength={5000} {...common} />
              ) : (
                <input type={f.type === 'number' ? 'number' : f.inputType || 'text'} min={f.min} max={f.max} {...common} />
              )}
            </label>
          )
        })}
      </div>
      <ErrorBox error={error} />
      <div className="button-row">
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? 'Saving…' : mode === 'create' ? `Create ${cfg.singular}` : 'Save changes'}
        </button>
        <button type="button" className="btn" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
      </div>
    </form>
  )
}

function EntityManager({ entityKey, toast }) {
  const cfg = { ...ENTITIES[entityKey], key: entityKey }
  const [q, setQ] = useState('')
  const [page, setPage] = useState(0)
  const [editor, setEditor] = useState(null) // {mode, initial}
  const [pendingDelete, setPendingDelete] = useState(null) // {id, force, message}
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState(null)
  const pageSize = 12
  useEffect(() => setPage(0), [q])
  const list = useApi(() => api.get(`/api/${entityKey}`, { q, skip: page * pageSize, limit: pageSize }), [entityKey, q, page])

  const startEdit = async (id) => {
    try {
      const detail = await api.get(`/api/${entityKey}/${enc(id)}`)
      setEditor({ mode: 'edit', initial: cfg.toForm(detail) })
    } catch (e) {
      toast(e.message, 'error')
    }
  }

  const doDelete = async () => {
    setDeleting(true)
    setDeleteError(null)
    try {
      const res = await api.del(`/api/${entityKey}/${enc(pendingDelete.id)}`, pendingDelete.force ? { force: true } : undefined)
      invalidatePickers()
      setPendingDelete(null)
      const extra = res.relationshipsRemoved !== undefined ? ` (${res.relationshipsRemoved} relationships removed)` : ''
      toast(`Deleted ${cfg.singular} ${res.id}${extra}.`)
      list.reload()
    } catch (e) {
      if (e.status === 409 && e.details?.requiresForce) {
        setPendingDelete({ ...pendingDelete, force: true, message: e.message })
      } else {
        setDeleteError(e)
      }
    } finally {
      setDeleting(false)
    }
  }

  const columns = cfg.columns.map((k, i) => ({
    key: k,
    title: k,
    num: typeof list.data?.items?.[0]?.[k] === 'number',
    render: i === 1 ? (r) => <EntityLink type={cfg.link} id={r[cfg.idKey]}>{r[k]}</EntityLink> : undefined,
  }))
  columns.push({
    key: '_actions',
    title: 'Actions',
    render: (r) => (
      <span className="button-row">
        <button className="btn btn-small" onClick={() => startEdit(r[cfg.idKey])}>Edit</button>
        <button className="btn btn-small btn-danger-quiet" onClick={() => { setDeleteError(null); setPendingDelete({ id: r[cfg.idKey], force: false }) }}>
          Delete
        </button>
      </span>
    ),
  })

  return (
    <>
      {editor ? (
        <EntityForm
          cfg={cfg}
          mode={editor.mode}
          initial={editor.initial}
          onCancel={() => setEditor(null)}
          onSaved={(res, mode) => {
            setEditor(null)
            toast(mode === 'create' ? `Created ${cfg.singular}.` : 'Saved changes.')
            list.reload()
          }}
        />
      ) : (
        <div className="filters">
          <label className="field grow">
            <span className="field-label">Search {cfg.title.toLowerCase()}</span>
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)} />
          </label>
          <button className="btn btn-primary" onClick={() => setEditor({ mode: 'create', initial: {} })}>
            New {cfg.singular}
          </button>
        </div>
      )}
      <Async state={list}>
        {(d) => (
          <>
            <Table rows={d.items} columns={columns} rowKey={(r) => r[cfg.idKey]} empty={`No ${cfg.title.toLowerCase()} match.`} />
            <Pager total={d.total} page={page} pageSize={pageSize} onPage={setPage} />
          </>
        )}
      </Async>
      <ConfirmDialog
        open={!!pendingDelete}
        title={`Delete ${cfg.singular} ${pendingDelete?.id || ''}?`}
        confirmLabel={pendingDelete?.force ? 'Detach and delete' : 'Delete'}
        busy={deleting}
        onCancel={() => setPendingDelete(null)}
        onConfirm={doDelete}
      >
        {pendingDelete?.message ? <p>{pendingDelete.message}</p> : <DeletePolicy entity={entityKey} />}
        <ErrorBox error={deleteError} />
      </ConfirmDialog>
    </>
  )
}

function DeletePolicy({ entity }) {
  const text = {
    researchers: 'Their authorship, affiliation and collaboration relationships are removed too. Blocked if they are the only author of a paper.',
    papers: 'Its authorship, topic, venue and citation relationships are removed, and co-authorship collaborations are recalculated.',
    institutions: 'Blocked while researchers work there. Its departments are deleted with it.',
    departments: 'Blocked while researchers belong to it.',
    topics: 'Blocked if a paper would be left without any topic.',
    conferences: 'Papers presented there keep existing but lose the link to this conference.',
    journals: 'Papers published there keep existing but lose the link to this journal.',
  }[entity]
  return <p>{text} This cannot be undone.</p>
}

function Collaborations({ toast }) {
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const [since, setSince] = useState('')
  const [error, setError] = useState(null)
  const submit = async (remove) => {
    setError(null)
    try {
      if (remove) {
        await api.del(`/api/collaborations/${enc(a)}/${enc(b)}`)
        toast('Collaboration removed.')
      } else {
        await api.post('/api/collaborations', { researcherA: a, researcherB: b, since: since ? Number(since) : null })
        toast('Collaboration declared.')
      }
    } catch (e) {
      setError(e)
    }
  }
  return (
    <section className="panel">
      <h2>Declared collaborations</h2>
      <p className="muted small">
        Collaborations are normally derived from co-authored papers. Use this to record a collaboration without a joint paper. A researcher
        cannot collaborate with themselves, and each pair is stored once.
      </p>
      <div className="filters">
        <Picker kind="researchers" label="Researcher A" value={a} onChange={setA} id="col-a" />
        <Picker kind="researchers" label="Researcher B" value={b} onChange={setB} id="col-b" />
        <label className="field">
          <span className="field-label">Since (year)</span>
          <input type="number" min="1900" max="2100" value={since} onChange={(e) => setSince(e.target.value)} />
        </label>
        <button className="btn btn-primary" disabled={!a || !b} onClick={() => submit(false)}>Declare</button>
        <button className="btn" disabled={!a || !b} onClick={() => submit(true)}>Remove</button>
      </div>
      <ErrorBox error={error} />
    </section>
  )
}

export default function Manage() {
  const [entity, setEntity] = useState('researchers')
  const [toastNode, toast] = useToast()
  return (
    <div className="page">
      <header className="page-head">
        <h1>Manage data</h1>
        <p className="lede">Create, edit and delete records. Every change is validated by the API and written to Neo4j in a single transaction.</p>
      </header>
      <div className="tabs" role="tablist">
        {[...Object.entries(ENTITIES).map(([k, v]) => [k, v.title]), ['collaborations', 'Collaborations']].map(([k, title]) => (
          <button key={k} role="tab" aria-selected={entity === k} className={entity === k ? 'tab active' : 'tab'} onClick={() => setEntity(k)}>
            {title}
          </button>
        ))}
      </div>
      {entity === 'collaborations' ? <Collaborations toast={toast} /> : <EntityManager key={entity} entityKey={entity} toast={toast} />}
      {toastNode}
    </div>
  )
}
