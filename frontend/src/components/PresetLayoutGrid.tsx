import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { requestDesign } from '../api';
import { DesignLoading } from './DesignLoading';
import { ExpandableLayoutCard } from './ExpandableLayoutCard';
import type { RecommendationBundle, RoomPreset } from '../types';

type Props = { kind: 'featured' | 'lighting' };

export function PresetLayoutGrid({ kind }: Props) {
  const [presets, setPresets] = useState<RoomPreset[]>([]);
  const [bundles, setBundles] = useState<RecommendationBundle[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const abort = new AbortController();
    fetch('/api/presets', { signal: abort.signal })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'Could not load room ideas.');
        const rows = (data.presets || []) as RoomPreset[];
        const preferredRoom = kind === 'featured' ? 'living_room' : 'bedroom';
        const basePreset = rows.find((preset) => preset.room_type === preferredRoom) || rows[0];
        if (!basePreset) throw new Error('The room catalog has no presets yet.');
        setPresets([basePreset]);
        const recommendationResponse = await requestDesign('/api/recommendations', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: abort.signal,
          body: JSON.stringify({
            room_type: basePreset.room_type,
            width_ft: basePreset.room_width_m / 0.3048,
            length_ft: basePreset.room_length_m / 0.3048,
            budget_inr: basePreset.budget_inr,
            style: basePreset.style_tag,
          }),
        });
        const recommendationData = await recommendationResponse.json();
        if (!recommendationResponse.ok || !recommendationData.success) {
          throw new Error(recommendationData.error || 'Could not build room recommendations.');
        }
        const options = (recommendationData.bundles || []) as RecommendationBundle[];
        const safeOptions = options.filter((option) => option.validation?.valid && option.layout?.state_133d?.length === 133);
        if (!safeOptions.length) throw new Error('No layouts passed the room checks.');
        setBundles(safeOptions.slice(0, 6));
      })
      .catch((caught: unknown) => {
        if (!abort.signal.aborted) setError(caught instanceof Error ? caught.message : 'Could not load room ideas.');
      })
      .finally(() => { if (!abort.signal.aborted) setLoading(false); });
    return () => abort.abort();
  }, [kind]);

  if (loading) return <DesignLoading message="Preparing room ideas…" />;
  if (error) return <div className="ss-layout-grid-state" role="status">Room ideas are temporarily unavailable.</div>;
  if (!presets.length || !bundles.length) return <div className="ss-layout-grid-state">Design ideas will appear here when the catalog is ready.</div>;

  return (
    <motion.div className="ss-layout-grid" layout>
      {bundles.map((bundle, index) => <ExpandableLayoutCard key={`${kind}-${bundle.id}`} preset={presets[0]} bundle={bundle} index={index} />)}
    </motion.div>
  );
}
