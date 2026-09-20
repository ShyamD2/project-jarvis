"""
Visual Verification Sentinel for Project J.A.R.V.I.S.
Provides closed-loop visual sensory verification for GUI and OS actions.
Captures pre/post action screen states, calculates structural pixel deltas,
and verifies that physical desktop state transformed as expected.
"""

from __future__ import annotations
import os
import time
from typing import Dict, Any, Optional, Tuple
from PIL import Image, ImageChops
import numpy as np

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("VisualSentinel")


class VisualSentinel:
    def __init__(self):
        self._artifact_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/sentinel_snapshots"))
        os.makedirs(self._artifact_dir, exist_ok=True)

    def capture_snapshot(self, label: str = "snap", bbox: Optional[Tuple[int, int, int, int]] = None) -> str:
        """Captures a timestamped screen snapshot and returns path."""
        from PIL import ImageGrab
        img = ImageGrab.grab(bbox=bbox)
        filename = f"{label}_{int(time.time() * 1000)}.png"
        path = os.path.join(self._artifact_dir, filename)
        img.save(path)
        return path

    def verify_visual_transition(
        self,
        baseline_path: str,
        post_path: Optional[str] = None,
        bbox: Optional[Tuple[int, int, int, int]] = None,
        min_diff_percent: float = 0.2
    ) -> Dict[str, Any]:
        """
        Calculates pixel difference between baseline and post-action screenshot.
        Verifies that physical GUI transformation occurred on the desktop.
        """
        if not os.path.exists(baseline_path):
            return {"verified": False, "error": "Baseline snapshot missing"}

        if post_path is None or not os.path.exists(post_path):
            post_path = self.capture_snapshot(label="post", bbox=bbox)

        try:
            img1 = Image.open(baseline_path).convert("RGB")
            img2 = Image.open(post_path).convert("RGB")

            # Ensure matching sizes
            if img1.size != img2.size:
                img2 = img2.resize(img1.size)

            diff = ImageChops.difference(img1, img2)
            diff_arr = np.array(diff)
            # Count pixels with noticeable channel difference (>20)
            changed_pixels = np.sum(diff_arr > 20)
            total_pixels = diff_arr.size
            diff_percent = (changed_pixels / total_pixels) * 100.0

            is_verified = diff_percent >= min_diff_percent
            logger.info(f"[VisualSentinel] Visual transition: diff={diff_percent:.2f}% (min={min_diff_percent}%) -> {'VERIFIED' if is_verified else 'STATIC'}")

            return {
                "verified": is_verified,
                "diff_percent": round(diff_percent, 3),
                "visual_transformed": is_verified,
                "baseline": baseline_path,
                "post": post_path
            }
        except Exception as e:
            logger.error(f"[VisualSentinel] Comparison failed: {e}")
            return {"verified": False, "error": str(e)}


visual_sentinel = VisualSentinel()
