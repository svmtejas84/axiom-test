"""
KDTree Geospatial Enrichment Module

This module enriches graph nodes with geospatial metadata:
1. Attaches merchant/utility information to transaction nodes
2. Computes merchant density scores (more merchants nearby = higher economic activity)
3. Cross-references property addresses for fraud detection

KDTree is a spatial data structure that enables fast nearest-neighbor queries.
In the Axiom context, it's used to:
- Find merchants near a user's location
- Identify dense commercial clusters
- Detect geographic anomalies (sudden location changes)
"""

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.spatial import KDTree

logger = logging.getLogger(__name__)


@dataclass
class Location:
    """
    Geographic location with latitude and longitude.

    Attributes:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        address: Human-readable address (optional)
        pincode: Indian postal code (optional)
    """

    latitude: float
    longitude: float
    address: str | None = None
    pincode: str | None = None


@dataclass
class MerchantInfo:
    """
    Information about a nearby merchant.

    Attributes:
        merchant_id: Unique merchant identifier
        distance_km: Distance from user location in kilometers
        category: Merchant category (retail, utility, food, transport, etc)
        transaction_count: Number of transactions at this merchant
        avg_transaction_value: Average transaction amount
    """

    merchant_id: str
    distance_km: float
    category: str | None = None
    transaction_count: int = 0
    avg_transaction_value: float = 0.0


@dataclass
class EnrichedNode:
    """
    Node enriched with geospatial metadata.

    Attributes:
        node_id: Original node ID
        node_type: "user", "landlord", "merchant"
        location: Geographic location
        nearby_merchants: List of MerchantInfo objects with distances
        merchant_density: 0-1 score of merchant density around node
        economic_cluster_score: 0-1 score of overall economic activity
        neighborhood_diversity: 0-1 score of merchant category diversity
        distance_to_nearest_merchant_km: Distance to closest merchant
        metadata: Additional enrichment data
    """

    node_id: str
    node_type: str
    location: Location
    nearby_merchants: list[MerchantInfo]
    merchant_density: float
    economic_cluster_score: float
    neighborhood_diversity: float
    distance_to_nearest_merchant_km: float
    metadata: dict[str, Any]


