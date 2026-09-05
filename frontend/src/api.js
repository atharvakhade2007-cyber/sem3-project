// API calls to Django backend (same origin, /api/ prefix)
// Routed through apiClient.js which injects the JWT Bearer token and
// auto-refreshes on 401. No CORS or proxy needed when served from Django.

import { apiJson } from './apiClient';

function apiCall(endpoint, method = 'GET', body = null) {
  return apiJson(`/api${endpoint}`, {
    method,
    body: body === null ? undefined : JSON.stringify(body),
  });
}

function apiCallV2(endpoint, method = 'GET', body = null) {
  return apiJson(`/api/v2${endpoint}`, {
    method,
    body: body === null ? undefined : JSON.stringify(body),
  });
}

// ─── Auth APIs ────────────────────────────────────

export async function login(usernameOrEmail, password, rememberMe = false) {
  return apiCall('/auth/login/', 'POST', {
    username_or_email: usernameOrEmail,
    password,
    remember_me: rememberMe,
  });
}

export async function signup(username, email, password) {
  return apiCall('/auth/signup/', 'POST', { username, email, password });
}

export async function logout() {
  return apiCall('/auth/logout/', 'POST');
}

export async function fetchProfile() {
  return apiCall('/user/profile/', 'GET');
}

export async function updateProfile(payload) {
  return apiCall('/user/profile/update/', 'PATCH', payload);
}

export async function changePassword(oldPassword, newPassword, confirmPassword) {
  return apiCall('/user/change-password/', 'POST', {
    old_password: oldPassword,
    new_password: newPassword,
    confirm_password: confirmPassword,
  });
}

export async function requestPasswordReset(email) {
  return apiCall('/auth/password-reset/', 'POST', { email });
}

export async function confirmPasswordReset(uid, token, newPassword) {
  return apiCall('/auth/password-reset-confirm/', 'POST', {
    uid,
    token,
    new_password: newPassword,
  });
}

// ─── Document APIs (pages legacy) ─────────────────

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append('file', file);
  return apiJson('/api/documents/upload/', { method: 'POST', body: formData });
}

export async function generateSummary(docId, apiKey = null) {
  return apiCall(`/documents/${docId}/summary/`, 'POST', { api_key: apiKey });
}

export async function generateFlashcards(docId, apiKey = null) {
  return apiCall(`/documents/${docId}/flashcards/`, 'POST', { api_key: apiKey });
}

// ─── Adaptive Test APIs (pages legacy) ────────────

export async function generateQuestionBank(docId, numQuestions = 20) {
  return apiCall('/test/generate-bank/', 'POST', {
    document_id: docId,
    num_questions: numQuestions,
  });
}

export async function startTest(docId) {
  return apiCall('/test/start/', 'POST', { document_id: docId });
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
  return apiCall('/test/complete/', 'POST', { session_id: sessionId });
}

// ─── Daily Quiz APIs (v2 — study_core) ────────────

export async function fetchDailyQuiz() {
  return apiCallV2('/daily-quiz/today/');
}

export async function submitDailyQuiz(answers, totalTimeSec) {
  return apiCallV2('/daily-quiz/submit/', 'POST', {
    answers,
    total_time_sec: totalTimeSec,
  });
}

export async function fetchDailyLeaderboard(tab = 'score') {
  return apiCallV2(`/daily-quiz/leaderboard/?tab=${tab}`);
}

// ─── Social APIs (friends & requests) ─────────────

export async function fetchFriends() {
  return apiCall('/social/friends/');
}

export async function fetchFriendRequests() {
  return apiCall('/social/requests/');
}

export async function fetchPendingCount() {
  return apiCall('/social/pending-count/');
}

export async function sendFriendRequest(userId) {
  return apiCall('/social/request/send/', 'POST', { user_id: userId });
}

export async function respondFriendRequest(requestId, action) {
  return apiCall(`/social/request/${requestId}/respond/`, 'POST', { action });
}

export async function cancelFriendRequest(requestId) {
  return apiCall(`/social/request/${requestId}/cancel/`, 'POST');
}

export async function manageFriend(userId, action) {
  return apiCall('/social/friends/manage/', 'POST', { user_id: userId, action });
}

export async function searchUsers(query) {
  return apiCall(`/social/users/search/?q=${encodeURIComponent(query)}`);
}

// ─── Duel (QuizChallenge) APIs ─────────────────────

export async function fetchMyCompletedSessions() {
  return apiCall('/challenges/sessions/');
}

export async function createChallenge(sessionId, challengedUserId) {
  return apiCall('/challenges/create/', 'POST', {
    session_id: sessionId,
    challenged_user_id: challengedUserId,
  });
}

export async function fetchChallenges() {
  return apiCall('/challenges/');
}

export async function fetchChallengeQuestions(challengeId) {
  return apiCall(`/challenges/${challengeId}/questions/`);
}

export async function submitChallenge(challengeId, answers) {
  return apiCall(`/challenges/${challengeId}/submit/`, 'POST', { answers });
}

// ─── Friend-scoped Leaderboard ─────────────────────

export async function fetchFriendLeaderboard(metric = 'all_time') {
  return apiCall(`/leaderboard/friends/?metric=${metric}`);
}