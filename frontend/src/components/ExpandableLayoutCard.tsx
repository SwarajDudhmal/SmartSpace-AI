import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { requestDesign } from '../api';
import type { LayoutLoadedDetail, RecommendationBundle, RoomPreset } from '../types';

type Props = {
  preset: RoomPreset;
  bundle: RecommendationBundle;
  index: number;
};

const numberINR = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 });
const displayRoom = (value: string) => (value || 'modern').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());

function roomToFeet(meters: number) {
  return (meters / 0.3048).toFixed(1);
}

export function ExpandableLayoutCard({ preset, bundle, index }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);

  async function loadIntoStudio() {
    setLoading(true);
    setError('');
    setLoaded(false);
    try {
      const response = await requestDesign('/api/recommendations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          room_type: preset.room_type,
          width_ft: roomToFeet(preset.room_width_m),
          length_ft: roomToFeet(preset.room_length_m),
          budget_inr: preset.budget_inr,
          style: preset.style_tag,
          variation_id: bundle.id,
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Could not generate a design for this room.');
      const bundles = Array.isArray(data.bundles) ? data.bundles : [];
      const chosen = data.selected_bundle || bundles.find((item: RecommendationBundle) => item.id === bundle.id);
      if (!chosen?.layout?.furniture?.length) throw new Error('The recommendation service returned no furniture layout.');
      if (!chosen.validation?.valid) throw new Error('This variation no longer passes the room safety checks. Choose another design.');

      const layout = chosen.layout;
      const state = layout.state_133d;
      if (!Array.isArray(state) || state.length !== 133) {
        throw new Error('This layout does not contain a valid 133-value studio state. Please try another preset.');
      }
      const detail: LayoutLoadedDetail = {
        layout: { ...layout, name: layout.name || preset.name, style: layout.style || preset.style_tag },
        bundle: chosen,
        source: 'homepage',
      };
      window.dispatchEvent(new CustomEvent<LayoutLoadedDetail>('smartspace:load-layout', { detail }));
      setLoaded(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not load this recommendation.');
    } finally {
      setLoading(false);
    }
  }

  const title = preset.name || `${displayRoom(preset.room_type)} layout`;
  const style = displayRoom(bundle.style || preset.style_tag || 'modern');

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, delay: Math.min(index * 0.045, 0.2) }}
      className={`ss-layout-card${expanded ? ' is-expanded' : ''}`}
    >
      <button className="ss-layout-card__toggle" type="button" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}>
        <span className="ss-layout-card__image-wrap">
          <img src={bundle.items.find((item) => item.style_tag === bundle.style)?.thumbnail_url || preset.thumbnail_url || '/static/images/interior-hero.jpg'} alt={`${style} ${displayRoom(preset.room_type)} inspiration`} loading="lazy" />
          <span className="ss-layout-card__style">{style}</span>
          <span className="ss-layout-card__expand" aria-hidden="true">{expanded ? '−' : '+'}</span>
        </span>
        <span className="ss-layout-card__copy">
          <span className="ss-layout-card__eyebrow">{displayRoom(preset.room_type)} · {bundle.validation.valid ? 'Verified layout' : 'Needs adjustment'}</span>
          <span className="ss-layout-card__title">{bundle.name || title}</span>
          <span className="ss-layout-card__description">{preset.description || 'A room plan selected from the SmartSpace design catalog.'}</span>
        </span>
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            className="ss-layout-card__details"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.24, ease: 'easeInOut' }}
          >
            <div className="ss-layout-card__metrics">
              <div><span>Estimated budget</span><strong>₹{numberINR.format(bundle.total_cost_inr || 0)}</strong></div>
              <div><span>A* circulation</span><strong>{Math.round((bundle.metrics?.circulation_ratio || 0) * 100)}% reachable</strong></div>
              <div><span>Room size</span><strong>{roomToFeet(preset.room_length_m)} × {roomToFeet(preset.room_width_m)} ft</strong></div>
            </div>
            <p className="ss-layout-card__budget-note">{style} · Budget limit ₹{numberINR.format(preset.budget_inr || 0)}</p>
            {error && <p className="ss-layout-card__error" role="alert">{error}</p>}
            {loaded && <p className="ss-layout-card__success" role="status">Recommendation ready. Opening it in the studio…</p>}
            <button className="ss-layout-card__action" type="button" onClick={loadIntoStudio} disabled={loading || !bundle.validation.valid}>
              {loading ? 'Building recommendation…' : bundle.validation.valid ? 'Load into Studio Editor' : 'Needs adjustment'} <span aria-hidden="true">→</span>
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.article>
  );
}
