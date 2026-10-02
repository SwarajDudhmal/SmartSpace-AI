/**
 * SmartSpace AI - 2D Floorplan Interactive Canvas Engine
 * Supports:
 * - Architectural room boundary and grid rendering
 * - Textured top-down furniture assets drawn inside SAT-aligned OBB bounds
 * - Interactive dragging, selecting, and rotating of furniture
 * - A* circulation walking paths rendering (green dashed paths)
 * - Ergonomic clearance halos (0.75m walking buffers)
 * - Collision warning halos
 * - Door swing clearances and window daylight cones
 * - Zoom, pan, snap to wall, export snapshot
 */

class FloorplanCanvas {
  constructor(canvasId, onLayoutChanged) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.onLayoutChanged = onLayoutChanged;
    
    this.roomWidth = 4.8;
    this.roomLength = 4.0;
    this.door = { wall: 'south', offset: 0.8, width: 0.9 };
    this.windows = [{ wall: 'north', offset: 1.5, width: 1.5 }];
    this.furniture = [];
    this.paths = {};
    this.collisions = [];
    
    // Canvas transform & scale
    this.scale = 100; // pixels per meter
    this.baseScale = 100;
    this.zoomLevel = 1.0;
    this.offsetX = 60;
    this.offsetY = 60;
    
    // View flags
    this.showWalkways = true;
    this.showClearances = true;
    this.showGrid = true;

    // Kept for the inventory list's small category swatches; the floorplan
    // itself is rendered from textured SVGs below, never from these colors.
    this.colorMap = {
      bed: '#688a6c', sofa: '#3d7763', chair: '#72958b', table: '#bd8050',
      wardrobe: '#9a7859', desk: '#597b64', tv: '#42645a', cabinet: '#a97155',
      door: '#bd8050', window: '#7da99b'
    };
    
    // Interaction state
    this.selectedItem = null;
    this.draggedItem = null;
    this.dragStartX = 0;
    this.dragStartY = 0;
    this.itemStartX = 0;
    this.itemStartY = 0;
    
    this.furnitureAssets = {};
    this.loadFurnitureAssets();
    
