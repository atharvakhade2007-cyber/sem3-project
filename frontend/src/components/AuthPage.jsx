import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { requestPasswordReset } from '../api';

// ─── Shared input styles ──────────────────────────

const inputStyle = {
  width: '100%',
  padding: '0.75rem 1rem',
  borderRadius: 10,
  border: '1px solid var(--input-border)',
  background: 'var(--input-bg)',
  color: 'var(--text)',
  fontSize: '0.95rem',
  outline: 'none',
};

const labelStyle = {
  display: 'block',
  fontSize: '0.82rem',
  fontWeight: 600,
  color: 'var(--text-secondary)',
  marginBottom: '0.35rem',
};

// ─── Password strength meter ──────────────────────

function PasswordStrengthMeter({ password }) {
  const checks = [
    { label: '8+ characters', ok: password.length >= 8 },
    { label: 'Contains a number', ok: /\d/.test(password) },
    { label: 'Contains a symbol', ok: /[^A-Za-z0-9]/.test(password) },
  ];
  const score = checks.filter(c => c.ok).length;
  const color = ['#64748b', '#ef4444', '#f59e0b', '#10b981'][score];
  const label = ['', 'Weak', 'Fair', 'Strong'][score];

  return (
    <div style={{ marginTop: '0.5rem' }}>
      <div style={{ display: 'flex', gap: '0.35rem' }}>
        {checks.map((c, i) => (
          <div key={i} style={{
            flex: 1,
            height: 4,
            borderRadius: 2,
            background: c.ok ? color : 'var(--card-border)',
            transition: 'background 0.2s',
          }} />
        ))}
      </div>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        marginTop: '0.35rem',
        fontSize: '0.72rem',
        color: 'var(--text-muted)',
      }}>
        <span>
          {checks.map((c, i) => (
            <span key={i} style={{ marginRight: '0.75rem' }}>
              {c.ok ? '✓' : '○'} {c.label}
            </span>
          ))}
        </span>
        {label && <strong style={{ color }}>{label}</strong>}
      </div>
    </div>
  );
}

// ─── Field error ──────────────────────────────────

function FieldError({ message }) {
  if (!message) return null;
  return (
    <div style={{ color: '#f87171', fontSize: '0.78rem', marginTop: '0.3rem' }}>
      {message}
    </div>
  );
}

// ─── Forgot password modal ────────────────────────

