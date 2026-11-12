import { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  ArrowDownRight, ArrowRight, ArrowUpRight, BookOpen, ChevronRight, Clock3,
  FileText, LayoutDashboard, Lightbulb, Plus, Search, Send, Sparkles, UserRound, X,
} from 'lucide-react'
import './styles.css'

const pages = [
  ['dashboard', 'Dashboard', LayoutDashboard],
  ['notes', 'My Notes', FileText],
  ['chat', 'AI Chat', Sparkles],
  ['recommendations', 'Recommendations', Lightbulb],
  ['users', 'Users', UserRound],
]
const prompts = ['Explain Kubernetes pods simply.', 'What is Docker?', 'Explain machine learning with an example.']
const blank = { title: '', subject: '', content: '' }
const getPage = () => pages.find(([key]) => '#' + key === location.hash)?.[0] || 'dashboard'

function stored(key) {
  try { return JSON.parse(localStorage.getItem(key)) || [] } catch { return [] }
}

async function api(path, { method = 'GET', body, signal } = {}) {
  const headers = {}
  const token = sessionStorage.getItem('studybuddy-token')
  if (body) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = 'Bearer ' + token
  const response = await fetch('/api' + path, {
    method, signal,
    headers,
    ...(body && { body: JSON.stringify(body) }),
  })
  if (response.status === 204) return
  const data = await response.json()
  if (response.status === 401 && token) {
    sessionStorage.removeItem('studybuddy-token')
    window.dispatchEvent(new Event('studybuddy:auth-expired'))
  }
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check your input and try again.')
  return data
}

function subjectStyle(subject) {
  return ({ python: 'blue', docker: 'green', kubernetes: 'amber', ai: 'rose' })[subject.toLowerCase()] || 'green'
}

function NoteCard({ note, onOpen }) {
  return <button className="note-card text-left" onClick={() => onOpen(note)}>
    <div className="flex items-center justify-between">
      <span className={'file-icon ' + subjectStyle(note.subject)}><FileText size={18} /></span>
      <ArrowUpRight size={17} className="muted" />
    </div>
    <h3>{note.title}</h3>
    <p>{note.content}</p>
    <span className={'subject ' + subjectStyle(note.subject)}>{note.subject}</span>
  </button>
}

function NoteDialog({ note, onClose, onChange }) {
  const ref = useRef()
  const [draft, setDraft] = useState(note)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  useEffect(() => { ref.current.showModal() }, [])
  async function submit(event, remove = false) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const saved = await api(note.id ? '/notes/' + note.id : '/notes', {
        method: remove ? 'DELETE' : note.id ? 'PUT' : 'POST',
        body: remove ? undefined : { title: draft.title, subject: draft.subject, content: draft.content },
      })
      onChange(saved, note.id)
      onClose()
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }
  return <dialog ref={ref} onCancel={event => { event.preventDefault(); if (!busy) onClose() }}>
    <form onSubmit={submit} className="grid gap-4">
      <div className="flex items-center justify-between">
        <h2>{note.id ? 'Edit note' : 'New note'}</h2>
        <button type="button" className="icon-button" aria-label="Close note" disabled={busy} onClick={onClose}><X size={20} /></button>
      </div>
      {['title', 'subject', 'content'].map((field, index) => {
        const Input = field === 'content' ? 'textarea' : 'input'
        return <label key={field} className="grid gap-2 capitalize">{field}
          <Input autoFocus={index === 0} required maxLength={[120, 60, 12000][index]} value={draft[field]}
            onChange={event => setDraft({ ...draft, [field]: event.target.value })} />
        </label>
      })}
      {error && <p role="alert" className="error">{error}</p>}
      {confirmDelete && <p role="alert" className="error">Delete this note permanently?</p>}
      <div className="flex justify-between gap-3">
        {note.id && <button className="danger" type="button" disabled={busy}
          onClick={event => confirmDelete ? submit(event, true) : setConfirmDelete(true)}>
          {confirmDelete ? 'Confirm delete' : 'Delete'}
        </button>}
        <button className="primary ml-auto" disabled={busy}>Save note</button>
      </div>
    </form>
  </dialog>
}

