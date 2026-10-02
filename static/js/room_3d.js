/**
 * SmartSpace AI - 3D WebGL Room Viewer Engine (Three.js)
 * Implements real-time 3D room visualization with shadows,
 * architectural boundaries, materials, and procedural 3D furniture models.
 */

class Room3DViewer {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.available = false;
    this.fallback = document.getElementById('threejsFallback');
    
    this.furnitureMeshes = [];
    this.roomMeshes = [];
    this.layoutData = null;
    
    this.colorMap = {
      bed: 0x3b82f6,
      sofa: 0x8b5cf6,
      chair: 0x06b6d4,
      table: 0x10b981,
      wardrobe: 0xf59e0b,
      desk: 0x6366f1,
      tv: 0xec4899,
      cabinet: 0xf97316,
      door: 0xef4444,
      window: 0x14b8a6
    };
    
    this.init();
  }

  init() {
    if (!window.THREE || !this.container) {
      return;
    }

    try {
      const width = this.container.clientWidth || 700;
      const height = this.container.clientHeight || 550;

    // Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0a0f1d);
    this.scene.fog = new THREE.FogExp2(0x0a0f1d, 0.04);

    // Camera
    this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    this.camera.position.set(0, 7.5, 7.5);

    // Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.container.appendChild(this.renderer.domElement);
    this.available = true;
    if (this.fallback) this.fallback.hidden = true;

    // OrbitControls
    if (window.THREE.OrbitControls) {
      this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
      this.controls.enableDamping = true;
      this.controls.dampingFactor = 0.05;
      this.controls.maxPolarAngle = Math.PI / 2 - 0.05; // Prevent camera sinking under floor
      this.controls.target.set(0, 0.8, 0);
    }

    // Lights
    this.setupLighting();

    // Resize handler
    window.addEventListener('resize', () => this.onResize());

    // Animation Loop
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
    } catch (error) {
      console.warn('3D preview could not initialize:', error);
      this.available = false;
    }
  }

  showFallback() {
    if (this.fallback) this.fallback.hidden = false;
  }

  setupLighting() {
    // Ambient Light
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    this.scene.add(ambientLight);

    // Warm Ceiling Light
    const pointLight = new THREE.PointLight(0xffedd5, 1.2, 12);
    pointLight.position.set(0, 2.7, 0);
    pointLight.castShadow = true;
    pointLight.shadow.mapSize.width = 1024;
    pointLight.shadow.mapSize.height = 1024;
    this.scene.add(pointLight);

    // Directional Sun / Window Light
    const sunLight = new THREE.DirectionalLight(0x93c5fd, 0.8);
    sunLight.position.set(3, 5, -4);
    sunLight.castShadow = true;
    this.scene.add(sunLight);
  }

  onResize() {
    if (!this.container || !this.renderer || !this.camera) return;
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  animate() {
    requestAnimationFrame(this.animate);
    if (this.controls) this.controls.update();
    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }
  }

  updateLayout(layoutData) {
    if (!this.available || !this.scene || !layoutData) return;
    this.layoutData = layoutData;

    // Clear previous room & furniture meshes
    this.clearMeshes();

    const roomW = layoutData.room_width || layoutData.dimensions?.width || 4.8;
    const roomL = layoutData.room_length || layoutData.dimensions?.length || 4.0;
    const roomH = layoutData.dimensions?.height || 2.7;

    // 1. Build Floor
    const floorGeo = new THREE.PlaneGeometry(roomW, roomL);
    const floorMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      roughness: 0.6,
      metalness: 0.1
    });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    this.scene.add(floor);
    this.roomMeshes.push(floor);

    // Floor Baseboard Border
    const borderMat = new THREE.MeshStandardMaterial({ color: 0x38bdf8 });
    const borderGeo = new THREE.BoxGeometry(roomW, 0.06, 0.06);
    const bSouth = new THREE.Mesh(borderGeo, borderMat);
    bSouth.position.set(0, 0.03, roomL / 2);
    this.scene.add(bSouth);
    this.roomMeshes.push(bSouth);

    // 2. Build 3D Furniture Items
    const furniture = layoutData.furniture || layoutData.initial_furniture || [];
    furniture.forEach(item => {
      const mesh = this.createFurniture3D(item, roomW, roomL);
      if (mesh) {
        this.scene.add(mesh);
        this.furnitureMeshes.push(mesh);
      }
    });
  }

  clearMeshes() {
    [...this.roomMeshes, ...this.furnitureMeshes].forEach(m => {
      this.scene.remove(m);
      if (m.geometry) m.geometry.dispose();
      if (m.material) {
        if (Array.isArray(m.material)) m.material.forEach(mat => mat.dispose());
        else m.material.dispose();
      }
    });
    this.roomMeshes = [];
    this.furnitureMeshes = [];
  }

  createFurniture3D(item, roomW, roomL) {
    const group = new THREE.Group();
    const type = item.type || 'chair';
    const w = item.width || 1.0;
    const d = item.depth || 1.0;
    const h = item.height || 0.8;
    const colorHex = this.colorMap[type] || 0x3b82f6;

    // Main Body
    const mat = new THREE.MeshStandardMaterial({
      color: colorHex,
      roughness: 0.4,
      metalness: 0.2
    });

    if (type === 'bed') {
      // Bed Base
      const base = new THREE.Mesh(new THREE.BoxGeometry(w, 0.35, d), mat);
      base.position.y = 0.175;
      base.castShadow = true;
      base.receiveShadow = true;
      group.add(base);

      // Mattress
      const mattressMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.9 });
      const mattress = new THREE.Mesh(new THREE.BoxGeometry(w * 0.94, 0.25, d * 0.92), mattressMat);
      mattress.position.y = 0.475;
      mattress.castShadow = true;
      group.add(mattress);

      // Headboard
      const headboard = new THREE.Mesh(new THREE.BoxGeometry(w, 0.9, 0.1), mat);
      headboard.position.set(0, 0.45, -d / 2 + 0.05);
      headboard.castShadow = true;
      group.add(headboard);

    } else if (type === 'sofa') {
      // Sofa seat
      const seat = new THREE.Mesh(new THREE.BoxGeometry(w, 0.35, d), mat);
      seat.position.y = 0.175;
      seat.castShadow = true;
      group.add(seat);

      // Backrest
      const back = new THREE.Mesh(new THREE.BoxGeometry(w, 0.5, 0.22), mat);
      back.position.set(0, 0.5, -d / 2 + 0.11);
      back.castShadow = true;
      group.add(back);

    } else if (type === 'tv') {
      // TV Stand
      const stand = new THREE.Mesh(new THREE.BoxGeometry(w * 0.4, 0.08, d * 1.5), mat);
      stand.position.y = 0.04;
      group.add(stand);

      // Screen
      const screenMat = new THREE.MeshStandardMaterial({ color: 0x020617, roughness: 0.1, metalness: 0.8 });
      const screen = new THREE.Mesh(new THREE.BoxGeometry(w, h, 0.04), screenMat);
      screen.position.set(0, h / 2 + 0.08, 0);
      screen.castShadow = true;
      group.add(screen);

    } else {
      // Generic Box representation for desks, wardrobes, chairs, tables
      const geo = new THREE.BoxGeometry(w, h, d);
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.y = h / 2;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      group.add(mesh);
    }

    // World placement (transform from 2D coordinates [0..roomW], [0..roomL] to Three.js centered coordinates)
    const posX = item.x - roomW / 2;
    const posZ = -(item.y - roomL / 2);
    group.position.set(posX, 0, posZ);

    // Rotation around Y axis
    const rotRad = ((item.rotation || 0) * Math.PI) / 180;
    group.rotation.y = rotRad;

    return group;
  }
}

window.Room3DViewer = Room3DViewer;