function ForgotPasswordModal({ onClose }) {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState(null); // {type, text, devReset}
  const [busy, setBusy] = useState(false);

  const submit = async e => {
    e.preventDefault();
    setBusy(true);
    setStatus(null);
    try {
      const data = await requestPasswordReset(email);
      setStatus({
        type: 'success',
        text: data.detail || 'Reset link sent.',
        devReset: data.dev_reset,
      });
    } catch (err) {
      setStatus({ type: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 200,
      background: 'rgba(0,0,0,0.6)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '1rem',
    }}>
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--card-bg-solid)',
          border: '1px solid var(--card-border)',
          borderRadius: 16,
          padding: '1.5rem',
          width: '100%',
          maxWidth: 400,
          boxShadow: 'var(--shadow)',
        }}
      >
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          marginBottom: '1rem',
        }}>
          <h3 style={{ fontSize: '1.05rem' }}>🔑 Reset Password</h3>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: 'var(--text-secondary)',
            fontSize: '1.2rem', cursor: 'pointer', lineHeight: 1,
          }}>✕</button>
        </div>

        {status?.type === 'success' ? (
          <div>
            <div style={{
              background: 'rgba(16,185,129,0.1)',
              border: '1px solid rgba(16,185,129,0.3)',
              color: '#34d399', borderRadius: 10, padding: '0.75rem 1rem',
              fontSize: '0.85rem', marginBottom: '1rem',
            }}>
              {status.text}
            </div>
            {status.devReset && (
              <div style={{
                background: 'rgba(99,102,241,0.08)',
                border: '1px dashed rgba(99,102,241,0.4)',
                borderRadius: 10, padding: '0.75rem 1rem',
                fontSize: '0.75rem', color: 'var(--text-secondary)',
                marginBottom: '1rem',
                fontFamily: 'monospace',
                wordBreak: 'break-all',
              }}>
                DEV ONLY — reset token:<br />
                uid: {status.devReset.uid}<br />
                token: {status.devReset.token}
              </div>
            )}
            <button onClick={onClose} style={{
              width: '100%', padding: '0.7rem', borderRadius: 10,
              border: 'none', cursor: 'pointer', fontWeight: 700,
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: '#fff',
            }}>
              Done
            </button>
          </div>
        ) : (
          <form onSubmit={submit}>
            <label style={labelStyle}>Email address</label>
            <input
              type="email"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              style={inputStyle}
            />
            {status?.type === 'error' && (
              <FieldError message={status.text} />
            )}
            <button
              type="submit"
              disabled={busy}
              style={{
                width: '100%', marginTop: '1rem', padding: '0.7rem',
                borderRadius: 10, border: 'none', cursor: 'pointer',
                fontWeight: 700, fontSize: '0.9rem',
                background: busy ? 'var(--card-border)' : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                color: busy ? 'var(--text-muted)' : '#fff',
              }}
            >
              {busy ? 'Sending…' : 'Send Reset Link'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────

export default function AuthPage({ mode = 'login' }) {
  const navigate = useNavigate();
  const { login, signup } = useAuth();

  const [tab, setTab] = useState(mode === 'signup' ? 'signup' : 'login');
  const [showPassword, setShowPassword] = useState(false);
  const [showReset, setShowReset] = useState(false);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState(null); // server-level error
  const [fieldErrors, setFieldErrors] = useState({}); // DRF field errors
  const [loginForm, setLoginForm] = useState({
    username_or_email: '',
    password: '',
    remember_me: false,
  });
  const [signupForm, setSignupForm] = useState({
    username: '',
    email: '',
    password: '',
    confirm_password: '',
  });

  const switchTab = next => {
    setTab(next);
    setFieldErrors({});
    setFormError(null);
    navigate(next === 'signup' ? '/signup' : '/login', { replace: true });
  };

  const setField = (form, field, value) => {
    const setter = form === 'login' ? setLoginForm : setSignupForm;
    setter(prev => ({ ...prev, [field]: value }));
    setFieldErrors(prev => ({ ...prev, [field]: null }));
  };

  const handleSubmit = async e => {
    e.preventDefault();
    setBusy(true);
    setFormError(null);
    setFieldErrors({});

    try {
      if (tab === 'login') {
        await login(
          loginForm.username_or_email.trim(),
          loginForm.password,
          loginForm.remember_me
        );
      } else {
        // Client-side checks before hitting the API
        const localErrors = {};
        if (signupForm.username.trim().length < 3) {
          localErrors.username = 'Username must be at least 3 characters.';
        }
        if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(signupForm.email.trim())) {
          localErrors.email = 'Enter a valid email address.';
        }
        if (signupForm.password !== signupForm.confirm_password) {
          localErrors.confirm_password = 'Passwords do not match.';
        }
        if (Object.keys(localErrors).length > 0) {
          setFieldErrors(localErrors);
          return;
        }
        await signup(
          signupForm.username.trim(),
          signupForm.email.trim(),
          signupForm.password
        );
      }
      navigate('/', { replace: true });
    } catch (err) {
      if (err.data && typeof err.data === 'object' && !err.data.error && !err.data.detail) {
        setFieldErrors(
          Object.fromEntries(
            Object.entries(err.data).map(([k, v]) => [k, Array.isArray(v) ? v[0] : v])
          )
        );
      } else {
        setFormError(err.message);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{
      minHeight: 'calc(100vh - 140px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '2rem 1rem',
    }}>
      <div style={{
        width: '100%',
        maxWidth: 440,
        background: 'var(--card-bg-solid)',
        border: '1px solid var(--card-border)',
        borderRadius: 20,
        boxShadow: 'var(--shadow)',
        padding: '2rem',
      }}>
        {/* Brand */}
        <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          <div style={{ fontSize: '2.2rem' }}>🧠</div>
          <h1 style={{ fontSize: '1.4rem', fontWeight: 800, marginTop: '0.25rem' }}>
            StudyMind AI
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '0.25rem' }}>
            {tab === 'login' ? 'Welcome back — pick up where you left off.' : 'Create your account and start learning smarter.'}
          </p>
        </div>

        {/* Tabs */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          background: 'var(--input-bg)',
          border: '1px solid var(--input-border)',
          borderRadius: 12,
          padding: '0.25rem',
          marginBottom: '1.5rem',
        }}>
          {[
            { key: 'login', label: 'Sign In' },
            { key: 'signup', label: 'Sign Up' },
          ].map(t => {
            const active = tab === t.key;
            return (
              <button
                key={t.key}
                onClick={() => switchTab(t.key)}
                style={{
                  padding: '0.6rem',
                  borderRadius: 9,
                  border: 'none',
                  cursor: 'pointer',
                  fontWeight: 700,
                  fontSize: '0.9rem',
                  color: active ? '#fff' : 'var(--text-secondary)',
                  background: active
                    ? 'linear-gradient(135deg, #6366f1, #8b5cf6)'
                    : 'transparent',
                  transition: 'all 0.15s',
                }}
              >
                {t.label}
              </button>
            );
          })}
        </div>

        {/* Server-level error */}
        {formError && (
          <div style={{
            background: 'rgba(239,68,68,0.1)',
            border: '1px solid rgba(239,68,68,0.35)',
            color: '#fca5a5',
            borderRadius: 10,
            padding: '0.7rem 1rem',
            fontSize: '0.85rem',
            marginBottom: '1rem',
          }}>
            {formError}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          {tab === 'login' ? (
            <>
              <div style={{ marginBottom: '1rem' }}>
                <label style={labelStyle}>Username or Email</label>
                <input
                  type="text"
                  required
                  value={loginForm.username_or_email}
                  onChange={e => setField('login', 'username_or_email', e.target.value)}
                  placeholder="you@example.com or username"
                  style={inputStyle}
                  autoComplete="username"
                />
              </div>

              <div style={{ marginBottom: '0.75rem' }}>
                <label style={labelStyle}>Password</label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={loginForm.password}
                    onChange={e => setField('login', 'password', e.target.value)}
                    placeholder="••••••••"
                    style={{ ...inputStyle, paddingRight: '2.6rem' }}
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(s => !s)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    style={{
                      position: 'absolute',
                      right: '0.6rem',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '1.05rem',
                    }}
                  >
                    {showPassword ? '🙈' : '👁️'}
                  </button>
                </div>
              </div>

              <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                marginBottom: '1.25rem',
              }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.85rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={loginForm.remember_me}
                    onChange={e => setField('login', 'remember_me', e.target.checked)}
                    style={{ accentColor: '#6366f1', width: 15, height: 15, cursor: 'pointer' }}
                  />
                  Remember Me
                </label>
                <button
                  type="button"
                  onClick={() => setShowReset(true)}
                  style={{
                    background: 'none', border: 'none', color: '#a78bfa',
                    fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer',
                  }}
                >
                  Forgot Password?
                </button>
              </div>

              <button
                type="submit"
                disabled={busy}
                style={{
                  width: '100%', padding: '0.8rem', borderRadius: 12,
                  border: 'none', cursor: 'pointer', fontWeight: 800,
                  fontSize: '0.95rem',
                  background: busy ? 'var(--card-border)' : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                  color: busy ? 'var(--text-muted)' : '#fff',
                  boxShadow: busy ? 'none' : '0 4px 18px rgba(99,102,241,0.4)',
                }}
              >
                {busy ? 'Signing in…' : 'Sign In'}
              </button>
            </>
          ) : (
            <>
              <div style={{ marginBottom: '1rem' }}>
                <label style={labelStyle}>Username</label>
                <input
                  type="text"
                  required
                  value={signupForm.username}
                  onChange={e => setField('signup', 'username', e.target.value)}
                  placeholder="e.g. study_warrior"
                  style={inputStyle}
                  autoComplete="username"
                />
                <FieldError message={fieldErrors.username} />
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={labelStyle}>Email</label>
                <input
                  type="email"
                  required
                  value={signupForm.email}
                  onChange={e => setField('signup', 'email', e.target.value)}
                  placeholder="you@example.com"
                  style={inputStyle}
                  autoComplete="email"
                />
                <FieldError message={fieldErrors.email} />
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={labelStyle}>Password</label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={signupForm.password}
                    onChange={e => setField('signup', 'password', e.target.value)}
                    placeholder="8+ chars, a number and a symbol"
                    style={{ ...inputStyle, paddingRight: '2.6rem' }}
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(s => !s)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    style={{
                      position: 'absolute',
                      right: '0.6rem',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '1.05rem',
                    }}
                  >
                    {showPassword ? '🙈' : '👁️'}
                  </button>
                </div>
                <PasswordStrengthMeter password={signupForm.password} />
                <FieldError message={fieldErrors.password} />
              </div>

              <div style={{ marginBottom: '1.5rem' }}>
                <label style={labelStyle}>Confirm Password</label>
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={signupForm.confirm_password}
                  onChange={e => setField('signup', 'confirm_password', e.target.value)}
                  placeholder="Repeat your password"
                  style={inputStyle}
                  autoComplete="new-password"
                />
                <FieldError message={fieldErrors.confirm_password} />
              </div>

              <button
                type="submit"
                disabled={busy}
                style={{
                  width: '100%', padding: '0.8rem', borderRadius: 12,
                  border: 'none', cursor: 'pointer', fontWeight: 800,
                  fontSize: '0.95rem',
                  background: busy ? 'var(--card-border)' : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                  color: busy ? 'var(--text-muted)' : '#fff',
                  boxShadow: busy ? 'none' : '0 4px 18px rgba(99,102,241,0.4)',
                }}
              >
                {busy ? 'Creating account…' : 'Create Account'}
              </button>
            </>
          )}
        </form>
      </div>

      {showReset && <ForgotPasswordModal onClose={() => setShowReset(false)} />}
    </div>
  );
}