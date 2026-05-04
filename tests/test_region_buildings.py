"""region_building junction maintenance."""

import json
import os

import pytest
from sqlalchemy import select

from app import create_app
from app.domain.region_buildings import rebuild_region_building_for_region
from app.extensions import db
from app.models import Building, Region, region_building

pytestmark = pytest.mark.usefixtures("_admin_env")


@pytest.fixture(scope="module", autouse=True)
def _admin_env():
    os.environ["ADMIN_PASSWORD"] = "test-pass"
    yield


@pytest.fixture()
def app(tmp_path):
    db_file = tmp_path / "rb.db"
    flask_app = create_app(
        override_config={
            "TESTING": True,
            "DEBUG": False,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file.as_posix()}",
            "WTF_CSRF_ENABLED": False,
        },
    )
    with flask_app.app_context():
        db.create_all()
        yield flask_app


def test_rebuild_region_includes_explicit_region_id(app):
    with app.app_context():
        r = Region(slug="campus", region_name="Campus", geojson=None, notes=None)
        db.session.add(r)
        db.session.flush()
        b = Building(
            slug="hall_a",
            display_name="Hall A",
            place_name="Hall A",
            latitude=40.0,
            longitude=-74.0,
            notes=None,
            region_id=int(r.id),
        )
        db.session.add(b)
        db.session.commit()
        rid, bid = r.id, b.id

        rebuild_region_building_for_region(int(rid))

        rows = db.session.execute(
            select(region_building.c.building_id).where(region_building.c.region_id == int(rid))
        ).fetchall()
        assert [int(x[0]) for x in rows] == [int(bid)]


def test_rebuild_region_point_in_polygon(app):
    poly = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-75.0, 39.0], [-73.0, 39.0], [-73.0, 41.0], [-75.0, 41.0], [-75.0, 39.0]]],
                },
            }
        ],
    }
    with app.app_context():
        r = Region(
            slug="box",
            region_name="Box",
            geojson=json.dumps(poly),
            notes=None,
        )
        db.session.add(r)
        db.session.flush()
        b = Building(
            slug="inside_pt",
            display_name="Inside",
            place_name="Inside",
            latitude=40.0,
            longitude=-74.0,
            notes=None,
            region_id=None,
        )
        db.session.add(b)
        db.session.commit()
        rid = r.id

        rebuild_region_building_for_region(int(rid))
        rows = db.session.execute(
            select(region_building.c.building_id).where(region_building.c.region_id == int(rid))
        ).fetchall()
        assert len(rows) >= 1
