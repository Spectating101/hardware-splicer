import asyncio
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger
import numpy as np
from PIL import Image
import hashlib
import time

from src.vision.enhanced_detector import EnhancedComponentDetector, ComponentDetection, DetectionMethod
from src.llm.enhanced_mapper import EnhancedFunctionalMapper, EducationalContent, RepairRecommendation, ProjectRecommendation
from src.services.websocket_service import AnalysisProgressTracker, websocket_manager
from src.services.cache_service import analysis_cache
from src.services.queue_service import queue_service, JobPriority
from src.intelligence.circuit_analyzer import circuit_intelligence
from src.intelligence.repair_guidance import repair_guidance
from src.intelligence.modification_planner import modification_planner
from src.intelligence.trace_analyzer import trace_analyzer
from src.intelligence.value_extractor import value_extractor
from src.intelligence.safety_validator import safety_validator

class EnhancedCircuitAnalyzer:
    """Enhanced circuit analyzer with real-time progress, caching, and advanced features."""
    
    def __init__(self):
        """Initialize the enhanced circuit analyzer."""
        self.detector = EnhancedComponentDetector()
        self.mapper = EnhancedFunctionalMapper()
        
        # Analysis statistics
        self.stats = {
            "total_analyses": 0,
            "successful_analyses": 0,
            "failed_analyses": 0,
            "average_processing_time": 0.0,
            "total_processing_time": 0.0
        }
        
        logger.info("Enhanced CircuitAnalyzer initialized")
    
    async def analyze_pcb(self, image: np.ndarray, 
                         backend: str = "ensemble",
                         enable_ocr: bool = True,
                         enable_quality_assessment: bool = True,
                         enable_caching: bool = True,
                         analysis_id: Optional[str] = None) -> Dict[str, Any]:
        """Complete enhanced PCB analysis pipeline with real-time progress."""
        
        if analysis_id is None:
            analysis_id = str(uuid.uuid4())
        
        progress_tracker = AnalysisProgressTracker(analysis_id)
        start_time = time.time()
        
        try:
            # Check cache first
            if enable_caching:
                image_hash = self._generate_image_hash(image)
                cached_result = analysis_cache.get_analysis_result(image_hash, backend, enable_ocr)
                if cached_result:
                    logger.info(f"Using cached result for analysis {analysis_id}")
                    await progress_tracker.complete_analysis(cached_result)
                    return cached_result
            
            # Step 1: Upload and preprocessing
            await progress_tracker.update_progress(
                "uploading", "Processing uploaded image...", 0.1
            )
            
            # Step 2: Component detection
            await progress_tracker.update_progress(
                "detecting", "Detecting components using enhanced algorithms...", 0.3
            )
            
            detection_methods = self._get_detection_methods(backend)
            detections = self.detector.detect_components(
                image, 
                methods=detection_methods,
                enable_ocr=enable_ocr,
                enable_quality_assessment=enable_quality_assessment
            )
            
            # Step 3: Circuit intelligence analysis
            await progress_tracker.update_progress(
                "intelligence", "Understanding circuit topology and relationships...", 0.45
            )

            image_dims = (image.shape[1], image.shape[0])  # width, height
            circuit_topology = circuit_intelligence.analyze_circuit(detections, image_dims)

            # Step 4: Functionality mapping
            await progress_tracker.update_progress(
                "analyzing", "Analyzing component capabilities and functionality...", 0.55
            )

            functionality_data = self.mapper.map_detections_to_functionality(detections)

            # Step 5: Project recommendations
            await progress_tracker.update_progress(
                "recommending", "Generating personalized project recommendations...", 0.7
            )
            
            project_recommendations = self.mapper.generate_project_recommendations(functionality_data)

            # Step 6: Educational content
            await progress_tracker.update_progress(
                "educating", "Creating educational content and learning materials...", 0.85
            )

            educational_content = self.mapper.generate_educational_content(functionality_data["components"])

            # Step 7: Repair recommendations
            repair_recommendations = self.mapper.generate_repair_recommendations(functionality_data["components"])

            # NEW STEPS: Advanced analysis
            # Step 8: Trace analysis (if image available)
            await progress_tracker.update_progress(
                "trace_analysis", "Analyzing PCB traces and connections...", 0.72
            )
            trace_analysis = trace_analyzer.analyze_traces(
                image, detections, calibration_mm=None
            )

            # Step 9: Component value extraction
            await progress_tracker.update_progress(
                "value_extraction", "Extracting component values...", 0.78
            )
            component_values = value_extractor.extract_values(image, detections)

            # Step 10: Generate diagnostic procedures
            await progress_tracker.update_progress(
                "diagnostics", "Generating diagnostic procedures...", 0.83
            )
            diagnostic_procedure = repair_guidance.generate_diagnostic_procedure(
                circuit_topology.device_type,
                symptoms=[],  # Could be provided by user
                components=[d.class_name for d in detections]
            )

            # Step 11: Generate modification plans (common ones)
            await progress_tracker.update_progress(
                "modifications", "Planning possible modifications...", 0.88
            )
            modification_plans = self._generate_modification_plans(
                circuit_topology, detections
            )

            # Step 12: Safety validation
            await progress_tracker.update_progress(
                "safety", "Performing safety validation...", 0.92
            )
            safety_info = self._generate_safety_info(circuit_topology, detections)

            # Step 13: Compile results
            await progress_tracker.update_progress(
                "finalizing", "Finalizing analysis results...", 0.95
            )

            results = self._compile_enhanced_results(
                detections, functionality_data, project_recommendations,
                educational_content, repair_recommendations, circuit_topology, analysis_id,
                trace_analysis, component_values, diagnostic_procedure,
                modification_plans, safety_info
            )
            
            # Cache results
            if enable_caching:
                image_hash = self._generate_image_hash(image)
                analysis_cache.set_analysis_result(image_hash, backend, enable_ocr, results)
            
            # Update statistics
            processing_time = time.time() - start_time
            self._update_statistics(True, processing_time)
            
            # Complete analysis
            await progress_tracker.complete_analysis(results)
            
            logger.info(f"Enhanced analysis {analysis_id} completed in {processing_time:.2f}s")
            return results
            
        except Exception as e:
            logger.error(f"Error in enhanced PCB analysis {analysis_id}: {e}")
            
            # Update statistics
            processing_time = time.time() - start_time
            self._update_statistics(False, processing_time)
            
            # Report error
            error_result = self._create_error_result(str(e), analysis_id)
            await progress_tracker.complete_analysis(error_result, success=False)
            
            return error_result
    
    def analyze_from_file(self, image_path: str, **kwargs) -> Dict[str, Any]:
        """Analyze PCB from image file."""
        try:
            # Load image
            image = Image.open(image_path)
            image_np = np.array(image)
            
            # Run analysis
            return asyncio.run(self.analyze_pcb(image_np, **kwargs))
            
        except Exception as e:
            logger.error(f"Error loading image from {image_path}: {e}")
            return self._create_error_result(f"Could not load image: {str(e)}")
    
    async def batch_analyze(self, image_paths: List[str], **kwargs) -> List[Dict[str, Any]]:
        """Analyze multiple PCB images in batch."""
        results = []
        
        for i, image_path in enumerate(image_paths):
            try:
                result = self.analyze_from_file(image_path, **kwargs)
                result["batch_index"] = i
                result["batch_total"] = len(image_paths)
                results.append(result)
                
                # Add delay between analyses to prevent overwhelming the system
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in batch analysis for {image_path}: {e}")
                error_result = self._create_error_result(str(e))
                error_result["batch_index"] = i
                error_result["batch_total"] = len(image_paths)
                results.append(error_result)
        
        return results
    
    def submit_batch_analysis_job(self, image_paths: List[str], **kwargs) -> str:
        """Submit batch analysis as a background job."""
        job_payload = {
            "image_paths": image_paths,
            "analysis_options": kwargs,
            "submitted_at": datetime.now().isoformat()
        }
        
        job_id = queue_service.submit_job(
            "batch_analysis",
            job_payload,
            priority=JobPriority.NORMAL
        )
        
        logger.info(f"Submitted batch analysis job {job_id} with {len(image_paths)} images")
        return job_id
    
    def get_batch_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a batch analysis job."""
        job = queue_service.get_job(job_id)
        if job:
            return {
                "job_id": job.id,
                "status": job.status.value,
                "task_type": job.task_type,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "result": job.result,
                "error": job.error,
                "progress": job.progress,
                "retries": job.retries
            }
        return {"error": "Job not found"}
    
    def _get_detection_methods(self, backend: str) -> List[DetectionMethod]:
        """Get detection methods based on backend preference."""
        if backend == "ensemble":
            return [DetectionMethod.ENSEMBLE]
        elif backend == "yolo":
            return [DetectionMethod.YOLO]
        elif backend == "classical":
            return [DetectionMethod.CLASSICAL]
        elif backend == "custom":
            return [DetectionMethod.CUSTOM]
        else:
            return [DetectionMethod.ENSEMBLE]
    
    def _compile_enhanced_results(self, detections: List[ComponentDetection],
                                functionality_data: Dict[str, Any],
                                project_recommendations: List[ProjectRecommendation],
                                educational_content: List[EducationalContent],
                                repair_recommendations: List[RepairRecommendation],
                                circuit_topology: Any,
                                analysis_id: str,
                                trace_analysis: Dict[str, Any] = None,
                                component_values: List[Any] = None,
                                diagnostic_procedure: Dict[str, Any] = None,
                                modification_plans: List[Dict[str, Any]] = None,
                                safety_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """Compile comprehensive analysis results."""
        
        # Convert dataclasses to dictionaries for JSON serialization
        projects = []
        for project in project_recommendations:
            project_dict = {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "difficulty": project.difficulty,
                "components_needed": project.components_needed,
                "estimated_cost": project.estimated_cost,
                "time_required": project.time_required,
                "skills_developed": project.skills_developed,
                "tutorial_url": project.tutorial_url,
                "score": project.score,
                "category": project.category,
                "popularity": project.popularity,
                "rating": project.rating,
                "tags": project.tags or []
            }
            projects.append(project_dict)
        
        education = []
        for content in educational_content:
            content_dict = {
                "title": content.title,
                "content": content.content,
                "difficulty": content.difficulty,
                "component_type": content.component_type,
                "video_url": content.video_url,
                "interactive_demo": content.interactive_demo,
                "quiz_questions": content.quiz_questions or [],
                "learning_objectives": content.learning_objectives or [],
                "prerequisites": content.prerequisites or [],
                "estimated_time": content.estimated_time
            }
            education.append(content_dict)
        
        repairs = []
        for repair in repair_recommendations:
            repair_dict = {
                "component_type": repair.component_type,
                "issue": repair.issue,
                "symptoms": repair.symptoms,
                "solutions": repair.solutions,
                "difficulty": repair.difficulty,
                "tools_needed": repair.tools_needed,
                "safety_notes": repair.safety_notes,
                "estimated_time": repair.estimated_time,
                "success_rate": repair.success_rate
            }
            repairs.append(repair_dict)
        
        # Convert detections to serializable format
        detection_list = []
        for detection in detections:
            detection_dict = {
                "bbox": detection.bbox,
                "class_name": detection.class_name,
                "confidence": detection.confidence,
                "method": detection.method.value,
                "metadata": detection.metadata,
                "center": detection.center,
                "area": detection.area,
                "aspect_ratio": detection.aspect_ratio,
                "text_content": detection.text_content,
                "quality_score": detection.quality_score
            }
            detection_list.append(detection_dict)
        
        # Generate detection summary
        detection_summary = self.detector.get_detection_summary(detections)
        
        # Calculate analysis metrics
        analysis_metrics = self._calculate_analysis_metrics(
            detections, functionality_data, projects, education, repairs
        )

        # Convert circuit topology to dictionary
        circuit_topology_dict = self._topology_to_dict(circuit_topology)

        # NEW: Add advanced analysis results
        advanced_analysis = {}
        if trace_analysis:
            advanced_analysis["trace_analysis"] = trace_analysis
        if component_values:
            advanced_analysis["component_values"] = [
                {
                    "component_id": v.component_id,
                    "component_type": v.component_type,
                    "value": v.value,
                    "unit": v.unit,
                    "tolerance": v.tolerance,
                    "part_number": v.part_number,
                    "confidence": v.confidence,
                    "extraction_method": v.extraction_method
                } for v in component_values
            ]
        if diagnostic_procedure:
            advanced_analysis["diagnostic_procedure"] = diagnostic_procedure
        if modification_plans:
            advanced_analysis["modification_plans"] = modification_plans
        if safety_info:
            advanced_analysis["safety_validation"] = safety_info

        results = {
            "success": True,
            "analysis_id": analysis_id,
            "timestamp": datetime.now().isoformat(),
            "processing_time": time.time(),
            "results": {
                "detections": detection_list,
                "detection_summary": detection_summary,
                "functionality_data": functionality_data,
                "circuit_topology": circuit_topology_dict,
                "project_recommendations": projects,
                "educational_content": education,
                "repair_recommendations": repairs,
                "advanced_analysis": advanced_analysis  # NEW!
            },
            "analysis_metadata": {
                "backend": "enhanced",
                "ocr_enabled": True,
                "quality_assessment_enabled": True,
                "caching_enabled": True,
                "detection_quality": detection_summary.get("detection_quality", "unknown"),
                "project_potential": functionality_data.get("project_potential", "unknown"),
                "analysis_version": "3.0.0",  # Bumped version for new capabilities
                "capabilities": [
                    "component_detection",
                    "circuit_topology",
                    "trace_analysis",
                    "value_extraction",
                    "repair_guidance",
                    "modification_planning",
                    "safety_validation"
                ]
            },
            "analysis_metrics": analysis_metrics,
            "recommendations": {
                "next_steps": self._generate_next_steps(functionality_data, projects),
                "learning_path": self._generate_learning_path(education),
                "maintenance_tips": self._generate_maintenance_tips(repairs)
            }
        }
        
        return results
    
    def _calculate_analysis_metrics(self, detections: List[ComponentDetection],
                                  functionality_data: Dict[str, Any],
                                  projects: List[Dict[str, Any]],
                                  education: List[Dict[str, Any]],
                                  repairs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate comprehensive analysis metrics."""
        
        # Component metrics
        total_components = len(detections)
        high_confidence_components = len([d for d in detections if d.confidence > 0.8])
        average_confidence = sum(d.confidence for d in detections) / total_components if total_components > 0 else 0
        
        # Value metrics
        total_market_value = functionality_data.get("total_market_value", 0.0)
        components_by_type = functionality_data.get("components", [])
        unique_component_types = len(set(comp["type"] for comp in components_by_type))
        
        # Project metrics
        project_count = len(projects)
        beginner_projects = len([p for p in projects if p["difficulty"] == "beginner"])
        intermediate_projects = len([p for p in projects if p["difficulty"] == "intermediate"])
        advanced_projects = len([p for p in projects if p["difficulty"] == "advanced"])
        
        # Educational metrics
        educational_content_count = len(education)
        beginner_content = len([e for e in education if e["difficulty"] == "beginner"])
        intermediate_content = len([e for e in education if e["difficulty"] == "intermediate"])
        advanced_content = len([e for e in education if e["difficulty"] == "advanced"])
        
        # Repair metrics
        repair_count = len(repairs)
        high_success_repairs = len([r for r in repairs if r["success_rate"] > 0.8])
        
        return {
            "component_metrics": {
                "total_components": total_components,
                "high_confidence_components": high_confidence_components,
                "average_confidence": round(average_confidence, 3),
                "unique_component_types": unique_component_types,
                "total_market_value": round(total_market_value, 2)
            },
            "project_metrics": {
                "total_projects": project_count,
                "beginner_projects": beginner_projects,
                "intermediate_projects": intermediate_projects,
                "advanced_projects": advanced_projects,
                "average_project_score": round(sum(p["score"] for p in projects) / project_count, 3) if project_count > 0 else 0
            },
            "educational_metrics": {
                "total_content": educational_content_count,
                "beginner_content": beginner_content,
                "intermediate_content": intermediate_content,
                "advanced_content": advanced_content
            },
            "repair_metrics": {
                "total_repairs": repair_count,
                "high_success_repairs": high_success_repairs,
                "average_success_rate": round(sum(r["success_rate"] for r in repairs) / repair_count, 3) if repair_count > 0 else 0
            },
            "overall_score": self._calculate_overall_score(
                total_components, average_confidence, project_count, educational_content_count
            )
        }
    
    def _calculate_overall_score(self, components: int, confidence: float, 
                               projects: int, education: int) -> float:
        """Calculate overall analysis quality score."""
        # Component score (40% weight)
        component_score = min(components / 10.0, 1.0) * confidence
        
        # Project score (30% weight)
        project_score = min(projects / 5.0, 1.0)
        
        # Educational score (20% weight)
        educational_score = min(education / 3.0, 1.0)
        
        # Confidence bonus (10% weight)
        confidence_bonus = confidence * 0.1
        
        total_score = (component_score * 0.4 + project_score * 0.3 + 
                      educational_score * 0.2 + confidence_bonus)
        
        return round(min(total_score, 1.0), 3)
    
    def _generate_next_steps(self, functionality_data: Dict[str, Any], 
                           projects: List[Dict[str, Any]]) -> List[str]:
        """Generate next steps recommendations."""
        next_steps = []
        
        if projects:
            best_project = max(projects, key=lambda x: x["score"])
            next_steps.append(f"Start with '{best_project['name']}' project (Score: {best_project['score']:.2f})")
        
        components = functionality_data.get("components", [])
        if components:
            high_value_components = [c for c in components if c.get("market_value", 0) > 0.5]
            if high_value_components:
                next_steps.append(f"Focus on {len(high_value_components)} high-value components for maximum reuse")
        
        if functionality_data.get("educational_score", 0) > 0.7:
            next_steps.append("Excellent learning opportunity - explore educational content")
        
        if functionality_data.get("reusability_score", 0) > 0.8:
            next_steps.append("High reusability potential - consider salvaging components")
        
        return next_steps
    
    def _generate_learning_path(self, education: List[Dict[str, Any]]) -> List[str]:
        """Generate learning path recommendations."""
        learning_path = []
        
        # Sort by difficulty
        beginner_content = [e for e in education if e["difficulty"] == "beginner"]
        intermediate_content = [e for e in education if e["difficulty"] == "intermediate"]
        advanced_content = [e for e in education if e["difficulty"] == "advanced"]
        
        if beginner_content:
            learning_path.append(f"Start with {len(beginner_content)} beginner topics")
        
        if intermediate_content:
            learning_path.append(f"Progress to {len(intermediate_content)} intermediate concepts")
        
        if advanced_content:
            learning_path.append(f"Advanced learners can explore {len(advanced_content)} advanced topics")
        
        return learning_path
    
    def _generate_maintenance_tips(self, repairs: List[Dict[str, Any]]) -> List[str]:
        """Generate maintenance tips from repair recommendations."""
        tips = []
        
        for repair in repairs:
            if repair["success_rate"] > 0.8:
                tips.append(f"High success rate ({repair['success_rate']:.1%}) for {repair['component_type']} repairs")
        
        if repairs:
            avg_time = sum(float(r["estimated_time"].split()[0]) for r in repairs if r["estimated_time"])
            tips.append(f"Average repair time: {avg_time/len(repairs):.1f} minutes")
        
        return tips
    
    def _topology_to_dict(self, topology: Any) -> Dict[str, Any]:
        """Convert CircuitTopology to dictionary for JSON serialization."""
        if not topology:
            return {}

        # Convert functional blocks
        blocks = []
        for block in topology.functional_blocks:
            blocks.append({
                "block_id": block.block_id,
                "block_type": block.block_type,
                "function": block.function,
                "capabilities": block.capabilities,
                "modification_potential": block.modification_potential,
                "critical_level": block.critical_level,
                "component_count": len(block.components),
                "center": block.center
            })

        return {
            "device_type": topology.device_type,
            "device_confidence": topology.device_confidence,
            "functional_blocks": blocks,
            "power_tree": topology.power_tree,
            "signal_paths": topology.signal_paths,
            "repair_complexity": topology.repair_complexity,
            "repurpose_potential": topology.repurpose_potential,
            "modification_suggestions": topology.modification_suggestions
        }

    def _generate_image_hash(self, image: np.ndarray) -> str:
        """Generate hash for image caching."""
        # Convert to bytes and hash
        image_bytes = image.tobytes()
        return hashlib.md5(image_bytes).hexdigest()
    
    def _create_error_result(self, error_message: str, analysis_id: Optional[str] = None) -> Dict[str, Any]:
        """Create error result structure."""
        if analysis_id is None:
            analysis_id = str(uuid.uuid4())
        
        return {
            "success": False,
            "analysis_id": analysis_id,
            "timestamp": datetime.now().isoformat(),
            "error": error_message,
            "results": {
                "detections": [],
                "detection_summary": {"total_components": 0},
                "functionality_data": {"components": [], "capabilities": []},
                "project_recommendations": [],
                "educational_content": [],
                "repair_recommendations": []
            },
            "analysis_metadata": {
                "backend": "enhanced",
                "error_occurred": True
            }
        }
    
    def _update_statistics(self, success: bool, processing_time: float):
        """Update analysis statistics."""
        self.stats["total_analyses"] += 1
        self.stats["total_processing_time"] += processing_time
        
        if success:
            self.stats["successful_analyses"] += 1
        else:
            self.stats["failed_analyses"] += 1
        
        # Update average processing time
        self.stats["average_processing_time"] = (
            self.stats["total_processing_time"] / self.stats["total_analyses"]
        )
    
    def get_analysis_statistics(self) -> Dict[str, Any]:
        """Get comprehensive analysis statistics."""
        return {
            **self.stats,
            "detector_stats": self.detector.get_detection_summary([]),
            "mapper_stats": self.mapper.get_analysis_statistics(),
            "cache_stats": analysis_cache.get_stats(),
            "queue_stats": queue_service.get_queue_stats(),
            "websocket_stats": websocket_manager.get_connection_stats()
        }
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get system health status."""
        return {
            "status": "healthy",
            "services": {
                "detector": "operational",
                "mapper": "operational",
                "cache": "operational",
                "queue": "operational",
                "websocket": "operational"
            },
            "performance": {
                "average_processing_time": self.stats["average_processing_time"],
                "success_rate": self.stats["successful_analyses"] / max(self.stats["total_analyses"], 1),
                "active_connections": len(websocket_manager.active_connections),
                "pending_jobs": queue_service.get_queue_stats().get("pending_jobs", 0)
            },
            "last_updated": datetime.now().isoformat()
        }

    def _generate_modification_plans(self, circuit_topology: Any,
                                     detections: List[ComponentDetection]) -> List[Dict[str, Any]]:
        """Generate common modification plans for the detected circuit."""
        plans = []

        device_type = circuit_topology.device_type if hasattr(circuit_topology, 'device_type') else 'unknown'
        components = [d.class_name for d in detections]

        # WiFi addition for Arduino
        if device_type == 'arduino' and not any('ESP' in c or 'WiFi' in c for c in components):
            plan = modification_planner.plan_circuit_enhancement(
                device_type, "WiFi connectivity", available_space=True
            )
            plans.append(self._plan_to_dict(plan))

        # Component extraction for routers
        if device_type == 'router':
            esp_components = [c for c in components if 'ESP' in c]
            if esp_components:
                plan = modification_planner.plan_component_extraction(
                    esp_components[0], device_type, "standalone IoT project"
                )
                plans.append(self._plan_to_dict(plan))

        # Firmware modification for programmable devices
        if device_type in ['arduino', 'router']:
            plan = modification_planner.plan_firmware_modification(
                device_type, "stock", "custom functionality"
            )
            plans.append(self._plan_to_dict(plan))

        return plans[:3]  # Limit to top 3 plans

    def _generate_safety_info(self, circuit_topology: Any,
                              detections: List[ComponentDetection]) -> Dict[str, Any]:
        """Generate safety information and validation."""
        components = [d.class_name for d in detections]

        # General safety info
        safety_info = {
            "high_voltage_present": any('transformer' in c.lower() or 'ac' in c.lower() for c in components),
            "esd_sensitive": any('ic' in c.lower() or 'chip' in c.lower() for c in components),
            "thermal_concerns": False,
            "general_warnings": []
        }

        # Check power budget for thermal concerns
        if hasattr(circuit_topology, 'power_budget') and circuit_topology.power_budget:
            if circuit_topology.power_budget.get('total_power_w', 0) > 5:
                safety_info["thermal_concerns"] = True
                safety_info["general_warnings"].append(
                    "High power consumption - monitor component temperatures"
                )

        # ESP8266/ESP32 voltage warnings
        if any('ESP' in c for c in components):
            safety_info["general_warnings"].append(
                "CRITICAL: ESP modules require 3.3V! DO NOT connect to 5V!"
            )

        # High voltage warning
        if safety_info["high_voltage_present"]:
            safety_info["general_warnings"].append(
                "HIGH VOLTAGE PRESENT - Disconnect from mains before working!"
            )

        # ESD warning
        if safety_info["esd_sensitive"]:
            safety_info["general_warnings"].append(
                "ESD-sensitive components present - use ESD protection"
            )

        # Generate safety checklist
        safety_info["safety_checklist"] = safety_validator.generate_safety_checklist(None)

        return safety_info

    def _plan_to_dict(self, plan: Any) -> Dict[str, Any]:
        """Convert modification plan to dictionary."""
        if not plan:
            return {}

        return {
            "modification_name": plan.modification_name,
            "modification_type": plan.modification_type.value if hasattr(plan.modification_type, 'value') else str(plan.modification_type),
            "goal": plan.goal,
            "difficulty": plan.difficulty,
            "estimated_time_minutes": plan.estimated_time_minutes,
            "cost_estimate_usd": plan.cost_estimate_usd,
            "required_skills": plan.required_skills,
            "tools_needed": plan.tools_needed,
            "parts_needed": plan.parts_needed,
            "steps": [
                {
                    "step_number": step.step_number,
                    "action": step.action,
                    "rationale": step.rationale,
                    "tools_required": step.tools_required,
                    "safety_warnings": step.safety_warnings,
                    "expected_outcome": step.expected_outcome,
                    "reversible": step.reversible
                } for step in plan.steps
            ],
            "safety_checks": plan.safety_checks,
            "reversibility": plan.reversibility,
            "success_criteria": plan.success_criteria
        }

# Global enhanced analyzer instance
enhanced_analyzer = EnhancedCircuitAnalyzer()