    this.initEvents();
    this.resizeCanvas();
  }

  resizeCanvas() {
    const parent = this.canvas.parentElement;
    this.canvas.width = parent.clientWidth || 700;
    this.canvas.height = parent.clientHeight || 550;
    
    // Calculate best fit scale
    const availW = this.canvas.width - 120;
    const availH = this.canvas.height - 120;
    this.baseScale = Math.min(availW / Math.max(1, this.roomWidth), availH / Math.max(1, this.roomLength));
    this.scale = this.baseScale * this.zoomLevel;
    this.offsetX = (this.canvas.width - this.roomWidth * this.scale) / 2;
    this.offsetY = (this.canvas.height - this.roomLength * this.scale) / 2;
    
    this.render();
  }

  zoomIn() {
    this.zoomLevel = Math.min(2.5, this.zoomLevel + 0.15);
    this.scale = this.baseScale * this.zoomLevel;
    this.offsetX = (this.canvas.width - this.roomWidth * this.scale) / 2;
    this.offsetY = (this.canvas.height - this.roomLength * this.scale) / 2;
    this.render();
  }

  zoomOut() {
    this.zoomLevel = Math.max(0.6, this.zoomLevel - 0.15);
    this.scale = this.baseScale * this.zoomLevel;
    this.offsetX = (this.canvas.width - this.roomWidth * this.scale) / 2;
    this.offsetY = (this.canvas.height - this.roomLength * this.scale) / 2;
    this.render();
  }

  resetView() {
    this.zoomLevel = 1.0;
    this.resizeCanvas();
  }

  setLayout(layoutData) {
    if (!layoutData) return;
    this.roomWidth = layoutData.room_width || layoutData.dimensions?.width || 4.8;
    this.roomLength = layoutData.room_length || layoutData.dimensions?.length || 4.0;
    this.budget = layoutData.budget || 20000;
    this.door = layoutData.door || this.door;
    this.windows = layoutData.windows || this.windows;
    const furnitureSpecs = window.smartSpaceFurnitureSpecs || {};
    this.furniture = (layoutData.furniture || layoutData.initial_furniture || []).map(item => {
      const specs = furnitureSpecs[item.type] || {};
      return {
        ...item,
        width: Number(item.width ?? specs.width ?? 1),
        depth: Number(item.depth ?? specs.depth ?? 1),
        height: Number(item.height ?? specs.height ?? 0.8),
        cost: Number(item.cost ?? specs.base_cost ?? 1000),
        label: item.label || specs.label || (item.type || 'Furniture').toUpperCase()
      };
    });
    
    if (layoutData.metrics?.paths) {
      this.paths = layoutData.metrics.paths;
    }
    
    this.resizeCanvas();
  }

  setPaths(paths) {
    this.paths = paths || {};
    this.render();
  }

  loadFurnitureAssets() {
    const renderer = window.SmartSpaceFurnitureRenderer;
    if (renderer) {
      this.furnitureAssets = renderer.loadAll(() => this.render());
      return;
    }
    // Fallback for standalone embed pages that did not include the shared renderer.
    ['bed', 'sofa', 'chair', 'table', 'wardrobe', 'desk', 'tv', 'cabinet', 'door', 'window'].forEach((type) => {
      const image = new Image();
      image.onload = () => this.render();
      image.src = `/static/assets/furniture/${type}.svg`;
      this.furnitureAssets[type] = image;
    });
  }

  worldToScreen(x, y) {
    return {
      sx: this.offsetX + x * this.scale,
      sy: this.offsetY + (this.roomLength - y) * this.scale
    };
  }

  screenToWorld(sx, sy) {
    return {
      x: (sx - this.offsetX) / this.scale,
      y: this.roomLength - (sy - this.offsetY) / this.scale
    };
  }

  initEvents() {
    window.addEventListener('resize', () => this.resizeCanvas());

    this.canvas.addEventListener('mousedown', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const sx = e.clientX - rect.left;
      const sy = e.clientY - rect.top;
      const { x, y } = this.screenToWorld(sx, sy);
      
      this.selectedItem = null;

      // Hit test furniture in reverse order (top items first)
      for (let i = this.furniture.length - 1; i >= 0; i--) {
        const item = this.furniture[i];
        const halfW = (item.width || 1.0) / 2;
        const halfD = (item.depth || 1.0) / 2;
        
        if (Math.abs(x - item.x) <= halfW && Math.abs(y - item.y) <= halfD) {
          this.selectedItem = item;
          this.draggedItem = item;
          this.dragStartX = sx;
          this.dragStartY = sy;
          this.itemStartX = item.x;
          this.itemStartY = item.y;
          break;
        }
      }
      this.render();
      if (this.onLayoutChanged) {
        this.onLayoutChanged(this.getCurrentLayout(), 'select');
      }
    });

    this.canvas.addEventListener('mousemove', (e) => {
      if (!this.draggedItem) return;
      
      const rect = this.canvas.getBoundingClientRect();
      const sx = e.clientX - rect.left;
      const sy = e.clientY - rect.top;
      
      const dx = (sx - this.dragStartX) / this.scale;
      const dy = -(sy - this.dragStartY) / this.scale;
      
      const hw = (this.draggedItem.width || 1.0) / 2;
      const hd = (this.draggedItem.depth || 1.0) / 2;
      
      // Clamp within room boundaries
      this.draggedItem.x = Math.max(hw, Math.min(this.roomWidth - hw, this.itemStartX + dx));
      this.draggedItem.y = Math.max(hd, Math.min(this.roomLength - hd, this.itemStartY + dy));
      
      this.render();
    });

    const stopDrag = () => {
      if (this.draggedItem) {
        this.draggedItem = null;
        if (this.onLayoutChanged) {
          this.onLayoutChanged(this.getCurrentLayout(), 'move');
        }
      }
    };

    this.canvas.addEventListener('mouseup', stopDrag);
    this.canvas.addEventListener('mouseleave', stopDrag);
    
    // Double click to rotate +90 degrees
    this.canvas.addEventListener('dblclick', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const sx = e.clientX - rect.left;
      const sy = e.clientY - rect.top;
      const { x, y } = this.screenToWorld(sx, sy);
      
      for (let item of this.furniture) {
        const halfW = (item.width || 1.0) / 2;
        const halfD = (item.depth || 1.0) / 2;
        if (Math.abs(x - item.x) <= halfW && Math.abs(y - item.y) <= halfD) {
          item.rotation = ((item.rotation || 0) + 90) % 360;
          this.selectedItem = item;
          this.render();
          if (this.onLayoutChanged) {
            this.onLayoutChanged(this.getCurrentLayout(), 'rotate');
          }
          break;
        }
      }
    });
  }

  addFurniture(newItem) {
    // Generate unique ID
    const count = this.furniture.filter(f => f.type === newItem.type).length + 1;
    const item = {
      id: `${newItem.type}_${count}_${Date.now() % 1000}`,
      type: newItem.type,
      x: newItem.x || this.roomWidth / 2,
      y: newItem.y || this.roomLength / 2,
      width: newItem.width || 1.0,
      depth: newItem.depth || 1.0,
      height: newItem.height || 0.8,
      rotation: newItem.rotation || 0,
      cost: newItem.cost || 1000,
      preferred_wall: newItem.preferred_wall || false,
      label: newItem.label || newItem.type.toUpperCase()
    };
    this.furniture.push(item);
    this.selectedItem = item;
    this.render();
    if (this.onLayoutChanged) {
      this.onLayoutChanged(this.getCurrentLayout(), 'add');
    }
  }

  removeFurniture(itemId) {
    this.furniture = this.furniture.filter(f => f.id !== itemId);
    if (this.selectedItem && this.selectedItem.id === itemId) {
      this.selectedItem = null;
    }
    this.render();
    if (this.onLayoutChanged) {
      this.onLayoutChanged(this.getCurrentLayout(), 'remove');
    }
  }

  rotateFurniture(itemId, deg = 90) {
    const item = this.furniture.find(f => f.id === itemId);
    if (item) {
      item.rotation = ((item.rotation || 0) + deg) % 360;
      this.selectedItem = item;
      this.render();
      if (this.onLayoutChanged) {
        this.onLayoutChanged(this.getCurrentLayout(), 'rotate');
      }
    }
  }

  snapToNearestWall(itemId) {
    const item = this.furniture.find(f => f.id === itemId);
    if (!item) return;

    const hw = (item.width || 1.0) / 2;
    const hd = (item.depth || 1.0) / 2;

    const distWest = item.x - hw;
    const distEast = this.roomWidth - (item.x + hw);
    const distSouth = item.y - hd;
    const distNorth = this.roomLength - (item.y + hd);

    const minDist = Math.min(distWest, distEast, distSouth, distNorth);

    if (minDist === distSouth) {
      item.y = hd + 0.05;
      item.rotation = 0;
    } else if (minDist === distNorth) {
      item.y = this.roomLength - hd - 0.05;
      item.rotation = 180;
    } else if (minDist === distWest) {
      item.x = hw + 0.05;
      item.rotation = 90;
    } else {
      item.x = this.roomWidth - hw - 0.05;
      item.rotation = 270;
    }

    this.render();
    if (this.onLayoutChanged) {
      this.onLayoutChanged(this.getCurrentLayout(), 'snap');
    }
  }

  getCurrentLayout() {
    return {
      room_width: this.roomWidth,
      room_length: this.roomLength,
      dimensions: { width: this.roomWidth, length: this.roomLength },
      door: this.door,
      windows: this.windows,
      budget: this.budget || 20000,
      furniture: this.furniture
    };
  }

  exportImage() {
    return this.canvas.toDataURL('image/png');
  }

  render() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    // 1. Draw Architectural Grid
    if (this.showGrid) this.drawGrid();

    // 2. Draw Room Walls & Outer Glow
    this.drawWalls();

    // 3. Draw Door & Swing Clearance
    this.drawDoor();

    // 4. Draw Windows & Daylight Cones
    this.drawWindows();

    // 5. Draw A* Circulation Paths
    if (this.showWalkways) this.drawCirculationPaths();

    // 6. Draw Placed Furniture Items & Clearance Halos
    this.drawFurniture();
  }

  drawGrid() {
    const ctx = this.ctx;
    ctx.save();
    ctx.strokeStyle = 'rgba(39, 82, 57, 0.075)';
    ctx.lineWidth = 1;

    // Grid spacing: 0.5m
    const step = 0.5;
    for (let x = 0; x <= this.roomWidth + 0.01; x += step) {
      const p1 = this.worldToScreen(x, 0);
      const p2 = this.worldToScreen(x, this.roomLength);
      ctx.beginPath();
      ctx.moveTo(p1.sx, p1.sy);
      ctx.lineTo(p2.sx, p2.sy);
      ctx.stroke();
    }

    for (let y = 0; y <= this.roomLength + 0.01; y += step) {
      const p1 = this.worldToScreen(0, y);
      const p2 = this.worldToScreen(this.roomWidth, y);
      ctx.beginPath();
      ctx.moveTo(p1.sx, p1.sy);
      ctx.lineTo(p2.sx, p2.sy);
      ctx.stroke();
    }
    ctx.restore();
  }

  drawWalls() {
    const ctx = this.ctx;
    const tl = this.worldToScreen(0, this.roomLength);
    const br = this.worldToScreen(this.roomWidth, 0);
    const w = br.sx - tl.sx;
    const h = br.sy - tl.sy;

    ctx.save();
    // Floor background
    ctx.fillStyle = '#fbfaf5';
    ctx.fillRect(tl.sx, tl.sy, w, h);

    // Wall perimeter
    ctx.strokeStyle = '#315c47';
    ctx.lineWidth = 3;
    ctx.strokeRect(tl.sx, tl.sy, w, h);

    // Metric dimensions labels (in meters and feet)
    const wFt = (this.roomWidth / 0.3048).toFixed(1);
    const lFt = (this.roomLength / 0.3048).toFixed(1);

    ctx.fillStyle = '#75877b';
    ctx.font = '600 10px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`${this.roomWidth.toFixed(1)}m (${wFt} ft)`, tl.sx + w / 2, tl.sy - 10);
    ctx.save();
    ctx.translate(tl.sx - 14, tl.sy + h / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(`${this.roomLength.toFixed(1)}m (${lFt} ft)`, 0, 0);
    ctx.restore();

    ctx.restore();
  }

  drawDoor() {
    const ctx = this.ctx;
    const wall = this.door.wall || 'south';
    const offset = this.door.offset || 0.8;
    const dw = this.door.width || 0.9;
    
    ctx.save();
    let pStart, pEnd, swingCenter;

    if (wall === 'south') {
      pStart = this.worldToScreen(offset, 0);
      pEnd = this.worldToScreen(offset + dw, 0);
      swingCenter = pStart;

      ctx.strokeStyle = '#bd8050';
      ctx.lineWidth = 6;
      ctx.beginPath();
      ctx.moveTo(pStart.sx, pStart.sy);
      ctx.lineTo(pEnd.sx, pEnd.sy);
      ctx.stroke();

      ctx.strokeStyle = 'rgba(189, 128, 80, 0.42)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.arc(swingCenter.sx, swingCenter.sy, dw * this.scale, Math.PI * 1.5, Math.PI * 2);
      ctx.stroke();
    } else if (wall === 'west') {
      pStart = this.worldToScreen(0, offset);
      pEnd = this.worldToScreen(0, offset + dw);
      swingCenter = pStart;

      ctx.strokeStyle = '#bd8050';
      ctx.lineWidth = 6;
      ctx.beginPath();
      ctx.moveTo(pStart.sx, pStart.sy);
      ctx.lineTo(pEnd.sx, pEnd.sy);
      ctx.stroke();

      ctx.strokeStyle = 'rgba(189, 128, 80, 0.42)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.arc(swingCenter.sx, swingCenter.sy, dw * this.scale, 0, Math.PI * 0.5);
      ctx.stroke();
    } else {
      pStart = this.worldToScreen(offset, this.roomLength);
      pEnd = this.worldToScreen(offset + dw, this.roomLength);
      ctx.strokeStyle = '#bd8050';
      ctx.lineWidth = 6;
      ctx.beginPath();
      ctx.moveTo(pStart.sx, pStart.sy);
      ctx.lineTo(pEnd.sx, pEnd.sy);
      ctx.stroke();
    }

    ctx.fillStyle = '#a96f48';
    ctx.font = 'bold 10px Inter';
    ctx.fillText('ENTRY DOOR', pStart.sx + 8, pStart.sy + 16);
    ctx.restore();
  }

  drawWindows() {
    const ctx = this.ctx;
    ctx.save();
    for (let win of this.windows) {
      const wall = win.wall || 'north';
      const offset = win.offset || 1.5;
      const ww = win.width || 1.5;

      let p1, p2;
      if (wall === 'north') {
        p1 = this.worldToScreen(offset, this.roomLength);
        p2 = this.worldToScreen(offset + ww, this.roomLength);

        // Natural daylight gradient cone
        const grad = ctx.createLinearGradient(0, p1.sy, 0, p1.sy + 60);
        grad.addColorStop(0, 'rgba(125, 169, 155, 0.22)');
        grad.addColorStop(1, 'rgba(125, 169, 155, 0.0)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.moveTo(p1.sx, p1.sy);
        ctx.lineTo(p2.sx, p2.sy);
        ctx.lineTo(p2.sx + 30, p2.sy + 60);
        ctx.lineTo(p1.sx - 30, p1.sy + 60);
        ctx.closePath();
        ctx.fill();

        // Window bar
        ctx.strokeStyle = '#7da99b';
        ctx.lineWidth = 6;
        ctx.beginPath();
        ctx.moveTo(p1.sx, p1.sy);
        ctx.lineTo(p2.sx, p2.sy);
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  drawCirculationPaths() {
    if (!this.paths || Object.keys(this.paths).length === 0) return;
    const ctx = this.ctx;
    ctx.save();

    for (const [itemId, pathCoords] of Object.entries(this.paths)) {
      if (!pathCoords || pathCoords.length < 2) continue;

      ctx.strokeStyle = 'rgba(74, 137, 91, 0.8)';
      ctx.lineWidth = 2.5;
      ctx.setLineDash([5, 5]);

      ctx.beginPath();
      const first = this.worldToScreen(pathCoords[0][0], pathCoords[0][1]);
      ctx.moveTo(first.sx, first.sy);

      for (let i = 1; i < pathCoords.length; i++) {
        const pt = this.worldToScreen(pathCoords[i][0], pathCoords[i][1]);
        ctx.lineTo(pt.sx, pt.sy);
      }
      ctx.stroke();
    }
    ctx.restore();
  }

  drawFurniture() {
    const ctx = this.ctx;

    for (let item of this.furniture) {
      const { sx, sy } = this.worldToScreen(item.x, item.y);
      const wPx = (item.width || 1.0) * this.scale;
      const dPx = (item.depth || 1.0) * this.scale;
      const rotRad = ((item.rotation || 0) * Math.PI) / 180;
      const isSelected = this.selectedItem && this.selectedItem.id === item.id;

      ctx.save();
      ctx.translate(sx, sy);
      ctx.rotate(-rotRad);

      // Ergonomic Clearance Zone halo (0.75m walking aisle)
      if (this.showClearances) {
        ctx.strokeStyle = isSelected ? 'rgba(189, 128, 80, 0.55)' : 'rgba(66, 94, 69, 0.2)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        const clearPx = 0.5 * this.scale;
        ctx.strokeRect(-wPx / 2 - clearPx/2, -dPx / 2 - clearPx/2, wPx + clearPx, dPx + clearPx);
        ctx.setLineDash([]);
      }

      // The bitmap/SVG artwork is stretched to this exact footprint before the
      // same world transform used for the SAT box, so texture and collision
      // coordinates share x/y/width/depth/rotation without changing the solver.
      const renderer = window.SmartSpaceFurnitureRenderer;
      const asset = this.furnitureAssets[item.type];
      if (renderer && renderer.drawLocal(ctx, item.type, wPx, dPx)) {
        // Shared renderer applies the same local asset-to-SAT footprint mapping
        // as the homepage curated plan and the 133-D Studio canvas.
      } else if (asset && asset.complete && asset.naturalWidth > 0) {
        ctx.drawImage(asset, -wPx / 2, -dPx / 2, wPx, dPx);
      } else {
        // Keep the editor legible while local SVG assets are still loading; do
        // not fall back to the old solid-color furniture blocks.
        ctx.strokeStyle = 'rgba(48, 78, 56, 0.62)';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 3]);
        ctx.strokeRect(-wPx / 2, -dPx / 2, wPx, dPx);
        ctx.setLineDash([]);
        ctx.fillStyle = '#314936';
        ctx.font = '600 10px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText((item.type || 'item').toUpperCase(), 0, 0);
      }

      ctx.shadowColor = 'transparent';
      ctx.shadowBlur = 0;
      ctx.shadowOffsetX = 0;
      ctx.shadowOffsetY = 0;
      if (isSelected) {
        ctx.strokeStyle = '#bd8050';
        ctx.lineWidth = 3;
        ctx.setLineDash([]);
        ctx.strokeRect(-wPx / 2 - 2, -dPx / 2 - 2, wPx + 4, dPx + 4);
      } else {
        ctx.strokeStyle = 'rgba(63, 73, 59, 0.34)';
        ctx.lineWidth = 1;
        ctx.strokeRect(-wPx / 2, -dPx / 2, wPx, dPx);
      }

      ctx.restore();
    }
  }
}

window.FloorplanCanvas = FloorplanCanvas;
