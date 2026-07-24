"use client";

import { useEffect, useRef } from "react";

// ─────────────────────────────────────────
// Population Field
//
// The signature visual of the platform: a canvas of drifting
// points standing in for the synthetic Thai population. Each
// point carries one of three states — buy / hesitant / reject —
// colored from the Thai temple-tile palette (jade / gold / clay).
//
// Passing `progress` (0-100) makes the field "resolve": jitter
// settles, undecided (gold) dots convert toward jade or clay in
// proportion to the given rates, mirroring an actual simulation
// converging on an answer instead of a generic spinner.
// ─────────────────────────────────────────

type Rates = { buy: number; reject: number };

interface PopulationFieldProps {
  density?: number;
  className?: string;
  /** 0–100. Omit for a purely ambient, non-resolving field. */
  progress?: number;
  /** Final buy/reject split the field resolves toward as progress → 100. */
  rates?: Rates;
}

interface Dot {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  state: "buy" | "hesitant" | "reject";
  finalState: "buy" | "hesitant" | "reject";
  flipAt: number;
}

const COLORS = {
  buy: { core: "76, 193, 145", glow: "47, 158, 116" },
  hesitant: { core: "232, 200, 121", glow: "212, 168, 83" },
  reject: { core: "208, 114, 87", glow: "184, 80, 61" },
};

export function PopulationField({
  density = 90,
  className,
  progress,
  rates = { buy: 0.32, reject: 0.24 },
}: PopulationFieldProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const progressRef = useRef(progress);
  progressRef.current = progress;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let width = 0;
    let height = 0;
    let dots: Dot[] = [];
    let raf = 0;

    function seed() {
      const rect = canvas!.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = rect.width;
      height = rect.height;
      canvas!.width = width * dpr;
      canvas!.height = height * dpr;
      ctx!.scale(dpr, dpr);

      const count = Math.round((width * height) / (10000 / density) / 100);
      dots = Array.from({ length: Math.max(60, count) }, () => {
        const roll = Math.random();
        const finalState: Dot["state"] =
          roll < rates.buy ? "buy" : roll < rates.buy + rates.reject ? "reject" : "hesitant";
        return {
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.12,
          vy: (Math.random() - 0.5) * 0.12,
          r: 1 + Math.random() * 1.6,
          state: progressRef.current === undefined ? finalState : "hesitant",
          finalState,
          flipAt: 30 + Math.random() * 65,
        };
      });
    }

    function draw() {
      ctx!.clearRect(0, 0, width, height);
      const p = progressRef.current;
      const settle = p === undefined ? 0 : Math.min(1, p / 100);

      for (const d of dots) {
        // Resolve state as progress passes each dot's flip threshold
        if (p !== undefined && p >= d.flipAt) d.state = d.finalState;

        // Motion: drift, dampened as the field settles
        d.x += d.vx * (1 - settle * 0.85);
        d.y += d.vy * (1 - settle * 0.85);
        if (d.x < 0) d.x = width;
        if (d.x > width) d.x = 0;
        if (d.y < 0) d.y = height;
        if (d.y > height) d.y = 0;

        const c = COLORS[d.state];
        const isBuy = d.state === "buy";
        const alpha = d.state === "hesitant" ? 0.55 : 0.85;

        ctx!.beginPath();
        ctx!.fillStyle = `rgba(${c.core}, ${alpha})`;
        if (isBuy) {
          ctx!.shadowBlur = 8;
          ctx!.shadowColor = `rgba(${c.glow}, 0.6)`;
        } else {
          ctx!.shadowBlur = 0;
        }
        ctx!.arc(d.x, d.y, d.r, 0, Math.PI * 2);
        ctx!.fill();
      }
    }

    function loop() {
      draw();
      if (!reduceMotion) raf = requestAnimationFrame(loop);
    }

    seed();
    draw();
    if (!reduceMotion) raf = requestAnimationFrame(loop);

    const ro = new ResizeObserver(() => {
      seed();
      draw();
    });
    ro.observe(canvas);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [density, rates.buy, rates.reject]);

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />;
}
