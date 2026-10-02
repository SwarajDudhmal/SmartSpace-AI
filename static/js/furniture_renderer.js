/* Shared SVG furniture renderer for the homepage plan and Studio CAD canvas. */
(function attachFurnitureRenderer(global) {
  const assetRoot = '/static/assets/furniture/';
  const images = Object.create(null);
  const classNames = ['bed', 'sofa', 'chair', 'table', 'wardrobe', 'desk', 'tv', 'cabinet', 'door', 'window'];

  function getAsset(type, onLoad) {
    if (!images[type]) {
      const image = new Image();
      image.onload = () => {
        if (typeof onLoad === 'function') onLoad(type);
        global.dispatchEvent(new CustomEvent('smartspace:furniture-asset-ready', { detail: { type } }));
      };
      image.onerror = () => console.warn(`Top-down ${type} asset could not be loaded.`);
      image.src = `${assetRoot}${type}.svg`;
      images[type] = image;
    }
    return images[type];
  }

  function loadAll(onLoad) {
    classNames.forEach((type) => getAsset(type, onLoad));
    return images;
  }

  // Draws the bundled SVG in the current center/rotation transform and maps it
  // to the same width/depth footprint used by SAT and the 133-D room state.
  function drawLocal(ctx, type, widthPx, depthPx, options = {}) {
    const image = getAsset(type, options.onLoad);
    if (!image.complete || !image.naturalWidth) return false;
    if (options.shadow !== false) {
      ctx.shadowColor = 'rgba(38, 52, 40, 0.16)';
      ctx.shadowBlur = options.shadowBlur || 5;
      ctx.shadowOffsetX = options.shadowOffsetX || 2;
      ctx.shadowOffsetY = options.shadowOffsetY || 2;
    }
    ctx.drawImage(image, -widthPx / 2, -depthPx / 2, widthPx, depthPx);
    ctx.shadowColor = 'transparent';
    ctx.shadowBlur = 0;
    ctx.shadowOffsetX = 0;
    ctx.shadowOffsetY = 0;
    return true;
  }

  function drawPlaced(ctx, type, centerX, centerY, widthM, depthM, rotationDeg, scale, options = {}) {
    ctx.save();
    ctx.translate(centerX, centerY);
    // Canvas y points down; negating the world CCW rotation keeps it aligned
    // with the SAT/world transform used by the interactive floorplan.
    ctx.rotate(-(Number(rotationDeg) || 0) * Math.PI / 180);
    const drawn = drawLocal(ctx, type, widthM * scale, depthM * scale, options);
    ctx.restore();
    return drawn;
  }

  function drawTexturedRug(ctx, x, y, width, height) {
    const radius = Math.min(width, height) * 0.07;
    ctx.save();
    ctx.shadowColor = 'rgba(46, 55, 44, .12)';
    ctx.shadowBlur = 10;
    ctx.fillStyle = '#e9e4d9';
    ctx.beginPath();
    ctx.roundRect(x, y, width, height, radius);
    ctx.fill();
    ctx.shadowColor = 'transparent';
    ctx.lineWidth = 1;
    ctx.strokeStyle = 'rgba(153, 141, 122, .54)';
    ctx.stroke();
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(x + 4, y + 4, Math.max(0, width - 8), Math.max(0, height - 8), Math.max(2, radius - 3));
    ctx.clip();
    ctx.strokeStyle = 'rgba(146, 132, 112, .12)';
    ctx.lineWidth = 1;
    const gap = Math.max(4, Math.min(8, width / 42));
    for (let px = x - height; px < x + width + height; px += gap) {
      ctx.beginPath(); ctx.moveTo(px, y); ctx.lineTo(px + height, y + height); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(px, y + height); ctx.lineTo(px + height, y); ctx.stroke();
    }
    ctx.restore();
    ctx.restore();
  }

  global.SmartSpaceFurnitureRenderer = { classNames, getAsset, loadAll, drawLocal, drawPlaced, drawTexturedRug };
})(window);
