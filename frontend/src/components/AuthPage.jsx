import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { requestPasswordReset } from '../api';

// ─── Password strength meter ──────────────────────

function PasswordStrengthMeter({ password }) {
  const checks = [
    { label: '8+ characters', ok: password.length >= 8 },
    { label: 'Contains a number', ok: /\d/.test(password) },
    { label: 'Contains a symbol', ok: /[^A-Za-z0-9]/.test(password) },
  ];
  const score = checks.filter(c => c.ok).length;
  const color = ['var(--text-muted)', 'var(--danger)', 'var(--streak)', 'var(--success)'][score];
  const label = ['', 'Weak', 'Fair', 'Strong'][score];

  return (
    <div style={{ marginTop: '0.5rem' }}>
      <div style={{ display: 'flex', gap: '0.35rem' }}>
        {checks.map((c, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: 4,
              borderRadius: 2,
              background: c.ok ? color : 'var(--input-bg)',
              transition: 'background 0.25s',
            }}
          />
        ))}
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: '0.4rem',
          fontSize: '0.72rem',
          color: 'var(--text-muted)',
        }}
      >
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
    <div style={{ color: 'var(--danger)', fontSize: '0.78rem', marginTop: '0.3rem' }}>
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
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 200,
        background: 'rgba(0,0,0,0.5)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        className="card rise"
        style={{
          width: '100%',
          maxWidth: 400,
          borderRadius: 'var(--radius-xl)',
          boxShadow: 'var(--shadow-raised)',
          padding: '1.75rem',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '1.25rem',
          }}
        >
          <h3 className="t-title">🔑 Reset Password</h3>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-secondary)',
              fontSize: '1.15rem',
              cursor: 'pointer',
              lineHeight: 1,
            }}
          >
            ✕
          </button>
        </div>

        {status?.type === 'success' ? (
          <div>
            <div
              style={{
                background: 'color-mix(in srgb, var(--success) 10%, transparent)',
                border: '1px solid color-mix(in srgb, var(--success) 30%, transparent)',
                color: 'var(--success)',
                borderRadius: 'var(--radius-sm)',
                padding: '0.75rem 1rem',
                fontSize: '0.85rem',
                marginBottom: '1rem',
              }}
            >
              {status.text}
            </div>
            {status.devReset && (
              <div
                style={{
                  background: 'var(--accent-soft)',
                  border: '1px dashed color-mix(in srgb, var(--accent) 40%, transparent)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.75rem 1rem',
                  fontSize: '0.75rem',
                  color: 'var(--text-secondary)',
                  marginBottom: '1rem',
                  fontFamily: 'ui-monospace, monospace',
                  wordBreak: 'break-all',
                }}
              >
                DEV ONLY — reset token:
                <br />
                uid: {status.devReset.uid}
                <br />
                token: {status.devReset.token}
              </div>
            )}
            <button onClick={onClose} className="btn btn-primary" style={{ width: '100%' }}>
              Done
            </button>
          </div>
        ) : (
          <form onSubmit={submit}>
            <label className="label">Email address</label>
            <input
              type="email"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="input"
            />
            {status?.type === 'error' && <FieldError message={status.text} />}
            <button
              type="submit"
              disabled={busy}
              className="btn btn-primary"
              style={{ width: '100%', marginTop: '1.1rem' }}
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
    <div
      style={{
        minHeight: 'calc(100vh - 140px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '3rem 1rem',
      }}
    >
      <div
        className="card rise"
        style={{
          width: '100%',
          maxWidth: 430,
          borderRadius: 'var(--radius-xl)',
          boxShadow: 'var(--shadow-raised)',
          padding: '2.25rem',
        }}
      >
        {/* Brand */}
        <div style={{ textAlign: 'center', marginBottom: '1.75rem' }}>
          <div
            className="icon-tile"
            style={{ width: 56, height: 56, margin: '0 auto 1rem', fontSize: '1.5rem' }}
          >
            🧠
          </div>
          <h1 className="t-headline" style={{ fontSize: '1.45rem' }}>
            {tab === 'login' ? 'Welcome back' : 'Create your account'}
          </h1>
          <p className="t-caption" style={{ marginTop: '0.45rem' }}>
            {tab === 'login'
              ? 'Pick up right where you left off.'
              : 'Start learning smarter in under a minute.'}
          </p>
        </div>

        {/* Segmented tab switch */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1.75rem' }}>
          <div className="segmented">
            {[
              { key: 'login', label: 'Sign In' },
              { key: 'signup', label: 'Sign Up' },
            ].map(t => (
              <button
                key={t.key}
                onClick={() => switchTab(t.key)}
                className={tab === t.key ? 'active' : ''}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Server-level error */}
        {formError && (
          <div
            style={{
              background: 'color-mix(in srgb, var(--danger) 10%, transparent)',
              border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)',
              color: 'var(--danger)',
              borderRadius: 'var(--radius-sm)',
              padding: '0.7rem 1rem',
              fontSize: '0.85rem',
              marginBottom: '1rem',
            }}
          >
            {formError}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          {tab === 'login' ? (
            <>
              <div style={{ marginBottom: '1rem' }}>
                <label className="label">Username or Email</label>
                <input
                  type="text"
                  required
                  value={loginForm.username_or_email}
                  onChange={e => setField('login', 'username_or_email', e.target.value)}
                  placeholder="you@example.com or username"
                  className="input"
                  autoComplete="username"
                />
              </div>

              <div style={{ marginBottom: '0.75rem' }}>
                <label className="label">Password</label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={loginForm.password}
                    onChange={e => setField('login', 'password', e.target.value)}
                    placeholder="••••••••"
                    className="input"
                    style={{ paddingRight: '2.6rem' }}
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(s => !s)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    style={{
                      position: 'absolute',
                      right: '0.7rem',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '1rem',
                    }}
                  >
                    {showPassword ? '🙈' : '👁️'}
                  </button>
                </div>
              </div>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '1.4rem',
                }}
              >
                <label
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.45rem',
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                    color: 'var(--text-secondary)',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={loginForm.remember_me}
                    onChange={e => setField('login', 'remember_me', e.target.checked)}
                    style={{ accentColor: 'var(--accent)', width: 15, height: 15, cursor: 'pointer' }}
                  />
                  Remember Me
                </label>
                <button
                  type="button"
                  onClick={() => setShowReset(true)}
                  className="btn btn-ghost"
                  style={{ fontSize: '0.82rem', padding: '0.3rem 0.5rem' }}
                >
                  Forgot Password?
                </button>
              </div>

              <button
                type="submit"
                disabled={busy}
                className="btn btn-primary"
                style={{ width: '100%', padding: '0.85rem', fontSize: '0.95rem' }}
              >
                {busy ? 'Signing in…' : 'Sign In'}
              </button>
            </>
          ) : (
            <>
              <div style={{ marginBottom: '1rem' }}>
                <label className="label">Username</label>
                <input
                  type="text"
                  required
                  value={signupForm.username}
                  onChange={e => setField('signup', 'username', e.target.value)}
                  placeholder="e.g. study_warrior"
                  className="input"
                  autoComplete="username"
                />
                <FieldError message={fieldErrors.username} />
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label className="label">Email</label>
                <input
                  type="email"
                  required
                  value={signupForm.email}
                  onChange={e => setField('signup', 'email', e.target.value)}
                  placeholder="you@example.com"
                  className="input"
                  autoComplete="email"
                />
                <FieldError message={fieldErrors.email} />
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label className="label">Password</label>
                <div style={{ position: 'relative' }}>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={signupForm.password}
                    onChange={e => setField('signup', 'password', e.target.value)}
                    placeholder="8+ chars, a number and a symbol"
                    className="input"
                    style={{ paddingRight: '2.6rem' }}
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(s => !s)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    style={{
                      position: 'absolute',
                      right: '0.7rem',
                      top: '50%',
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '1rem',
                    }}
                  >
                    {showPassword ? '🙈' : '👁️'}
                  </button>
                </div>
                <PasswordStrengthMeter password={signupForm.password} />
                <FieldError message={fieldErrors.password} />
              </div>

              <div style={{ marginBottom: '1.5rem' }}>
                <label className="label">Confirm Password</label>
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={signupForm.confirm_password}
                  onChange={e => setField('signup', 'confirm_password', e.target.value)}
                  placeholder="Repeat your password"
                  className="input"
                  autoComplete="new-password"
                />
                <FieldError message={fieldErrors.confirm_password} />
              </div>

              <button
                type="submit"
                disabled={busy}
                className="btn btn-primary"
                style={{ width: '100%', padding: '0.85rem', fontSize: '0.95rem' }}
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
