from flask import Blueprint, jsonify, request
from sqlalchemy.orm import Session
from ..db import get_db, SessionLocal
from .. import models, schemas
from sqlalchemy import exc

buildings_bp = Blueprint("buildings", __name__, url_prefix="/api/buildings")

def _get_db():
    return SessionLocal()

@buildings_bp.route("", methods=["GET"])
def list_buildings():
    db = _get_db()
    try:
        buildings = db.query(models.Building).order_by(models.Building.name).all()
        return jsonify([schemas.BuildingResponse.from_orm(b).dict() for b in buildings])
    finally:
        db.close()

@buildings_bp.route("", methods=["POST"])
def create_building():
    payload = request.get_json()
    try:
        data = schemas.BuildingCreate(**payload)
    except Exception as e:
        return jsonify({"detail": str(e)}), 422
        
    db = _get_db()
    try:
        if db.query(models.Building).filter(models.Building.name == data.name).first():
            return jsonify({"detail": "Building name already exists"}), 400
            
        new_b = models.Building(name=data.name, code=data.code, description=data.description, is_shared=data.is_shared or False, college_id=data.college_id)
        db.add(new_b)
        db.commit()
        db.refresh(new_b)
        return jsonify(schemas.BuildingResponse.from_orm(new_b).dict())
    finally:
        db.close()

@buildings_bp.route("/<int:id>", methods=["PUT"])
def update_building(id):
    payload = request.get_json()
    try:
        data = schemas.BuildingUpdate(**payload)
    except Exception as e:
        return jsonify({"detail": str(e)}), 422
        
    db = _get_db()
    try:
        b = db.query(models.Building).get(id)
        if not b:
            return jsonify({"detail": "Building not found"}), 404
            
        if data.name:
            dup = db.query(models.Building).filter(models.Building.name == data.name).filter(models.Building.id != id).first()
            if dup:
                return jsonify({"detail": "Building name already exists"}), 400
            b.name = data.name
        if data.code is not None:
            b.code = data.code
        if data.description is not None:
            b.description = data.description
        if data.is_shared is not None:
            b.is_shared = data.is_shared
        if "college_id" in (payload or {}):
            b.college_id = data.college_id
            
        db.commit()
        db.refresh(b)
        return jsonify(schemas.BuildingResponse.from_orm(b).dict())
    finally:
        db.close()

@buildings_bp.route("/<int:id>", methods=["DELETE"])
def delete_building(id):
    db = _get_db()
    try:
        b = db.query(models.Building).get(id)
        if not b:
            return jsonify({"detail": "Building not found"}), 404
            
        # Check dependencies (rooms)
        if b.rooms:
            return jsonify({"detail": "Cannot delete building with assigned rooms."}), 400
            
        db.delete(b)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()


@buildings_bp.route("/distances", methods=["GET"])
def list_distances():
    db = _get_db()
    try:
        dists = db.query(models.BuildingDistance).all()
        return jsonify([schemas.BuildingDistanceResponse.from_orm(d).dict() for d in dists])
    finally:
        db.close()

@buildings_bp.route("/distances", methods=["POST"])
def upsert_distance():
    # Expects { from_id, to_id, minutes }
    payload = request.get_json()
    try:
        data = schemas.BuildingDistanceCreate(**payload)
    except Exception as e:
        return jsonify({"detail": str(e)}), 422
        
    db = _get_db()
    try:
        # Check standardized pair order (min, max) to avoid duplicates like (1,2) and (2,1)
        # OR just enforce caller handles it. 
        # Better: check if exists
        
        existing = db.query(models.BuildingDistance).filter(
            models.BuildingDistance.from_building_id == data.from_building_id,
            models.BuildingDistance.to_building_id == data.to_building_id
        ).first()
        
        if existing:
            existing.travel_time_minutes = data.travel_time_minutes
            rec = existing
        else:
            rec = models.BuildingDistance(
                from_building_id=data.from_building_id,
                to_building_id=data.to_building_id,
                travel_time_minutes=data.travel_time_minutes
            )
            db.add(rec)
            
        db.commit()
        db.refresh(rec)
        return jsonify(schemas.BuildingDistanceResponse.from_orm(rec).dict())
    finally:
        db.close()

@buildings_bp.route("/distances/<int:id>", methods=["DELETE"])
def delete_distance(id):
    db = _get_db()
    try:
        rec = db.query(models.BuildingDistance).get(id)
        if not rec:
            return jsonify({"detail": "Record not found"}), 404
        db.delete(rec)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()
