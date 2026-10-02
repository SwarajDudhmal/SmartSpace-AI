/* Accessible recommendation overlay shared by the Studio and room form. */
(() => {
  const dialog = document.getElementById('recommendationDialog');
  const openButton = document.getElementById('openRecommendationsBtn');
  if (!dialog || !openButton) return;

  const closeButton = document.getElementById('closeRecommendationsBtn');
  const generateButton = document.getElementById('generateRecommendationsBtn');
  const results = document.getElementById('recommendationBundleResults');
  const error = document.getElementById('recommendationRequestError');
  const engineStatus = document.getElementById('recommendationEngineStatus');
  const byId = (id) => document.getElementById(id);

  function readLayout() {
    for (const key of ['smartspace_studio_layout', 'smartspace_current_room']) {
      try {
        const value = localStorage.getItem(key) || sessionStorage.getItem(key);
        if (value) return JSON.parse(value);
      } catch (_error) { /* Invalid/stale browser state is ignored. */ }
    }
    return null;
  }

  function canonicalRoom(layout) {
    const name = String(layout?.room_type || layout?.roomType || '').toLowerCase();
    if (name.includes('bed')) return 'bedroom';
    if (name.includes('office') || name.includes('work')) return 'home_office';
    if (name.includes('dining')) return 'dining_room';
    if (name.includes('kitchen')) return 'kitchen';
    if (name.includes('bath')) return 'bathroom';
    return 'living_room';
  }

  function openPicker() {
    const layout = readLayout();
    if (layout) {
      byId('recommendationRoomType').value = canonicalRoom(layout);
      byId('recommendationWidth').value = ((layout.room_width || layout.dimensions?.width || 4.8) / 0.3048).toFixed(1);
      byId('recommendationLength').value = ((layout.room_length || layout.dimensions?.length || 4.0) / 0.3048).toFixed(1);
      byId('recommendationBudget').value = layout.budget || 85000;
      const style = String(layout.style || 'modern').toLowerCase();
      byId('recommendationStyle').value = [...byId('recommendationStyle').options].some((option) => option.value === style) ? style : 'modern';
    }
    results.replaceChildren();
    error.hidden = true;
    engineStatus.textContent = '';
    dialog.hidden = false;
    dialog.setAttribute('aria-hidden', 'false');
    generateButton.focus();
  }

  function closePicker() {
    dialog.hidden = true;
    dialog.setAttribute('aria-hidden', 'true');
    openButton.focus();
  }

  function render(data) {
    results.replaceChildren();
    engineStatus.textContent = data.active_generator === 'trained_dqn'
      ? 'Generator: trained DQN · every layout is validated by spatial rules.'
      : 'Generator: curated room presets · no trained layout checkpoint is installed. SAT and A* validate the candidate layouts.';
    for (const bundle of data.bundles || []) {
      const card = document.createElement('article');
      card.className = 'recommendation-bundle-card';
      const header = document.createElement('div');
      header.className = 'recommendation-bundle-head';
      const title = document.createElement('h3');
      title.textContent = bundle.name;
      const badge = document.createElement('span');
      badge.className = bundle.validation?.valid ? 'bundle-valid' : 'bundle-review';
      badge.textContent = bundle.validation?.valid ? 'SAT + A* validated' : 'Needs layout adjustment';
      header.append(title, badge);

      const metrics = document.createElement('p');
      metrics.className = 'recommendation-bundle-metrics';
      metrics.textContent = `₹${Number(bundle.total_cost_inr || 0).toLocaleString('en-IN')} · ${bundle.budget_used_percent || 0}% budget · ${Math.round((bundle.metrics?.circulation_ratio || 0) * 100)}% A* reachability · ${bundle.metrics?.collision_count || 0} SAT collisions`;
      const products = document.createElement('ul');
      products.className = 'recommendation-product-list';
      (bundle.items || []).forEach((item) => {
        const row = document.createElement('li');
        row.textContent = `${item.name} · ₹${Number(item.base_cost_inr || 0).toLocaleString('en-IN')}`;
        products.append(row);
      });
      const note = document.createElement('p');
      note.className = 'recommendation-omissions';
      note.textContent = bundle.omitted_categories?.length
        ? `Budget/room fit left out: ${[...new Set(bundle.omitted_categories)].join(', ')}.`
        : `Aspect-ratio match: ${bundle.preset_match?.name || 'curated room layout'}.`;
      const apply = document.createElement('button');
      apply.type = 'button';
      apply.className = 'btn btn-dqn';
      apply.textContent = 'Apply this design';
      apply.disabled = !bundle.validation?.valid;
      apply.addEventListener('click', () => {
        const nextLayout = JSON.parse(JSON.stringify(bundle.layout));
        nextLayout.name = `${bundle.name} · ${data.room_type.replaceAll('_', ' ')}`;
        nextLayout.room_type = data.room_type;
        nextLayout.style = data.requested_style;
        dialog.hidden = true;
        dialog.setAttribute('aria-hidden', 'true');
        window.dispatchEvent(new CustomEvent('smartspace:load-layout', {
          detail: { layout: nextLayout, source: 'recommendation-modal' }
        }));
      });
      card.append(header, metrics, products, note, apply);
      results.append(card);
    }
  }

  async function generate() {
    generateButton.disabled = true;
    generateButton.textContent = 'Finding designs…';
    error.hidden = true;
    try {
      const response = await window.smartspaceFetch('/api/recommendations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          room_type: byId('recommendationRoomType').value,
          width_ft: Number(byId('recommendationWidth').value),
          length_ft: Number(byId('recommendationLength').value),
          budget_inr: Number(byId('recommendationBudget').value),
          style: byId('recommendationStyle').value,
        }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Could not find a suitable design.');
      render(data);
    } catch (requestError) {
      error.textContent = requestError.message || 'Could not generate designs.';
      error.hidden = false;
    } finally {
      generateButton.disabled = false;
      generateButton.textContent = 'Find matching designs';
    }
  }

  openButton.addEventListener('click', openPicker);
  closeButton?.addEventListener('click', closePicker);
  generateButton?.addEventListener('click', generate);
  dialog.addEventListener('click', (event) => { if (event.target === dialog) closePicker(); });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !dialog.hidden) closePicker();
  });
})();
