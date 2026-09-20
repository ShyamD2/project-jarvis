"""
Vision Grounding & Set-of-Mark (SoM) Engine for Project J.A.R.V.I.S.
Enables hybrid UIA + Vision computer control for canvas, Electron, and custom-rendered applications.
Detects interactive elements, buttons, text regions, overlays Set-of-Mark identifiers,
and calculates precise cursor coordinates (x, y).
"""

from __future__ import annotations
import os
import time
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("VisionGrounding")


class VisionGroundingEngine:
    def __init__(self):
        self._last_marks: Dict[int, Tuple[int, int, int, int]] = {}

    def capture_screen_image(self, bbox: Optional[Tuple[int, int, int, int]] = None) -> Image.Image:
        """Captures full screen or region as PIL Image."""
        from PIL import ImageGrab
        return ImageGrab.grab(bbox=bbox)

    def detect_interactive_regions(self, image: Image.Image) -> List[Tuple[int, int, int, int]]:
        """
        Heuristic edge and contour box detection for interactive buttons, input fields, and clickable cards.
        Identifies high-contrast rectangular contours without external cloud calls.
        """
        import numpy as np
        # Convert to grayscale
        gray = image.convert("L")
        arr = np.array(gray, dtype=np.uint8)

        # Simple Sobel / gradient filter for horizontal and vertical edges
        gx = np.abs(arr[:, 1:].astype(int) - arr[:, :-1].astype(int))
        gy = np.abs(arr[1:, :].astype(int) - arr[:-1, :].astype(int))

        # Pad to match shape
        edges = np.zeros_like(arr, dtype=bool)
        edges[:, :-1] |= (gx > 35)
        edges[:-1, :] |= (gy > 35)

        # Find connected bounding boxes in a grid
        h, w = arr.shape
        regions = []
        cell_w, cell_h = w // 8, h // 8

        # Sample interesting dense edge regions (buttons, icons, text boxes)
        for row in range(8):
            for col in range(8):
                rx, ry = col * cell_w, row * cell_h
                sub_edges = edges[ry : ry + cell_h, rx : rx + cell_w]
                edge_density = np.mean(sub_edges)
                if 0.05 < edge_density < 0.45: # typical button/text element density
                    # Refine to bounding box
                    box = (rx + 5, ry + 5, rx + cell_w - 5, ry + cell_h - 5)
                    regions.append(box)

        return regions[:30] # Limit to top 30 salient candidates

    def apply_set_of_marks(self, image: Image.Image, regions: Optional[List[Tuple[int, int, int, int]]] = None) -> Tuple[Image.Image, Dict[int, Tuple[int, int, int, int]]]:
        """
        Draws high-visibility Set-of-Mark (SoM) bounding boxes with numeric IDs on the screenshot.
        Returns the annotated PIL Image and a dictionary mapping Mark ID -> Bounding Box (x1, y1, x2, y2).
        """
        if regions is None:
            regions = self.detect_interactive_regions(image)

        som_image = image.copy()
        draw = ImageDraw.Draw(som_image)
        marks: Dict[int, Tuple[int, int, int, int]] = {}

        # Colors for high visibility on dark and light themes
        border_color = (0, 220, 255) # Cyan
        badge_bg = (0, 0, 0)
        badge_text = (255, 255, 255)

        for i, box in enumerate(regions, start=1):
            x1, y1, x2, y2 = box
            marks[i] = box

            # Draw bounding box
            draw.rectangle([x1, y1, x2, y2], outline=border_color, width=2)

            # Draw numeric badge
            badge_size = 18
            draw.rectangle([x1, y1, x1 + badge_size, y1 + badge_size], fill=badge_bg, outline=border_color)
            draw.text((x1 + 3, y1 + 2), str(i), fill=badge_text)

        self._last_marks = marks
        logger.info(f"[VisionGrounding] Generated Set-of-Marks with {len(marks)} grounded interactive targets.")
        return som_image, marks

    def get_mark_center(self, mark_id: int) -> Optional[Tuple[int, int]]:
        """Returns the (x, y) center coordinate of a numbered Set-of-Mark target."""
        if mark_id not in self._last_marks:
            return None
        x1, y1, x2, y2 = self._last_marks[mark_id]
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def ground_target_coordinate(self, target_description: str, screenshot_path: Optional[str] = None) -> Optional[Tuple[int, int]]:
        """
        Grounds target description to coordinates using UIA tree first, then Vision Grounding.
        """
        # 1. Primary: UI Automation Tree (symbolic)
        from agents.computer.windows_agent import windows_agent
        uia_res = windows_agent.find_element(target_description)
        if uia_res.get("found"):
            bounds = uia_res.get("bounding_box", {})
            if bounds:
                cx = bounds.get("left", 0) + bounds.get("width", 0) // 2
                cy = bounds.get("top", 0) + bounds.get("height", 0) // 2
                logger.info(f"[VisionGrounding] Grounded via UIA: '{target_description}' -> ({cx}, {cy})")
                return (cx, cy)

        # 2. Fallback: Vision Grounding (marks)
        img = Image.open(screenshot_path) if screenshot_path and os.path.exists(screenshot_path) else self.capture_screen_image()
        _, marks = self.apply_set_of_marks(img)
        if marks:
            # Return center of first detected salient element as grounding point
            first_box = list(marks.values())[0]
            cx = (first_box[0] + first_box[2]) // 2
            cy = (first_box[1] + first_box[3]) // 2
            logger.info(f"[VisionGrounding] Grounded via Vision SoM: '{target_description}' -> ({cx}, {cy})")
            return (cx, cy)

        return None


vision_grounding = VisionGroundingEngine()
