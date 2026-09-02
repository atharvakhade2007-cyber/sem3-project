// API calls to Django backend (same origin, /api/ prefix)
// No CORS or proxy needed when served from Django

async function apiCall(endpoint, method = 'GET', body = null) {
  const opts = {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    },
    credentials: 'same-origin',
  };

  // Get CSRF token from cookies
  const csrfToken = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];

  if (csrfToken) {
    opts.headers['X-CSRFToken'] = csrfToken;
  }

  if (body) {
    opts.body = JSON.stringify(body);
  }

  const res = await fetch(`/api${endpoint}`, opts);

  // Handle non-JSON responses
  const contentType = res.headers.get('content-type');
  if (!contentType || !contentType.includes('application/json')) {
    const text = await res.text();
    throw new Error(`Expected JSON but got: ${text.substring(0, 200)}...`);
  }

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.error || `API error: ${res.status}`);
  }

  return data;
}

// ─── Document APIs ─────────────────────────────

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append('file', file);

  const csrfToken = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];

  const headers = {};
  if (csrfToken) {
    headers['X-CSRFToken'] = csrfToken;
  }

  const res = await fetch('/api/documents/upload/', {
    method: 'POST',
    headers,
    body: formData,
    credentials: 'same-origin',
  });

  const contentType = res.headers.get('content-type');
  if (!contentType || !contentType.includes('application/json')) {
    const text = await res.text();
    throw new Error(`Expected JSON but got: ${text.substring(0, 200)}...`);
  }

  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Upload failed');
  return data;
}

export async function generateSummary(docId, apiKey = null) {
  return apiCall(`/documents/${docId}/summary/`, 'POST', { api_key: apiKey });
}

export async function generateFlashcards(docId, apiKey = null) {
  return apiCall(`/documents/${docId}/flashcards/`, 'POST', { api_key: apiKey });
}

// ─── Adaptive Test APIs ────────────────────────

export async function generateQuestionBank(docId, numQuestions = 20) {
  return apiCall('/test/generate-bank/', 'POST', {
    document_id: docId,
    num_questions: numQuestions,
  });
}

export async function startTest(docId) {
  return apiCall('/test/start/', 'POST', {
    document_id: docId,
  });
}

export async function submitAnswer(sessionId, questionId, selectedIndex, timeTakenSec) {
  return apiCall('/test/submit-answer/', 'POST', {
    session_id: sessionId,
    question_id: questionId,
    selected_index: selectedIndex,
    time_taken_sec: timeTakenSec,
  });
}

export async function completeTest(sessionId) {
  return apiCall('/test/complete/', 'POST', {
    session_id: sessionId,
  });
}

// ─── Daily Quiz APIs (v2 — study_core) ───────────

async function apiCallV2(endpoint, method = 'GET', body = null) {
  const opts = {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    },
    credentials: 'same-origin',
  };

  const csrfToken = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];

  if (csrfToken) {
    opts.headers['X-CSRFToken'] = csrfToken;
  }

  if (body) {
    opts.body = JSON.stringify(body);
  }

  const res = await fetch(`/api/v2${endpoint}`, opts);

  const contentType = res.headers.get('content-type');
  if (!contentType || !contentType.includes('application/json')) {
    const text = await res.text();
    throw new Error(`Expected JSON but got: ${text.substring(0, 200)}...`);
  }

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.error || `API error: ${res.status}`);
  }

  return data;
}

export async function fetchDailyQuiz() {
  return apiCallV2('/daily-quiz/today/');
}

export async function submitDailyQuiz(answers, totalTimeSec) {
  return apiCallV2('/daily-quiz/submit/', 'POST', {
    answers,
    total_time_sec: totalTimeSec,
  });
}

export async function fetchDailyLeaderboard() {
  return apiCallV2('/daily-quiz/leaderboard/');
}