function App() {
  const [page, setPage] = useState(getPage)
  const [authReady, setAuthReady] = useState(false)
  const [authStatus, setAuthStatus] = useState(null)
  const [currentUser, setCurrentUser] = useState(null)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [authError, setAuthError] = useState('')
  const [signingIn, setSigningIn] = useState(false)
  const [users, setUsers] = useState([])
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [usersError, setUsersError] = useState('')
  const [usersBusy, setUsersBusy] = useState(false)
  const [usersLoading, setUsersLoading] = useState(false)
  const [notes, setNotes] = useState([])
  const [recent, setRecent] = useState([])
  const [query, setQuery] = useState('')
  const [subject, setSubject] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(true)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState('')
  const [searchError, setSearchError] = useState('')
  const [editor, setEditor] = useState(null)
  const [version, setVersion] = useState(0)
  const [suggestions, setSuggestions] = useState([])
  const [suggestionError, setSuggestionError] = useState('')
  const [loadingSuggestions, setLoadingSuggestions] = useState(false)
  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState('')
  const [chatError, setChatError] = useState('')
  const [sending, setSending] = useState(false)
  const [configured, setConfigured] = useState(null)
  const chatLog = useRef()
  const activeQuery = query.trim()

  useEffect(() => {
    let active = true
    const token = sessionStorage.getItem('studybuddy-token')
    Promise.all([
      api('/auth/status').catch(error => { throw error }),
      token ? api('/auth/me').catch(() => null) : Promise.resolve(null),
    ]).then(([status, user]) => {
      if (!active) return
      setAuthStatus(status)
      setCurrentUser(user)
      if (!user) sessionStorage.removeItem('studybuddy-token')
    }).catch(error => {
      if (active) setAuthError(error.message)
    }).finally(() => {
      if (active) setAuthReady(true)
    })
    const expired = () => {
      sessionStorage.removeItem('studybuddy-token')
      setCurrentUser(null)
      setNotes([])
      setRecent([])
      setEditor(null)
      setAuthError('Your session expired. Sign in again.')
    }
    window.addEventListener('studybuddy:auth-expired', expired)
    return () => {
      active = false
      window.removeEventListener('studybuddy:auth-expired', expired)
    }
  }, [])

  useEffect(() => {
    setRecent(currentUser ? stored('studybuddy-recent:' + currentUser.id) : [])
  }, [currentUser])

  useEffect(() => {
    const change = () => setPage(getPage())
    window.addEventListener('hashchange', change)
    return () => window.removeEventListener('hashchange', change)
  }, [])

  useEffect(() => {
    if (!currentUser) { setLoading(false); return }
    const controller = new AbortController()
    api('/notes', { signal: controller.signal })
      .then(data => { setNotes(data); setError(''); setLoading(false) })
      .catch(err => { if (!controller.signal.aborted) { setError(err.message); setLoading(false) } })
    return () => controller.abort()
  }, [version, currentUser])

  useEffect(() => {
    if (!activeQuery || !currentUser) return
    const controller = new AbortController()
    const timer = setTimeout(() => {
      api('/search?' + new URLSearchParams({ q: activeQuery }), { signal: controller.signal })
        .then(data => { setResults(data); setSearchError(''); setSearching(false) })
        .catch(err => { if (!controller.signal.aborted) { setSearchError(err.message); setSearching(false) } })
    }, 140)
    return () => { clearTimeout(timer); controller.abort() }
  }, [activeQuery, version, currentUser])

  useEffect(() => {
    if (page !== 'recommendations' || !currentUser) return
    const controller = new AbortController()
    const params = new URLSearchParams()
    recent.forEach(item => params.append('subject', item.subject))
    setLoadingSuggestions(true)
    setSuggestionError('')
    api('/recommendations?' + params, { signal: controller.signal })
      .then(data => { setSuggestions(data); setLoadingSuggestions(false) })
      .catch(err => { if (!controller.signal.aborted) { setSuggestionError(err.message); setLoadingSuggestions(false) } })
    return () => controller.abort()
  }, [page, recent, currentUser])

  useEffect(() => {
    if (page === 'chat' && currentUser) api('/chat/status').then(data => setConfigured(data.configured)).catch(() => {})
  }, [page, currentUser])

  useEffect(() => {
    if (page !== 'users' || currentUser?.role !== 'admin') return
    const controller = new AbortController()
    setUsersLoading(true)
    api('/auth/users', { signal: controller.signal })
      .then(data => { setUsers(data); setUsersError(''); setUsersLoading(false) })
      .catch(err => {
        if (!controller.signal.aborted) {
          setUsersError(err.message)
          setUsersLoading(false)
        }
      })
    return () => controller.abort()
  }, [page, currentUser])

  useEffect(() => {
    if (page === 'users' && currentUser && currentUser.role !== 'admin') location.hash = 'dashboard'
  }, [page, currentUser])

  useEffect(() => {
    if (chatLog.current) chatLog.current.scrollTop = chatLog.current.scrollHeight
  }, [messages, sending, page])

  function updateRecent(items) {
    try {
      if (currentUser) localStorage.setItem('studybuddy-recent:' + currentUser.id, JSON.stringify(items))
    } catch { /* Storage may be disabled. */ }
    setRecent(items)
  }

  function noteChanged(saved, id) {
    if (id) {
      updateRecent(saved ? recent.map(item => item.id === id
        ? { id, title: saved.title, subject: saved.subject } : item)
        : recent.filter(item => item.id !== id))
    }
    setVersion(value => value + 1)
  }

  function openNote(note) {
    const updated = [{ id: note.id, title: note.title, subject: note.subject },
      ...recent.filter(item => item.id !== note.id)].slice(0, 8)
    updateRecent(updated)
    setEditor(note)
  }

  function changeSearch(value) {
    if (value.trim() !== activeQuery) {
      setSearching(Boolean(value.trim()))
      setSearchError('')
    }
    setQuery(value)
  }

  function showNotes(value = '') {
    changeSearch(value)
    setSubject('')
    location.hash = 'notes'
  }

  async function ask(text) {
    if (!text.trim() || sending) return
    const message = { role: 'user', text: text.trim() }
    const conversation = [...messages, message]
    setMessages(conversation)
    setQuestion('')
    setChatError('')
    setSending(true)
    try {
      const { reply } = await api('/chat', {
        method: 'POST',
        body: { messages: conversation.slice(-11).map(item => ({ ...item, text: item.text.slice(0, 20000) })) },
      })
      setMessages([...conversation, { role: 'model', text: reply }])
      setConfigured(true)
    } catch (err) {
      setChatError(err.message)
      setMessages(messages)
      setQuestion(message.text)
    } finally {
      setSending(false)
    }
  }

  async function signIn(event) {
    event.preventDefault()
    setSigningIn(true)
    setAuthError('')
    try {
      const result = await api('/auth/login', { method: 'POST', body: { username, password } })
      sessionStorage.setItem('studybuddy-token', result.token)
      setCurrentUser(result.user)
      setPassword('')
    } catch (err) {
      setAuthError(err.message)
    } finally {
      setSigningIn(false)
    }
  }

  async function addUser(event) {
    event.preventDefault()
    setUsersBusy(true)
    setUsersError('')
    try {
      const created = await api('/auth/users', {
        method: 'POST',
        body: { username: newUsername, password: newPassword },
      })
      setUsers(items => [...items, created].sort((a, b) => a.username.localeCompare(b.username)))
      setNewUsername('')
      setNewPassword('')
    } catch (err) {
      setUsersError(err.message)
    } finally {
      setUsersBusy(false)
    }
  }

  function signOut() {
    sessionStorage.removeItem('studybuddy-token')
    setCurrentUser(null)
    setMessages([])
    setNotes([])
    setRecent([])
    setEditor(null)
    setSuggestions([])
    setQuery('')
  }

  const visible = (activeQuery ? results : notes).filter(note => !subject || note.subject === subject)
  const viewedNotes = recent.map(item => notes.find(note => note.id === item.id)).filter(Boolean).slice(0, 3)
  const title = pages.find(([key]) => key === page)[1]

  if (!authReady) return <main className="login-shell"><p role="status">Connecting to StudyBuddy…</p></main>
  if (!currentUser) return <main className="login-shell">
    <section className="login-card">
      <a className="brand login-brand" href="#dashboard"><span><BookOpen size={20} /></span>StudyBuddy <small>AI</small></a>
      <h1>Welcome back</h1>
      <p className="login-copy">Sign in to your private study workspace.</p>
      {authStatus && !authStatus.configured && <p className="setup-message" role="status">
        {authStatus.bootstrap_required
          ? 'No accounts exist yet. Configure AUTH_ADMIN_USERNAME and AUTH_ADMIN_PASSWORD (at least 12 characters) for the auth service, then restart it.'
          : 'Authentication is not configured. Set AUTH_TOKEN_SECRET to a private value of at least 32 characters and configure an admin account on the backend.'}
      </p>}
      {authError && <p role="alert" className="error">{authError}</p>}
      <form className="grid gap-4" onSubmit={signIn}>
        <label className="grid gap-2">Username
          <input required autoComplete="username" value={username} onChange={event => setUsername(event.target.value)} />
        </label>
        <label className="grid gap-2">Password
          <input required type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} />
        </label>
        <button className="primary" disabled={signingIn || authStatus?.configured === false}>
          {signingIn ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </section>
  </main>

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#dashboard"><span><BookOpen size={20} /></span>StudyBuddy <small>AI</small></a>
      <nav aria-label="Main navigation">
        {pages.filter(([key]) => key !== 'users' || currentUser.role === 'admin').map(([key, label, Icon]) => <a key={key} href={'#' + key} aria-current={key === page ? 'page' : undefined}
          onClick={() => { if (key === 'notes') { changeSearch(''); setSubject('') } }}>
          <Icon size={18} />{label}
        </a>)}
      </nav>
      <div className="sidebar-bottom account-info">
        <BookOpen size={16} /><span>{currentUser.username}</span>
        <button className="text-button" onClick={signOut}>Sign out</button>
      </div>
    </aside>

    <div className="main-shell">
      <header className="topbar">
        <div className="breadcrumb">Workspace <ChevronRight size={14} /> <strong>{title}</strong></div>
        <div className="global-search">
          <Search size={17} />
          <input type="search" aria-label="Search notes" placeholder="Search notes…" maxLength={120}
            value={query} onChange={event => showNotes(event.target.value)}
            onKeyDown={event => { if (event.key === 'Enter') showNotes(query) }} />
        </div>
      </header>
      <main className="workspace">
        {page === 'dashboard' && <>
          <div className="page-heading">
            <div><h1>Dashboard</h1><p>Pick up where you left off or start a new note.</p></div>
            <button className="primary" onClick={() => setEditor(blank)}><Plus size={17} /> New note</button>
          </div>
          <section className="chat-banner">
            <div className="banner-content">
              <span className="banner-icon"><Sparkles size={21} /></span>
              <div><h2>Stuck on a topic?</h2><p>Ask StudyBuddy to break it down with an example.</p>
                <a className="banner-link" href="#chat">Ask StudyBuddy <ArrowRight size={16} /></a></div>
            </div>
            <div className="banner-art" aria-hidden="true"><BookOpen size={144} strokeWidth={0.55} /><Sparkles size={47} strokeWidth={0.9} /></div>
          </section>
          <section className="section">
            <div className="section-heading"><h2>Saved notes</h2><button className="text-button" onClick={() => showNotes()}>View all notes <ArrowRight size={16} /></button></div>
            {error ? <p className="error" role="alert">{error}</p> : loading ? <p>Loading notes…</p> : notes.length ?
              <div className="note-grid">{notes.slice(0, 4).map(note => <NoteCard key={note.id} note={note} onOpen={openNote} />)}</div> :
              <p className="empty">Add a note to start your study library.</p>}
          </section>
          <section className="section">
            <div className="section-heading"><h2>Recently viewed</h2></div>
            {viewedNotes.length ? <div className="recent-list">{viewedNotes.map(note => <button key={note.id} onClick={() => openNote(note)}>
              <Clock3 size={17} /><span>{note.title}</span><small>{note.subject}</small><ChevronRight size={16} />
            </button>)}</div> : <div className="empty flex items-center gap-3"><Clock3 size={18} /> Notes you open will appear here.</div>}
          </section>
        </>}

        {page === 'notes' && <>
          <div className="page-heading">
            <div><h1>My Notes</h1><p>Organize what you learn by subject.</p></div>
            <button className="primary" onClick={() => setEditor(blank)}><Plus size={17} /> New note</button>
          </div>
          <div className="filters">
            <label className="flex items-center gap-2">Subject
              <select value={subject} onChange={event => setSubject(event.target.value)}>
                <option value="">All subjects</option>
                {[...new Set(notes.map(note => note.subject))].sort().map(name => <option key={name}>{name}</option>)}
              </select>
            </label>
            {activeQuery && <button className="text-button" onClick={() => changeSearch('')}>Clear search <X size={16} /></button>}
          </div>
          {(error || (activeQuery && searchError)) ? <p className="error" role="alert">{error || searchError}</p> :
            (loading || (activeQuery && searching)) ? <p role="status">Loading notes…</p> : visible.length ?
              <div className="note-grid">{visible.map(note => <NoteCard key={note.id} note={note} onOpen={openNote} />)}</div> :
              <p className="empty">{activeQuery || subject ? 'No matching notes.' : 'Add a note to start your study library.'}</p>}
        </>}

        {page === 'chat' && <>
          <div className="page-heading"><div><h1>AI Chat</h1><p>Get a simple explanation or work through a question.</p></div>
            {messages.length > 0 && <button className="secondary" disabled={sending} onClick={() => { setMessages([]); setChatError(''); setQuestion('') }}>Clear chat</button>}
          </div>
          <section className="chat-panel" aria-label="AI tutor">
            {configured === false && <p className="setup-message">Set <code>GEMINI_API_KEY</code> on the backend to enable chat. See the README for setup.</p>}
            <div className="chat-log" ref={chatLog} role="log" aria-label="Conversation">
              {messages.length === 0 && <div className="chat-start"><span className="banner-icon"><Sparkles size={21} /></span>
                <h2>What are you studying?</h2><div className="prompt-list">{prompts.map(text => <button key={text} onClick={() => ask(text)} disabled={sending || configured === false}>{text}<ArrowUpRight size={16} /></button>)}</div>
              </div>}
              {messages.map((message, index) => <div key={index} className={'message ' + message.role}>
                <strong>{message.role === 'user' ? 'You' : 'StudyBuddy'}</strong><p>{message.text}</p>
              </div>)}
              {sending && <p className="muted">StudyBuddy is thinking…</p>}
            </div>
            {chatError && <p role="alert" className="error chat-error">{chatError}</p>}
            <form className="composer" onSubmit={event => { event.preventDefault(); ask(question) }}>
              <input aria-label="Your question" placeholder="Ask a study question…" maxLength={2000} value={question} onChange={event => setQuestion(event.target.value)} disabled={sending || configured === false} />
              <button className="primary" type="submit" disabled={sending || configured === false || !question.trim()}><Send size={16} /> Send</button>
            </form>
          </section>
        </>}

        {page === 'recommendations' && <>
          <div className="page-heading"><div><h1>Recommendations</h1><p>Explore topics related to the notes you’ve opened.</p></div></div>
          {suggestionError ? <p className="error" role="alert">{suggestionError}</p> : loadingSuggestions ? <p>Loading suggestions…</p> : suggestions.length ?
            <div className="note-grid">{suggestions.map(item => <article className="note-card" key={item.topic}>
              <span className={'file-icon ' + subjectStyle(item.subject)}><Lightbulb size={18} /></span>
              <h3>{item.topic}</h3><p>{item.description}</p>
              <button className="text-button" onClick={() => { setQuestion('Explain ' + item.topic + ' with a simple example.'); location.hash = 'chat' }}>
                Ask about this <ArrowDownRight size={15} />
              </button>
            </article>)}</div> : <div className="empty">Open a note about Python, Docker, Kubernetes, or AI to get suggestions.
              <button className="text-button mt-3" onClick={() => showNotes()}>Browse notes <ArrowRight size={16} /></button>
            </div>}
        </>}

        {page === 'users' && currentUser.role === 'admin' && <>
          <div className="page-heading"><div><h1>Users</h1><p>Create accounts for your study group. Public signup is disabled.</p></div></div>
          <section className="user-management">
            <h2>Create a student account</h2>
            <form className="user-form" onSubmit={addUser}>
              <label>Username
                <input required minLength={3} maxLength={80} autoComplete="off" value={newUsername}
                  onChange={event => setNewUsername(event.target.value)} />
              </label>
              <label>Temporary password
                <input required minLength={12} maxLength={200} type="password" autoComplete="new-password"
                  value={newPassword} onChange={event => setNewPassword(event.target.value)} />
              </label>
              <button className="primary" disabled={usersBusy}>{usersBusy ? 'Creating…' : 'Create account'}</button>
            </form>
            {usersError && <p role="alert" className="error">{usersError}</p>}
            <h2 className="user-list-title">Accounts</h2>
            {usersLoading ? <p role="status">Loading accounts…</p> : users.length ? <div className="recent-list">{users.map(user => <div className="user-row" key={user.id}>
              <span>{user.username}</span><small>{user.role}</small>
            </div>)}</div> : <p className="empty">No accounts found.</p>}
          </section>
        </>}
      </main>
    </div>
    {editor && <NoteDialog note={editor} onClose={() => setEditor(null)} onChange={noteChanged} />}
  </div>
}

createRoot(document.getElementById('root')).render(<App />)
