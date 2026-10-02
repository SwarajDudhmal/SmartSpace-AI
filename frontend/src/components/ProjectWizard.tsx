import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { useEffect, useMemo, useRef, useState, type MouseEvent, type ReactNode } from 'react';
import { ProjectPhotoUpload } from './ProjectPhotoUpload';
import { DesignLoading } from './DesignLoading';
import { requestDesign } from '../api';

type WizardData = {
  name: string;
  roomType: string;
  description: string;
  length: string;
  width: string;
  height: string;
  doors: string;
  windows: string;
  budget: string;
  designStyle: string;
  primaryColor: string;
  secondaryColor: string;
  preferredMaterial: string;
};

type Bundle = {
  id: string;
  name: string;
  style: string;
  total_cost_inr: number;
  metrics?: { circulation_ratio?: number; collision_count?: number };
  validation?: { valid?: boolean };
};

const steps = ['Project basics', 'Room details', 'Design preferences', 'Upload & launch'];

function roomTypeKey(value: string) {
  const normalized = value.toLowerCase();
  if (normalized.includes('bed')) return 'bedroom';
  if (normalized.includes('office')) return 'home_office';
  if (normalized.includes('dining')) return 'dining_room';
  if (normalized.includes('kitchen')) return 'kitchen';
  if (normalized.includes('bath')) return 'bathroom';
  return 'living_room';
}

