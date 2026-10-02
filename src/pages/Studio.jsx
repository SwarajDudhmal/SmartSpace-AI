import React, { useState } from 'react';

/**
 * SmartSpace AI - Studio View (Progressive Disclosure)
 * Consolidates Current Plan, AI Controls, and Room Checks into a compact top status bar.
 * Moves Interior Design Notes into an accessible slide-over drawer toggled via "Design Insights".
 * Constrains the bottom Furniture Palette to h-64 to prevent 1080p viewport overflow.
 */
export default function Studio({
  layout,
  metrics,
  furniture,
  onUpdateLayout,
  onOptimize,
  onResetLayout,
  onExportSpec,
  canvasRef,
}) {
  // Controlled slide-over drawer state for Interior design notes
  const [isNotesOpen, setIsNotesOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('inventory');

  const ergonomicsScore = metrics?.ergonomics_score ?? 0;
  const collisionCount = metrics?.collision_count ?? 0;
  const circulationRatio = metrics?.circulation_ratio !== undefined ? Math.round(metrics.circulation_ratio * 100) : 100;
  const totalCost = metrics?.total_cost ?? 0;
  const budget = layout?.budget ?? 20000;
  const budgetPercent = Math.min(100, Math.round((totalCost / Math.max(1, budget)) * 100));

  return (
    <div className="flex flex-col h-screen w-full overflow-hidden bg-slate-50 text-slate-800 font-sans">
      {/* ── TOP CONSOLIDATED STATUS BAR ── */}
      <header className="flex-none h-14 px-5 bg-white/90 backdrop-blur-md border-b border-slate-200/80 shadow-xs flex items-center justify-between z-20">
        <div className="flex items-center gap-4">
          <div className="flex flex-col">
            <h1 className="text-sm font-bold text-slate-900 leading-tight">
              {layout?.name || 'Your Room'}
            </h1>
            <span className="text-[11px] text-slate-500">
              {layout?.room_type?.replace('_', ' ') || 'Living Room'} · {layout?.dimensions?.width || 12} × {layout?.dimensions?.length || 10} ft
            </span>
          </div>

          <div className="h-5 w-px bg-slate-200" aria-hidden="true" />

          {/* Unified "Layout Health" badge */}
          <div
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-xs"
            title="Unified ergonomic layout rating"
          >
            <span className="text-[10px] uppercase tracking-wider font-bold">Layout Health</span>
            <span className="text-sm font-extrabold">{ergonomicsScore}%</span>
            <span className="text-[10px] text-emerald-600 font-medium hidden sm:inline">
              · {circulationRatio}% A* reachable
            </span>
          </div>

          <div className="h-5 w-px bg-slate-200" aria-hidden="true" />

          {/* Inline Cost vs. Budget metric */}
          <div className="inline-flex items-center gap-2 text-xs text-slate-600 bg-slate-100/80 px-3 py-1 rounded-lg border border-slate-200/60">
            <span className="text-slate-500 font-medium">Cost / Budget:</span>
            <strong className="font-bold text-slate-900">
              ₹{totalCost.toLocaleString('en-IN')} / ₹{budget.toLocaleString('en-IN')}
            </strong>
            <div className="w-12 h-1.5 bg-slate-200 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-300 ${totalCost > budget ? 'bg-rose-500' : 'bg-emerald-500'}`}
                style={{ width: `${budgetPercent}%` }}
              />
            </div>
          </div>

          {/* Collision Indicator Chip */}
          <span
            className={`text-xs px-2 py-0.5 rounded-md font-medium ${
              collisionCount > 0
                ? 'bg-amber-100 text-amber-800 border border-amber-200'
                : 'bg-emerald-50 text-emerald-700'
            }`}
          >
            {collisionCount} {collisionCount === 1 ? 'collision' : 'collisions'}
          </span>
        </div>

        {/* AI Action Controls & Clean Design Insights Toggle */}
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={onOptimize}
            className="px-3 py-1.5 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 rounded-lg shadow-xs transition-colors flex items-center gap-1.5"
          >
            <span>Optimize layout</span>
            <span aria-hidden="true">→</span>
          </button>

          <button
            type="button"
            onClick={() => setIsNotesOpen(true)}
            aria-expanded={isNotesOpen}
            className="px-3 py-1.5 text-xs font-semibold text-emerald-800 bg-emerald-50 hover:bg-emerald-100 border border-emerald-300 rounded-lg shadow-xs transition-colors flex items-center gap-1.5"
          >
            <span aria-hidden="true">✦</span>
            <span>Design Insights</span>
          </button>

          <button
            type="button"
            onClick={onExportSpec}
            className="px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-900 bg-white hover:bg-slate-100 border border-slate-200 rounded-lg shadow-xs transition-colors"
          >
            Export ↓
          </button>
        </div>
      </header>

      {/* ── 2D CAD CANVAS VIEWPORT (EXPANDED TO FULL AVAILABLE HEIGHT) ── */}
      <main className="flex-1 relative bg-slate-100 overflow-hidden flex flex-col">
        <div className="absolute inset-0 flex items-center justify-center p-4">
          <div className="relative w-full h-full rounded-2xl bg-white border border-slate-200 shadow-sm overflow-hidden">
            {/* The 2D CAD canvas rendering pipeline attaches here */}
            <canvas ref={canvasRef} id="floorplanCanvas" className="w-full h-full block" />
          </div>
        </div>
      </main>

      {/* ── PRESERVED BOTTOM PALETTE (CONSTRAINED TO h-64, NO 1080p OVERFLOW) ── */}
      <footer className="flex-none h-64 bg-white border-t border-slate-200 shadow-lg flex flex-col z-10">
        <div className="flex items-center justify-between px-5 py-2.5 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <h2 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Furniture & room details
            </h2>
            <div className="flex items-center bg-slate-100 p-0.5 rounded-lg text-xs">
              <button
                type="button"
                onClick={() => setActiveTab('inventory')}
                className={`px-3 py-1 rounded-md font-medium transition-colors ${
                  activeTab === 'inventory' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                Room furniture ({furniture?.length || 0})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('catalog')}
                className={`px-3 py-1 rounded-md font-medium transition-colors ${
                  activeTab === 'catalog' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                Add furniture
              </button>
            </div>
          </div>
          <button
            type="button"
            onClick={onResetLayout}
            className="text-xs text-slate-500 hover:text-slate-800 font-medium"
          >
            ↺ Reset layout
          </button>
        </div>

        {/* Scrollable list content safely contained in h-64 */}
        <div className="flex-1 overflow-y-auto p-4">
          {activeTab === 'inventory' ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {furniture?.map((item) => (
                <div
                  key={item.id}
                  className="p-3 bg-slate-50 hover:bg-slate-100 border border-slate-200/80 rounded-xl text-xs flex items-center justify-between transition-colors"
                >
                  <div>
                    <strong className="block font-semibold text-slate-800">{item.label || item.type}</strong>
                    <span className="text-[11px] text-slate-500">
                      {item.width} × {item.depth} m · ₹{Number(item.cost || 0).toLocaleString('en-IN')}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-slate-500">Select items from catalog to place into floorplan.</div>
          )}
        </div>
      </footer>

      {/* ── COLLAPSIBLE SLIDE-OVER DRAWER (INTERIOR DESIGN NOTES) ── */}
      {isNotesOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-slate-900/30 backdrop-blur-xs transition-opacity animate-in fade-in"
            onClick={() => setIsNotesOpen(false)}
            aria-hidden="true"
          />

          <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
            <aside
              className="w-screen max-w-md bg-white border-l border-slate-200 shadow-2xl p-6 flex flex-col gap-5 overflow-y-auto animate-in slide-in-from-right duration-300"
              aria-label="Interior design notes and insights"
            >
              <div className="flex items-center justify-between pb-4 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <span className="text-emerald-600 text-lg">✦</span>
                  <h2 className="text-base font-bold text-slate-900">Interior design notes</h2>
                </div>
                <button
                  type="button"
                  onClick={() => setIsNotesOpen(false)}
                  className="w-8 h-8 rounded-lg border border-slate-200 text-slate-400 hover:text-slate-700 hover:bg-slate-50 flex items-center justify-center transition-colors"
                  aria-label="Close notes"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-4 text-xs">
                <div className="p-3 bg-emerald-50/70 border border-emerald-100 rounded-xl">
                  <h3 className="font-semibold text-emerald-900 mb-1">Room Palette & Style</h3>
                  <p className="text-emerald-700">
                    {layout?.style || 'Modern'} direction: Warm neutrals paired with balanced natural accents.
                  </p>
                </div>

                <div className="space-y-2">
                  <h3 className="font-semibold text-slate-900 uppercase tracking-wider text-[11px]">
                    Layout principles
                  </h3>
                  <ul className="space-y-2 text-slate-600">
                    <li className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
                      <strong className="block text-slate-800">A* walking path:</strong> Keep the main route clear from the entrance.
                    </li>
                    <li className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
                      <strong className="block text-slate-800">Door clearance:</strong> Maintain door swing radius without obstruction.
                    </li>
                    <li className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
                      <strong className="block text-slate-800">Daylight exposure:</strong> Avoid placing tall wardrobes across window walls.
                    </li>
                    <li className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
                      <strong className="block text-slate-800">Wall alignment:</strong> Anchor major items flush with primary bounding walls.
                    </li>
                  </ul>
                </div>
              </div>
            </aside>
          </div>
        </div>
      )}
    </div>
  );
}
