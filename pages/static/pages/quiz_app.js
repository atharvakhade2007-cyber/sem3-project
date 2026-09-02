(() => {
  // Helper: get CSRF token from cookies
  function getCookie(name) {
    const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return v ? v.pop() : '';
  }

  // Audio feedback via WebAudio (no external files)
  const audioCtx = typeof AudioContext !== 'undefined' ? new AudioContext() : null;
  function playTone(type = 'success') {
    if (!audioCtx) return;
    const o = audioCtx.createOscillator();
    const g = audioCtx.createGain();
    o.type = type === 'success' ? 'sine' : 'square';
    o.frequency.value = type === 'success' ? 880 : 220;
    o.connect(g);
    g.connect(audioCtx.destination);
    g.gain.setValueAtTime(0.0001, audioCtx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.1, audioCtx.currentTime + 0.02);
    o.start();
    setTimeout(() => {
      g.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.12);
      setTimeout(() => o.stop(), 200);
    }, 120);
  }

  // DOM shortcuts
  const el = id => document.getElementById(id);
  const optionsContainer = el('options');
  const nextBtn = el('nextBtn');
  const questionText = el('question-text');
  const questionXp = el('question-xp');
  const feedback = el('feedback');
  const eloPopup = el('eloPopup');
  const xpBar = el('xp-bar');
  const currentEloEl = el('current-elo');
  const eloBadge = el('elo-badge');
  const levelTitle = el('level-title');
  const streakEl = el('streak');
  const streakFlame = el('streak-flame');
  const totalXpEl = el('total-xp');
  const totalQuestionsEl = el('total-questions');

  // Session state
  let currentQuestion = null;
  let session = { correct: 0, wrong: 0, streak: 0, xp: 0, totalQuestions: 0, elo: 1250 };

  function setBadgeTitle(elo) {
    if (elo < 1000) return 'Novice';
    if (elo < 1200) return 'Scholar';
    if (elo < 1400) return 'Expert';
    return 'Master';
  }

  function showEloChange(value) {
    eloPopup.textContent = (value > 0 ? '+' : '') + value + ' Elo';
    eloPopup.style.opacity = '1';
    eloPopup.style.transform = 'translateY(-6px)';
    eloPopup.classList.remove('pointer-events-none');
    setTimeout(() => {
      eloPopup.style.opacity = '0';
      eloPopup.style.transform = 'translateY(0)';
      eloPopup.classList.add('pointer-events-none');
    }, 1400);
  }

  function updateHeaderFromState() {
    currentEloEl.textContent = session.elo;
    eloBadge.textContent = `${session.elo} — ${setBadgeTitle(session.elo)}`;
    levelTitle.textContent = setBadgeTitle(session.elo);
    streakEl.textContent = session.streak;
    totalXpEl.textContent = session.xp;
    totalQuestionsEl.textContent = session.totalQuestions;
    el('session-correct').textContent = session.correct;
    el('session-wrong').textContent = session.wrong;
    // XP bar (approx) - map xp to 0-100 for demo
    const pct = Math.min(100, (session.xp % 300) / 3);
    xpBar.style.width = pct + '%';
    // Flame intensity
    if (session.streak >= 5) streakFlame.classList.add('flame--big'); else streakFlame.classList.remove('flame--big');
  }

  function setQuestion(q) {
    currentQuestion = q;
    if (!q) {
      questionText.textContent = 'No more questions available.';
      optionsContainer.innerHTML = '';
      nextBtn.disabled = true;
      return;
    }
    // Backend sends question_text and option_a..option_d - normalize into options array
    questionText.textContent = q.question_text || q.text || 'Question text missing';
    questionXp.textContent = 'XP: ' + (q.xp || q.elo_rating || 0);
    optionsContainer.innerHTML = '';
    const opts = [];
    if (q.option_a) opts.push(q.option_a);
    if (q.option_b) opts.push(q.option_b);
    if (q.option_c) opts.push(q.option_c);
    if (q.option_d) opts.push(q.option_d);
    // fallback to q.options if present
    if (opts.length === 0 && Array.isArray(q.options)) opts.push(...q.options);
    (opts || []).forEach((opt, i) => {
      const b = document.createElement('button');
      b.className = 'text-left w-full bg-gray-700 hover:bg-gray-700/80 px-4 py-3 rounded flex items-center gap-4';
      // store letter (A/B/C/D) for backend
      const letter = ['A','B','C','D'][i] || String(i+1);
      b.dataset.letter = letter;
      b.dataset.index = i;
      b.innerHTML = `<span class="w-7 inline-flex items-center justify-center font-medium text-sm">${letter}</span><span class="flex-1">${opt}</span>`;
      b.addEventListener('click', onOptionClick);
      optionsContainer.appendChild(b);
    });
    nextBtn.disabled = true;
    feedback.textContent = '';
  }

  async function getNextQuestion() {
    try {
      nextBtn.disabled = true;
      questionText.textContent = 'Loading next question…';
      const res = await fetch('/api/get-next-question/');
      if (!res.ok) throw new Error('Network error');
      const data = await res.json();
      if (data && data.question) {
        setQuestion(data.question);
        // update header if returned
        if (data.session) Object.assign(session, data.session);
        updateHeaderFromState();
      } else if (data && data.no_more) {
        setQuestion(null);
        feedback.textContent = data.message || 'No questions left.';
      } else {
        setQuestion(null);
      }
    } catch (e) {
      questionText.textContent = 'Unable to load question.';
      console.error(e);
    }
  }

  async function onOptionClick(ev) {
    const btn = ev.currentTarget;
    if (!currentQuestion) return;
    // disable all options while submitting
    Array.from(optionsContainer.children).forEach(c => c.disabled = true);
    const selected = Number(btn.dataset.index);
    // highlight selected immediately
    btn.classList.add('ring-2', 'ring-indigo-500');
    try {
      // Backend expects selected_option as 'A'|'B'|'C'|'D' and question_id
      const letter = btn.dataset.letter || ['A','B','C','D'][selected];
      const res = await fetch('/api/submit-answer/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
        body: JSON.stringify({ question_id: currentQuestion.id, selected_option: letter })
      });
      if (!res.ok) throw new Error('Submit failed');
      const data = await res.json();
      // Backend returns 'is_correct' and 'correct_option' (A/B/C/D)
      const correct = data.is_correct === true || data.is_correct === 'true';
      const correctOption = data.correct_option || data.correctOption;
      // visual feedback
      if (correct) {
        playTone('success');
        btn.classList.add('bg-green-600');
        btn.classList.add('option-feedback-correct');
        session.correct += 1;
        session.streak = (session.streak || 0) + 1;
      } else {
        playTone('fail');
        btn.classList.add('bg-red-700');
        btn.classList.add('option-feedback-wrong');
        session.wrong += 1;
        session.streak = 0;
        // reveal correct
        if (correctOption) {
          // find option button with matching letter
          Array.from(optionsContainer.children).forEach(c => {
            if (c.dataset.letter === correctOption) c.classList.add('bg-green-700');
          });
        }
      }
      }
      // update elo/xp from response if available
      // Update Elo/xp from backend keys
      const eloChange = ('elo_change' in data) ? data.elo_change : (('eloChange' in data) ? data.eloChange : null);
      if (eloChange !== null && eloChange !== undefined) showEloChange(eloChange);
      if ('new_user_elo' in data) session.elo = data.new_user_elo; else if ('newUserElo' in data) session.elo = data.newUserElo; else if ('new_elo' in data) session.elo = data.new_elo;
      if ('xp' in data) session.xp = data.xp; if ('total_xp' in data) session.totalXp = data.total_xp; if ('totalXp' in data) session.totalXp = data.totalXp;
      if ('current_streak' in data) session.streak = data.current_streak;
      session.totalQuestions = (session.totalQuestions||0) + 1;
      updateHeaderFromState();
      feedback.textContent = data.message || (correct ? 'Correct!' : 'Incorrect');
      nextBtn.disabled = false;
    } catch (err) {
      console.error(err);
      feedback.textContent = 'Error submitting answer. Try again.';
      Array.from(optionsContainer.children).forEach(c => c.disabled = false);
    }
  }

  nextBtn.addEventListener('click', async () => {
    await getNextQuestion();
  });

  // PDF Upload UI
  const uploadOpen = el('uploadOpen');
  const uploadModal = el('uploadModal');
  const uploadClose = el('uploadClose');
  const dropArea = el('dropArea');
  const fileInput = el('fileInput');
  const uploadStatus = el('uploadStatus');

  uploadOpen.addEventListener('click', () => uploadModal.classList.remove('hidden'));
  uploadClose.addEventListener('click', () => uploadModal.classList.add('hidden'));
  dropArea.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', e => handleFile(e.target.files[0]));
  dropArea.addEventListener('dragover', e => { e.preventDefault(); dropArea.classList.add('bg-gray-800'); });
  dropArea.addEventListener('dragleave', e => { e.preventDefault(); dropArea.classList.remove('bg-gray-800'); });
  dropArea.addEventListener('drop', e => { e.preventDefault(); dropArea.classList.remove('bg-gray-800'); const f = e.dataTransfer.files[0]; handleFile(f); });

  async function handleFile(file) {
    if (!file) return;
    if (file.type !== 'application/pdf') { uploadStatus.textContent = 'Please upload a PDF file.'; return; }
    uploadStatus.textContent = 'Extracting text...';
    // POST to upload endpoint if exists
    try {
      const fd = new FormData(); fd.append('file', file);
      const res = await fetch('/api/upload-pdf/', { method: 'POST', headers: { 'X-CSRFToken': getCookie('csrftoken') }, body: fd });
      if (!res.ok) throw new Error('Upload failed');
      // poll or await response
      uploadStatus.textContent = 'Generating questions with AI...';
      const data = await res.json();
      if (data && data.status === 'ready') {
        uploadStatus.textContent = 'Ready! Questions added.';
      } else {
        uploadStatus.textContent = data.message || 'Upload finished.';
      }
      setTimeout(() => uploadModal.classList.add('hidden'), 1200);
    } catch (err) {
      console.error(err);
      uploadStatus.textContent = 'Upload failed or endpoint missing.';
    }
  }

  // Initial load
  document.addEventListener('DOMContentLoaded', () => {
    // Try to fetch first question
    getNextQuestion();
  });

})();
