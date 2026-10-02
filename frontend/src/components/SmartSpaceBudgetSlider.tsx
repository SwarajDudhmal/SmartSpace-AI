import { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';

const MIN_BUDGET = 20_000;
const MAX_BUDGET = 500_000;
const formatter = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 });

function getInitialBudget() {
  const liveBudget = Number(window.smartSpaceStudioBudget);
  if (Number.isFinite(liveBudget) && liveBudget > 0) return Math.min(MAX_BUDGET, Math.max(MIN_BUDGET, liveBudget));
  try {
    const stored = JSON.parse(localStorage.getItem('smartspace_studio_layout') || 'null');
    const budget = Number(stored?.budget);
    if (Number.isFinite(budget) && budget > 0) return Math.min(MAX_BUDGET, Math.max(MIN_BUDGET, budget));
  } catch { /* use the safe default */ }
  return 85_000;
}

export function SmartSpaceBudgetSlider() {
  const [budget, setBudget] = useState(getInitialBudget);

  useEffect(() => {
    const sync = (event: Event) => {
      const next = Number((event as CustomEvent<{ budget: number }>).detail?.budget);
      if (Number.isFinite(next)) setBudget(Math.min(MAX_BUDGET, Math.max(MIN_BUDGET, next)));
    };
    window.addEventListener('smartspace:budget-synced', sync);
    return () => window.removeEventListener('smartspace:budget-synced', sync);
  }, []);

  function updateBudget(nextValue: number) {
    const next = Math.min(MAX_BUDGET, Math.max(MIN_BUDGET, nextValue));
    setBudget(next);
    window.dispatchEvent(new CustomEvent('smartspace:budget-change', { detail: { budget: next } }));
  }

  const fill = ((budget - MIN_BUDGET) / (MAX_BUDGET - MIN_BUDGET)) * 100;

  return (
    <section className="ss-budget" aria-labelledby="ss-budget-title">
      <div className="ss-budget__heading">
        <div><span className="ss-budget__eyebrow">Budget limit</span><h3 id="ss-budget-title">Set your spend</h3></div>
        <output htmlFor="ss-budget-slider">₹{formatter.format(budget)}</output>
      </div>
      <input
        id="ss-budget-slider"
        className="ss-budget__range"
        type="range"
        min={MIN_BUDGET}
        max={MAX_BUDGET}
        step={5_000}
        value={budget}
        style={{ '--ss-budget-fill': `${fill}%` } as CSSProperties & { '--ss-budget-fill': string }}
        onChange={(event) => updateBudget(Number(event.currentTarget.value))}
        aria-label="Furniture budget in Indian rupees"
      />
      <div className="ss-budget__range-labels"><span>₹20,000</span><span>₹5,00,000</span></div>
      <p>Layout costs and recommendations update with your budget.</p>
    </section>
  );
}