class KDTreeEnricher:
    """
    Enriches trust graph nodes with geospatial features.

    This enricher:
    1. Indexes all merchants by location (KDTree)
    2. For each user/landlord, finds nearby merchants with distances
    3. Computes merchant density and economic cluster scores
    4. Calculates neighborhood diversity (category mix)
    5. Detects location anomalies
    6. Handles user addresses for fraud detection

    Features:
    - Haversine distance calculation (accurate for Earth's curvature)
    - Merchant category diversity scoring
    - Neighborhood economic integration metrics
    - Address-based fraud detection (location spoofing, SIM swapping)

    Example:
        >>> enricher = KDTreeEnricher()
        >>> enricher.index_merchants(merchant_data)
        >>> enriched = await enricher.enrich_node(
        ...     "user123",
        ...     Location(lat=28.7041, lon=77.1025, address="123 Main St, Delhi"),
        ...     node_type="user"
        ... )
        >>> print(f"Nearest merchant: {enriched.distance_to_nearest_merchant_km:.2f}km")
        >>> print(f"Diversity score: {enriched.neighborhood_diversity:.2f}")
    """

    # Parameters for spatial analysis
    SEARCH_RADIUS_KM = 2.0  # Default: look for merchants within 2 km
    EARTH_RADIUS_KM = 6371.0  # For haversine distance
    MAX_MERCHANTS_NEARBY = 20  # Saturation point for merchant density
    CATEGORY_DIVERSITY_THRESHOLD = 5  # Minimum merchant categories for high diversity

    def __init__(self, search_radius_km: float = SEARCH_RADIUS_KM) -> None:
        """
        Initialize KDTree enricher with user address tracking.

        Args:
            search_radius_km: Radius for nearest-neighbor queries (default 2km)
        """
        self.search_radius_km = search_radius_km
        self.merchant_tree: KDTree | None = None
        self.merchant_locations: dict[str, Location] = {}  # merchant_id -> Location
        self.merchant_metadata: dict[str, dict[str, Any]] = {}  # merchant_id -> {category, ...}
        self.merchant_ids: list[str] = []  # Ordered merchant IDs for tree
        self.user_addresses: dict[str, Location] = {}  # user_id -> Location (for fraud detection)
        
        logger.info(f"Initialized KDTreeEnricher (radius={search_radius_km}km)")

    def index_merchants(
        self,
        merchants: dict[str, Location],
        merchant_metadata: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """
        Build KDTree index of merchant locations with metadata.

        Args:
            merchants: Dictionary mapping merchant_id -> Location
            merchant_metadata: Dictionary mapping merchant_id -> {"category": "retail", ...}

        Note:
            - Call this once after all merchants are added to the graph
            - Call again if merchants are added/removed
            - Merchant metadata helps compute neighborhood diversity
        """
        if not merchants:
            logger.warning("No merchants to index")
            return

        self.merchant_locations = merchants
        self.merchant_metadata = merchant_metadata or {}
        self.merchant_ids = list(merchants.keys())

        # Extract coordinates for KDTree (latitude, longitude)
        coordinates = np.array(
            [
                [merchants[mid].latitude, merchants[mid].longitude]
                for mid in self.merchant_ids
            ]
        )

        # Build KDTree in lat-lon space (fast for spatial queries)
        self.merchant_tree = KDTree(coordinates)

        logger.info(
            f"Indexed {len(merchants)} merchants in KDTree "
            f"with {len(self.merchant_metadata)} metadata entries"
        )

    async def enrich_node(
        self,
        node_id: str,
        location: Location,
        node_type: str = "user",
    ) -> EnrichedNode:
        """
        Enrich a single node with geospatial metadata including merchant distances.

        Args:
            node_id: Node identifier
            location: Node's geographic location with address
            node_type: "user", "landlord", or "merchant"

        Returns:
            EnrichedNode with nearby merchants (sorted by distance) and diversity metrics

        Algorithm:
            1. Store user address for fraud detection
            2. Query KDTree for merchants within search radius
            3. Calculate haversine distances to each merchant
            4. Sort by distance, extract category diversity
            5. Compute economic cluster score from diversity + density
        """
        # Track user address for fraud detection
        if node_type == "user":
            self.user_addresses[node_id] = location

        nearby_merchants: list[MerchantInfo] = []
        merchant_density = 0.0
        economic_cluster_score = 0.0
        neighborhood_diversity = 0.0
        distance_to_nearest_km = float("inf")

        if self.merchant_tree is not None and self.merchant_ids:
            # Convert search radius from km to lat-lon degrees (approximate: 1° ≈ 111 km)
            radius_degrees = self.search_radius_km / 111.0

            # Query KDTree for nearby merchants
            query_point = np.array([[location.latitude, location.longitude]])
            distances_degrees, indices = self.merchant_tree.query(
                query_point,
                k=len(self.merchant_ids),
                distance_upper_bound=radius_degrees,
            )

            distances_degrees = distances_degrees[0]
            indices = indices[0]

            # Convert distances from degrees to kilometers using haversine
            for idx, dist_deg in zip(indices, distances_degrees):
                if dist_deg < radius_degrees and idx < len(self.merchant_ids):
                    merchant_id = self.merchant_ids[idx]
                    merchant_loc = self.merchant_locations[merchant_id]

                    # Accurate haversine distance
                    dist_km = self._haversine_distance(
                        location.latitude,
                        location.longitude,
                        merchant_loc.latitude,
                        merchant_loc.longitude,
                    )

                    if dist_km <= self.search_radius_km:
                        merchant_metadata = self.merchant_metadata.get(
                            merchant_id, {"category": "unknown"}
                        )

                        merchant_info = MerchantInfo(
                            merchant_id=merchant_id,
                            distance_km=dist_km,
                            category=merchant_metadata.get("category"),
                            transaction_count=merchant_metadata.get(
                                "transaction_count", 0
                            ),
                            avg_transaction_value=merchant_metadata.get(
                                "avg_transaction_value", 0.0
                            ),
                        )
                        nearby_merchants.append(merchant_info)

                        if dist_km < distance_to_nearest_km:
                            distance_to_nearest_km = dist_km

            # Sort by distance (closest first)
            nearby_merchants.sort(key=lambda m: m.distance_km)

            # Calculate merchant density score
            merchant_density = min(
                len(nearby_merchants) / self.MAX_MERCHANTS_NEARBY, 1.0
            )

            # Calculate neighborhood diversity (merchant category mix)
            categories = set(m.category for m in nearby_merchants if m.category)
            neighborhood_diversity = min(
                len(categories) / self.CATEGORY_DIVERSITY_THRESHOLD, 1.0
            )

            # Economic cluster score: weighted average of density + diversity
            # High density + high diversity = economically integrated
            economic_cluster_score = (
                0.6 * merchant_density + 0.4 * neighborhood_diversity
            )

            if distance_to_nearest_km == float("inf"):
                distance_to_nearest_km = self.search_radius_km  # No merchants found

        enriched = EnrichedNode(
            node_id=node_id,
            node_type=node_type,
            location=location,
            nearby_merchants=nearby_merchants,
            merchant_density=merchant_density,
            economic_cluster_score=economic_cluster_score,
            neighborhood_diversity=neighborhood_diversity,
            distance_to_nearest_merchant_km=distance_to_nearest_km,
            metadata={
                "search_radius_km": self.search_radius_km,
                "merchants_found": len(nearby_merchants),
                "unique_categories": len(
                    set(m.category for m in nearby_merchants if m.category)
                ),
                "avg_distance_km": float(
                    np.mean([m.distance_km for m in nearby_merchants])
                    if nearby_merchants
                    else self.search_radius_km
                ),
            },
        )

        logger.debug(
            f"Enriched {node_type} {node_id}: "
            f"nearest_merchant={distance_to_nearest_km:.2f}km, "
            f"density={merchant_density:.2f}, "
            f"diversity={neighborhood_diversity:.2f}, "
            f"cluster={economic_cluster_score:.2f}, "
            f"merchants={len(nearby_merchants)}"
        )

        return enriched

    def _calculate_cluster_score(self, merchant_ids: list[str]) -> float:
        """
        Calculate economic cluster score based on merchant diversity.

        Higher score = more diverse economic activity.

        Args:
            merchant_ids: List of nearby merchant IDs

        Returns:
            Score in [0, 1]
        """
        if not merchant_ids:
            return 0.0

        # Use metadata categories for diversity
        categories = set()
        for mid in merchant_ids:
            meta = self.merchant_metadata.get(mid, {})
            category = meta.get("category", "unknown")
            categories.add(category)

        # Normalize by threshold
        return min(len(categories) / self.CATEGORY_DIVERSITY_THRESHOLD, 1.0)

    def detect_location_anomaly(
        self,
        user_id: str,
        current_location: Location,
        previous_locations: list[Location] | None = None,
    ) -> dict[str, Any]:
        """
        Detect if user has moved suspiciously far or changed addresses abruptly.

        Indicates possible fraud (location spoofing, SIM swapping, account takeover).

        Args:
            user_id: User identifier
            current_location: Current location
            previous_locations: History of prior locations (optional)

        Returns:
            Dictionary with:
            - is_anomalous: bool
            - anomaly_type: "location_jump", "address_change", "none"
            - distance_km: Distance traveled
            - confidence: Anomaly confidence [0, 1]
        """
        anomaly_result = {
            "is_anomalous": False,
            "anomaly_type": "none",
            "distance_km": 0.0,
            "confidence": 0.0,
        }

        if not previous_locations:
            return anomaly_result

        # Check against stored user address
        if user_id in self.user_addresses:
            stored_loc = self.user_addresses[user_id]
            dist_from_stored = self._haversine_distance(
                current_location.latitude,
                current_location.longitude,
                stored_loc.latitude,
                stored_loc.longitude,
            )

            # Flag if moved >50km from usual address (likely fraud or travel)
            if dist_from_stored > 50.0:
                anomaly_result["is_anomalous"] = True
                anomaly_result["anomaly_type"] = "location_jump"
                anomaly_result["distance_km"] = dist_from_stored
                anomaly_result["confidence"] = min(
                    (dist_from_stored - 50.0) / 100.0, 1.0
                )  # 50-150km range
                logger.warning(
                    f"Location anomaly for {user_id}: {dist_from_stored:.1f}km "
                    f"from stored address"
                )

        # Check for rapid movement between consecutive transactions
        if len(previous_locations) >= 1:
            last_loc = previous_locations[-1]
            dist_rapid = self._haversine_distance(
                current_location.latitude,
                current_location.longitude,
                last_loc.latitude,
                last_loc.longitude,
            )

            # Flag if moved >5km instantly (human impossible)
            if dist_rapid > 5.0:
                anomaly_result["is_anomalous"] = True
                anomaly_result["anomaly_type"] = "address_change"
                anomaly_result["distance_km"] = dist_rapid
                anomaly_result["confidence"] = min(dist_rapid / 10.0, 1.0)
                logger.warning(
                    f"Rapid movement for {user_id}: {dist_rapid:.1f}km "
                    f"from last location"
                )

        return anomaly_result

    def _haversine_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """
        Calculate great-circle distance between two lat-lon coordinates.

        Uses the Haversine formula (accurate for Earth).

        Args:
            lat1, lon1: First coordinate
            lat2, lon2: Second coordinate

        Returns:
            Distance in kilometers
        """
        # Convert to radians
        lat1_rad = np.radians(lat1)
        lon1_rad = np.radians(lon1)
        lat2_rad = np.radians(lat2)
        lon2_rad = np.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = (
            np.sin(dlat / 2) ** 2
            + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2) ** 2
        )
        c = 2 * np.arcsin(np.sqrt(a))

        distance_km = self.EARTH_RADIUS_KM * c
        return distance_km

    def attach_to_graph_nodes(
        self,
        graph_nodes: dict[str, Any],
        enriched_nodes: dict[str, EnrichedNode],
    ) -> None:
        """
        Attach enriched metadata to graph nodes.

        Args:
            graph_nodes: Dictionary of node_id -> node attributes
            enriched_nodes: Dictionary of node_id -> EnrichedNode

        Note:
            - Modifies graph_nodes in-place
            - Called after graph construction and enrichment
        """
        for node_id, enriched in enriched_nodes.items():
            if node_id in graph_nodes:
                graph_nodes[node_id]["merchant_density"] = enriched.merchant_density
                graph_nodes[node_id]["economic_cluster_score"] = (
                    enriched.economic_cluster_score
                )
                graph_nodes[node_id]["nearby_merchants"] = enriched.nearby_merchants
