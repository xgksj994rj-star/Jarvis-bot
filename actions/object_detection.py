"""
Object Detection & Tracking
Detects, highlights, and tracks objects on screen in real-time
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from PIL import Image, ImageDraw, ImageFont
import asyncio

class ObjectDetector:
    """Detects and tracks objects on screen"""
    
    def __init__(self):
        self.net = None
        self.layer_names = None
        self.classes = None
        self.confidence_threshold = 0.5
        self.nms_threshold = 0.4
        self.tracked_objects = {}
        self.object_counter = 0
        
        self._initialize_yolo()
    
    def _initialize_yolo(self):
        """Initialize YOLOv3 for object detection"""
        try:
            # YOLOv3 pre-trained model
            weights_path = "config/yolov3.weights"
            config_path = "config/yolov3.cfg"
            names_path = "config/coco.names"
            
            # Load class names
            with open(names_path, 'r') as f:
                self.classes = [line.strip() for line in f.readlines()]
            
            # Load network
            self.net = cv2.dnn.readNet(weights_path, config_path)
            
            # Get layer names
            self.layer_names = self.net.getLayerNames()
            self.layer_names = [self.layer_names[i - 1] 
                               for i in self.net.getUnconnectedOutLayers()]
        
        except Exception as e:
            print(f"Could not load YOLOv3. Using fallback object detection: {e}")
            self.use_fallback = True
    
    async def detect_objects(self, image: Image.Image) -> Dict[str, Any]:
        """
        Detect objects in an image
        
        Args:
            image: PIL Image to detect objects in
        
        Returns:
            Detection results with objects and confidence
        """
        result = {
            "objects_detected": [],
            "total_count": 0,
            "annotated_image": None,
            "detection_time": 0
        }
        
        try:
            import time
            start_time = time.time()
            
            # Convert PIL to OpenCV format
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            height, width, _ = cv_image.shape
            
            if self.net:
                # Prepare blob for neural network
                blob = cv2.dnn.blobFromImage(cv_image, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
                self.net.setInput(blob)
                
                # Forward pass
                outs = self.net.forward(self.layer_names)
                
                # Process detections
                boxes = []
                confidences = []
                class_ids = []
                
                for out in outs:
                    for detection in out:
                        scores = detection[5:]
                        class_id = np.argmax(scores)
                        confidence = scores[class_id]
                        
                        if confidence > self.confidence_threshold:
                            # Object detected
                            center_x = int(detection[0] * width)
                            center_y = int(detection[1] * height)
                            w = int(detection[2] * width)
                            h = int(detection[3] * height)
                            
                            # Rectangle coordinates
                            x = int(center_x - w / 2)
                            y = int(center_y - h / 2)
                            
                            boxes.append([x, y, w, h])
                            confidences.append(float(confidence))
                            class_ids.append(class_id)
                
                # Apply NMS (Non-Maximum Suppression)
                indices = cv2.dnn.NMSBoxes(boxes, confidences, self.confidence_threshold, self.nms_threshold)
                
                # Extract final detections
                for i in indices.flatten():
                    x, y, w, h = boxes[i]
                    confidence = confidences[i]
                    class_id = class_ids[i]
                    
                    obj_info = {
                        "class": self.classes[class_id] if self.classes else f"Object {class_id}",
                        "confidence": float(confidence),
                        "bbox": {
                            "x": int(x),
                            "y": int(y),
                            "width": int(w),
                            "height": int(h)
                        }
                    }
                    
                    result["objects_detected"].append(obj_info)
            
            else:
                # Fallback: edge detection
                result = await self._fallback_edge_detection(cv_image)
            
            # Draw annotations
            result["annotated_image"] = await self._annotate_image(image, result["objects_detected"])
            result["total_count"] = len(result["objects_detected"])
            result["detection_time"] = time.time() - start_time
            
            # Track objects
            await self._track_objects(result["objects_detected"])
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    async def _fallback_edge_detection(self, cv_image: np.ndarray) -> Dict[str, Any]:
        """Fallback object detection using edge detection"""
        result = {
            "objects_detected": [],
            "method": "edge_detection"
        }
        
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            
            # Edge detection
            edges = cv2.Canny(gray, 100, 200)
            
            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            # Get bounding boxes for large contours
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 500:  # Minimum size threshold
                    x, y, w, h = cv2.boundingRect(contour)
                    
                    result["objects_detected"].append({
                        "class": "object",
                        "confidence": 0.5,
                        "bbox": {"x": x, "y": y, "width": w, "height": h}
                    })
        
        except:
            pass
        
        return result
    
    async def _annotate_image(self, image: Image.Image, objects: List[Dict]) -> Image.Image:
        """Add bounding boxes and labels to image"""
        try:
            annotated = image.copy()
            draw = ImageDraw.Draw(annotated)
            
            colors = [
                (255, 0, 0),      # Red
                (0, 255, 0),      # Green
                (0, 0, 255),      # Blue
                (255, 255, 0),    # Yellow
                (255, 0, 255),    # Magenta
                (0, 255, 255)     # Cyan
            ]
            
            for i, obj in enumerate(objects):
                bbox = obj["bbox"]
                x, y, w, h = bbox["x"], bbox["y"], bbox["width"], bbox["height"]
                
                color = colors[i % len(colors)]
                
                # Draw bounding box
                draw.rectangle(
                    [(x, y), (x + w, y + h)],
                    outline=color,
                    width=2
                )
                
                # Draw label
                label = f"{obj['class']} ({obj['confidence']:.2f})"
                draw.text((x, y - 10), label, fill=color)
        
        except:
            pass
        
        return annotated
    
    async def _track_objects(self, detected_objects: List[Dict]):
        """Track objects across frames"""
        # Simple centroid tracking
        current_centroids = {}
        
        for obj in detected_objects:
            bbox = obj["bbox"]
            cx = bbox["x"] + bbox["width"] / 2
            cy = bbox["y"] + bbox["height"] / 2
            
            # Find closest tracked object
            min_distance = float('inf')
            closest_id = None
            
            for obj_id, prev_centroid in self.tracked_objects.items():
                distance = np.sqrt((cx - prev_centroid[0])**2 + (cy - prev_centroid[1])**2)
                
                if distance < min_distance and distance < 50:  # Distance threshold
                    min_distance = distance
                    closest_id = obj_id
            
            if closest_id:
                current_centroids[closest_id] = (cx, cy)
            else:
                # New object
                current_centroids[self.object_counter] = (cx, cy)
                self.object_counter += 1
        
        self.tracked_objects = current_centroids
    
    async def count_objects(self, image: Image.Image, 
                           object_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Count specific objects in an image
        
        Args:
            image: Image to analyze
            object_type: Optional specific object to count
        
        Returns:
            Count results
        """
        detection_result = await self.detect_objects(image)
        
        result = {
            "object_type": object_type,
            "count": 0,
            "objects": []
        }
        
        for obj in detection_result["objects_detected"]:
            if not object_type or object_type.lower() in obj["class"].lower():
                result["count"] += 1
                result["objects"].append(obj)
        
        return result
    
    async def highlight_object_type(self, image: Image.Image, 
                                   object_type: str) -> Image.Image:
        """Highlight specific object type in image"""
        detection_result = await self.detect_objects(image)
        
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)
        
        for obj in detection_result["objects_detected"]:
            if object_type.lower() in obj["class"].lower():
                bbox = obj["bbox"]
                x, y, w, h = bbox["x"], bbox["y"], bbox["width"], bbox["height"]
                
                # Highlight with bright color
                draw.rectangle([(x, y), (x + w, y + h)], outline=(0, 255, 255), width=3)
        
        return annotated
    
    async def track_motion(self, previous_image: Image.Image, 
                          current_image: Image.Image) -> Dict[str, Any]:
        """Detect and track motion between frames"""
        result = {
            "motion_detected": False,
            "motion_regions": [],
            "motion_intensity": 0
        }
        
        try:
            # Convert to grayscale
            prev_gray = cv2.cvtColor(np.array(previous_image), cv2.COLOR_RGB2GRAY)
            curr_gray = cv2.cvtColor(np.array(current_image), cv2.COLOR_RGB2GRAY)
            
            # Compute frame difference
            frame_diff = cv2.absdiff(prev_gray, curr_gray)
            
            # Threshold
            _, thresh = cv2.threshold(frame_diff, 30, 255, cv2.THRESH_BINARY)
            
            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            motion_intensity = 0
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 100:
                    x, y, w, h = cv2.boundingRect(contour)
                    result["motion_regions"].append({
                        "x": x, "y": y, "width": w, "height": h
                    })
                    motion_intensity += area
            
            result["motion_detected"] = len(result["motion_regions"]) > 0
            result["motion_intensity"] = int(motion_intensity)
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
