"""
HTTP REST API Server for Construction Estimator Frontend

Provides HTTP REST API endpoints that wrap the MCP tools for frontend consumption.
This allows the React frontend to interact with the construction estimator backend.

Endpoints:
- POST /api/natural_search: Full-text search
- POST /api/vector_search: Semantic vector search
- POST /api/quick_calculate: Cost calculation
- POST /api/show_rate_details: Detailed resource breakdown
- GET /health: Health check endpoint

Author: Construction Estimator Team
"""

import logging
import os
from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from src.database.db_manager import DatabaseManager
from src.search.search_engine import SearchEngine
from src.search.cost_calculator import CostCalculator
from src.search.rate_comparator import RateComparator
from src.search.vector_engine import VectorSearchEngine


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Initialize FastAPI app
app = FastAPI(
    title="Construction Estimator API",
    description="HTTP REST API for construction rate search and cost calculation",
    version="1.0.0",
    root_path="/api",  # For reverse proxy path routing
)


# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Database initialization
DB_PATH = os.getenv("DATABASE_PATH", "data/processed/estimates.db")

if not Path(DB_PATH).exists():
    logger.error(f"Database file not found: {DB_PATH}")
    raise FileNotFoundError(f"Database file not found: {DB_PATH}")

logger.info(f"Initializing API server with database: {DB_PATH}")

db_manager = DatabaseManager(DB_PATH)
db_manager.connect()
logger.info("DatabaseManager connected successfully")

search_engine = SearchEngine(db_manager)
cost_calculator = CostCalculator(db_manager)
rate_comparator = RateComparator(DB_PATH)

# Initialize VectorSearchEngine
openai_api_key = os.getenv("OPENAI_API_KEY")
if openai_api_key:
    vector_engine = VectorSearchEngine(
        db_manager=db_manager,
        api_key=openai_api_key,
        base_url=os.getenv("OPENAI_BASE_URL"),
    )
    logger.info("VectorSearchEngine initialized")
else:
    vector_engine = None
    logger.warning("OPENAI_API_KEY not set - vector search unavailable")

logger.info("All services initialized successfully")


# Pydantic models for request/response validation
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results")
    unit_type: Optional[str] = Field(
        None, description="Unit type filter (м2, м3, т, etc.)"
    )


class VectorSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results")
    unit_type: Optional[str] = Field(None, description="Unit type filter")
    similarity_threshold: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Minimum similarity score"
    )


class QuickCalculateRequest(BaseModel):
    rate_identifier: str = Field(..., description="Rate code or search query")
    quantity: float = Field(..., gt=0, description="Quantity to calculate")


class RateDetailsRequest(BaseModel):
    rate_code: str = Field(..., description="Rate code")
    quantity: float = Field(default=1.0, gt=0, description="Quantity for calculation")


class CompareRequest(BaseModel):
    rate_codes: List[str] = Field(..., min_items=2, description="Rate codes to compare")
    quantity: float = Field(..., gt=0, description="Quantity for comparison")


# API Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration"""
    return {
        "status": "healthy",
        "service": "construction-estimator-api",
        "database": "connected" if db_manager.connection else "disconnected",
        "vector_search": "enabled" if vector_engine else "disabled",
    }


@app.post("/natural_search")
async def natural_search(request: SearchRequest):
    """
    Full-text search for construction rates using Russian text query.

    Returns matching rates with their codes, names, units, and costs.
    """
    try:
        logger.info(f"natural_search: query='{request.query}', limit={request.limit}")

        filters = {"unit_type": request.unit_type} if request.unit_type else None
        results = search_engine.search(
            query=request.query, filters=filters, limit=request.limit
        )

        # Results are already a list of dicts
        results_list = results if isinstance(results, list) else []

        return {"success": True, "count": len(results_list), "results": results_list}

    except Exception as e:
        logger.error(f"natural_search error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vector_search")
async def vector_search(request: VectorSearchRequest):
    """
    Semantic vector search for construction rates using embeddings.

    More robust than full-text search for variations in descriptions.
    """
    if not vector_engine:
        raise HTTPException(
            status_code=503,
            detail="Vector search not available - OPENAI_API_KEY not configured",
        )

    try:
        logger.info(f"vector_search: query='{request.query}', limit={request.limit}")

        filters = {"unit_type": request.unit_type} if request.unit_type else None
        results = vector_engine.search(
            query=request.query,
            limit=request.limit,
            filters=filters,
            similarity_threshold=request.similarity_threshold,
        )

        results_list = results if isinstance(results, list) else []

        return {"success": True, "count": len(results_list), "results": results_list}

    except Exception as e:
        logger.error(f"vector_search error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/quick_calculate")
async def quick_calculate(request: QuickCalculateRequest):
    """
    Calculate cost for a rate with auto-detection of input type.

    Accepts either:
    - Rate code (e.g., "ГЭСНп10-05-001-01")
    - Russian description (will search and use best match)
    """
    try:
        logger.info(
            f"quick_calculate: identifier='{request.rate_identifier}', quantity={request.quantity}"
        )

        result = cost_calculator.quick_calculate(
            rate_identifier=request.rate_identifier, quantity=request.quantity
        )

        return {
            "success": True,
            "rate_info": {
                "rate_code": result["rate_code"],
                "rate_full_name": result["rate_full_name"],
                "unit_type": result["unit_type"],
            },
            "cost_per_unit": round(result["cost_per_unit"], 2),
            "total_cost": round(result["total_cost"], 2),
            "material_cost": round(result["material_cost"], 2),
            "labor_cost": round(result["labor_cost"], 2),
            "machinery_cost": round(result["machinery_cost"], 2),
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"quick_calculate error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/show_rate_details")
async def show_rate_details(request: RateDetailsRequest):
    """
    Get comprehensive resource breakdown for a rate.

    Returns detailed list of all resources (materials, labor, machinery)
    with quantities, units, and costs.
    """
    try:
        logger.info(
            f"show_rate_details: rate_code='{request.rate_code}', quantity={request.quantity}"
        )

        result = cost_calculator.get_detailed_breakdown(
            rate_code=request.rate_code, quantity=request.quantity
        )

        return {
            "success": True,
            "rate_info": {
                "rate_code": result["rate_code"],
                "rate_full_name": result["rate_full_name"],
                "unit_type": result["unit_type"],
            },
            "total_cost": round(result["total_cost"], 2),
            "cost_per_unit": round(result["cost_per_unit"], 2),
            "materials": round(result["materials"], 2),
            "labor": round(result["labor"], 2),
            "machinery": round(result["machinery"], 2),
            "resources": result["resources"],
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"show_rate_details error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/compare_variants")
async def compare_variants(request: CompareRequest):
    """
    Compare multiple rates side-by-side for cost analysis.

    Returns sorted comparison with cost differences from cheapest option.
    """
    try:
        logger.info(
            f"compare_variants: codes={request.rate_codes}, quantity={request.quantity}"
        )

        result = rate_comparator.compare_rates(
            rate_codes=request.rate_codes, quantity=request.quantity
        )

        return {
            "success": True,
            "count": len(result["comparison"]),
            "comparison": result["comparison"],
        }

    except Exception as e:
        logger.error(f"compare_variants error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Server entry point
if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    logger.info(f"Starting HTTP API server on {host}:{port}")

    uvicorn.run(app, host=host, port=port, log_level="info")
