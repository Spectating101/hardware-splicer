import sqlite3
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger
from pathlib import Path
from src.config import settings


class CircuitDatabase:
    """Database manager for Circuit.AI analysis results."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize database connection."""
        self.database_url = db_path or settings.database_url
        self.db_path = self._resolve_db_path(self.database_url)
        self._ensure_db_directory()
        self._init_database()

    def _resolve_db_path(self, database_url: str) -> str:
        """Resolve SQLite file path from configured database URL."""
        if database_url.startswith("sqlite:///"):
            return database_url.replace("sqlite:///", "", 1)
        if database_url.startswith("sqlite://"):
            return database_url.replace("sqlite://", "", 1)
        logger.warning(f"Non-SQLite database_url detected ({database_url}); falling back to local SQLite store")
        return "data/circuit_ai.db"
    
    def _ensure_db_directory(self):
        """Ensure database directory exists."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    def _init_database(self):
        """Initialize database with schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Read and execute schema
                schema_path = Path("db/schema.sql")
                if schema_path.exists():
                    with open(schema_path, 'r') as f:
                        schema = f.read()
                    try:
                        # The bundled schema targets PostgreSQL; fall back to SQLite-safe tables on error
                        conn.executescript(schema)
                        logger.info("Database initialized with schema")
                    except sqlite3.Error as e:
                        conn.rollback()
                        logger.warning(f"Schema not compatible with SQLite ({e}); using basic SQLite schema instead")
                        self._create_basic_tables(conn)
                else:
                    logger.warning("Schema file not found, creating basic tables")
                    self._create_basic_tables(conn)
                # Perform lightweight migrations to ensure new columns/tables exist
                self._migrate_schema(conn)
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
    
    def _create_basic_tables(self, conn):
        """Create basic tables if schema file is not available."""
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS pcb_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_path TEXT,
                analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_components INTEGER,
                detection_quality TEXT,
                average_confidence REAL,
                project_potential TEXT,
                processing_time REAL,
                user_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS component_detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pcb_analysis_id INTEGER,
                component_type TEXT,
                confidence REAL,
                bbox_x1 REAL,
                bbox_y1 REAL,
                bbox_x2 REAL,
                bbox_y2 REAL,
                center_x REAL,
                center_y REAL,
                reuse_value TEXT,
                difficulty TEXT,
                capabilities TEXT,
                market_value REAL,
                educational_value TEXT,
                FOREIGN KEY (pcb_analysis_id) REFERENCES pcb_analyses(id)
            );
            
            CREATE TABLE IF NOT EXISTS project_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pcb_analysis_id INTEGER,
                project_id TEXT,
                score REAL,
                components_available TEXT,
                components_needed TEXT,
                estimated_cost TEXT,
                safety_level TEXT,
                educational_value TEXT,
                FOREIGN KEY (pcb_analysis_id) REFERENCES pcb_analyses(id)
            );
            
            CREATE TABLE IF NOT EXISTS user_favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                component_type TEXT,
                analysis_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES pcb_analyses(id)
            );
            
            CREATE TABLE IF NOT EXISTS user_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                action_type TEXT,
                action_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """Ensure new columns/tables are present without destructive changes."""
        try:
            def column_exists(table: str, column: str) -> bool:
                cur = conn.execute(f"PRAGMA table_info({table})")
                return any(row[1] == column for row in cur.fetchall())

            # component_detections: add new columns if missing
            for col, ddl in [
                ("market_value", "ALTER TABLE component_detections ADD COLUMN market_value REAL"),
                ("educational_value", "ALTER TABLE component_detections ADD COLUMN educational_value TEXT"),
                ("ocr_text", "ALTER TABLE component_detections ADD COLUMN ocr_text TEXT"),
                ("part_number", "ALTER TABLE component_detections ADD COLUMN part_number TEXT"),
            ]:
                try:
                    if not column_exists("component_detections", col):
                        conn.execute(ddl)
                except Exception:
                    pass

            # pcb_analyses: add user_id if missing
            try:
                if not column_exists("pcb_analyses", "user_id"):
                    conn.execute("ALTER TABLE pcb_analyses ADD COLUMN user_id TEXT")
            except Exception:
                pass
            # pcb_analyses: add backend and ocr columns if missing
            try:
                if not column_exists("pcb_analyses", "backend"):
                    conn.execute("ALTER TABLE pcb_analyses ADD COLUMN backend TEXT")
            except Exception:
                pass
            try:
                if not column_exists("pcb_analyses", "ocr"):
                    conn.execute("ALTER TABLE pcb_analyses ADD COLUMN ocr INTEGER")
            except Exception:
                pass

            # Ensure user_favorites and user_history tables exist
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS user_favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    component_type TEXT,
                    analysis_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (analysis_id) REFERENCES pcb_analyses(id)
                );
                CREATE TABLE IF NOT EXISTS user_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    action_type TEXT,
                    action_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_user_favorites_user ON user_favorites(user_id);
                CREATE INDEX IF NOT EXISTS idx_user_history_user ON user_history(user_id);
                CREATE INDEX IF NOT EXISTS idx_pcb_analyses_user_date ON pcb_analyses(user_id, analysis_date);
                CREATE INDEX IF NOT EXISTS idx_component_detections_type_reuse ON component_detections(component_type, reuse_value);
                -- Add annotated_image_path to pcb_analyses if missing
                """
            )
            # Add annotated_image_path column
            try:
                if not column_exists("pcb_analyses", "annotated_image_path"):
                    conn.execute("ALTER TABLE pcb_analyses ADD COLUMN annotated_image_path TEXT")
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Schema migration failed: {e}")
    
    def store_analysis_result(self, analysis_data: Dict[str, Any], image_path: str = None) -> int:
        """Store analysis result in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Store main analysis
                detection_summary = analysis_data.get("detection_summary", {})
                functionality_data = analysis_data.get("functionality_analysis", {})
                
                # Derive processing time (prefer numeric timing_seconds; fallback to parsing string)
                meta = analysis_data.get("analysis_metadata", {})
                processing_time = meta.get("timing_seconds")
                if processing_time is None:
                    tps = meta.get("total_processing_time")
                    try:
                        # Expect formats like "1.8 seconds"
                        processing_time = float(str(tps).split()[0]) if tps else 0.0
                    except Exception:
                        processing_time = 0.0

                # Backend/OCR metadata
                backend = analysis_data.get("analysis_metadata", {}).get("backend")
                ocr_flag = 1 if analysis_data.get("analysis_metadata", {}).get("ocr") else 0

                cursor = conn.execute(
                    """
                    INSERT INTO pcb_analyses 
                    (image_path, total_components, detection_quality, average_confidence, project_potential, processing_time, backend, ocr, annotated_image_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        image_path,
                        detection_summary.get("total_components", 0),
                        detection_summary.get("detection_quality", "unknown"),
                        detection_summary.get("average_confidence", 0.0),
                        functionality_data.get("project_potential", "none"),
                        processing_time or 0.0,
                        backend,
                        ocr_flag,
                        meta.get("annotated_image_path"),
                    ),
                )
                
                analysis_id = cursor.lastrowid
                
                # Store component detections
                components = functionality_data.get("components", [])
                for component in components:
                    bbox = component.get("bbox", [0, 0, 0, 0])
                    capabilities = json.dumps(component.get("capabilities", []))
                    
                    conn.execute("""
                            INSERT INTO component_detections 
                            (pcb_analysis_id, component_type, confidence, bbox_x1, bbox_y1, bbox_x2, bbox_y2, 
                             center_x, center_y, reuse_value, difficulty, capabilities, market_value, educational_value, ocr_text, part_number)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            analysis_id,
                            component.get("type", "unknown"),
                            component.get("detection_confidence", 0.0),
                            bbox[0] if len(bbox) > 0 else 0,
                            bbox[1] if len(bbox) > 1 else 0,
                            bbox[2] if len(bbox) > 2 else 0,
                            bbox[3] if len(bbox) > 3 else 0,
                            component.get("center", [0, 0])[0] if component.get("center") else 0,
                            component.get("center", [0, 0])[1] if component.get("center") else 0,
                            component.get("reuse_value", "unknown"),
                            component.get("difficulty", "unknown"),
                            capabilities,
                            component.get("market_value", 0.0),
                            component.get("educational_value", ""),
                            component.get("ocr_text", ""),
                            component.get("part_number", "")
                        ))
                
                # Store project recommendations
                recommendations = analysis_data.get("project_recommendations", [])
                for rec in recommendations:
                    conn.execute("""
                            INSERT INTO project_recommendations 
                            (pcb_analysis_id, project_id, score, components_available, components_needed)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            analysis_id,
                            rec.get("project_id", ""),
                            rec.get("score", 0.0),
                            json.dumps(rec.get("components_available", [])),
                            json.dumps(rec.get("components_needed", []))
                        ))
                
                conn.commit()
                logger.info(f"Analysis result stored with ID: {analysis_id}")
                return analysis_id
                
        except Exception as e:
            logger.error(f"Failed to store analysis result: {e}")
            return None
    
    def get_analysis_by_id(self, analysis_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve analysis result by ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get main analysis
                analysis_row = conn.execute(
                    """
                    SELECT id, image_path, analysis_date, total_components, detection_quality, 
                           average_confidence, project_potential, processing_time, backend, ocr, annotated_image_path
                    FROM pcb_analyses WHERE id = ?
                    """,
                    (analysis_id,),
                ).fetchone()
                
                if not analysis_row:
                    return None
                
                # Get component detections
                components = conn.execute("""
                    SELECT * FROM component_detections WHERE pcb_analysis_id = ?
                """, (analysis_id,)).fetchall()
                
                # Get project recommendations
                recommendations = conn.execute("""
                    SELECT * FROM project_recommendations WHERE pcb_analysis_id = ?
                """, (analysis_id,)).fetchall()
                
                # Format results
                return {
                    "analysis_id": analysis_id,
                    "image_path": analysis_row[1],
                    "analysis_date": analysis_row[2],
                    "total_components": analysis_row[3],
                    "detection_quality": analysis_row[4],
                    "average_confidence": analysis_row[5],
                    "project_potential": analysis_row[6],
                    "processing_time": analysis_row[7],
                    "backend": analysis_row[8],
                    "ocr": bool(analysis_row[9]) if analysis_row[9] is not None else None,
                    "annotated_image_path": analysis_row[10],
                    "components": components,
                    "recommendations": recommendations,
                }
                
        except Exception as e:
            logger.error(f"Failed to retrieve analysis: {e}")
            return None
    
    def get_recent_analyses(self, limit: int = 10, offset: int = 0, date_from: Optional[str] = None, date_to: Optional[str] = None, backend: Optional[str] = None, min_conf: Optional[float] = None) -> List[Dict[str, Any]]:
        """Get recent analysis results."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = [
                    "SELECT id, image_path, analysis_date, total_components, detection_quality, project_potential, average_confidence, backend, ocr",
                    "FROM pcb_analyses",
                ]
                where = []
                params = []
                if date_from:
                    where.append("analysis_date >= ?")
                    params.append(date_from)
                if date_to:
                    where.append("analysis_date <= ?")
                    params.append(date_to)
                if backend:
                    where.append("backend = ?")
                    params.append(backend)
                if min_conf is not None:
                    where.append("average_confidence >= ?")
                    params.append(min_conf)
                if where:
                    query.append("WHERE " + " AND ".join(where))
                query.append("ORDER BY analysis_date DESC LIMIT ? OFFSET ?")
                params.extend([limit, offset])
                sql = "\n".join(query)
                rows = conn.execute(sql, params).fetchall()
                
                return [
                    {
                        "id": row[0],
                        "image_path": row[1],
                        "analysis_date": row[2],
                        "total_components": row[3],
                        "detection_quality": row[4],
                        "project_potential": row[5],
                        "average_confidence": row[6],
                        "backend": row[7],
                        "ocr": bool(row[8]) if row[8] is not None else None,
                    }
                    for row in rows
                ]
                
        except Exception as e:
            logger.error(f"Failed to retrieve recent analyses: {e}")
            return []

    def get_performance_stats(self) -> Dict[str, Any]:
        """Aggregate performance statistics from analyses."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                agg = conn.execute(
                    """
                    SELECT COUNT(*) as cnt, AVG(processing_time) as avg_time, MAX(analysis_date) as last_date
                    FROM pcb_analyses
                    """
                ).fetchone()
                return {
                    "total_analyses": agg[0] or 0,
                    "avg_processing_time": float(agg[1]) if agg and agg[1] is not None else 0.0,
                    "last_analysis_date": agg[2]
                }
        except Exception as e:
            logger.error(f"Failed to get performance stats: {e}")
            return {"total_analyses": 0, "avg_processing_time": 0.0, "last_analysis_date": None}
    
    def get_component_statistics(self) -> Dict[str, Any]:
        """Get statistics about detected components."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Component type counts
                component_counts = conn.execute("""
                    SELECT component_type, COUNT(*) as count
                    FROM component_detections
                    GROUP BY component_type
                    ORDER BY count DESC
                """).fetchall()
                
                # Average confidence by component type
                confidence_stats = conn.execute("""
                    SELECT component_type, AVG(confidence) as avg_confidence
                    FROM component_detections
                    GROUP BY component_type
                """).fetchall()
                
                # Reuse value distribution
                reuse_stats = conn.execute("""
                    SELECT reuse_value, COUNT(*) as count
                    FROM component_detections
                    GROUP BY reuse_value
                """).fetchall()
                
                return {
                    "component_counts": dict(component_counts),
                    "confidence_stats": dict(confidence_stats),
                    "reuse_stats": dict(reuse_stats)
                }
                
        except Exception as e:
            logger.error(f"Failed to get component statistics: {e}")
            return {}
    
    def get_project_recommendation_stats(self) -> Dict[str, Any]:
        """Get statistics about project recommendations."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Most recommended projects
                project_counts = conn.execute("""
                    SELECT project_id, COUNT(*) as count, AVG(score) as avg_score
                    FROM project_recommendations
                    GROUP BY project_id
                    ORDER BY count DESC
                """).fetchall()
                
                # Score distribution
                score_stats = conn.execute("""
                    SELECT 
                        CASE 
                            WHEN score >= 0.8 THEN 'high'
                            WHEN score >= 0.6 THEN 'medium'
                            ELSE 'low'
                        END as score_category,
                        COUNT(*) as count
                    FROM project_recommendations
                    GROUP BY score_category
                """).fetchall()
                
                return {
                    "project_counts": [{"project_id": row[0], "count": row[1], "avg_score": row[2]} for row in project_counts],
                    "score_distribution": dict(score_stats)
                }
                
        except Exception as e:
            logger.error(f"Failed to get project recommendation stats: {e}")
            return {}
    
    def add_user_favorite(self, user_id: str, component_type: str, analysis_id: int) -> bool:
        """Add a component to user favorites."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO user_favorites (user_id, component_type, analysis_id)
                    VALUES (?, ?, ?)
                """, (user_id, component_type, analysis_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to add user favorite: {e}")
            return False
    
    def get_user_favorites(self, user_id: str) -> List[Dict[str, Any]]:
        """Get user's favorite components."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute("""
                    SELECT uf.*, cd.component_type, cd.confidence, cd.market_value
                    FROM user_favorites uf
                    JOIN component_detections cd ON uf.analysis_id = cd.pcb_analysis_id
                    WHERE uf.user_id = ?
                    ORDER BY uf.created_at DESC
                """, (user_id,)).fetchall()
                
                return [
                    {
                        "id": row[0],
                        "component_type": row[2],
                        "analysis_id": row[3],
                        "confidence": row[6],
                        "market_value": row[7],
                        "created_at": row[4]
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get user favorites: {e}")
            return []
    
    def log_user_action(self, user_id: str, action_type: str, action_data: Dict[str, Any]) -> bool:
        """Log user action for analytics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO user_history (user_id, action_type, action_data)
                    VALUES (?, ?, ?)
                """, (user_id, action_type, json.dumps(action_data)))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to log user action: {e}")
            return False
    
    def get_user_analytics(self, user_id: str) -> Dict[str, Any]:
        """Get user analytics and usage statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get analysis count
                analysis_count = conn.execute("""
                    SELECT COUNT(*) FROM pcb_analyses WHERE user_id = ?
                """, (user_id,)).fetchone()[0]
                
                # Get favorite components
                favorite_count = conn.execute("""
                    SELECT COUNT(*) FROM user_favorites WHERE user_id = ?
                """, (user_id,)).fetchone()[0]
                
                # Get recent activity
                recent_actions = conn.execute("""
                    SELECT action_type, COUNT(*) as count
                    FROM user_history
                    WHERE user_id = ?
                    GROUP BY action_type
                    ORDER BY count DESC
                """, (user_id,)).fetchall()
                
                return {
                    "analysis_count": analysis_count,
                    "favorite_count": favorite_count,
                    "recent_activity": [
                        {"action_type": row[0], "count": row[1]}
                        for row in recent_actions
                    ]
                }
        except Exception as e:
            logger.error(f"Failed to get user analytics: {e}")
            return {"analysis_count": 0, "favorite_count": 0, "recent_activity": []} 
