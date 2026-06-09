"""
Real-Time Annotation Overlay
Display AI insights and labels on screen in real-time
"""

import cv2
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from PIL import Image, ImageDraw, ImageFont
import asyncio
from datetime import datetime

class AnnotationOverlay:
    """Manages real-time screen annotations"""
    
    def __init__(self):
        self.active_annotations = []
        self.overlay_config = {
            "font_size": 12,
            "font_color": (255, 255, 255),
            "background_color": (0, 0, 0),
            "background_alpha": 0.7,
            "line_width": 2
        }
        self.annotation_history = []
    
    async def annotate_screen(self, 
                            image: Image.Image,
                            annotations: List[Dict],
                            include_timestamp: bool = True) -> Image.Image:
        """
        Apply annotations to an image
        
        Args:
            image: Base image to annotate
            annotations: List of annotation objects
            include_timestamp: Whether to include timestamp
        
        Returns:
            Annotated image
        """
        try:
            annotated = image.copy()
            draw = ImageDraw.Draw(annotated)
            
            # Add timestamp
            if include_timestamp:
                timestamp = datetime.now().strftime("%H:%M:%S")
                draw.text(
                    (10, 10),
                    f"Time: {timestamp}",
                    fill=self.overlay_config["font_color"]
                )
            
            # Apply annotations
            for i, annotation in enumerate(annotations):
                annotation_type = annotation.get("type")
                
                if annotation_type == "bbox":
                    await self._draw_bbox(draw, annotation)
                elif annotation_type == "text":
                    await self._draw_text_label(draw, annotation)
                elif annotation_type == "arrow":
                    await self._draw_arrow(draw, annotation)
                elif annotation_type == "highlight":
                    await self._draw_highlight(draw, annotation)
                elif annotation_type == "circle":
                    await self._draw_circle(draw, annotation)
                elif annotation_type == "line":
                    await self._draw_line(draw, annotation)
                elif annotation_type == "polygon":
                    await self._draw_polygon(draw, annotation)
            
            self._record_annotation_batch(annotations)
            return annotated
        
        except Exception as e:
            print(f"Error annotating screen: {e}")
            return image
    
    async def _draw_bbox(self, draw: ImageDraw.ImageDraw, annotation: Dict):
        """Draw bounding box"""
        bbox = annotation.get("bbox", {})
        x, y, w, h = bbox.get("x"), bbox.get("y"), bbox.get("width"), bbox.get("height")
        
        if all([x, y, w, h]):
            color = tuple(annotation.get("color", (0, 255, 0)))
            thickness = annotation.get("thickness", 2)
            
            draw.rectangle(
                [(x, y), (x + w, y + h)],
                outline=color,
                width=thickness
            )
            
            # Add label
            label = annotation.get("label")
            if label:
                draw.text((x, y - 10), label, fill=color)
    
    async def _draw_text_label(self, draw: ImageDraw.ImageDraw, annotation: Dict):
        """Draw text label"""
        text = annotation.get("text", "")
        position = annotation.get("position", (0, 0))
        color = tuple(annotation.get("color", (255, 255, 255)))
        
        # Optional background
        background = annotation.get("background", False)
        if background:
            bbox = draw.textbbox(position, text)
            draw.rectangle(bbox, fill=tuple(annotation.get("bg_color", (0, 0, 0))))
        
        draw.text(position, text, fill=color)
    
    async def _draw_arrow(self, draw: ImageDraw.ImageDraw, annotation: Dict):
        """Draw arrow pointing at something"""
        start = tuple(annotation.get("start", (0, 0)))
        end = tuple(annotation.get("end", (100, 100)))
        color = tuple(annotation.get("color", (0, 255, 255)))
        thickness = annotation.get("thickness", 2)
        
        # Draw arrow line
        draw.line([start, end], fill=color, width=thickness)
        
        # Draw arrow head
        angle = np.arctan2(end[1] - start[1], end[0] - start[0])
        arrow_size = 10
        
        p1_x = int(end[0] - arrow_size * np.cos(angle - np.pi/6))
        p1_y = int(end[1] - arrow_size * np.sin(angle - np.pi/6))
        p2_x = int(end[0] - arrow_size * np.cos(angle + np.pi/6))
        p2_y = int(end[1] - arrow_size * np.sin(angle + np.pi/6))
        
        draw.polygon([end, (p1_x, p1_y), (p2_x, p2_y)], fill=color)
    
    async def _draw_highlight(self, draw: ImageDraw.ImageDraw, annotation: Dict):
        """Draw highlight/selection box"""
        bbox = annotation.get("bbox", {})
        x, y, w, h = bbox.get("x"), bbox.get("y"), bbox.get("width"), bbox.get("height")
        
        if all([x, y, w, h]):
            color = tuple(annotation.get("color", (255, 255, 0)))
            alpha = annotation.get("alpha", 0.3)
            
            # Draw filled rectangle with semi-transparency
            draw.rectangle(
                [(x, y), (x + w, y + h)],
                fill=color,
                outline=color
            )
    
    async def _draw_circle(self, draw: ImageDraw.ImageDraw, annotation: Dict):
        """Draw circle"""
        center = tuple(annotation.get("center", (0, 0)))
        radius = annotation.get("radius", 10)
        color = tuple(annotation.get("color", (0, 255, 0)))
        thickness = annotation.get("thickness", 2)
        
        x, y = center
        draw.ellipse(
            [(x - radius, y - radius), (x + radius, y + radius)],
            outline=color,
            width=thickness
        )
    
    async def _draw_line(self, draw: ImageDraw.ImageDraw, annotation: Dict):
        """Draw line"""
        start = tuple(annotation.get("start", (0, 0)))
        end = tuple(annotation.get("end", (100, 100)))
        color = tuple(annotation.get("color", (255, 255, 255)))
        thickness = annotation.get("thickness", 2)
        
        draw.line([start, end], fill=color, width=thickness)
    
    async def _draw_polygon(self, draw: ImageDraw.ImageDraw, annotation: Dict):
        """Draw polygon"""
        points = annotation.get("points", [])
        color = tuple(annotation.get("color", (0, 255, 0)))
        
        if len(points) >= 3:
            draw.polygon(
                [tuple(p) for p in points],
                fill=color,
                outline=color
            )
    
    def _record_annotation_batch(self, annotations: List[Dict]):
        """Record batch of annotations"""
        self.annotation_history.append({
            "timestamp": datetime.now().isoformat(),
            "annotation_count": len(annotations),
            "annotations": annotations
        })
        
        # Keep history manageable
        if len(self.annotation_history) > 500:
            self.annotation_history = self.annotation_history[-500:]
    
    async def create_insight_overlay(self,
                                    base_image: Image.Image,
                                    insights: List[str],
                                    position: str = "top_right") -> Image.Image:
        """
        Create an overlay panel with AI insights
        
        Args:
            base_image: Base image
            insights: List of insight strings
            position: Position (top_left, top_right, bottom_left, bottom_right)
        
        Returns:
            Image with insight overlay
        """
        try:
            annotated = base_image.copy()
            draw = ImageDraw.Draw(annotated, 'RGBA')
            
            # Panel dimensions
            panel_width = 300
            panel_height = 50 + (len(insights) * 30)
            
            # Calculate position
            img_width, img_height = base_image.size
            if position == "top_right":
                x, y = img_width - panel_width - 10, 10
            elif position == "top_left":
                x, y = 10, 10
            elif position == "bottom_right":
                x, y = img_width - panel_width - 10, img_height - panel_height - 10
            else:  # bottom_left
                x, y = 10, img_height - panel_height - 10
            
            # Draw semi-transparent background
            draw.rectangle(
                [(x, y), (x + panel_width, y + panel_height)],
                fill=(0, 0, 0, 180)
            )
            
            # Draw border
            draw.rectangle(
                [(x, y), (x + panel_width, y + panel_height)],
                outline=(0, 255, 255),
                width=2
            )
            
            # Draw insights
            draw.text((x + 10, y + 10), "🤖 Jarvis Insights:", fill=(0, 255, 255))
            
            for i, insight in enumerate(insights[:5]):  # Limit to 5
                y_offset = y + 40 + (i * 25)
                # Wrap text if too long
                if len(insight) > 30:
                    insight = insight[:27] + "..."
                draw.text((x + 15, y_offset), f"• {insight}", fill=(200, 200, 200))
            
            return annotated
        
        except Exception as e:
            print(f"Error creating insight overlay: {e}")
            return base_image
    
    async def create_debug_overlay(self,
                                  base_image: Image.Image,
                                  debug_info: Dict) -> Image.Image:
        """
        Create a debug information overlay
        
        Args:
            base_image: Base image
            debug_info: Debug information dict
        
        Returns:
            Image with debug info
        """
        try:
            annotated = base_image.copy()
            draw = ImageDraw.Draw(annotated)
            
            y_offset = 10
            
            for key, value in debug_info.items():
                text = f"{key}: {value}"
                draw.text((10, y_offset), text, fill=(0, 255, 0))
                y_offset += 20
            
            return annotated
        
        except Exception as e:
            print(f"Error creating debug overlay: {e}")
            return base_image
    
    async def create_heatmap_overlay(self,
                                    base_image: Image.Image,
                                    heatmap_data: np.ndarray,
                                    alpha: float = 0.5) -> Image.Image:
        """
        Create a heatmap overlay
        
        Args:
            base_image: Base image
            heatmap_data: Heatmap array
            alpha: Transparency (0-1)
        
        Returns:
            Image with heatmap overlay
        """
        try:
            # Normalize heatmap
            heatmap = cv2.normalize(heatmap_data, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            
            # Apply colormap
            heatmap_colored = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
            
            # Convert to PIL
            heatmap_pil = Image.fromarray(cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB))
            
            # Blend with base image
            result = Image.new('RGB', base_image.size)
            result = Image.blend(base_image, heatmap_pil, alpha)
            
            return result
        
        except Exception as e:
            print(f"Error creating heatmap: {e}")
            return base_image
    
    async def get_annotation_statistics(self) -> Dict[str, Any]:
        """Get statistics about annotations"""
        if not self.annotation_history:
            return {"total_annotations": 0}
        
        total_annotations = sum(h["annotation_count"] for h in self.annotation_history)
        
        return {
            "total_annotations": total_annotations,
            "history_size": len(self.annotation_history),
            "avg_per_batch": total_annotations / len(self.annotation_history) if self.annotation_history else 0,
            "most_recent": self.annotation_history[-1]["timestamp"]
        }
