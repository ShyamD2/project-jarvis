/**
 * J.A.R.V.I.S. MASTER PROCEDURAL 3D HOLOGRAPHIC REACTOR
 * Real-Time 7-Layer WebGL Computational Reactor built with Three.js
 * Reference Target: Iron Man / Avengers J.A.R.V.I.S. Core Hologram
 */

class JarvisReactor3D {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) {
      console.error("[JarvisReactor3D] Canvas element not found:", canvasId);
      return;
    }

    this.container = this.canvas.parentElement;
    this.width = this.container.clientWidth || 580;
    this.height = this.container.clientHeight || 580;

    // State & Audio Telemetry
    this.state = "IDLE"; // IDLE, LISTENING, THINKING, EXECUTING, SPEAKING, ERROR
    this.audioEnergy = 0.0;
    this.audioFreqs = new Uint8Array(32);
    this.pulseTime = 0;
    this.baseRadius = 3.6;

    // Mouse Parallax
    this.mouse = { x: 0, y: 0, targetX: 0, targetY: 0 };
    this.isDragging = false;
    this.dragStart = { x: 0, y: 0 };
    this.manualRot = { x: 0.15, y: -0.25, targetX: 0.15, targetY: -0.25 };

    this.initScene();
    this.createGlowTexture();
    this.buildLayer1_EnergyCore();
    this.buildLayer2_ComputationalStructure();
    this.buildLayer3_NeuralParticleField();
    this.buildLayer4_ComputationalNetwork();
    this.buildLayer5_FragmentedOuterShell();
    this.buildLayer6_OrbitalRings();
    this.buildLayer7_RadialEnergyStreams();

    this.setupEvents();
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);

    console.log("⚡ [JarvisReactor3D] Procedural Holographic Reactor initialized successfully.");
  }

  initScene() {
    this.scene = new THREE.Scene();
    // Dark void transparent canvas so HUD background stays clean
    this.scene.background = null;

    this.camera = new THREE.PerspectiveCamera(45, this.width / this.height, 0.1, 100);
    this.camera.position.set(0, 0, 9.8);
    this.camera.lookAt(0, 0, 0);

    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      alpha: true,
      antialias: true,
      powerPreference: "high-performance"
    });
    this.renderer.setSize(this.width, this.height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    // Master Reactor Anchor Group (for rotation and parallax)
    this.reactorGroup = new THREE.Group();
    this.scene.add(this.reactorGroup);
  }

  createGlowTexture() {
    // Generates a soft, procedural bokeh radial glow texture via offscreen 2D canvas
    const size = 128;
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");

    const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    gradient.addColorStop(0.0, "rgba(255, 255, 255, 1.0)");
    gradient.addColorStop(0.18, "rgba(255, 220, 120, 0.95)");
    gradient.addColorStop(0.45, "rgba(255, 150, 20, 0.6)");
    gradient.addColorStop(0.75, "rgba(220, 90, 0, 0.2)");
    gradient.addColorStop(1.0, "rgba(0, 0, 0, 0.0)");

    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, size, size);

    this.glowTexture = new THREE.CanvasTexture(canvas);
  }

  // =========================================================================
  // LAYER 1: INNER ENERGY CORE (Blazing Incandescent Nucleus & Fast Toruses)
  // =========================================================================
  buildLayer1_EnergyCore() {
    this.coreGroup = new THREE.Group();

    // Central blazing nucleus sprite
    const spriteMat = new THREE.SpriteMaterial({
      map: this.glowTexture,
      color: 0xffffff,
      blending: THREE.AdditiveBlending,
      transparent: true,
      opacity: 0.95,
      depthWrite: false
    });
    this.nucleusSprite = new THREE.Sprite(spriteMat);
    this.nucleusSprite.scale.set(2.2, 2.2, 1.0);
    this.coreGroup.add(this.nucleusSprite);

    // Corona aura sprite (warm deep amber)
    const coronaMat = new THREE.SpriteMaterial({
      map: this.glowTexture,
      color: 0xff7700,
      blending: THREE.AdditiveBlending,
      transparent: true,
      opacity: 0.6,
      depthWrite: false
    });
    this.coronaSprite = new THREE.Sprite(coronaMat);
    this.coronaSprite.scale.set(4.0, 4.0, 1.0);
    this.coreGroup.add(this.coronaSprite);

    // Inner Concentric High-Speed Gimbal Rings (3 rings)
    this.innerRings = [];
    const ringRadii = [0.45, 0.72, 1.05];
    const ringColors = [0xffffff, 0xffd700, 0xff9900];

    ringRadii.forEach((r, idx) => {
      const segs = 64;
      const pts = [];
      for (let i = 0; i <= segs; i++) {
        const theta = (i / segs) * Math.PI * 2;
        pts.push(new THREE.Vector3(Math.cos(theta) * r, Math.sin(theta) * r, 0));
      }
      const geom = new THREE.BufferGeometry().setFromPoints(pts);
      const mat = new THREE.LineBasicMaterial({
        color: ringColors[idx],
        transparent: true,
        opacity: 0.85 - idx * 0.15,
        blending: THREE.AdditiveBlending,
        depthWrite: false
      });
      const ring = new THREE.LineLoop(geom, mat);
      ring.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, 0);
      ring.userData = {
        rotSpeedX: (0.02 + idx * 0.015) * (idx % 2 === 0 ? 1 : -1),
        rotSpeedY: (0.025 - idx * 0.01) * (idx % 2 === 0 ? -1 : 1),
        baseScale: 1.0
      };
      this.innerRings.push(ring);
      this.coreGroup.add(ring);
    });

    // Core energy vortex filaments (concentrated spinning particle ring)
    const vortexCount = 180;
    const vortexGeom = new THREE.BufferGeometry();
    const vortexPos = new Float32Array(vortexCount * 3);
    const vortexCol = new Float32Array(vortexCount * 3);

    for (let i = 0; i < vortexCount; i++) {
      const angle = (i / vortexCount) * Math.PI * 2;
      const r = 0.5 + Math.random() * 0.6;
      const z = (Math.random() - 0.5) * 0.4;
      vortexPos[i * 3] = Math.cos(angle) * r;
      vortexPos[i * 3 + 1] = Math.sin(angle) * r;
      vortexPos[i * 3 + 2] = z;

      vortexCol[i * 3] = 1.0;
      vortexCol[i * 3 + 1] = 0.85 + Math.random() * 0.15;
      vortexCol[i * 3 + 2] = 0.3 + Math.random() * 0.4;
    }
    vortexGeom.setAttribute("position", new THREE.BufferAttribute(vortexPos, 3));
    vortexGeom.setAttribute("color", new THREE.BufferAttribute(vortexCol, 3));

    const vortexMat = new THREE.PointsMaterial({
      size: 0.09,
      map: this.glowTexture,
      vertexColors: true,
      blending: THREE.AdditiveBlending,
      transparent: true,
      opacity: 0.9,
      depthWrite: false
    });
    this.vortexPoints = new THREE.Points(vortexGeom, vortexMat);
    this.coreGroup.add(this.vortexPoints);

    this.reactorGroup.add(this.coreGroup);
  }

  // =========================================================================
  // LAYER 2: INNER COMPUTATIONAL STRUCTURE (Cybernetic Curved & Stepped Traces)
  // =========================================================================
  buildLayer2_ComputationalStructure() {
    this.compGroup = new THREE.Group();

    // Procedural Circuit Traces on Concentric Spherical Shells
    const linePoints = [];
    const numTraces = 60;

    for (let t = 0; t < numTraces; t++) {
      const radius = 1.3 + Math.random() * 1.5;
      let phi = Math.acos(2 * Math.random() - 1);
      let theta = Math.random() * Math.PI * 2;

      // Start coordinate
      let p0 = new THREE.Vector3().setFromSphericalCoords(radius, phi, theta);
      const steps = 3 + Math.floor(Math.random() * 4);

      for (let s = 0; s < steps; s++) {
        // Step either along latitude (phi) or longitude (theta) for 90-degree circuit traces
        if (Math.random() > 0.5) {
          theta += (Math.random() - 0.5) * 0.5;
        } else {
          phi = Math.max(0.1, Math.min(Math.PI - 0.1, phi + (Math.random() - 0.5) * 0.4));
        }
        let p1 = new THREE.Vector3().setFromSphericalCoords(radius, phi, theta);
        linePoints.push(p0.x, p0.y, p0.z);
        linePoints.push(p1.x, p1.y, p1.z);
        p0 = p1;
      }
    }

    const compGeom = new THREE.BufferGeometry();
    compGeom.setAttribute("position", new THREE.Float32BufferAttribute(linePoints, 3));
    const compMat = new THREE.LineBasicMaterial({
      color: 0xffaa00,
      transparent: true,
      opacity: 0.6,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    this.compLines = new THREE.LineSegments(compGeom, compMat);
    this.compGroup.add(this.compLines);

    this.reactorGroup.add(this.compGroup);
  }

  // =========================================================================
  // LAYER 3: NEURAL PARTICLE FIELD (3,500+ Floating Glowing Gold/Amber Photons)
  // =========================================================================
  buildLayer3_NeuralParticleField() {
    this.particleCount = 3800;
    const geom = new THREE.BufferGeometry();
    const positions = new Float32Array(this.particleCount * 3);
    const colors = new Float32Array(this.particleCount * 3);
    const sizes = new Float32Array(this.particleCount);

    this.particleMeta = [];

    const goldHues = [
      new THREE.Color(0xffffff), // intense white-gold core
      new THREE.Color(0xffe070), // bright gold
      new THREE.Color(0xffaa00), // warm amber
      new THREE.Color(0xff7700), // deep orange
      new THREE.Color(0xff4400)  // energy red-orange
    ];

    for (let i = 0; i < this.particleCount; i++) {
      // Clustered radius distribution (dense towards core, expanding outwards)
      const u = Math.random();
      const r = 0.8 + Math.pow(u, 1.8) * (this.baseRadius - 0.4);
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);

      const x = r * Math.sin(phi) * Math.cos(theta);
      const y = r * Math.sin(phi) * Math.sin(theta);
      const z = r * Math.cos(phi);

      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;

      // Color based on radial distance
      let colIdx = Math.min(goldHues.length - 1, Math.floor((r / this.baseRadius) * goldHues.length));
      if (Math.random() < 0.15) colIdx = 0; // occasional pure white sparks
      const col = goldHues[colIdx];

      colors[i * 3] = col.r;
      colors[i * 3 + 1] = col.g;
      colors[i * 3 + 2] = col.b;

      sizes[i] = 0.05 + Math.random() * 0.12;

      this.particleMeta.push({
        radius: r,
        theta: theta,
        phi: phi,
        speedTheta: (Math.random() - 0.5) * 0.006,
        speedPhi: (Math.random() - 0.5) * 0.003,
        pulseOffset: Math.random() * Math.PI * 2
      });
    }

    geom.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geom.setAttribute("color", new THREE.BufferAttribute(colors, 3));

    const mat = new THREE.PointsMaterial({
      size: 0.12,
      map: this.glowTexture,
      vertexColors: true,
      blending: THREE.AdditiveBlending,
      transparent: true,
      opacity: 0.9,
      depthWrite: false
    });

    this.particleField = new THREE.Points(geom, mat);
    this.reactorGroup.add(this.particleField);
  }

  // =========================================================================
  // LAYER 4: COMPUTATIONAL NETWORK (3D Interconnected Nodes & Filaments)
  // =========================================================================
  buildLayer4_ComputationalNetwork() {
    this.netGroup = new THREE.Group();
    const nodeCount = 140;
    const nodes = [];

    for (let i = 0; i < nodeCount; i++) {
      const r = 1.4 + Math.random() * 2.1;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      nodes.push(new THREE.Vector3().setFromSphericalCoords(r, phi, theta));
    }

    // Interconnect nearest neighbors
    const linePos = [];
    const maxDist = 1.25;

    for (let i = 0; i < nodeCount; i++) {
      let connections = 0;
      for (let j = i + 1; j < nodeCount; j++) {
        const d = nodes[i].distanceTo(nodes[j]);
        if (d < maxDist && connections < 3) {
          linePos.push(nodes[i].x, nodes[i].y, nodes[i].z);
          linePos.push(nodes[j].x, nodes[j].y, nodes[j].z);
          connections++;
        }
      }
    }

    const netGeom = new THREE.BufferGeometry();
    netGeom.setAttribute("position", new THREE.Float32BufferAttribute(linePos, 3));
    const netMat = new THREE.LineBasicMaterial({
      color: 0xffaa00,
      transparent: true,
      opacity: 0.45,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    this.networkLines = new THREE.LineSegments(netGeom, netMat);
    this.netGroup.add(this.networkLines);

    // Traveling Data Packets on Network Lines
    this.dataPacketCount = 35;
    const packetGeom = new THREE.BufferGeometry();
    const packetPos = new Float32Array(this.dataPacketCount * 3);
    packetGeom.setAttribute("position", new THREE.BufferAttribute(packetPos, 3));

    const packetMat = new THREE.PointsMaterial({
      size: 0.16,
      map: this.glowTexture,
      color: 0xffffff,
      blending: THREE.AdditiveBlending,
      transparent: true,
      opacity: 1.0,
      depthWrite: false
    });
    this.dataPackets = new THREE.Points(packetGeom, packetMat);
    this.netGroup.add(this.dataPackets);

    // Store line segments for packet trajectory calculation
    this.netLinePoints = linePos;

    this.reactorGroup.add(this.netGroup);
  }

  // =========================================================================
  // LAYER 5: FRAGMENTED OUTER SHELL (Broken Arcs, Stepped Circuits & Floating Chips)
  // =========================================================================
  buildLayer5_FragmentedOuterShell() {
    this.shellGroup = new THREE.Group();

    // 1. Broken Outer Circular Arcs
    const arcPoints = [];
    const numArcs = 32;
    const R = this.baseRadius;

    for (let a = 0; a < numArcs; a++) {
      const arcRadius = R * (0.92 + Math.random() * 0.2); // Some extend beyond boundary
      const arcLen = 0.2 + Math.random() * 0.6; // Incomplete arc segment
      const startAngle = Math.random() * Math.PI * 2;
      const tiltX = (Math.random() - 0.5) * Math.PI;
      const tiltY = (Math.random() - 0.5) * Math.PI;

      const segs = 16;
      let prevPt = null;

      for (let s = 0; s <= segs; s++) {
        const theta = startAngle + (s / segs) * arcLen;
        let v = new THREE.Vector3(Math.cos(theta) * arcRadius, Math.sin(theta) * arcRadius, 0);
        v.applyEuler(new THREE.Euler(tiltX, tiltY, 0));

        if (prevPt) {
          arcPoints.push(prevPt.x, prevPt.y, prevPt.z);
          arcPoints.push(v.x, v.y, v.z);
        }
        prevPt = v.clone();
      }
    }

    // 2. Stepped Rectangular Holographic Fragment Wireframes
    for (let f = 0; f < 24; f++) {
      const fR = R * (0.95 + Math.random() * 0.18);
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const center = new THREE.Vector3().setFromSphericalCoords(fR, phi, theta);

      const w = 0.15 + Math.random() * 0.25;
      const h = 0.08 + Math.random() * 0.18;

      // Small tangential box outline
      const corner1 = center.clone().add(new THREE.Vector3(-w, -h, 0));
      const corner2 = center.clone().add(new THREE.Vector3(w, -h, 0));
      const corner3 = center.clone().add(new THREE.Vector3(w, h, 0));
      const corner4 = center.clone().add(new THREE.Vector3(-w, h, 0));

      arcPoints.push(corner1.x, corner1.y, corner1.z, corner2.x, corner2.y, corner2.z);
      arcPoints.push(corner2.x, corner2.y, corner2.z, corner3.x, corner3.y, corner3.z);
      arcPoints.push(corner3.x, corner3.y, corner3.z, corner4.x, corner4.y, corner4.z);
      arcPoints.push(corner4.x, corner4.y, corner4.z, corner1.x, corner1.y, corner1.z);
    }

    const shellGeom = new THREE.BufferGeometry();
    shellGeom.setAttribute("position", new THREE.Float32BufferAttribute(arcPoints, 3));
    const shellMat = new THREE.LineBasicMaterial({
      color: 0xff8800,
      transparent: true,
      opacity: 0.55,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    this.shellLines = new THREE.LineSegments(shellGeom, shellMat);
    this.shellGroup.add(this.shellLines);

    this.reactorGroup.add(this.shellGroup);
  }

  // =========================================================================
  // LAYER 6: ORBITAL RINGS (14 Independent Tilted Computational Energy Fields)
  // =========================================================================
  buildLayer6_OrbitalRings() {
    this.ringsGroup = new THREE.Group();
    this.orbitalRings = [];

    const ringCount = 14;
    const ringConfigs = [
      { rPct: 0.55, pitch: 0.2, yaw: 0.0, roll: 0.0, speed: 0.012, color: 0xffd700, opacity: 0.75, ticks: true },
      { rPct: 0.70, pitch: -0.4, yaw: 0.5, roll: 0.2, speed: -0.015, color: 0xffaa00, opacity: 0.65, ticks: false },
      { rPct: 0.85, pitch: 0.7, yaw: -0.3, roll: 0.4, speed: 0.009, color: 0xff8800, opacity: 0.6, ticks: true },
      { rPct: 0.95, pitch: -0.15, yaw: 0.1, roll: -0.6, speed: -0.018, color: 0xffd700, opacity: 0.8, ticks: true },
      { rPct: 1.05, pitch: 0.5, yaw: 0.8, roll: 0.1, speed: 0.007, color: 0xff9900, opacity: 0.5, ticks: false },
      { rPct: 1.15, pitch: -0.6, yaw: -0.7, roll: -0.3, speed: -0.011, color: 0xff7700, opacity: 0.45, ticks: false },
      { rPct: 1.25, pitch: 0.1, yaw: -0.9, roll: 0.8, speed: 0.014, color: 0xffaa00, opacity: 0.4, ticks: true }
    ];

    // Double to reach 14 rings with varied inclinations
    while (ringConfigs.length < ringCount) {
      const base = ringConfigs[ringConfigs.length % 7];
      ringConfigs.push({
        rPct: base.rPct * (0.9 + Math.random() * 0.2),
        pitch: (Math.random() - 0.5) * Math.PI,
        yaw: (Math.random() - 0.5) * Math.PI,
        roll: (Math.random() - 0.5) * Math.PI,
        speed: (Math.random() - 0.5) * 0.02,
        color: base.color,
        opacity: 0.35 + Math.random() * 0.4,
        ticks: Math.random() > 0.4
      });
    }

    ringConfigs.forEach((cfg) => {
      const r = this.baseRadius * cfg.rPct * 0.82;
      const segs = 96;
      const pts = [];

      for (let i = 0; i <= segs; i++) {
        const theta = (i / segs) * Math.PI * 2;
        pts.push(new THREE.Vector3(Math.cos(theta) * r, Math.sin(theta) * r, 0));
      }

      const ringGeom = new THREE.BufferGeometry().setFromPoints(pts);
      const ringMat = new THREE.LineBasicMaterial({
        color: cfg.color,
        transparent: true,
        opacity: cfg.opacity,
        blending: THREE.AdditiveBlending,
        depthWrite: false
      });
      const ringMesh = new THREE.LineLoop(ringGeom, ringMat);

      // Ring Pivot Container for Euler rotation
      const pivot = new THREE.Group();
      pivot.rotation.set(cfg.pitch, cfg.yaw, cfg.roll);
      pivot.add(ringMesh);

      // Optional Radial Ticks along ring perimeter (Instrument / Calibration look)
      if (cfg.ticks) {
        const tickPts = [];
        const numTicks = 36;
        for (let t = 0; t < numTicks; t++) {
          const a = (t / numTicks) * Math.PI * 2;
          const tickLen = (t % 4 === 0) ? 0.14 : 0.07;
          tickPts.push(Math.cos(a) * (r - tickLen), Math.sin(a) * (r - tickLen), 0);
          tickPts.push(Math.cos(a) * r, Math.sin(a) * r, 0);
        }
        const tickGeom = new THREE.BufferGeometry();
        tickGeom.setAttribute("position", new THREE.Float32BufferAttribute(tickPts, 3));
        const tickMat = new THREE.LineBasicMaterial({
          color: cfg.color,
          transparent: true,
          opacity: cfg.opacity * 0.8,
          blending: THREE.AdditiveBlending,
          depthWrite: false
        });
        const tickMesh = new THREE.LineSegments(tickGeom, tickMat);
        pivot.add(tickMesh);
      }

      // Orbiting Carrier Photon on the ring
      const carrierGeom = new THREE.BufferGeometry();
      carrierGeom.setAttribute("position", new THREE.Float32BufferAttribute([r, 0, 0], 3));
      const carrierMat = new THREE.PointsMaterial({
        size: 0.2,
        map: this.glowTexture,
        color: 0xffffff,
        blending: THREE.AdditiveBlending,
        transparent: true,
        opacity: 0.95,
        depthWrite: false
      });
      const carrier = new THREE.Points(carrierGeom, carrierMat);
      pivot.add(carrier);

      pivot.userData = {
        speed: cfg.speed,
        radius: r,
        carrierAngle: Math.random() * Math.PI * 2,
        carrierObj: carrier
      };

      this.orbitalRings.push(pivot);
      this.ringsGroup.add(pivot);
    });

    this.reactorGroup.add(this.ringsGroup);
  }

  // =========================================================================
  // LAYER 7: RADIAL ENERGY STREAMS (Spokes with Outward Traveling Data Pulses)
  // =========================================================================
  buildLayer7_RadialEnergyStreams() {
    this.streamGroup = new THREE.Group();
    const spokeCount = 52;
    const spokePts = [];
    this.spokeVectors = [];

    for (let i = 0; i < spokeCount; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const dir = new THREE.Vector3().setFromSphericalCoords(1.0, phi, theta);

      const rInner = 0.5 + Math.random() * 0.4;
      const rOuter = this.baseRadius * (0.85 + Math.random() * 0.25);

      const pIn = dir.clone().multiplyScalar(rInner);
      const pOut = dir.clone().multiplyScalar(rOuter);

      spokePts.push(pIn.x, pIn.y, pIn.z);
      spokePts.push(pOut.x, pOut.y, pOut.z);

      this.spokeVectors.push({ in: pIn, out: pOut, dir: dir, rIn: rInner, rOut: rOuter });
    }

    const streamGeom = new THREE.BufferGeometry();
    streamGeom.setAttribute("position", new THREE.Float32BufferAttribute(spokePts, 3));
    const streamMat = new THREE.LineBasicMaterial({
      color: 0xff8800,
      transparent: true,
      opacity: 0.35,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    this.streamLines = new THREE.LineSegments(streamGeom, streamMat);
    this.streamGroup.add(this.streamLines);

    // Traveling Radial Photon Pulses
    this.pulseSparksCount = 30;
    const pulseGeom = new THREE.BufferGeometry();
    const pulsePos = new Float32Array(this.pulseSparksCount * 3);
    pulseGeom.setAttribute("position", new THREE.BufferAttribute(pulsePos, 3));

    const pulseMat = new THREE.PointsMaterial({
      size: 0.18,
      map: this.glowTexture,
      color: 0xffffff,
      blending: THREE.AdditiveBlending,
      transparent: true,
      opacity: 1.0,
      depthWrite: false
    });
    this.pulseSparks = new THREE.Points(pulseGeom, pulseMat);
    this.streamGroup.add(this.pulseSparks);

    this.sparksMeta = [];
    for (let s = 0; s < this.pulseSparksCount; s++) {
      this.sparksMeta.push({
        spokeIdx: Math.floor(Math.random() * spokeCount),
        t: Math.random(),
        speed: 0.015 + Math.random() * 0.02
      });
    }

    this.reactorGroup.add(this.streamGroup);
  }

  // =========================================================================
  // INTERACTION & RESIZE
  // =========================================================================
  setupEvents() {
    window.addEventListener("resize", () => {
      this.width = this.container.clientWidth || 580;
      this.height = this.container.clientHeight || 580;
      this.camera.aspect = this.width / this.height;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(this.width, this.height);
    });

    window.addEventListener("mousemove", (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      this.mouse.targetX = (e.clientX - cx) / (window.innerWidth / 2);
      this.mouse.targetY = (e.clientY - cy) / (window.innerHeight / 2);
    });

    // Touch support
    window.addEventListener("touchmove", (e) => {
      if (e.touches.length > 0) {
        const t = e.touches[0];
        const rect = this.canvas.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        this.mouse.targetX = (t.clientX - cx) / (window.innerWidth / 2);
        this.mouse.targetY = (t.clientY - cy) / (window.innerHeight / 2);
      }
    });
  }

  // =========================================================================
  // STATE & AUDIO INTERFACES
  // =========================================================================
  setState(newState) {
    if (this.state !== newState) {
      console.log(`[JarvisReactor3D] State change: ${this.state} -> ${newState}`);
      this.state = newState;
    }
  }

  updateAudio(energy, freqArray) {
    this.audioEnergy = energy || 0.0;
    if (freqArray && freqArray.length >= 32) {
      this.audioFreqs = freqArray;
    }
  }

  // =========================================================================
  // 60FPS MASTER ANIMATION LOOP
  // =========================================================================
  animate() {
    requestAnimationFrame(this.animate);
    this.pulseTime += 0.02;

    // Smooth Mouse Parallax Damping
    this.mouse.x += (this.mouse.targetX - this.mouse.x) * 0.05;
    this.mouse.y += (this.mouse.targetY - this.mouse.y) * 0.05;

    // Idle Harmonic Parallax & Camera Float
    const floatY = Math.sin(this.pulseTime * 0.7) * 0.08;
    const floatX = Math.cos(this.pulseTime * 0.5) * 0.06;

    this.camera.position.x = this.mouse.x * 0.45 + floatX;
    this.camera.position.y = -this.mouse.y * 0.35 + floatY;
    this.camera.lookAt(0, 0, 0);

    // State Modifiers
    let speedMult = 1.0;
    let energyBoost = this.audioEnergy;
    let corePulseFreq = 2.0;
    let coreBaseScale = 2.2;

    switch (this.state) {
      case "LISTENING":
        speedMult = 1.4;
        energyBoost = Math.max(energyBoost, 0.4);
        coreBaseScale = 2.6;
        break;
      case "THINKING":
        speedMult = 2.5;
        corePulseFreq = 6.0;
        energyBoost = 0.6 + Math.sin(this.pulseTime * 8) * 0.25;
        break;
      case "EXECUTING":
        speedMult = 3.0;
        energyBoost = 0.8;
        break;
      case "SPEAKING":
        speedMult = 1.3;
        energyBoost = 0.3 + Math.sin(this.pulseTime * 5) * 0.35;
        coreBaseScale = 2.4;
        break;
      case "SUCCESS":
        speedMult = 1.2;
        energyBoost = 0.5 + Math.sin(this.pulseTime * 3) * 0.2;
        coreBaseScale = 2.4;
        break;
      case "ERROR":
        speedMult = 0.5;
        break;
      default: // IDLE
        speedMult = 1.0;
        break;
    }

    // 1. Core Pulsing & Breathing
    const corePulse = Math.sin(this.pulseTime * corePulseFreq) * 0.15;
    const nScale = (coreBaseScale + corePulse) * (1.0 + energyBoost * 0.25);
    this.nucleusSprite.scale.set(nScale, nScale, 1.0);
    this.coronaSprite.scale.set(nScale * 1.8, nScale * 1.8, 1.0);

    // Rotate Core Inner Rings
    this.innerRings.forEach((r) => {
      r.rotation.x += r.userData.rotSpeedX * speedMult;
      r.rotation.y += r.userData.rotSpeedY * speedMult;
      const s = 1.0 + energyBoost * 0.15;
      r.scale.set(s, s, s);
    });

    // Spin Core Vortex
    if (this.vortexPoints) {
      this.vortexPoints.rotation.z += 0.03 * speedMult;
    }

    // 2. Rotate Computational Structure
    if (this.compLines) {
      this.compLines.rotation.y += 0.003 * speedMult;
      this.compLines.rotation.x += 0.0015 * speedMult;
    }

    // 3. Animate 3,800 Neural Particles
    const posAttr = this.particleField.geometry.attributes.position;
    const positions = posAttr.array;

    for (let i = 0; i < this.particleCount; i++) {
      const meta = this.particleMeta[i];
      meta.theta += meta.speedTheta * speedMult;
      meta.phi += meta.speedPhi * speedMult;

      const dynamicR = meta.radius * (1.0 + Math.sin(this.pulseTime + meta.pulseOffset) * 0.02 + energyBoost * 0.06);

      positions[i * 3] = dynamicR * Math.sin(meta.phi) * Math.cos(meta.theta);
      positions[i * 3 + 1] = dynamicR * Math.sin(meta.phi) * Math.sin(meta.theta);
      positions[i * 3 + 2] = dynamicR * Math.cos(meta.phi);
    }
    posAttr.needsUpdate = true;
    this.particleField.rotation.y += 0.001 * speedMult;

    // 4. Animate Network Data Packets
    const packetPosAttr = this.dataPackets.geometry.attributes.position;
    const packetPositions = packetPosAttr.array;
    const totalLines = this.netLinePoints.length / 6;

    if (totalLines > 0) {
      for (let p = 0; p < this.dataPacketCount; p++) {
        const lineIdx = (p * 3) % totalLines;
        const progress = ((this.pulseTime * (0.4 + (p % 5) * 0.1) * speedMult) + (p * 0.2)) % 1.0;

        const x1 = this.netLinePoints[lineIdx * 6];
        const y1 = this.netLinePoints[lineIdx * 6 + 1];
        const z1 = this.netLinePoints[lineIdx * 6 + 2];
        const x2 = this.netLinePoints[lineIdx * 6 + 3];
        const y2 = this.netLinePoints[lineIdx * 6 + 4];
        const z2 = this.netLinePoints[lineIdx * 6 + 5];

        packetPositions[p * 3] = x1 + (x2 - x1) * progress;
        packetPositions[p * 3 + 1] = y1 + (y2 - y1) * progress;
        packetPositions[p * 3 + 2] = z1 + (z2 - z1) * progress;
      }
      packetPosAttr.needsUpdate = true;
    }
    this.netGroup.rotation.y -= 0.002 * speedMult;

    // 5. Fragmented Shell Movement
    if (this.shellLines) {
      this.shellLines.rotation.y += 0.0012 * speedMult;
      this.shellLines.rotation.z += 0.0008 * speedMult;
    }

    // 6. Orbital Rings Rotation & Carrier Photons
    this.orbitalRings.forEach((ringPivot) => {
      ringPivot.rotation.z += ringPivot.userData.speed * speedMult;
      ringPivot.userData.carrierAngle += ringPivot.userData.speed * 2.2 * speedMult;

      const cAngle = ringPivot.userData.carrierAngle;
      const cR = ringPivot.userData.radius;
      ringPivot.userData.carrierObj.position.set(Math.cos(cAngle) * cR, Math.sin(cAngle) * cR, 0);
    });

    // 7. Radial Energy Stream Sparks
    const sparkPosAttr = this.pulseSparks.geometry.attributes.position;
    const sparkPositions = sparkPosAttr.array;

    for (let s = 0; s < this.pulseSparksCount; s++) {
      const meta = this.sparksMeta[s];
      meta.t = (meta.t + meta.speed * speedMult) % 1.0;

      const spoke = this.spokeVectors[meta.spokeIdx];
      const curR = spoke.rIn + (spoke.rOut - spoke.rIn) * meta.t;

      sparkPositions[s * 3] = spoke.dir.x * curR;
      sparkPositions[s * 3 + 1] = spoke.dir.y * curR;
      sparkPositions[s * 3 + 2] = spoke.dir.z * curR;
    }
    sparkPosAttr.needsUpdate = true;
    this.streamGroup.rotation.y += 0.0018 * speedMult;

    // Master Reactor Anchor Drift
    this.reactorGroup.rotation.y = this.mouse.x * 0.35;
    this.reactorGroup.rotation.x = -this.mouse.y * 0.25;

    this.renderer.render(this.scene, this.camera);
  }

  setState(newState) {
    const valid = ["IDLE", "LISTENING", "THINKING", "EXECUTING", "SPEAKING", "SUCCESS", "ERROR"];
    if (valid.includes(newState)) {
      this.state = newState;
    }
  }

  setAudioEnergy(energy) {
    this.audioEnergy = Math.max(0.0, Math.min(1.0, energy));
  }
}

// Attach globally
window.JarvisReactor3D = JarvisReactor3D;
