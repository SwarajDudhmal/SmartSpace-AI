/**
 * SmartSpace AI - Main Application Controller
 * Handles custom user room loading from /room-details,
 * Interactive furniture inventory management (Add, Rotate, Snap, Delete),
 * 2D Canvas & 3D WebGL synchronization, and DQN Layout AI animation.
 */

document.addEventListener('DOMContentLoaded', () => {
  let floorplanCanvas = null;
  let room3D = null;
  let currentLayout = null;
  let currentViewMode = '2d';
  let isOptimizing = false;
  let evaluationVersion = 0;
  let replacementItemId = null;

  // UI Element References
  const canvasElement = document.getElementById('floorplanCanvas');
  const threejsContainer = document.getElementById('threejsContainer');
  const dqnOptimizeBtn = document.getElementById('dqnOptimizeBtn');
  const resetLayoutBtn = document.getElementById('resetLayoutBtn');
  const exportSpecBtn = document.getElementById('exportSpecBtn');
  const exportPngBtn = document.getElementById('exportPngBtn');
  const actionLog = document.getElementById('actionLog');
  const detectedThumbImg = document.getElementById('detectedThumbImg');

  // Metric Displays
  const metricScore = document.getElementById('metricScore');
  const metricCollisions = document.getElementById('metricCollisions');
  const metricCirculation = document.getElementById('metricCirculation');
  const metricCost = document.getElementById('metricCost');
  const budgetBar = document.getElementById('budgetProgressBar');
  const budgetRatioText = document.getElementById('budgetRatioText');
  const ergonomicsStatus = document.getElementById('ergonomicsStatus');
  const recommendationPalette = document.getElementById('recommendationPalette');
  const recommendationList = document.getElementById('recommendationList');

  // Canvas View Controls
  const zoomInBtn = document.getElementById('zoomInBtn');
  const zoomOutBtn = document.getElementById('zoomOutBtn');
  const resetViewBtn = document.getElementById('resetViewBtn');
  const toggleWalkways = document.getElementById('toggleWalkways');
  const toggleClearances = document.getElementById('toggleClearances');

  // Initialize Canvas & 3D Viewer
  floorplanCanvas = new FloorplanCanvas('floorplanCanvas', (newLayout, eventType) => {
    onLayoutManuallyUpdated(newLayout, eventType);
  });

  room3D = new Room3DViewer('threejsContainer');

  function setActionLog(label, message, tone = 'cyan') {
    if (!actionLog) return;
    actionLog.replaceChildren();
    const badge = document.createElement('span');
    badge.className = `badge ${tone}`;
    badge.textContent = label;
    actionLog.append(badge, document.createTextNode(` ${message}`));
  }

  function mergeRoomLayout(layout) {
    const previous = currentLayout || {};
    return {
      ...previous,
      ...layout,
      name: layout?.name || previous.name,
      style: layout?.style || previous.style,
      annotated_image: layout?.annotated_image === undefined ? previous.annotated_image : layout.annotated_image,
      projectId: layout?.projectId || previous.projectId,
      projectName: layout?.projectName || previous.projectName
    };
  }

  function renderRoomPhoto() {
    const empty = document.getElementById('roomPhotoEmpty');
    const status = document.getElementById('visionPreviewStatus');
    const noUpload = currentLayout?.photo_uploaded === false || currentLayout?.vision_fallback_reason === 'No photo was uploaded.';
    // A legacy annotation without upload provenance may be a demo image.
    const photo = noUpload ? null : (currentLayout?.room_photo || (currentLayout?.photo_uploaded === true ? currentLayout.annotated_image : null));
    if (detectedThumbImg) {
      detectedThumbImg.hidden = !photo;
      if (photo) {
        detectedThumbImg.src = photo;
        detectedThumbImg.alt = `Uploaded room photo for ${currentLayout.name || 'this project'}`;
      } else {
        detectedThumbImg.removeAttribute('src');
      }
    }
    if (empty) {
      empty.hidden = Boolean(photo);
      empty.textContent = currentLayout?.photo_uploaded
        ? 'The uploaded photo preview is unavailable. Upload a valid JPG or PNG in Step 4.'
        : 'No photo was uploaded for this project. Add your room photo in Step 4 when creating a project.';
    }
    if (status) {
      status.textContent = !photo ? '' : currentLayout.vision_detected_count > 0
        ? `${currentLayout.vision_detected_count} objects detected in your uploaded photo.`
        : currentLayout.vision_fallback_reason || 'Your uploaded room photo.';
      status.classList.toggle('model-unavailable', Boolean(photo && currentLayout.vision_fallback_reason));
    }
  }

  function persistStudioLayout() {
    try {
      localStorage.setItem('smartspace_studio_layout', JSON.stringify(currentLayout));
    } catch (error) {
      const compactLayout = { ...currentLayout };
      delete compactLayout.annotated_image;
      try {
        localStorage.setItem('smartspace_studio_layout', JSON.stringify(compactLayout));
      } catch (storageError) {
        console.warn('This browser could not persist the latest studio layout.', storageError);
        try {
          sessionStorage.setItem('smartspace_studio_layout', JSON.stringify(compactLayout));
        } catch (_sessionError) {
          // The current editing session remains usable even when browser storage is disabled.
        }
      }
    }
  }

  function readSavedRoom(key) {
    try {
      const localValue = localStorage.getItem(key);
      if (localValue) return localValue;
    } catch (_localError) {
      // Use tab-scoped storage when persistent browser storage is unavailable.
    }
    try {
      return sessionStorage.getItem(key);
    } catch (_sessionError) {
      return null;
    }
  }

  async function updateSystemStatus() {
    try {
      const response = await fetch('/api/system-status');
      const status = await response.json();
      if (!response.ok || !status.success) throw new Error('Model status is unavailable.');
      const vision = status.vision;
      const optimizer = status.optimizer;
      const visionText = vision.available ? `Vision · ${vision.backend}` : 'Vision · weights needed';
      const optimizerText = optimizer.trained
        ? `Optimizer · trained ${optimizer.backend}`
        : `Optimizer · spatial search (${optimizer.backend})`;
      const visionBadge = document.getElementById('visionHeaderBadge');
      const optimizerBadge = document.getElementById('optimizerHeaderBadge');
      const optimizerDetail = document.getElementById('optimizerModelBadge');
      if (visionBadge) visionBadge.textContent = `👁 ${visionText}`;
      if (optimizerBadge) optimizerBadge.textContent = `🧠 ${optimizerText}`;
      if (optimizerDetail) optimizerDetail.textContent = optimizer.mode;
      renderRoomPhoto();
    } catch (error) {
      console.error('Could not load model status:', error);
      renderRoomPhoto();
    }
  }

  // -------------------------------------------------------------
  // Load Room Data: Check LocalStorage (from /room-details) First!
  // -------------------------------------------------------------
  async function initializeRoom(restoreSavedLayout = true) {
    const resumeId = new URLSearchParams(window.location.search).get('resume');
    if (resumeId && /^\d+$/.test(resumeId)) {
      try {
        const response = await fetch(`/api/project-history/${resumeId}`);
        const data = await response.json();
        if (response.status === 401) {
          window.location.assign(`/login?next=${encodeURIComponent(`/studio?resume=${resumeId}`)}`);
          return;
        }
        if (!response.ok || !data.success || !data.project?.layout) throw new Error(data.error || 'Saved project could not be restored.');
        currentLayout = data.project.layout;
        currentLayout.history_id = data.project.id;
        currentLayout.state_133d = data.project.state_133d;
        window.smartSpaceMdpState = data.project.state_133d;
        window.dispatchEvent(new CustomEvent('smartspace:mdp-state', {
          detail: { state: data.project.state_133d, source: 'project-history' }
        }));
        updateStudioLayout(currentLayout);
        updateRoomHeaders(currentLayout);
        persistStudioLayout();
        await evaluateLayout(currentLayout);
        setActionLog('RESUMED', `${currentLayout.name || data.project.project_name} restored from My Projects.`, 'emerald');
        window.history.replaceState({}, document.title, '/studio');
        return;
      } catch (error) {
        console.error('Saved project could not be restored:', error);
        setActionLog('ERROR', error.message || 'Saved project could not be restored.', 'amber');
        return;
      }
    }
    const requestedPreset = new URLSearchParams(window.location.search).get('preset');
    if (requestedPreset) {
      try { sessionStorage.removeItem('smartspace_pending_layout'); } catch (_storageError) { }
      try {
        const response = await fetch(`/api/presets/${encodeURIComponent(requestedPreset)}`);
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'Preset could not be loaded.');
        currentLayout = data.preset;
        updateStudioLayout(currentLayout);
        updateRoomHeaders(currentLayout);
        persistStudioLayout();
        await evaluateLayout(currentLayout);
        setActionLog('PRESET', `${currentLayout.name} loaded from the homepage.`, 'emerald');
        window.history.replaceState({}, document.title, '/studio');
        return;
      } catch (error) {
        console.error('Database preset load failed:', error);
        setActionLog('ERROR', error.message || 'Could not load that room preset.', 'amber');
      }
    }
    // The wizard handoff belongs to this tab, not an old persistent draft.
    let pendingRecommendation = null;
    try { pendingRecommendation = sessionStorage.getItem('smartspace_pending_layout'); } catch (_storageError) { }
    if (pendingRecommendation) {
      try {
        const layout = JSON.parse(pendingRecommendation);
        sessionStorage.removeItem('smartspace_pending_layout');
        window.dispatchEvent(new CustomEvent('smartspace:load-layout', {
          detail: { layout, source: 'homepage' }
        }));
        return;
      } catch (_error) {
        try { sessionStorage.removeItem('smartspace_pending_layout'); } catch (_storageError) { }
      }
    }
    const storedRoom = (restoreSavedLayout && readSavedRoom('smartspace_studio_layout'))
      || readSavedRoom('smartspace_current_room');
    if (storedRoom) {
      try {
        const parsed = JSON.parse(storedRoom);
        currentLayout = parsed;
        updateStudioLayout(currentLayout);
        evaluateLayout(currentLayout);
        updateRoomHeaders(currentLayout);
        setActionLog('READY', `${currentLayout.name || 'Room'} is ready to edit.`, 'emerald');
        return;
      } catch (e) {
        console.error('Failed to parse stored room:', e);
        try { localStorage.removeItem('smartspace_studio_layout'); } catch (_error) { }
        try { sessionStorage.removeItem('smartspace_studio_layout'); } catch (_error) { }
      }
    }
    // A new visitor must provide their own room inputs before opening Studio.
    window.location.replace('/create-project');
  }

  function updateRoomHeaders(layout) {
    const nameEl = document.getElementById('studioRoomName');
    const metaEl = document.getElementById('studioRoomMeta');
    const w = layout.room_width || layout.dimensions?.width || 4.8;
    const l = layout.room_length || layout.dimensions?.length || 4.0;
    const wFt = (w / 0.3048).toFixed(1);
    const lFt = (l / 0.3048).toFixed(1);
    const budgetVal = layout.budget || 20000;

    window.smartSpaceStudioBudget = Number(budgetVal);
    window.dispatchEvent(new CustomEvent('smartspace:budget-synced', {
      detail: { budget: Number(budgetVal) }
    }));

    if (nameEl) nameEl.textContent = layout.name || 'Custom Studio Room';
    if (metaEl) {
      metaEl.textContent = `Dimensions: ${lFt} ft × ${wFt} ft (${l.toFixed(2)}m × ${w.toFixed(2)}m) · Budget: ₹${budgetVal.toLocaleString()} · Style: ${layout.style || 'Modern'}`;
    }
  }

  async function loadRoomPreset(presetId) {
    try {
      const res = await fetch('/api/sample-rooms');
      const data = await res.json();
      if (data.success && data.rooms[presetId]) {
        currentLayout = data.rooms[presetId];
        updateStudioLayout(currentLayout);
        evaluateLayout(currentLayout);
        updateRoomHeaders(currentLayout);
        setActionLog('PRESET', `Loaded ${currentLayout.name}.`);
      }
    } catch (err) {
      console.error('Failed to load preset:', err);
      setActionLog('ERROR', 'Could not load the sample room. Refresh and try again.', 'amber');
    }
  }

  function updateStudioLayout(layout, replace = false) {
    evaluationVersion += 1;
    currentLayout = replace ? { ...layout } : mergeRoomLayout(layout);
    renderRoomPhoto();
    floorplanCanvas.setLayout(currentLayout);
    currentLayout.furniture = floorplanCanvas.furniture.map(item => ({ ...item }));
    if (room3D && currentViewMode === '3d') {
      room3D.updateLayout(currentLayout);
    }
    updateInventoryList(currentLayout.furniture);
  }

  function updateMetricsUI(metrics) {
    if (!metrics) return;

    const score = metrics.ergonomics_score || 0;
    if (metricScore) {
      metricScore.textContent = `${score}%`;
      metricScore.className = score >= 80 ? 'metric-value emerald' : (score >= 50 ? 'metric-value cyan' : 'metric-value amber');
    }

    if (ergonomicsStatus) {
      if (score >= 90) ergonomicsStatus.textContent = '🌟 Optimal Ergonomic Layout';
      else if (score >= 70) ergonomicsStatus.textContent = '✅ Good Circulation & Clearance';
      else if (metrics.collision_count > 0) ergonomicsStatus.textContent = '⚠️ Furniture Intersections Detected';
      else ergonomicsStatus.textContent = '⚡ Needs Circulation Optimization';
    }

    if (metricCollisions) {
      metricCollisions.textContent = metrics.collision_count || 0;
      metricCollisions.className = (metrics.collision_count > 0) ? 'metric-value amber' : 'metric-value emerald';
    }

    if (metricCirculation) {
      const ratio = metrics.circulation_ratio !== undefined ? (metrics.circulation_ratio * 100).toFixed(0) : 100;
      metricCirculation.textContent = `${ratio}%`;
    }

    const cost = metrics.total_cost || 0;
    const maxBudget = currentLayout?.budget || 20000;
    if (metricCost) {
      metricCost.textContent = `₹${cost.toLocaleString()}`;
    }

    if (budgetBar) {
      const pct = Math.min(100, (cost / Math.max(1, maxBudget)) * 100);
      budgetBar.style.width = `${pct}%`;
      budgetBar.style.backgroundColor = cost > maxBudget ? '#ef4444' : '#10b981';
    }

    if (budgetRatioText) {
      budgetRatioText.textContent = `₹${cost.toLocaleString()} / ₹${maxBudget.toLocaleString()}`;
    }
  }

  function updateDesignRecommendations(advice) {
    if (!recommendationList || !advice) return;
    if (recommendationPalette) {
      recommendationPalette.textContent = `${advice.style || 'Modern'} palette: ${advice.palette_summary || 'warm neutrals with a considered accent'}`;
    }

    recommendationList.replaceChildren();
    (advice.recommendations || []).forEach((item) => {
      const card = document.createElement('article');
      card.className = 'recommendation-card';

      const category = document.createElement('span');
      category.className = 'recommendation-category';
      category.textContent = item.category || 'Design';

      const title = document.createElement('h3');
      title.textContent = item.title || 'Design suggestion';

      const detail = document.createElement('p');
      detail.textContent = item.detail || '';

      card.append(category, title, detail);
      recommendationList.append(card);
    });
  }

  async function evaluateLayout(layout) {
    const version = ++evaluationVersion;
    try {
      const res = await fetch('/api/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(layout)
      });
      const data = await res.json();
      if (version !== evaluationVersion) return;
      if (data.success && data.metrics) {
        updateMetricsUI(data.metrics);
        updateDesignRecommendations(data.design_advice);
        if (Array.isArray(data.state_133d) && data.state_133d.length === 133 && currentLayout) {
          currentLayout.state_133d = data.state_133d;
          window.smartSpaceMdpState = data.state_133d;
          window.dispatchEvent(new CustomEvent('smartspace:mdp-state', {
            detail: { state: data.state_133d }
          }));
        }
        if (currentLayout && data.design_advice) {
          currentLayout.design_advice = data.design_advice;
          persistStudioLayout();
        }
        if (data.metrics.paths) {
          floorplanCanvas.setPaths(data.metrics.paths);
        }
      }
    } catch (err) {
      console.error('Failed to evaluate layout:', err);
    }
  }

  window.addEventListener('smartspace:load-layout', async (event) => {
    if (isOptimizing) return;
    const incoming = event.detail?.layout || event.detail;
    if (!incoming || !Array.isArray(incoming.furniture)) return;

    updateStudioLayout(incoming, event.detail?.source !== 'recommendation-modal');
    updateRoomHeaders(currentLayout);
    persistStudioLayout();
    setActionLog('DESIGN', `${currentLayout.name || 'Recommended layout'} loaded into the studio.`, 'emerald');
    await evaluateLayout(currentLayout);
  });

  window.addEventListener('smartspace:budget-change', async (event) => {
    if (!currentLayout || isOptimizing) return;
    const requestedBudget = Number(event.detail?.budget);
    if (!Number.isFinite(requestedBudget)) return;
    currentLayout.budget = Math.min(500000, Math.max(20000, Math.round(requestedBudget)));
    updateRoomHeaders(currentLayout);
    persistStudioLayout();
    setActionLog('BUDGET', `Limit updated to ₹${currentLayout.budget.toLocaleString('en-IN')}.`, 'emerald');
    await evaluateLayout(currentLayout);
  });

  function onLayoutManuallyUpdated(newLayout, eventType) {
    currentLayout = mergeRoomLayout(newLayout);
    persistStudioLayout();
    updateRoomHeaders(currentLayout);
    if (room3D && currentViewMode === '3d') {
      room3D.updateLayout(currentLayout);
    }
    evaluateLayout(currentLayout);
    updateInventoryList(currentLayout.furniture);
  }

  // -------------------------------------------------------------
  // React inventory handoff (select, rotate, swap, delete).
  // -------------------------------------------------------------
  function updateInventoryList(furniture) {
    if (replacementItemId && !furniture.some(item => item.id === replacementItemId)) setReplacementTarget(null);
    const snapshot = {
      items: furniture.map(item => ({ ...item, color: floorplanCanvas.colorMap[item.type] || '#347b58' })),
      selectedId: floorplanCanvas.selectedItem?.id,
      disabled: isOptimizing,
    };
    window.smartSpaceFurnitureInventory = snapshot;
    window.dispatchEvent(new CustomEvent('smartspace:furniture-updated', { detail: snapshot }));
  }

  function setReplacementTarget(id) {
    replacementItemId = id;
    const item = floorplanCanvas.furniture.find(candidate => candidate.id === id);
    const hint = document.getElementById('catalogActionHint');
    if (hint) hint.textContent = item
      ? `Choose a replacement for ${item.label || item.type}.`
      : 'Choose an item to add it to your plan';
    const cancel = document.getElementById('cancelFurnitureSwap');
    if (cancel) cancel.hidden = !item;
    document.querySelectorAll('.catalog-add-btn').forEach(button => {
      button.textContent = item ? '⇄ Swap into room' : '＋ Add to room';
    });
  }

  window.addEventListener('smartspace:request-furniture', () => updateInventoryList(floorplanCanvas.furniture));
  window.addEventListener('smartspace:furniture-action', (event) => {
    if (isOptimizing) return;
    const { action, id } = event.detail || {};
    const item = floorplanCanvas.furniture.find(candidate => candidate.id === id);
    if (!item) return;
    if (action === 'select') {
      floorplanCanvas.selectedItem = item;
      floorplanCanvas.render();
      updateInventoryList(floorplanCanvas.furniture);
    } else if (action === 'rotate') {
      floorplanCanvas.rotateFurniture(id, 90);
    } else if (action === 'delete') {
      floorplanCanvas.removeFurniture(id);
    } else if (action === 'swap') {
      setReplacementTarget(id);
      document.querySelector('[data-subtab="subtab-catalog"]')?.click();
    }
  });
  document.getElementById('cancelFurnitureSwap')?.addEventListener('click', () => setReplacementTarget(null));

  // Add Item From Catalog
  document.querySelectorAll('.catalog-add-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (isOptimizing) return;
      const type = btn.getAttribute('data-type');
      const w = parseFloat(btn.getAttribute('data-w') || 1.2);
      const d = parseFloat(btn.getAttribute('data-d') || 0.8);
      const cost = parseFloat(btn.getAttribute('data-cost') || 2500);
      const label = btn.getAttribute('data-label') || type.toUpperCase();

      const replacement = {
        type: type,
        width: w,
        depth: d,
        cost: cost,
        label: label,
        height: window.smartSpaceFurnitureSpecs?.[type]?.height || 0.8,
        preferred_wall: ['bed', 'wardrobe', 'desk', 'tv', 'cabinet'].includes(type)
      };

      const target = floorplanCanvas.furniture.find(item => item.id === replacementItemId);
      if (target) {
        Object.assign(target, replacement);
        floorplanCanvas.selectedItem = target;
        setReplacementTarget(null);
        floorplanCanvas.render();
        onLayoutManuallyUpdated(floorplanCanvas.getCurrentLayout(), 'replace');
        document.querySelector('[data-subtab="subtab-inventory"]')?.click();
        setActionLog('SWAPPED', `${label} replaced the selected furniture.`);
        return;
      }

      floorplanCanvas.addFurniture(replacement);

      if (actionLog) {
        setActionLog('ADDED', `${label} added to the room.`);
      }
    });
  });

  // -------------------------------------------------------------
  // Viewport Controls & Canvas Tools
  // -------------------------------------------------------------
  if (zoomInBtn) zoomInBtn.addEventListener('click', () => floorplanCanvas.zoomIn());
  if (zoomOutBtn) zoomOutBtn.addEventListener('click', () => floorplanCanvas.zoomOut());
  if (resetViewBtn) resetViewBtn.addEventListener('click', () => floorplanCanvas.resetView());

  if (toggleWalkways) {
    toggleWalkways.addEventListener('change', (e) => {
      floorplanCanvas.showWalkways = e.target.checked;
      floorplanCanvas.render();
    });
  }

  if (toggleClearances) {
    toggleClearances.addEventListener('change', (e) => {
      floorplanCanvas.showClearances = e.target.checked;
      floorplanCanvas.render();
    });
  }

  // 2D / 3D View Mode Toggle
  document.querySelectorAll('.view-mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const mode = btn.getAttribute('data-mode');
      document.querySelectorAll('.view-mode-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      currentViewMode = mode;
      if (mode === '2d') {
        canvasElement.style.display = 'block';
        threejsContainer.style.display = 'none';
        const fallback = document.getElementById('threejsFallback');
        if (fallback) fallback.hidden = true;
        floorplanCanvas.resizeCanvas();
      } else {
        canvasElement.style.display = 'none';
        threejsContainer.style.display = 'block';
        if (room3D && !room3D.available) room3D.showFallback();
        if (room3D?.available && currentLayout) {
          room3D.onResize();
          room3D.updateLayout(currentLayout);
        }
      }
    });
  });

  // -------------------------------------------------------------
  // DQN Layout Optimization Animation
  // -------------------------------------------------------------
  if (dqnOptimizeBtn) {
    dqnOptimizeBtn.addEventListener('click', async () => {
      if (isOptimizing || !currentLayout) return;
      isOptimizing = true;
      evaluationVersion += 1;
      floorplanCanvas.interactionDisabled = true;
      floorplanCanvas.draggedItem = null;
      updateInventoryList(floorplanCanvas.furniture);
      const controls = [...document.querySelectorAll('.catalog-add-btn, #resetLayoutBtn, #openRecommendationsBtn, #generateRecommendationsBtn, #saveProjectBtn, #ss-budget-slider')];
      const disabledBefore = controls.map(control => control.disabled);
      controls.forEach(control => { control.disabled = true; });
      dqnOptimizeBtn.disabled = true;
      dqnOptimizeBtn.innerHTML = '<span>Optimizing layout…</span>';

      try {
        const res = await window.smartspaceFetch('/api/optimize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(currentLayout)
        });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.error || 'The layout could not be optimized.');
        if (data.validation?.valid !== true || data.comfort?.valid !== true || (data.final_layout?.metrics?.collision_count ?? 0) !== 0
          || !Array.isArray(data.final_layout?.state_133d) || data.final_layout.state_133d.length !== 133) {
          throw new Error('The optimizer returned an unvalidated layout. Your plan has not been replaced.');
        }
        
        if (data.success && data.trajectory) {
          await playTrajectoryAnimation(data.trajectory);
          updateStudioLayout(data.final_layout);
          window.smartSpaceMdpState = data.final_layout.state_133d;
          window.dispatchEvent(new CustomEvent('smartspace:mdp-state', { detail: { state: data.final_layout.state_133d, source: 'optimizer' } }));
          updateMetricsUI(data.final_layout.metrics);
          updateRoomHeaders(currentLayout);
          persistStudioLayout();
          await evaluateLayout(currentLayout);
          setActionLog(data.optimizer_trained ? 'DQN' : 'LAYOUT',
            'Layout complete: no collisions; viewing directions, usable furniture access and 0.75 m walking routes checked.',
            'emerald');
        }
      } catch (err) {
        console.error('DQN optimization failed:', err);
        setActionLog('ERROR', err.message || 'The optimizer is unavailable. Try again.', 'amber');
      } finally {
        isOptimizing = false;
        floorplanCanvas.interactionDisabled = false;
        controls.forEach((control, index) => { control.disabled = disabledBefore[index]; });
        updateInventoryList(floorplanCanvas.furniture);
        dqnOptimizeBtn.disabled = false;
        dqnOptimizeBtn.innerHTML = '<span>Optimize layout</span>';
      }
    });
  }

  async function playTrajectoryAnimation(trajectory) {
    for (let frame of trajectory) {
      updateStudioLayout(frame.layout);
      updateMetricsUI(frame.layout.metrics);
      if (actionLog) {
        setActionLog(`STEP ${frame.step}`, `${frame.action_desc} · Score ${frame.score}%`, 'purple');
      }
      await new Promise(r => setTimeout(r, 85));
    }
  }

  // Reset Layout
  if (resetLayoutBtn) {
    resetLayoutBtn.addEventListener('click', () => {
      if (isOptimizing) return;
      try { localStorage.removeItem('smartspace_studio_layout'); } catch (_error) { }
      try { sessionStorage.removeItem('smartspace_studio_layout'); } catch (_error) { }
      initializeRoom(false);
    });
  }

  const saveProjectBtn = document.getElementById('saveProjectBtn');
  if (saveProjectBtn) {
    saveProjectBtn.addEventListener('click', async () => {
      if (!currentLayout || isOptimizing) return;
      saveProjectBtn.disabled = true;
      saveProjectBtn.textContent = 'Saving design…';
      try {
        const response = await fetch('/api/project-history', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            layout: currentLayout,
            history_id: currentLayout.history_id || null,
            project_id: currentLayout.projectId || null,
            project_name: currentLayout.projectName || currentLayout.name || 'My SmartSpace design'
          })
        });
        const data = await response.json();
        if (response.status === 401) {
          setActionLog('SIGN IN', 'Sign in to keep this design in My Projects.', 'amber');
          return;
        }
        if (!response.ok || !data.success) throw new Error(data.error || 'This design could not be saved.');
        currentLayout.history_id = data.project.id;
        currentLayout.state_133d = data.state_133d;
        persistStudioLayout();
        setActionLog('SAVED', 'Design saved to My Projects. You can resume it any time.', 'emerald');
      } catch (error) {
        setActionLog('ERROR', error.message || 'This design could not be saved.', 'amber');
      } finally {
        saveProjectBtn.disabled = false;
        saveProjectBtn.textContent = 'Save this design';
      }
    });
  }

  // Progressive disclosure: Design Insights slide-over drawer state
  let isNotesOpen = false;
  const toggleNotesBtn = document.getElementById('toggleNotesBtn');
  const notesDrawer = document.getElementById('notesSlideOverDrawer');
  const closeNotesDrawerBtn = document.getElementById('closeNotesDrawerBtn');
  const notesDrawerBackdrop = document.getElementById('notesDrawerBackdrop');

  function setNotesOpen(open) {
    isNotesOpen = Boolean(open);
    if (notesDrawer) {
      if (isNotesOpen) {
        notesDrawer.hidden = false;
        requestAnimationFrame(() => {
          notesDrawer.classList.add('is-open');
          notesDrawer.setAttribute('aria-hidden', 'false');
        });
      } else {
        notesDrawer.classList.remove('is-open');
        notesDrawer.setAttribute('aria-hidden', 'true');
        setTimeout(() => {
          if (!isNotesOpen) notesDrawer.hidden = true;
        }, 300);
      }
    }
    if (toggleNotesBtn) {
      toggleNotesBtn.setAttribute('aria-expanded', String(isNotesOpen));
      toggleNotesBtn.classList.toggle('active', isNotesOpen);
    }
  }

  if (toggleNotesBtn) {
    toggleNotesBtn.addEventListener('click', () => setNotesOpen(!isNotesOpen));
  }
  if (closeNotesDrawerBtn) {
    closeNotesDrawerBtn.addEventListener('click', () => setNotesOpen(false));
  }
  if (notesDrawerBackdrop) {
    notesDrawerBackdrop.addEventListener('click', () => setNotesOpen(false));
  }

  updateSystemStatus();

  // Export Specification (.txt)
  if (exportSpecBtn) {
    exportSpecBtn.addEventListener('click', async () => {
      if (!currentLayout) return;
      try {
        const res = await fetch('/api/export-spec', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ layout: currentLayout })
        });
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${(currentLayout.name || 'room').toLowerCase().replace(/\s+/g, '_')}_spec.txt`;
        document.body.appendChild(a);
        a.click();
        a.remove();
      } catch (err) {
        console.error('Export failed:', err);
      }
    });
  }

  // Export Floorplan Snapshot (.png)
  if (exportPngBtn) {
    exportPngBtn.addEventListener('click', () => {
      const dataUrl = floorplanCanvas.exportImage();
      const a = document.createElement('a');
      a.href = dataUrl;
      a.download = `${(currentLayout.name || 'room').toLowerCase().replace(/\s+/g, '_')}_floorplan.png`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    });
  }

  // Initialize
  initializeRoom();
});
