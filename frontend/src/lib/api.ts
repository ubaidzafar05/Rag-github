const API_BASE = 'http://localhost:8000';

export async function getCurrentUser() {
  const res = await fetch(`${API_BASE}/user/me`, { credentials: 'include' });
  if (res.status === 401) return null;
  if (!res.ok) throw new Error('Failed to fetch user');
  return res.json();
}

export async function ingestRepo(repoUrl: string, docsUrl?: string) {
  const res = await fetch(`${API_BASE}/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url: repoUrl, docs_url: docsUrl || null }),
    credentials: 'include',
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Ingestion failed');
  }
  return res.json();
}

export async function ingestRepoAsync(repoUrl: string, docsUrl?: string) {
  const res = await fetch(`${API_BASE}/ingest/async`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url: repoUrl, docs_url: docsUrl || null }),
    credentials: 'include',
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Ingestion failed');
  }
  return res.json();
}

export async function getIngestStatus(jobId: string) {
  const res = await fetch(`${API_BASE}/ingest/status/${jobId}`, {
    credentials: 'include',
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to fetch ingestion status');
  }
  return res.json();
}

export async function createSession(repoUrl: string, name?: string) {
  const res = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url: repoUrl, name }),
    credentials: 'include',
  });
  if (!res.ok) throw new Error('Failed to create session');
  return res.json();
}

export async function getSessions() {
  const res = await fetch(`${API_BASE}/sessions`, { credentials: 'include' });
  if (!res.ok) throw new Error('Failed to load sessions');
  return res.json();
}

export async function getSession(sessionId: number) {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`, { credentials: 'include' });
  if (!res.ok) throw new Error('Failed to load session');
  return res.json();
}

export async function deleteSession(sessionId: number) {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (!res.ok) throw new Error('Failed to delete session');
  return res.json();
}

export async function getSessionMessages(sessionId: number) {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/messages`, { credentials: 'include' });
  if (!res.ok) throw new Error('Failed to load messages');
  return res.json();
}

export async function sendChatMessage(message: string, history: Array<{ role: string, parts: string[] }>, sessionId?: number) {
  const url = sessionId ? `${API_BASE}/chat?session_id=${sessionId}` : `${API_BASE}/chat`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
    credentials: 'include',
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Chat request failed');
  }
  return res.json();
}

export async function checkHealth() {
  const res = await fetch(`${API_BASE}/`);
  return res.ok;
}

export async function applyFix(filePath: string, content: string) {
  const res = await fetch(`${API_BASE}/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_path: filePath, content }),
    credentials: 'include',
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to apply fix');
  }
  return res.json();
}
