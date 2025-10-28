"""
Intelligent Crop System

Provides intelligent video cropping with:
- Face detection and tracking
- Motion-aware framing
- Dynamic crop adjustment with smooth transitions

Follows clean architecture separation - this module handles analysis only,
actual FFmpeg integration happens in clip_export.py
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, NamedTuple
from dataclasses import dataclass, field
from enum import Enum

from .logging import get_logger
from .exceptions import ProcessingError

logger = get_logger('clip_generation.intelligent_crop')


class CropStrategy(Enum):
    """Crop strategy types"""
    CENTER = "center"  # Simple center crop
    FACE_TRACKING = "face_tracking"  # Follow detected faces
    MOTION_AWARE = "motion_aware"  # Follow motion/activity
    SPEAKER_TRACKING = "speaker_tracking"  # Track active speaker
    HYBRID = "hybrid"  # Combine multiple strategies


@dataclass
class CropRegion:
    """Represents a crop region at a specific time"""
    timestamp_ms: int
    x: int
    y: int
    width: int
    height: int
    confidence: float = 1.0
    strategy_used: str = "center"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'timestamp_ms': self.timestamp_ms,
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height,
            'confidence': self.confidence,
            'strategy_used': self.strategy_used
        }


@dataclass
class FaceDetection:
    """Face detection result"""
    x: int
    y: int
    width: int
    height: int
    confidence: float
    frame_index: int
    timestamp_ms: int


@dataclass
class MotionRegion:
    """Motion detection result"""
    x: int
    y: int
    width: int
    height: int
    intensity: float
    frame_index: int
    timestamp_ms: int


@dataclass
class IntelligentCropConfig:
    """Configuration for intelligent crop analysis"""
    # Strategy
    strategy: CropStrategy = CropStrategy.HYBRID
    
    # Face detection
    enable_face_detection: bool = True
    face_detection_interval: int = 5  # Analyze every N frames
    face_min_confidence: float = 0.5
    face_cascade_path: Optional[str] = None  # Use default if None
    
    # Motion detection
    enable_motion_detection: bool = True
    motion_detection_interval: int = 3
    motion_threshold: float = 25.0
    motion_min_area: int = 500
    
    # Crop parameters
    target_aspect_ratio: Tuple[int, int] = (9, 16)  # width:height
    smooth_transitions: bool = True
    transition_smoothness: float = 0.3  # 0=instant, 1=very smooth
    padding_percent: float = 0.15  # Extra space around detected region
    
    # Performance
    max_analysis_fps: int = 10  # Downsample for analysis
    use_gpu: bool = True  # Use GPU acceleration if available
    
    def __post_init__(self):
        """Validate configuration"""
        if self.transition_smoothness < 0 or self.transition_smoothness > 1:
            raise ValueError("transition_smoothness must be between 0 and 1")
        if self.padding_percent < 0 or self.padding_percent > 0.5:
            raise ValueError("padding_percent must be between 0 and 0.5")


class FaceDetector:
    """Face detection using OpenCV Haar Cascades or DNN"""
    
    def __init__(self, config: IntelligentCropConfig):
        self.config = config
        self.cascade = None
        self._initialize_detector()
    
    def _initialize_detector(self):
        """Initialize face detection model"""
        try:
            # Try to load Haar Cascade
            if self.config.face_cascade_path:
                cascade_path = self.config.face_cascade_path
            else:
                # Use OpenCV's built-in cascade
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            
            self.cascade = cv2.CascadeClassifier(cascade_path)
            
            if self.cascade.empty():
                logger.warning("Failed to load face cascade, face detection disabled")
                self.cascade = None
            else:
                logger.info(f"Face detector initialized with cascade: {cascade_path}")
                
        except Exception as e:
            logger.warning(f"Failed to initialize face detector: {e}")
            self.cascade = None
    
    def detect_faces(self, frame: np.ndarray, frame_index: int, timestamp_ms: int) -> List[FaceDetection]:
        """Detect faces in a frame"""
        if self.cascade is None:
            return []
        
        try:
            # Convert to grayscale for detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect faces
            faces = self.cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )
            
            results = []
            for (x, y, w, h) in faces:
                # Calculate confidence (Haar cascades don't provide this, use size as proxy)
                confidence = min(1.0, (w * h) / (frame.shape[0] * frame.shape[1]) * 10)
                
                if confidence >= self.config.face_min_confidence:
                    results.append(FaceDetection(
                        x=int(x),
                        y=int(y),
                        width=int(w),
                        height=int(h),
                        confidence=confidence,
                        frame_index=frame_index,
                        timestamp_ms=timestamp_ms
                    ))
            
            return results
            
        except Exception as e:
            logger.warning(f"Face detection failed for frame {frame_index}: {e}")
            return []


class MotionDetector:
    """Motion detection using optical flow or frame differencing"""
    
    def __init__(self, config: IntelligentCropConfig):
        self.config = config
        self.prev_frame = None
    
    def detect_motion(self, frame: np.ndarray, frame_index: int, timestamp_ms: int) -> List[MotionRegion]:
        """Detect motion regions in a frame"""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            
            # Need previous frame for comparison
            if self.prev_frame is None:
                self.prev_frame = gray
                return []
            
            # Compute frame difference
            frame_delta = cv2.absdiff(self.prev_frame, gray)
            thresh = cv2.threshold(frame_delta, self.config.motion_threshold, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            
            # Find contours
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            results = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < self.config.motion_min_area:
                    continue
                
                (x, y, w, h) = cv2.boundingRect(contour)
                intensity = area / (frame.shape[0] * frame.shape[1])
                
                results.append(MotionRegion(
                    x=int(x),
                    y=int(y),
                    width=int(w),
                    height=int(h),
                    intensity=float(intensity),
                    frame_index=frame_index,
                    timestamp_ms=timestamp_ms
                ))
            
            # Update previous frame
            self.prev_frame = gray
            
            return results
            
        except Exception as e:
            logger.warning(f"Motion detection failed for frame {frame_index}: {e}")
            return []


class IntelligentCropAnalyzer:
    """
    Main intelligent crop analyzer
    
    Analyzes video to determine optimal crop regions over time
    """
    
    def __init__(self, config: IntelligentCropConfig):
        self.config = config
        self.face_detector = FaceDetector(config) if config.enable_face_detection else None
        self.motion_detector = MotionDetector(config) if config.enable_motion_detection else None
    
    def analyze_video(
        self,
        video_path: Path,
        start_ms: int,
        end_ms: int,
        target_width: int,
        target_height: int
    ) -> List[CropRegion]:
        """
        Analyze video segment and generate crop regions
        
        Args:
            video_path: Path to source video
            start_ms: Start time in milliseconds
            end_ms: End time in milliseconds
            target_width: Target crop width
            target_height: Target crop height
        
        Returns:
            List of crop regions with timestamps
        """
        logger.info(f"Analyzing video for intelligent crop: {video_path}")
        logger.info(f"Segment: {start_ms}ms - {end_ms}ms, target: {target_width}x{target_height}")
        
        try:
            # Open video
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise ProcessingError(f"Failed to open video: {video_path}")
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            logger.info(f"Video properties: {video_width}x{video_height} @ {fps}fps, {total_frames} frames")
            
            # Calculate frame range
            start_frame = int((start_ms / 1000.0) * fps)
            end_frame = int((end_ms / 1000.0) * fps)
            
            # Set to start frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            
            # Collect detections
            face_detections = []
            motion_regions = []
            
            frame_index = start_frame
            analysis_frame_interval = max(1, int(fps / self.config.max_analysis_fps))
            
            logger.info(f"Analyzing frames {start_frame} to {end_frame} (interval: {analysis_frame_interval})")
            
            while frame_index <= end_frame:
                ret, frame = cap.read()
                if not ret:
                    break
                
                timestamp_ms = int((frame_index / fps) * 1000)
                
                # Analyze frame at intervals
                if (frame_index - start_frame) % analysis_frame_interval == 0:
                    # Face detection
                    if self.face_detector and frame_index % self.config.face_detection_interval == 0:
                        faces = self.face_detector.detect_faces(frame, frame_index, timestamp_ms)
                        face_detections.extend(faces)
                    
                    # Motion detection
                    if self.motion_detector and frame_index % self.config.motion_detection_interval == 0:
                        motion = self.motion_detector.detect_motion(frame, frame_index, timestamp_ms)
                        motion_regions.extend(motion)
                
                frame_index += 1
            
            cap.release()
            
            logger.info(f"Analysis complete: {len(face_detections)} faces, {len(motion_regions)} motion regions")
            
            # Generate crop regions based on detections
            crop_regions = self._generate_crop_regions(
                face_detections,
                motion_regions,
                video_width,
                video_height,
                target_width,
                target_height,
                start_ms,
                end_ms,
                fps
            )
            
            # Smooth transitions if enabled
            if self.config.smooth_transitions:
                crop_regions = self._smooth_transitions(crop_regions)
            
            logger.info(f"Generated {len(crop_regions)} crop regions")
            return crop_regions
            
        except Exception as e:
            logger.error(f"Failed to analyze video: {e}", exc_info=True)
            # Return fallback center crop
            return self._generate_fallback_crop(
                video_width, video_height, target_width, target_height, start_ms, end_ms
            )
    
    def _generate_crop_regions(
        self,
        face_detections: List[FaceDetection],
        motion_regions: List[MotionRegion],
        video_width: int,
        video_height: int,
        target_width: int,
        target_height: int,
        start_ms: int,
        end_ms: int,
        fps: float
    ) -> List[CropRegion]:
        """Generate crop regions from detections"""
        
        if not face_detections and not motion_regions:
            # No detections, use center crop
            return self._generate_fallback_crop(
                video_width, video_height, target_width, target_height, start_ms, end_ms
            )
        
        crop_regions = []
        
        # Strategy: Prioritize faces, fall back to motion, then center
        if face_detections:
            crop_regions = self._crop_from_faces(
                face_detections, video_width, video_height, target_width, target_height, start_ms, end_ms, fps
            )
        elif motion_regions:
            crop_regions = self._crop_from_motion(
                motion_regions, video_width, video_height, target_width, target_height, start_ms, end_ms, fps
            )
        
        return crop_regions
    
    def _crop_from_faces(
        self,
        faces: List[FaceDetection],
        video_width: int,
        video_height: int,
        target_width: int,
        target_height: int,
        start_ms: int,
        end_ms: int,
        fps: float
    ) -> List[CropRegion]:
        """Generate crop regions based on face detections"""
        
        crop_regions = []
        
        # Group faces by time windows
        time_window_ms = 1000  # 1 second windows
        current_time = start_ms
        
        while current_time <= end_ms:
            window_end = current_time + time_window_ms
            
            # Find faces in this window
            window_faces = [f for f in faces if current_time <= f.timestamp_ms < window_end]
            
            if window_faces:
                # Calculate average face position (weighted by confidence)
                total_weight = sum(f.confidence for f in window_faces)
                avg_x = sum(f.x * f.confidence for f in window_faces) / total_weight
                avg_y = sum(f.y * f.confidence for f in window_faces) / total_weight
                avg_w = sum(f.width * f.confidence for f in window_faces) / total_weight
                avg_h = sum(f.height * f.confidence for f in window_faces) / total_weight
                
                # Calculate crop region centered on face with padding
                center_x = avg_x + avg_w / 2
                center_y = avg_y + avg_h / 2
                
                # Add padding
                padding = self.config.padding_percent
                crop_w = target_width
                crop_h = target_height
                
                crop_x = int(center_x - crop_w / 2)
                crop_y = int(center_y - crop_h / 2)
                
                # Constrain to video bounds
                crop_x = max(0, min(crop_x, video_width - crop_w))
                crop_y = max(0, min(crop_y, video_height - crop_h))
                
                crop_regions.append(CropRegion(
                    timestamp_ms=current_time,
                    x=crop_x,
                    y=crop_y,
                    width=crop_w,
                    height=crop_h,
                    confidence=total_weight / len(window_faces),
                    strategy_used="face_tracking"
                ))
            else:
                # No faces in window, use previous crop or center
                if crop_regions:
                    last_crop = crop_regions[-1]
                    crop_regions.append(CropRegion(
                        timestamp_ms=current_time,
                        x=last_crop.x,
                        y=last_crop.y,
                        width=last_crop.width,
                        height=last_crop.height,
                        confidence=0.5,
                        strategy_used="interpolated"
                    ))
                else:
                    # Center crop
                    crop_x = (video_width - target_width) // 2
                    crop_y = (video_height - target_height) // 2
                    crop_regions.append(CropRegion(
                        timestamp_ms=current_time,
                        x=crop_x,
                        y=crop_y,
                        width=target_width,
                        height=target_height,
                        confidence=0.3,
                        strategy_used="center"
                    ))
            
            current_time += time_window_ms
        
        return crop_regions
    
    def _crop_from_motion(
        self,
        motion_regions: List[MotionRegion],
        video_width: int,
        video_height: int,
        target_width: int,
        target_height: int,
        start_ms: int,
        end_ms: int,
        fps: float
    ) -> List[CropRegion]:
        """Generate crop regions based on motion detection"""
        
        # Similar to face tracking but using motion intensity
        crop_regions = []
        
        time_window_ms = 500  # Shorter windows for motion
        current_time = start_ms
        
        while current_time <= end_ms:
            window_end = current_time + time_window_ms
            
            window_motion = [m for m in motion_regions if current_time <= m.timestamp_ms < window_end]
            
            if window_motion:
                # Weight by intensity
                total_intensity = sum(m.intensity for m in window_motion)
                avg_x = sum(m.x * m.intensity for m in window_motion) / total_intensity
                avg_y = sum(m.y * m.intensity for m in window_motion) / total_intensity
                
                center_x = avg_x + target_width / 2
                center_y = avg_y + target_height / 2
                
                crop_x = int(center_x - target_width / 2)
                crop_y = int(center_y - target_height / 2)
                
                crop_x = max(0, min(crop_x, video_width - target_width))
                crop_y = max(0, min(crop_y, video_height - target_height))
                
                crop_regions.append(CropRegion(
                    timestamp_ms=current_time,
                    x=crop_x,
                    y=crop_y,
                    width=target_width,
                    height=target_height,
                    confidence=min(1.0, total_intensity * 10),
                    strategy_used="motion_aware"
                ))
            else:
                if crop_regions:
                    last_crop = crop_regions[-1]
                    crop_regions.append(CropRegion(
                        timestamp_ms=current_time,
                        x=last_crop.x,
                        y=last_crop.y,
                        width=last_crop.width,
                        height=last_crop.height,
                        confidence=0.5,
                        strategy_used="interpolated"
                    ))
            
            current_time += time_window_ms
        
        return crop_regions if crop_regions else self._generate_fallback_crop(
            video_width, video_height, target_width, target_height, start_ms, end_ms
        )
    
    def _generate_fallback_crop(
        self,
        video_width: int,
        video_height: int,
        target_width: int,
        target_height: int,
        start_ms: int,
        end_ms: int
    ) -> List[CropRegion]:
        """Generate simple center crop as fallback"""
        
        crop_x = (video_width - target_width) // 2
        crop_y = (video_height - target_height) // 2
        
        # Single crop region for entire duration
        return [CropRegion(
            timestamp_ms=start_ms,
            x=max(0, crop_x),
            y=max(0, crop_y),
            width=target_width,
            height=target_height,
            confidence=1.0,
            strategy_used="center"
        )]
    
    def _smooth_transitions(self, crop_regions: List[CropRegion]) -> List[CropRegion]:
        """Apply smoothing to crop transitions"""
        
        if len(crop_regions) <= 1:
            return crop_regions
        
        smoothed = [crop_regions[0]]
        alpha = 1.0 - self.config.transition_smoothness  # Smoothness factor
        
        for i in range(1, len(crop_regions)):
            prev = smoothed[-1]
            curr = crop_regions[i]
            
            # Exponential moving average for smooth transitions
            smooth_x = int(alpha * curr.x + (1 - alpha) * prev.x)
            smooth_y = int(alpha * curr.y + (1 - alpha) * prev.y)
            
            smoothed.append(CropRegion(
                timestamp_ms=curr.timestamp_ms,
                x=smooth_x,
                y=smooth_y,
                width=curr.width,
                height=curr.height,
                confidence=curr.confidence,
                strategy_used=curr.strategy_used
            ))
        
        return smoothed


def create_crop_filter_string(crop_regions: List[CropRegion], fps: float) -> str:
    """
    Create FFmpeg crop filter string from crop regions
    
    Args:
        crop_regions: List of crop regions with timestamps
        fps: Video frame rate
    
    Returns:
        FFmpeg filter string for dynamic cropping
    """
    
    if not crop_regions:
        raise ValueError("No crop regions provided")
    
    if len(crop_regions) == 1:
        # Static crop
        region = crop_regions[0]
        return f"crop={region.width}:{region.height}:{region.x}:{region.y}"
    
    # Dynamic crop with timeline
    # Use crop filter with enable expressions for time-based switching
    filters = []
    
    for i, region in enumerate(crop_regions):
        start_time = region.timestamp_ms / 1000.0
        
        if i < len(crop_regions) - 1:
            end_time = crop_regions[i + 1].timestamp_ms / 1000.0
            enable_expr = f"between(t,{start_time},{end_time})"
        else:
            enable_expr = f"gte(t,{start_time})"
        
        crop_filter = f"crop={region.width}:{region.height}:{region.x}:{region.y}:enable='{enable_expr}'"
        filters.append(crop_filter)
    
    # Combine with overlay approach (complex but smooth)
    # For simplicity, return first region's crop with note
    # Full implementation would use zoompan or custom filter
    logger.info(f"Generated {len(filters)} crop keyframes")
    
    # Return simple crop for now - full dynamic cropping requires more complex FFmpeg filter
    # This is a placeholder for the integration point
    return f"crop={crop_regions[0].width}:{crop_regions[0].height}:{crop_regions[0].x}:{crop_regions[0].y}"
