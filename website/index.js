/**
 * Parrot AI - Interactive JavaScript
 * Waveform animations, audio player, and scroll effects
 */

// ============================================================================
// Waveform Animation
// ============================================================================

class WaveformVisualizer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;

    this.ctx = this.canvas.getContext("2d");
    this.waves = [];
    this.particles = [];
    this.animationId = null;

    this.resize();
    window.addEventListener("resize", () => this.resize());

    this.initWaves();
    this.initParticles();
    this.animate();
  }

  resize() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect.width * window.devicePixelRatio;
    this.canvas.height = rect.height * window.devicePixelRatio;
    this.canvas.style.width = rect.width + "px";
    this.canvas.style.height = rect.height + "px";
    this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    this.width = rect.width;
    this.height = rect.height;
  }

  initWaves() {
    const colors = [
      {
        color: "rgba(0, 212, 170, 0.6)",
        amplitude: 40,
        frequency: 0.02,
        speed: 0.03,
      },
      {
        color: "rgba(0, 168, 204, 0.4)",
        amplitude: 30,
        frequency: 0.025,
        speed: 0.02,
      },
      {
        color: "rgba(0, 229, 255, 0.3)",
        amplitude: 25,
        frequency: 0.03,
        speed: 0.025,
      },
    ];

    this.waves = colors.map((w) => ({
      ...w,
      phase: Math.random() * Math.PI * 2,
    }));
  }

  initParticles() {
    for (let i = 0; i < 30; i++) {
      this.particles.push({
        x: Math.random() * this.width,
        y: Math.random() * this.height,
        size: Math.random() * 3 + 1,
        speedX: (Math.random() - 0.5) * 0.5,
        speedY: (Math.random() - 0.5) * 0.5,
        opacity: Math.random() * 0.5 + 0.2,
      });
    }
  }

  drawWave(wave, time) {
    this.ctx.beginPath();
    this.ctx.strokeStyle = wave.color;
    this.ctx.lineWidth = 2;

    const centerY = this.height / 2;

    for (let x = 0; x <= this.width; x++) {
      const y =
        centerY +
        Math.sin(x * wave.frequency + time * wave.speed + wave.phase) *
          wave.amplitude +
        Math.sin(x * wave.frequency * 2 + time * wave.speed * 1.5) *
          (wave.amplitude * 0.3);

      if (x === 0) {
        this.ctx.moveTo(x, y);
      } else {
        this.ctx.lineTo(x, y);
      }
    }

    this.ctx.stroke();

    // Glow effect
    this.ctx.shadowBlur = 15;
    this.ctx.shadowColor = wave.color;
    this.ctx.stroke();
    this.ctx.shadowBlur = 0;
  }

  drawParticles() {
    this.particles.forEach((p) => {
      this.ctx.beginPath();
      this.ctx.fillStyle = `rgba(0, 212, 170, ${p.opacity})`;
      this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      this.ctx.fill();

      // Update position
      p.x += p.speedX;
      p.y += p.speedY;

      // Wrap around
      if (p.x < 0) p.x = this.width;
      if (p.x > this.width) p.x = 0;
      if (p.y < 0) p.y = this.height;
      if (p.y > this.height) p.y = 0;
    });
  }

  animate() {
    const time = performance.now();

    // Clear with fade effect
    this.ctx.fillStyle = "rgba(10, 10, 15, 0.1)";
    this.ctx.fillRect(0, 0, this.width, this.height);

    // Draw waves
    this.waves.forEach((wave) => this.drawWave(wave, time));

    // Draw particles
    this.drawParticles();

    this.animationId = requestAnimationFrame(() => this.animate());
  }
}

// ============================================================================
// Player Waveform
// ============================================================================

class PlayerWaveform {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;

    this.ctx = this.canvas.getContext("2d");
    this.bars = [];
    this.isPlaying = false;

    this.resize();
    window.addEventListener("resize", () => this.resize());

