"""Maintain ``region_building`` rows (explicit region_id + point-in-polygon)."""

from __future__ import annotations

import json
from sqlalchemy import delete, func, insert, select

from app.extensions import db
from app.models import Building, Region, region_building as region_building_tbl

try:
    from shapely.geometry import Point, shape
    from shapely.geometry.base import BaseGeometry
except ImportError:  # pragma: no cover - tests install shapely
    Point = None  # type: ignore[misc, assignment]
    shape = None  # type: ignore[misc, assignment]
    BaseGeometry = object  # type: ignore[misc, assignment]


def _polygon_from_geojson(raw: str | None) -> BaseGeometry | None:
    if not raw or not raw.strip() or shape is None:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    try:
        if isinstance(data, dict) and data.get("type") == "FeatureCollection":
            polys: list[BaseGeometry] = []
            for feat in data.get("features") or []:
                if not isinstance(feat, dict):
                    continue
                geom = feat.get("geometry")
                if not isinstance(geom, dict):
                    continue
                g = shape(geom)
                if g.geom_type == "Polygon":
                    polys.append(g)
                elif g.geom_type == "MultiPolygon":
                    polys.extend(g.geoms)
            if not polys:
                return None
            if len(polys) == 1:
                return polys[0]
            from shapely.ops import unary_union

            return unary_union(polys)
        g = shape(data)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if g.is_empty:
        return None
    if g.geom_type == "Polygon":
        return g
    if g.geom_type == "MultiPolygon":
        return g
    return None


def building_belongs_to_region(building: Building, region: Region) -> bool:
    rid = int(region.id)
    if building.region_id is not None and int(building.region_id) == rid:
        return True
    poly = _polygon_from_geojson(region.geojson)
    if poly is None or Point is None:
        return False
    try:
        pt = Point(float(building.longitude), float(building.latitude))
    except (TypeError, ValueError):
        return False
    return bool(poly.covers(pt) or poly.touches(pt))


def rebuild_region_building_for_region(region_id: int) -> int:
    """Replace all junction rows for one region. Returns number of rows inserted."""

    region = db.session.get(Region, int(region_id))
    if region is None:
        return 0

    db.session.execute(delete(region_building_tbl).where(region_building_tbl.c.region_id == int(region_id)))

    building_ids: set[int] = set()
    for b in Building.query.all():
        if building_belongs_to_region(b, region):
            building_ids.add(int(b.id))

    for bid in sorted(building_ids):
        db.session.execute(
            insert(region_building_tbl).values(region_id=int(region_id), building_id=int(bid))
        )

    return len(building_ids)


def rebuild_region_building_for_building(building_id: int) -> None:
    """Recompute junction rows for every region that could include this building."""

    b = db.session.get(Building, int(building_id))
    if b is None:
        return

    db.session.execute(delete(region_building_tbl).where(region_building_tbl.c.building_id == int(building_id)))

    for r in Region.query.all():
        if building_belongs_to_region(b, r):
            db.session.execute(
                insert(region_building_tbl).values(region_id=int(r.id), building_id=int(building_id))
            )


def rebuild_all_region_buildings() -> None:
    """Full recompute (e.g. after migration)."""

    db.session.execute(delete(region_building_tbl))
    for r in Region.query.order_by(Region.id.asc()).all():
        rebuild_region_building_for_region(int(r.id))


def building_ids_for_region(region_id: int) -> list[int]:
    stmt = (
        select(region_building_tbl.c.building_id)
        .where(region_building_tbl.c.region_id == int(region_id))
        .order_by(region_building_tbl.c.building_id.asc())
    )
    return [int(r[0]) for r in db.session.execute(stmt).fetchall()]


def ensure_region_building_rows(region_id: int) -> None:
    """If junction is empty, rebuild once (fallback for legacy data)."""

    n = db.session.execute(
        select(func.count())
        .select_from(region_building_tbl)
        .where(region_building_tbl.c.region_id == int(region_id))
    ).scalar()
    if not n:
        rebuild_region_building_for_region(int(region_id))