export function ProjectWizard({ initialStep = 1 }: { initialStep?: number }) {
  const [step, setStep] = useState(Math.min(4, Math.max(1, initialStep)));
  const [values, setValues] = useState<WizardData>({
    name: 'My Modern Living Room', roomType: 'Living Room',
    description: 'Need a spacious and ergonomic layout',
    length: '12', width: '10', height: '10', doors: '1', windows: '1', budget: '85000',
    designStyle: 'Modern', primaryColor: 'White', secondaryColor: 'Beige', preferredMaterial: 'Wood',
  });
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [selectedBundleId, setSelectedBundleId] = useState('');
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoError, setPhotoError] = useState('');
  const [loadingBundles, setLoadingBundles] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState('');
  const recommendationRequest = useRef<AbortController | null>(null);
  const launchRequest = useRef<AbortController | null>(null);
  const panelHeading = useRef<HTMLHeadingElement>(null);
  const reduceMotion = useReducedMotion();
  const progress = useMemo(() => `${Math.round((step / steps.length) * 100)}%`, [step]);

  useEffect(() => {
    const restoreWizard = () => {
      launchRequest.current?.abort();
      launchRequest.current = null;
      recommendationRequest.current?.abort();
      recommendationRequest.current = null;
      setLaunching(false);
      setLoadingBundles(false);
    };
    window.addEventListener('pageshow', restoreWizard);
    return () => {
      window.removeEventListener('pageshow', restoreWizard);
      recommendationRequest.current?.abort();
      launchRequest.current?.abort();
    };
  }, []);

  function update<K extends keyof WizardData>(key: K, value: WizardData[K]) {
    recommendationRequest.current?.abort();
    setLoadingBundles(false);
    setBundles([]);
    setSelectedBundleId('');
    setValues((current) => ({ ...current, [key]: value }));
  }

  function moveTo(next: number) {
    launchRequest.current?.abort();
    launchRequest.current = null;
    setLaunching(false);
    recommendationRequest.current?.abort();
    setLoadingBundles(false);
    setError('');
    setStep(Math.min(4, Math.max(1, next)));
    window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' });
  }

  function continueWizard(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault();
    setError('');
    if (step === 1 && values.name.trim().length < 2) {
      setError('Give this project a name with at least two characters.');
      return;
    }
    if (step === 2) {
      const length = Number(values.length), width = Number(values.width), height = Number(values.height);
      const budget = Number(values.budget);
      const doors = Number(values.doors), windows = Number(values.windows);
      if (!Number.isFinite(length) || length < 6 || length > 60 || !Number.isFinite(width) || width < 6 || width > 60
        || !Number.isFinite(height) || height < 7 || height > 25 || !Number.isFinite(budget) || budget < 20000 || budget > 500000
        || !Number.isInteger(doors) || doors < 1 || doors > 5 || !Number.isInteger(windows) || windows < 0 || windows > 6) {
        setError('Check the measurements and door/window counts; set a budget from ₹20,000 to ₹5,00,000.');
        return;
      }
    }
    if (step === 3 && (!values.primaryColor.trim() || !values.secondaryColor.trim())) {
      setError('Add both a primary and secondary color, or keep the suggested defaults.');
      return;
    }
    moveTo(step + 1);
  }

  async function previewBundles() {
    recommendationRequest.current?.abort();
    const controller = new AbortController();
    recommendationRequest.current = controller;
    setError('');
    setLoadingBundles(true);
    try {
      const response = await requestDesign('/api/recommendations', {
        signal: controller.signal,
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          room_type: roomTypeKey(values.roomType),
          length_ft: Number(values.length), width_ft: Number(values.width),
          budget_inr: Number(values.budget), style: values.designStyle,
        }),
      });
      const data = await response.json();
      if (controller.signal.aborted) return;
      if (!response.ok || !data.success) throw new Error(data.error || 'Recommendations are unavailable right now.');
      setBundles(data.bundles || []);
      setSelectedBundleId('');
    } catch (requestError) {
      if (!controller.signal.aborted) setError(requestError instanceof Error ? requestError.message : 'Could not load design bundles.');
    } finally {
      if (recommendationRequest.current === controller) {
        recommendationRequest.current = null;
        setLoadingBundles(false);
      }
    }
  }

  async function launchStudio(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault();
    if (step !== 4 || event.detail > 1 || launching || launchRequest.current) return;
    if (photoError) { setError('Remove or replace the invalid photo before opening Studio.'); return; }
    recommendationRequest.current?.abort();
    setLoadingBundles(false);
    const controller = new AbortController();
    launchRequest.current = controller;
    setLaunching(true);
    setError('');
    try {
      const projectResponse = await requestDesign('/api/projects', {
        signal: controller.signal,
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: values.name, roomType: values.roomType, description: values.description }),
      });
      const projectResult = await projectResponse.json();
      if (!projectResponse.ok || !projectResult.success) throw new Error(projectResult.error || 'Could not save project details.');
      if (controller.signal.aborted) return;

      const formData = new FormData();
      const fields: Record<string, string> = {
        roomName: values.name, roomType: values.roomType, length: values.length,
        width: values.width, height: values.height, doors: values.doors, windows: values.windows,
        budget: values.budget, designStyle: values.designStyle, primaryColor: values.primaryColor,
        secondaryColor: values.secondaryColor, preferredMaterial: values.preferredMaterial,
        description: values.description,
      };
      Object.entries(fields).forEach(([key, value]) => formData.set(key, value));
      if (photo) formData.set('roomPhoto', photo, photo.name);
      if (selectedBundleId) formData.set('variation_id', selectedBundleId);
      // fetch sets the multipart boundary; never set Content-Type manually here.
      const response = await requestDesign('/api/detect', {
        method: 'POST', body: formData, credentials: 'same-origin', signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Could not prepare this room. Please try again.');
      if (controller.signal.aborted) return;
      if (data.room?.state_133d?.length !== 133) throw new Error('The backend returned an invalid room state.');
      // **Atomic handoff:** Studio consumes this new room before any old draft.
      // Keep the metric state if an annotated photo exceeds storage capacity.
      const compactRoom = { ...data.room };
      delete compactRoom.annotated_image;
      try {
        sessionStorage.setItem('smartspace_pending_layout', JSON.stringify(data.room));
      } catch {
        try { sessionStorage.setItem('smartspace_pending_layout', JSON.stringify(compactRoom)); }
        catch { throw new Error('Enable browser storage to open your new room in Studio.'); }
      }
      window.location.assign('/studio');
    } catch (launchError) {
      if (!controller.signal.aborted) {
        setError(launchError instanceof Error ? launchError.message : 'Could not open the design studio.');
      }
    } finally {
      if (launchRequest.current === controller) {
        launchRequest.current = null;
        setLaunching(false);
      }
    }
  }

  function field(label: string, key: keyof WizardData, type = 'text', extra: Record<string, unknown> = {}) {
    const id = `wizard-${key}`;
    return <label className="ss-wizard-field" htmlFor={id} key={key}>
      <span>{label}</span>
      <input id={id} type={type} value={values[key]} onChange={(event) => update(key, event.currentTarget.value)} {...extra} />
    </label>;
  }

  function select(label: string, key: keyof WizardData, choices: string[]) {
    return <label className="ss-wizard-field" htmlFor={`wizard-${key}`} key={key}>
      <span>{label}</span>
      <select id={`wizard-${key}`} value={values[key]} onChange={(event) => update(key, event.currentTarget.value)}>
        {choices.map((choice) => <option key={choice}>{choice}</option>)}
      </select>
    </label>;
  }

  let panel: ReactNode;
  if (step === 1) {
    panel = <div className="ss-wizard-grid">
      {field('Project name', 'name', 'text', { required: true, maxLength: 120, placeholder: 'e.g. Calm family living room' })}
      {select('Room type', 'roomType', ['Living Room', 'Bedroom', 'Master Bedroom', 'Kitchen', 'Bathroom', 'Dining Room', 'Home Office', 'Studio Apartment'])}
      <label className="ss-wizard-field ss-wizard-field--wide" htmlFor="wizard-description">
        <span>What should this room feel like?</span>
        <textarea id="wizard-description" rows={4} value={values.description} onChange={(event) => update('description', event.currentTarget.value)} placeholder="Tell us what matters in this space…" />
      </label>
    </div>;
  } else if (step === 2) {
    panel = <div className="ss-wizard-grid ss-wizard-grid--three">
      {field('Length (ft)', 'length', 'number', { min: 6, max: 60, step: 0.5, required: true, inputMode: 'decimal' })}
      {field('Width (ft)', 'width', 'number', { min: 6, max: 60, step: 0.5, required: true, inputMode: 'decimal' })}
      {field('Height (ft)', 'height', 'number', { min: 7, max: 25, step: 0.5, required: true, inputMode: 'decimal' })}
      {field('Doors', 'doors', 'number', { min: 1, max: 5, step: 1, required: true })}
      {field('Windows', 'windows', 'number', { min: 0, max: 6, step: 1, required: true })}
      {field('Maximum budget (₹)', 'budget', 'number', { min: 20000, max: 500000, step: 500, required: true })}
      <p className="ss-wizard-note">Enter room measurements in feet. The layout engine converts them to meters for planning.</p>
    </div>;
  } else if (step === 3) {
    panel = <div className="ss-wizard-grid">
      {select('Design style', 'designStyle', ['Modern', 'Minimalist', 'Scandinavian', 'Industrial', 'Contemporary'])}
      {select('Preferred material', 'preferredMaterial', ['Wood', 'Metal', 'Glass', 'Fabric / Upholstered'])}
      {field('Primary color', 'primaryColor', 'text', { required: true })}
      {field('Secondary color', 'secondaryColor', 'text', { required: true })}
      <div className="ss-wizard-style-tip"><span aria-hidden="true">✦</span><p>Your style choices guide the palette and material suggestions. You can change these later.</p></div>
    </div>;
  } else {
    panel = <div className="ss-wizard-upload-step">
      <section className="ss-wizard-upload-card" aria-labelledby="wizard-photo-title">
        <div className="ss-wizard-section-heading"><span className="ss-wizard-step-icon">04</span><div><h3 id="wizard-photo-title">Add a room photo</h3><p>YOLO can locate furniture in a photo when its model weights are installed.</p></div></div>
        <ProjectPhotoUpload photo={photo} onPhotoChange={setPhoto} onValidationChange={setPhotoError} validationMessage={photoError} disabled={launching} />
      </section>
      <section className="ss-wizard-bundles" aria-labelledby="wizard-bundles-title" aria-busy={loadingBundles}>
        <div className="ss-wizard-section-heading"><span className="ss-wizard-step-icon">✧</span><div><h3 id="wizard-bundles-title">Preview recommended bundles</h3><p>Suggestions use your room size, budget and preferred style.</p></div></div>
        <button type="button" className="ss-wizard-secondary" onClick={previewBundles} disabled={loadingBundles || launching}>
          {loadingBundles ? 'Finding layouts…' : bundles.length ? 'Refresh recommendations' : 'Show recommended bundles'}
        </button>
        <AnimatePresence>{loadingBundles && <DesignLoading key="recommendation-progress" message="Comparing furniture and checking walkways…" />}</AnimatePresence>
        {!loadingBundles && bundles.length > 0 && <div className="ss-wizard-bundle-grid">
          {bundles.slice(0, 6).map((bundle) => <article className="ss-wizard-bundle" key={bundle.id}>
            <span>{bundle.style}</span><h4>{bundle.name}</h4>
            <strong>₹{Number(bundle.total_cost_inr || 0).toLocaleString('en-IN')}</strong>
            <small>{Math.round((bundle.metrics?.circulation_ratio || 0) * 100)}% A* reachability · {bundle.metrics?.collision_count || 0} collisions</small>
            <small>{bundle.validation?.valid ? 'Passed room checks' : 'Needs manual adjustment'}</small>
            <button type="button" className="ss-wizard-secondary" aria-pressed={selectedBundleId === bundle.id}
              onClick={() => setSelectedBundleId(bundle.id)} disabled={launching}>
              {selectedBundleId === bundle.id ? 'Selected for Studio' : 'Use this bundle'}
            </button>
          </article>)}
        </div>}
      </section>
    </div>;
  }

  return <main className="ss-wizard-page">
    <div className="ss-wizard-shell">
      <header className="ss-wizard-intro">
        <p className="ss-wizard-eyebrow">A few details make a better room</p>
        <h1>Start with your <em>space.</em></h1>
        <p>Set the basics, then we’ll shape a floor plan around your room and preferences.</p>
      </header>
      <section className="ss-wizard-card" aria-label="Design setup wizard">
        <div className="ss-wizard-progress-row"><span>STEP {String(step).padStart(2, '0')} <b>{steps[step - 1]}</b></span><span>{step} of 4</span></div>
        <div className="ss-wizard-progress"><span style={{ width: progress }} /></div>
        <div className="ss-wizard-stepper" aria-label="Wizard progress">
          {steps.map((title, index) => <div className={index + 1 <= step ? 'is-current' : ''} key={title}><i>{index + 1 < step ? '✓' : index + 1}</i><span>{title}</span></div>)}
        </div>
        <form onSubmit={(event) => event.preventDefault()} aria-busy={launching}>
          <AnimatePresence mode="wait" initial={false}>
            <motion.section key={step} className="ss-wizard-panel" initial={{ opacity: 0, y: reduceMotion ? 0 : 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: reduceMotion ? 0 : -8 }} transition={{ duration: reduceMotion ? 0 : 0.2 }} onAnimationComplete={() => panelHeading.current?.focus()}>
              <div className="ss-wizard-panel-heading">
                <span>0{step} / 04</span>
                <h2 ref={panelHeading} tabIndex={-1}>{['Project basics', 'Room dimensions', 'Design preferences', 'Photo & recommendations'][step - 1]}</h2>
                <p>{[
                  'Give your design a name and tell us the kind of room you want to create.',
                  'Accurate measurements help keep furniture in scale and circulation clear.',
                  'Choose a style and material direction for a cohesive interior.',
                  'Add a photo if you have one, preview a few layouts, then open your studio.',
                ][step - 1]}</p>
              </div>
              {panel}
            </motion.section>
          </AnimatePresence>
          {error && <p className="ss-wizard-error" role="alert">{error}</p>}
          <AnimatePresence>{launching && <DesignLoading key="studio-progress" message="Preparing your room for Studio…" />}</AnimatePresence>
          <div className="ss-wizard-actions">
            <button type="button" className="ss-wizard-back" onClick={() => moveTo(step - 1)} disabled={step === 1}>Back</button>
            {step < 4
              ? <button key="continue" type="button" className="ss-wizard-next" onClick={continueWizard}>Continue <span aria-hidden="true">→</span></button>
              : <button key="launch" type="button" className="ss-wizard-next" onClick={launchStudio} disabled={launching}>{launching ? 'Preparing your room…' : 'Open design studio'} <span aria-hidden="true">→</span></button>}
          </div>
        </form>
      </section>
      <p className="ss-wizard-footnote">You can refine furniture, layout, and budget in the Studio.</p>
    </div>
  </main>;
}
