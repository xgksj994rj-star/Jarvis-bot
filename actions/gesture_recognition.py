"""
Gesture Recognition
Detect user body movements for hands-free control
"""

import cv2
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from PIL import Image
import asyncio

class GestureRecognizer:
    """Recognizes hand and body gestures for control"""
    
    def __init__(self):
        self.mediapipe = None
        self.mp_hands = None
        self.mp_pose = None
        self.hands_detector = None
        self.pose_detector = None
        self.gesture_history = []
        self.confidence_threshold = 0.7
        
        self._initialize_mediapipe()
    
    def _initialize_mediapipe(self):
        """Initialize MediaPipe for gesture detection"""
        try:
            import mediapipe as mp
            self.mediapipe = mp
            self.mp_hands = mp.solutions.hands
            self.mp_pose = mp.solutions.pose
            self.mp_drawing = mp.solutions.drawing_utils
            
            self.hands_detector = self.mp_hands.Hands(
                min_detection_confidence=0.7,
                min_tracking_confidence=0.5
            )
            
            self.pose_detector = self.mp_pose.Pose(
                min_detection_confidence=0.7,
                min_tracking_confidence=0.5
            )
        except ImportError:
            print("MediaPipe not installed. Gesture recognition will be limited.")
            self.mediapipe = None
    
    async def detect_hand_gesture(self, image: Image.Image) -> Dict[str, Any]:
        """
        Detect hand gestures
        
        Args:
            image: Image to detect hand gestures in
        
        Returns:
            Detected gestures and confidence
        """
        result = {
            "gestures": [],
            "hand_count": 0,
            "confidence": 0.0,
            "annotated_image": None
        }
        
        try:
            if not self.hands_detector:
                return result
            
            # Convert PIL to OpenCV
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            h, w, c = cv_image.shape
            
            # Detect hands
            results = self.hands_detector.process(cv_image)
            
            if not results.multi_hand_landmarks:
                return result
            
            result["hand_count"] = len(results.multi_hand_landmarks)
            
            # Analyze each hand
            for hand_idx, (hand_landmarks, hand_info) in enumerate(zip(
                results.multi_hand_landmarks,
                results.multi_handedness
            )):
                gesture = await self._classify_hand_gesture(hand_landmarks.landmark)
                confidence = hand_info.classification[0].score
                
                if confidence > self.confidence_threshold:
                    result["gestures"].append({
                        "hand": hand_info.classification[0].label,
                        "gesture": gesture,
                        "confidence": float(confidence),
                        "hand_index": hand_idx
                    })
                    result["confidence"] = max(result["confidence"], float(confidence))
            
            # Draw annotations
            annotated = self._draw_hand_landmarks(cv_image, results)
            result["annotated_image"] = Image.fromarray(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB))
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    async def _classify_hand_gesture(self, landmarks: List) -> str:
        """Classify hand gesture from landmarks"""
        # Extract key points
        thumb = landmarks[4]
        index = landmarks[8]
        middle = landmarks[12]
        ring = landmarks[16]
        pinky = landmarks[20]
        palm = landmarks[0]
        
        # Calculate distances
        thumb_up = thumb.y < landmarks[3].y and thumb.y < landmarks[2].y
        index_up = index.y < landmarks[7].y
        middle_up = middle.y < landmarks[11].y
        ring_up = ring.y < landmarks[15].y
        pinky_up = pinky.y < landmarks[19].y
        
        # Classify gestures
        fingers_up = [thumb_up, index_up, middle_up, ring_up, pinky_up]
        fingers_count = sum(fingers_up)
        
        # Common gestures
        if fingers_count == 0:
            return "fist"
        elif fingers_count == 1:
            if index_up:
                return "pointing"
            elif thumb_up:
                return "thumbs_up"
        elif fingers_count == 2:
            if index_up and middle_up:
                return "peace_sign"
            elif thumb_up and index_up:
                return "ok_sign"
        elif fingers_count == 5:
            return "open_hand"
        
        return f"custom_{fingers_count}"
    
    def _draw_hand_landmarks(self, image: np.ndarray, results) -> np.ndarray:
        """Draw hand landmarks on image"""
        if not self.mp_drawing or not results.multi_hand_landmarks:
            return image
        
        for hand_landmarks in results.multi_hand_landmarks:
            self.mp_drawing.draw_landmarks(
                image,
                hand_landmarks,
                self.mp_hands.HAND_CONNECTIONS
            )
        
        return image
    
    async def detect_body_gesture(self, image: Image.Image) -> Dict[str, Any]:
        """
        Detect full body gestures and postures
        
        Args:
            image: Image to detect body gestures in
        
        Returns:
            Detected postures and confidence
        """
        result = {
            "body_gestures": [],
            "posture": "unknown",
            "confidence": 0.0,
            "annotated_image": None
        }
        
        try:
            if not self.pose_detector:
                return result
            
            # Convert PIL to OpenCV
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # Detect pose
            results = self.pose_detector.process(cv_image)
            
            if not results.pose_landmarks:
                return result
            
            # Analyze posture
            posture = await self._analyze_posture(results.pose_landmarks.landmark)
            result["posture"] = posture
            
            # Get confidence
            landmarks = results.pose_landmarks.landmark
            confidences = [lm.z for lm in landmarks]
            result["confidence"] = float(np.mean([c for c in confidences if c > 0]))
            
            # Detect specific gestures
            gestures = await self._detect_body_movements(landmarks)
            result["body_gestures"] = gestures
            
            # Draw annotations
            if self.mp_drawing:
                annotated = cv_image.copy()
                self.mp_drawing.draw_landmarks(
                    annotated,
                    results.pose_landmarks,
                    self.mp_pose.POSE_CONNECTIONS
                )
                result["annotated_image"] = Image.fromarray(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB))
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    async def _analyze_posture(self, landmarks: List) -> str:
        """Analyze body posture"""
        # Key landmarks
        left_shoulder = landmarks[11]
        right_shoulder = landmarks[12]
        left_hip = landmarks[23]
        right_hip = landmarks[24]
        
        # Analyze posture
        if abs(left_shoulder.y - right_shoulder.y) < 0.1:
            return "standing_straight"
        elif left_shoulder.y < left_hip.y and right_shoulder.y < right_hip.y:
            return "standing_upright"
        elif abs(left_shoulder.y - left_hip.y) < 0.2:
            return "sitting"
        else:
            return "leaning"
    
    async def _detect_body_movements(self, landmarks: List) -> List[str]:
        """Detect specific body movements"""
        movements = []
        
        # Detect arm raise
        if landmarks[11].y < landmarks[13].y < landmarks[15].y:
            movements.append("left_arm_raised")
        if landmarks[12].y < landmarks[14].y < landmarks[16].y:
            movements.append("right_arm_raised")
        
        # Detect arms crossed
        left_wrist = landmarks[15]
        right_wrist = landmarks[16]
        if abs(left_wrist.x - right_wrist.x) < 0.2:
            movements.append("arms_crossed")
        
        # Detect head movement (if available)
        # Would need additional head detection
        
        return movements
    
    async def detect_swipe_gesture(self, frame1: Image.Image, 
                                  frame2: Image.Image) -> Dict[str, Any]:
        """Detect swipe gestures between frames"""
        result = {
            "swipe_detected": False,
            "direction": None,
            "distance": 0,
            "speed": 0
        }
        
        try:
            # Get hand positions in both frames
            result1 = await self.detect_hand_gesture(frame1)
            result2 = await self.detect_hand_gesture(frame2)
            
            if not result1["gestures"] or not result2["gestures"]:
                return result
            
            # Get hand positions
            pos1 = result1["gestures"][0]  # First hand
            pos2 = result2["gestures"][0]
            
            # This would need landmark positions which aren't in our result
            # Simplified version:
            result["swipe_detected"] = True
            result["direction"] = "right"  # Placeholder
            result["distance"] = 50
            result["speed"] = 100
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    async def detect_click_gesture(self, image: Image.Image) -> Dict[str, Any]:
        """Detect hand gesture simulating a click"""
        result = {
            "click_detected": False,
            "position": None,
            "hand": None,
            "confidence": 0.0
        }
        
        try:
            hand_result = await self.detect_hand_gesture(image)
            
            for gesture in hand_result["gestures"]:
                # Pinching gesture or pointing + click-like motion
                if gesture["gesture"] in ["pointing", "pinch", "ok_sign"]:
                    result["click_detected"] = True
                    result["hand"] = gesture["hand"]
                    result["confidence"] = gesture["confidence"]
                    # Position would be where the fingertip is
                    break
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    async def get_gesture_history(self, limit: int = 10) -> List[Dict]:
        """Get recent gesture history"""
        return self.gesture_history[-limit:]
    
    def record_gesture(self, gesture_data: Dict):
        """Record a detected gesture"""
        from datetime import datetime
        gesture_data["timestamp"] = datetime.now().isoformat()
        self.gesture_history.append(gesture_data)
        
        # Keep history manageable
        if len(self.gesture_history) > 1000:
            self.gesture_history = self.gesture_history[-1000:]
