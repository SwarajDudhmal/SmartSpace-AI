import { motion } from 'framer-motion';
import { useEffect, useState } from 'react';

type SavedProject = {
  id: number;
  project_name: string;
  room_type: string;
  updated_at: string;
  budget: number;
  estimated_cost: number;
  state_dimensions: number;
};

export function ProjectsDashboard() {
  const [projects, setProjects] = useState<SavedProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [signingOut, setSigningOut] = useState(false);

  useEffect(() => {
    let active = true;
    fetch('/api/project-history')
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'Your projects could not be loaded.');
        if (active) setProjects(data.projects || []);
      })
      .catch((requestError) => { if (active) setError(requestError instanceof Error ? requestError.message : 'Could not load saved projects.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  async function signOut() {
    setSigningOut(true);
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.assign('/');
  }

  return <main className="ss-projects-page">
    <header className="ss-projects-heading">
      <div><p className="ss-wizard-eyebrow">YOUR SMARTSPACE</p><h1>My <em>projects.</em></h1><p>Open a saved room and continue shaping the plan.</p></div>
      <div className="ss-projects-heading-actions"><button type="button" onClick={signOut} disabled={signingOut}>{signingOut ? 'Signing out…' : 'Sign out'}</button><a href="/create-project" className="ss-projects-new">New design <span aria-hidden="true">→</span></a></div>
    </header>
    {loading && <div className="ss-projects-state">Loading your saved rooms…</div>}
    {error && <div className="ss-projects-state ss-projects-state--error" role="alert">{error} <a href="/login">Sign in again</a></div>}
    {!loading && !error && projects.length === 0 && <section className="ss-projects-empty"><span aria-hidden="true">⌂</span><h2>Your first design starts here.</h2><p>When you save a room in the Studio, it will appear here ready to resume.</p><a href="/create-project" className="ss-projects-new">Create a room <span aria-hidden="true">→</span></a></section>}
    {!loading && projects.length > 0 && <div className="ss-projects-grid">
      {projects.map((project, index) => <motion.article className="ss-project-card" key={project.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(index * 0.05, 0.3) }}>
        <div className="ss-project-card-visual" aria-hidden="true"><span>⌂</span><small>{project.room_type.replaceAll('_', ' ')}</small></div>
        <div className="ss-project-card-body"><span className="ss-project-card-date">UPDATED {new Date(`${project.updated_at.replace(' ', 'T')}Z`).toLocaleDateString()}</span>
          <h2>{project.project_name}</h2><p>{project.room_type.replaceAll('_', ' ')} · {project.state_dimensions}-value room state</p>
          <div className="ss-project-card-metrics"><span>Budget <strong>₹{Number(project.budget).toLocaleString('en-IN')}</strong></span><span>Estimate <strong>₹{Number(project.estimated_cost).toLocaleString('en-IN')}</strong></span></div>
          <a href={`/studio?resume=${project.id}`} className="ss-project-resume">Resume design <span aria-hidden="true">→</span></a>
        </div>
      </motion.article>)}
    </div>}
  </main>;
}
