import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { PresetLayoutGrid } from './components/PresetLayoutGrid';
import { SmartSpaceBudgetSlider } from './components/SmartSpaceBudgetSlider';
import { ProjectPhotoUpload } from './components/ProjectPhotoUpload';
import { ProjectWizard } from './components/ProjectWizard';
import { AuthPage } from './components/AuthPage';
import { ProjectsDashboard } from './components/ProjectsDashboard';
import { FurniturePanel } from './components/FurniturePanel';
import type { LayoutLoadedDetail } from './types';
import './styles.css';

document.querySelectorAll<HTMLElement>('[data-layout-card-grid]').forEach((slot) => {
  const kind = slot.dataset.layoutCardGrid === 'lighting' ? 'lighting' : 'featured';
  createRoot(slot).render(<StrictMode><PresetLayoutGrid kind={kind} /></StrictMode>);
});

const budgetSlot = document.getElementById('studio-budget-react-root');
if (budgetSlot) createRoot(budgetSlot).render(<StrictMode><SmartSpaceBudgetSlider /></StrictMode>);

const furnitureSlot = document.getElementById('inventoryList');
if (furnitureSlot) createRoot(furnitureSlot).render(<StrictMode><FurniturePanel /></StrictMode>);

const photoSlot = document.getElementById('project-photo-upload-root');
if (photoSlot) createRoot(photoSlot).render(<StrictMode><ProjectPhotoUpload /></StrictMode>);

const wizardSlot = document.getElementById('project-wizard-root');
if (wizardSlot) {
  const initialStep = Number(wizardSlot.dataset.initialStep || new URLSearchParams(location.search).get('step') || 1);
  createRoot(wizardSlot).render(<StrictMode><ProjectWizard initialStep={initialStep} /></StrictMode>);
}

const authSlot = document.getElementById('auth-react-root');
if (authSlot) {
  const mode = authSlot.dataset.authMode === 'register' ? 'register' : 'login';
  createRoot(authSlot).render(<StrictMode><AuthPage mode={mode} /></StrictMode>);
}

const projectsSlot = document.getElementById('projects-dashboard-root');
if (projectsSlot) createRoot(projectsSlot).render(<StrictMode><ProjectsDashboard /></StrictMode>);

// Homepage cards hand the generated layout to Flask's existing editor. The editor
// initializes first on /studio and consumes the pending layout via the same event.
window.addEventListener('smartspace:load-layout', (event: Event) => {
  if (window.location.pathname === '/studio') return;
  const detail = (event as CustomEvent<LayoutLoadedDetail>).detail;
  if (!detail?.layout?.furniture?.length) return;
  try {
    sessionStorage.setItem('smartspace_pending_layout', JSON.stringify(detail.layout));
    window.location.assign('/studio?loadRecommendation=1');
  } catch {
    window.location.assign('/studio');
  }
});