    this.initBars();
    this.draw();
  }

  resize() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect.width * window.devicePixelRatio;
    this.canvas.height = rect.height * window.devicePixelRatio;
    this.canvas.style.width = rect.width + "px";
    this.canvas.style.height = rect.height + "px";
    this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    this.width = rect.width;
    this.height = rect.height;
    this.initBars();
  }

  initBars() {
    this.bars = [];
    const barCount = Math.floor(this.width / 4);

    for (let i = 0; i < barCount; i++) {
      this.bars.push({
        height: Math.random() * 0.5 + 0.2,
        targetHeight: Math.random() * 0.5 + 0.2,
      });
    }
  }

  draw() {
    this.ctx.clearRect(0, 0, this.width, this.height);

    const barWidth = 2;
    const gap = 2;
    const centerY = this.height / 2;

    this.bars.forEach((bar, i) => {
      // Animate height
      if (this.isPlaying) {
        bar.targetHeight = Math.random() * 0.8 + 0.2;
      }
      bar.height += (bar.targetHeight - bar.height) * 0.1;

      const height = bar.height * this.height * 0.8;
      const x = i * (barWidth + gap);

      // Gradient
      const gradient = this.ctx.createLinearGradient(
        x,
        centerY - height / 2,
        x,
        centerY + height / 2,
      );
      gradient.addColorStop(0, "rgba(0, 212, 170, 0.8)");
      gradient.addColorStop(0.5, "rgba(0, 168, 204, 1)");
      gradient.addColorStop(1, "rgba(0, 212, 170, 0.8)");

      this.ctx.fillStyle = gradient;
      this.ctx.fillRect(x, centerY - height / 2, barWidth, height);
    });

    requestAnimationFrame(() => this.draw());
  }

  setPlaying(isPlaying) {
    this.isPlaying = isPlaying;
    if (!isPlaying) {
      this.bars.forEach((bar) => {
        bar.targetHeight = Math.random() * 0.3 + 0.1;
      });
    }
  }
}

// ============================================================================
// Audio Player Controller
// ============================================================================

class AudioPlayer {
  constructor() {
    this.playBtn = document.getElementById("playBtn");
    this.progressFill = document.getElementById("progressFill");
    this.currentTimeEl = document.getElementById("currentTime");
    this.durationEl = document.getElementById("duration");

    if (!this.playBtn) return;

    this.isPlaying = false;
    this.duration = 12; // Demo duration in seconds
    this.currentTime = 0;
    this.intervalId = null;

    this.waveform = new PlayerWaveform("playerWaveform");

    this.playBtn.addEventListener("click", () => this.toggle());
  }

  toggle() {
    this.isPlaying = !this.isPlaying;

    const playIcon = this.playBtn.querySelector(".play-icon");
    const pauseIcon = this.playBtn.querySelector(".pause-icon");

    if (this.isPlaying) {
      playIcon.style.display = "none";
      pauseIcon.style.display = "block";
      this.waveform.setPlaying(true);
      this.startProgress();
    } else {
      playIcon.style.display = "block";
      pauseIcon.style.display = "none";
      this.waveform.setPlaying(false);
      this.stopProgress();
    }
  }

  startProgress() {
    this.intervalId = setInterval(() => {
      this.currentTime += 0.1;

      if (this.currentTime >= this.duration) {
        this.currentTime = 0;
        this.toggle();
        return;
      }

      const progress = (this.currentTime / this.duration) * 100;
      this.progressFill.style.width = progress + "%";
      this.currentTimeEl.textContent = this.formatTime(this.currentTime);
      this.durationEl.textContent = this.formatTime(this.duration);
    }, 100);
  }

  stopProgress() {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }

  formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  }
}

// ============================================================================
// Scroll Animations
// ============================================================================

function initScrollAnimations() {
  const observerOptions = {
    threshold: 0.1,
    rootMargin: "0px 0px -50px 0px",
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("animate-in");
      }
    });
  }, observerOptions);

  // Observe elements
  document
    .querySelectorAll(".feature-card, .step, .tech-item")
    .forEach((el) => {
      el.style.opacity = "0";
      el.style.transform = "translateY(30px)";
      el.style.transition = "opacity 0.6s ease, transform 0.6s ease";
      observer.observe(el);
    });
}

// Add animate-in class styles
const style = document.createElement("style");
style.textContent = `
    .animate-in {
        opacity: 1 !important;
        transform: translateY(0) !important;
    }
`;
document.head.appendChild(style);

// ============================================================================
// Navbar Background on Scroll
// ============================================================================

function initNavbarScroll() {
  const navbar = document.querySelector(".navbar");

  window.addEventListener("scroll", () => {
    if (window.scrollY > 50) {
      navbar.style.background = "rgba(10, 10, 15, 0.95)";
    } else {
      navbar.style.background = "rgba(10, 10, 15, 0.8)";
    }
  });
}

// ============================================================================
// Smooth Scroll for Anchor Links
// ============================================================================

function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", (e) => {
      e.preventDefault();
      const target = document.querySelector(anchor.getAttribute("href"));
      if (target) {
        const offset = 80; // Navbar height
        const position = target.offsetTop - offset;

        window.scrollTo({
          top: position,
          behavior: "smooth",
        });
      }
    });
  });
}

// ============================================================================
// Initialize
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {
  // Initialize waveform
  new WaveformVisualizer("waveformCanvas");

  // Initialize audio player
  new AudioPlayer();

  // Initialize scroll animations
  initScrollAnimations();

  // Initialize navbar
  initNavbarScroll();

  // Initialize smooth scroll
  initSmoothScroll();

  // Set initial duration display
  const durationEl = document.getElementById("duration");
  if (durationEl) {
    durationEl.textContent = "0:12";
  }

  console.log("🦜 Parrot AI - Website loaded successfully!");
});
