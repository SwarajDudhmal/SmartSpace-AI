import { motion } from 'framer-motion';
import { useState, type FormEvent } from 'react';

export function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const registering = mode === 'register';
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      const response = await fetch(`/api/auth/${registering ? 'register' : 'login'}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'We could not sign you in. Please try again.');
      const params = new URLSearchParams(window.location.search);
      const destination = params.get('next') || '/projects';
      window.location.assign(destination.startsWith('/') && !destination.startsWith('//') ? destination : '/projects');
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Could not complete this request.');
      setBusy(false);
    }
  }

  return <main className="ss-auth-page">
    <div className="ss-auth-orbit ss-auth-orbit--one" aria-hidden="true" />
    <div className="ss-auth-orbit ss-auth-orbit--two" aria-hidden="true" />
    <motion.section className="ss-auth-card" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
      <a className="ss-auth-back" href="/">← Overview</a>
      <span className="ss-auth-mark" aria-hidden="true">⌂</span>
      <p className="ss-auth-eyebrow">Your design space</p>
      <h1>{registering ? 'Create your account.' : 'Welcome back.'}</h1>
      <p className="ss-auth-lede">{registering ? 'Save your designs and pick up where you left off.' : 'Sign in to open your saved rooms and recent layouts.'}</p>
      <form className="ss-auth-form" onSubmit={submit}>
        {registering && <label className="ss-auth-field"><span>Your name</span><input value={name} onChange={(event) => setName(event.currentTarget.value)} autoComplete="name" required minLength={2} maxLength={80} /></label>}
        <label className="ss-auth-field"><span>Email address</span><input type="email" value={email} onChange={(event) => setEmail(event.currentTarget.value)} autoComplete="email" required maxLength={254} /></label>
        <label className="ss-auth-field"><span>Password</span><input type="password" value={password} onChange={(event) => setPassword(event.currentTarget.value)} autoComplete={registering ? 'new-password' : 'current-password'} required minLength={8} maxLength={256} /></label>
        {registering && <small className="ss-auth-password-note">Use at least 8 characters.</small>}
        {error && <p className="ss-auth-error" role="alert">{error}</p>}
        <button className="ss-auth-submit" type="submit" disabled={busy}>{busy ? 'Please wait…' : registering ? 'Create account' : 'Sign in'} <span aria-hidden="true">→</span></button>
      </form>
      <p className="ss-auth-switch">{registering ? 'Already have an account?' : 'New to SmartSpace?'} <a href={registering ? '/login' : '/register'}>{registering ? 'Sign in' : 'Create an account'}</a></p>
      <p className="ss-auth-security">Your password is stored as a secure one-way hash. It is never saved as plain text.</p>
    </motion.section>
    <aside className="ss-auth-aside">
      <span>SMARTSPACE / YOUR WORKSPACE</span>
      <h2>Thoughtful rooms,<br /><em>saved for you.</em></h2>
      <p>Keep your room plans, test a few ideas, and return to the latest state whenever you need it.</p>
    </aside>
  </main>;
}
