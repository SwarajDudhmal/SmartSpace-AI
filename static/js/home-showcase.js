/* Render the selected database room with the same local SVG assets/transform as Studio. */
document.addEventListener('DOMContentLoaded', () => {
  const canvas = document.getElementById('homepageLayoutCanvas');
  const presets = window.SMARTSPACE_SHOWCASE_PRESETS || [];
  const renderer = window.SmartSpaceFurnitureRenderer;
  if (!canvas || !presets.length || !renderer) return;
  const preset = presets[0];
  const layout = preset.layout || {};

  function itemBounds(item) {
    const halfW = Number(item.width || 0) / 2;
    const halfD = Number(item.depth || 0) / 2;
    const rotation = Number(item.rotation || 0) * Math.PI / 180;
    const cos = Math.cos(rotation), sin = Math.sin(rotation);
    const xs = [], ys = [];
    [[-halfW, -halfD], [halfW, -halfD], [halfW, halfD], [-halfW, halfD]].forEach(([x, y]) => {
      xs.push(Number(item.x) + x * cos - y * sin);
      ys.push(Number(item.y) + x * sin + y * cos);
    });
    return { minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) };
  }

  function draw() {
    const bounds = canvas.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(bounds.width * ratio);
    canvas.height = Math.round(bounds.height * ratio);
    const ctx = canvas.getContext('2d');
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    const w = bounds.width, h = bounds.height;
    const roomW = Number(layout.room_width || preset.width_m || 4.8);
    const roomL = Number(layout.room_length || preset.length_m || 4.0);
    const scale = Math.min((w - 54) / roomW, (h - 54) / roomL);
    const planW = roomW * scale, planH = roomL * scale;
    const left = (w - planW) / 2, top = (h - planH) / 2;
    const screenPoint = (x, y) => ({ x: left + x * scale, y: top + planH - y * scale });

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#f9fbf7';
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = '#fff';
    ctx.fillRect(left, top, planW, planH);
    ctx.save();
    ctx.beginPath(); ctx.rect(left, top, planW, planH); ctx.clip();
    ctx.strokeStyle = 'rgba(67,105,76,.09)';
    ctx.lineWidth = 1;
    for (let x = 0; x <= roomW; x += 0.5) {
      const sx = left + x * scale;
      ctx.beginPath(); ctx.moveTo(sx, top); ctx.lineTo(sx, top + planH); ctx.stroke();
    }
    for (let y = 0; y <= roomL; y += 0.5) {
      const sy = top + planH - y * scale;
      ctx.beginPath(); ctx.moveTo(left, sy); ctx.lineTo(left + planW, sy); ctx.stroke();
    }

    const furniture = layout.furniture || [];
    const sofa = furniture.find((item) => item.type === 'sofa');
    const coffeeTable = furniture.find((item) => item.type === 'table');
    if (sofa && coffeeTable) {
      const sofaBox = itemBounds(sofa), tableBox = itemBounds(coffeeTable), margin = 0.15;
      const minX = Math.min(sofaBox.minX, tableBox.minX) - margin;
      const maxX = Math.max(sofaBox.maxX, tableBox.maxX) + margin;
      const minY = Math.min(sofaBox.minY, tableBox.minY) - margin;
      const maxY = Math.max(sofaBox.maxY, tableBox.maxY) + margin;
      const rugTopLeft = screenPoint(minX, maxY), rugBottomRight = screenPoint(maxX, minY);
      renderer.drawTexturedRug(ctx, rugTopLeft.x, rugTopLeft.y,
        rugBottomRight.x - rugTopLeft.x, rugBottomRight.y - rugTopLeft.y);
    }

    // Keep the saved A* waypoints visible over the rug and below the furniture.
    const paths = (layout.metrics && layout.metrics.paths) || {};
    Object.values(paths).forEach((points) => {
      if (!Array.isArray(points) || points.length < 2) return;
      ctx.beginPath();
      points.forEach((point, index) => {
        const p = screenPoint(Number(point[0]), Number(point[1]));
        if (index === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y);
      });
      ctx.strokeStyle = 'rgba(67,157,99,.7)';
      ctx.lineWidth = 2.2;
      ctx.setLineDash([5, 4]); ctx.stroke(); ctx.setLineDash([]);
    });

    // Shared renderer maps the real room asset to width/depth and rotates it
    // with the same positive-CCW world angle used by SAT and the Studio canvas.
    furniture.forEach((item) => {
      const p = screenPoint(Number(item.x), Number(item.y));
      renderer.drawPlaced(ctx, item.type, p.x, p.y, Number(item.width), Number(item.depth),
        Number(item.rotation || 0), scale, { shadowBlur: 4 });
    });
    ctx.restore();

    // Architectural green perimeter and a clear door aperture.
    ctx.strokeStyle = '#315a3d';
    ctx.lineWidth = 3;
    ctx.strokeRect(left, top, planW, planH);
    const door = layout.door || { wall: 'south', offset: 0.25, width: 0.9 };
    ctx.strokeStyle = '#f9fbf7'; ctx.lineWidth = 7; ctx.beginPath();
    if (door.wall === 'south') {
      const y = top + planH;
      ctx.moveTo(left + door.offset * scale, y);
      ctx.lineTo(left + (door.offset + door.width) * scale, y);
    } else if (door.wall === 'north') {
      ctx.moveTo(left + door.offset * scale, top);
      ctx.lineTo(left + (door.offset + door.width) * scale, top);
    } else if (door.wall === 'west') {
      ctx.moveTo(left, top + planH - door.offset * scale);
      ctx.lineTo(left, top + planH - (door.offset + door.width) * scale);
    } else {
      ctx.moveTo(left + planW, top + planH - door.offset * scale);
      ctx.lineTo(left + planW, top + planH - (door.offset + door.width) * scale);
    }
    ctx.stroke();
    ctx.fillStyle = '#557460'; ctx.font = '10px Arial, sans-serif';
    ctx.textAlign = 'left'; ctx.textBaseline = 'top';
    ctx.fillText(`${roomL.toFixed(1)} m × ${roomW.toFixed(1)} m`, 12, 12);
  }

  renderer.loadAll(draw);
  draw();
  if ('ResizeObserver' in window) new ResizeObserver(draw).observe(canvas);
  window.addEventListener('resize', draw, { passive: true });
});
