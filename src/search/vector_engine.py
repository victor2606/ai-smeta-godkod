"""
Vector Search Engine for Construction Rates

Provides semantic search capabilities using OpenAI embeddings API.
Complements FTS5 full-text search with vector similarity search.

Author: Construction Estimator Team
Model: text-embedding-3-small (1536 dimensions, multilingual)
Storage: sqlite-vec extension for efficient vector similarity search
"""

import logging
import os
import struct
from typing import List, Dict, Any, Optional

import numpy as np
import httpx
from openai import OpenAI

from src.database.db_manager import DatabaseManager


logger = logging.getLogger(__name__)


class VectorSearchEngine:
    """
    Semantic search engine using OpenAI embeddings.

    Uses text-embedding-3-small model for generating embeddings and sqlite-vec
    for efficient cosine similarity search.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        api_key: str,
        model_name: str = "text-embedding-3-small",
        base_url: Optional[str] = None,
    ):
        """
        Initialize vector search engine.

        Args:
            db_manager: Database manager instance
            api_key: OpenAI API key
            model_name: OpenAI embedding model (default: text-embedding-3-small)
            base_url: Custom OpenAI API base URL (default: from OPENAI_BASE_URL env or OpenAI default)
        """
        self.db_manager = db_manager
        self.model_name = model_name

        # Use explicit base_url, or fallback to OPENAI_BASE_URL env var
        effective_base_url = base_url or os.getenv("OPENAI_BASE_URL")

        # Configure HTTP proxy if specified
        http_client = None
        proxy_url = os.getenv("OPENAI_PROXY")  # Format: http://user:pass@host:port
        if proxy_url:
            try:
                http_client = httpx.Client(proxy=proxy_url, timeout=30.0)
                logger.info(
                    f"Using HTTP proxy for OpenAI: {proxy_url.split('@')[-1]}"
                )  # Log without credentials
            except Exception as e:
                logger.warning(f"Failed to configure proxy {proxy_url}: {e}")
                http_client = None

        self.client = OpenAI(
            api_key=api_key,
            base_url=effective_base_url,  # None means use OpenAI default
            http_client=http_client,
        )

        # Dimension based on model
        if "small" in model_name:
            self.embedding_dim = 1536
        elif "large" in model_name:
            self.embedding_dim = 3072
        else:
            self.embedding_dim = 1536  # default

        logger.info(f"VectorSearchEngine initialized with OpenAI model: {model_name}")

    def _encode_query(self, query: str) -> np.ndarray:
        """
        Encode text query into vector embedding using OpenAI API.

        Args:
            query: Text query to encode

        Returns:
            Numpy array of shape (embedding_dim,)
        """
        response = self.client.embeddings.create(input=query, model=self.model_name)
        embedding = np.array(response.data[0].embedding, dtype=np.float32)

        # Normalize for cosine similarity
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding

    def _encode_batch(self, texts: List[str]) -> List[np.ndarray]:
        """
        Encode multiple texts in one API call (more efficient).

        Args:
            texts: List of texts to encode

        Returns:
            List of numpy arrays
        """
        response = self.client.embeddings.create(input=texts, model=self.model_name)

        embeddings = []
        for item in response.data:
            embedding = np.array(item.embedding, dtype=np.float32)

            # Normalize
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            embeddings.append(embedding)

        return embeddings

    def _serialize_vector(self, vector: np.ndarray) -> bytes:
        """
        Serialize numpy vector to bytes for sqlite-vec.

        Args:
            vector: Numpy array to serialize

        Returns:
            Bytes representation
        """
        # sqlite-vec expects float32 little-endian format
        return struct.pack(f"{len(vector)}f", *vector.astype(np.float32))

    def _deserialize_vector(self, blob: bytes) -> np.ndarray:
        """
        Deserialize bytes from sqlite-vec to numpy vector.

        Args:
            blob: Bytes from database

        Returns:
            Numpy array
        """
        count = len(blob) // 4  # 4 bytes per float32
        return np.array(struct.unpack(f"{count}f", blob))

    def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        similarity_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search using vector similarity.

        Args:
            query: Natural language search query
            limit: Maximum number of results (default: 10)
            filters: Optional filters (e.g., {'unit_type': 'м2'})
            similarity_threshold: Minimum cosine similarity (0-1, default: 0.0)

        Returns:
            List of rate dictionaries with similarity scores

        Raises:
            ValueError: If query is empty or limit is invalid
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        if limit <= 0 or limit > 1000:
            raise ValueError(f"Limit must be between 1 and 1000, got: {limit}")

        logger.info(f"Vector search query: '{query}', limit: {limit}")

        # Generate query embedding
        query_vector = self._encode_query(query)
        query_blob = self._serialize_vector(query_vector)

        # Build SQL query
        sql = """
            SELECT
                rate_code,
                rate_full_name,
                unit_type,
                unit_quantity,
                total_cost / unit_quantity as cost_per_unit,
                total_cost,
                labor_cost,
                machine_cost,
                material_cost,
                vec_distance_cosine(embedding, ?) as distance
            FROM rates
            WHERE embedding IS NOT NULL
        """

        params = [query_blob]

        # Add filters
        if filters:
            if "unit_type" in filters:
                sql += " AND unit_type = ?"
                params.append(filters["unit_type"])

            if "min_cost" in filters:
                sql += " AND (total_cost / unit_quantity) >= ?"
                params.append(filters["min_cost"])

            if "max_cost" in filters:
                sql += " AND (total_cost / unit_quantity) <= ?"
                params.append(filters["max_cost"])

        # Add similarity threshold (cosine distance = 1 - similarity)
        if similarity_threshold > 0:
            max_distance = 1.0 - similarity_threshold
            sql += " AND vec_distance_cosine(embedding, ?) <= ?"
            params.append(query_blob)
            params.append(max_distance)

        # Order by similarity and limit
        sql += """
            ORDER BY distance ASC
            LIMIT ?
        """
        params.append(limit)

        try:
            rows = self.db_manager.execute_query(sql, tuple(params))

            results = []
            for row in rows:
                (
                    rate_code,
                    rate_full_name,
                    unit_type,
                    unit_quantity,
                    cost_per_unit,
                    total_cost,
                    labor_cost,
                    machine_cost,
                    material_cost,
                    distance,
                ) = row

                # Convert cosine distance to similarity score (0-1)
                similarity = 1.0 - distance

                results.append(
                    {
                        "rate_code": rate_code,
                        "rate_full_name": rate_full_name,
                        "unit_type": unit_type,
                        "unit_quantity": unit_quantity,
                        "cost_per_unit": cost_per_unit,
                        "total_cost": total_cost,
                        "labor_cost": labor_cost,
                        "machine_cost": machine_cost,
                        "material_cost": material_cost,
                        "similarity": similarity,
                        "distance": distance,
                    }
                )

            logger.info(f"Vector search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Vector search failed: {str(e)}", exc_info=True)
            raise

    def generate_embedding(self, text: str) -> bytes:
        """
        Generate embedding for text and return as serialized bytes.

        Useful for batch embedding generation during data import.

        Args:
            text: Text to embed

        Returns:
            Serialized embedding bytes
        """
        vector = self._encode_query(text)
        return self._serialize_vector(vector)

    def generate_embeddings_batch(self, texts: List[str]) -> List[bytes]:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed

        Returns:
            List of serialized embedding bytes
        """
        vectors = self._encode_batch(texts)
        return [self._serialize_vector(v) for v in vectors]

    def get_embedding_stats(self) -> Dict[str, Any]:
        """
        Get statistics about embeddings in database.

        Returns:
            Dictionary with embedding statistics
        """
        stats_sql = """
            SELECT
                COUNT(*) as total_rates,
                SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as embedded_rates,
                SUM(CASE WHEN embedding IS NULL THEN 1 ELSE 0 END) as missing_embeddings
            FROM rates
        """

        meta_sql = """
            SELECT model_name, embedding_dimension, total_rates_embedded, last_embedded_at
            FROM embedding_metadata
            ORDER BY id DESC
            LIMIT 1
        """

        stats_row = self.db_manager.execute_query(stats_sql)[0]
        meta_rows = self.db_manager.execute_query(meta_sql)

        stats = {
            "total_rates": stats_row[0],
            "embedded_rates": stats_row[1],
            "missing_embeddings": stats_row[2],
            "embedding_coverage": (stats_row[1] / stats_row[0] * 100)
            if stats_row[0] > 0
            else 0,
        }

        if meta_rows:
            meta = meta_rows[0]
            stats["model_name"] = meta[0]
            stats["embedding_dimension"] = meta[1]
            stats["metadata_embedded_count"] = meta[2]
            stats["last_embedded_at"] = meta[3]

        return stats
