from flask import Blueprint, request, jsonify
from sqlalchemy.exc import SQLAlchemyError
import pdfplumber
import logging
import re
import os
import tempfile
from typing import List, Dict, Any

from .. import models
from ..db import SessionLocal

curriculum_bp = Blueprint("curriculum", __name__)
logger = logging.getLogger(__name__)

# Fallback logger to project root for visibility
log_path = os.path.join(os.getcwd(), "curriculum_debug.log")
fh = logging.FileHandler(log_path)
fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(fh)
logger.setLevel(logging.INFO)

def parse_curriculum_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    subjects = []
    
    year_map = {
        "FIRST YEAR": 1, "SECOND YEAR": 2, "THIRD YEAR": 3, "FOURTH YEAR": 4
    }

    # Global State
    state = {
        "current_year": 1, 
        "current_semester": 1
    }
    
    logger.info(f"--- STARTING ROBUST VISUAL PARSE of {pdf_path} ---")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                logger.info(f"Processing Page {page_num}")
                
                # 1. Gather all elements with spatial data
                elements = []
                
                # a) Extract Lines of text
                words = page.extract_words()
                lines_data = {}
                for w in words:
                    y = round(w['top'], 0) # Round to prevent jitter
                    if y not in lines_data: lines_data[y] = []
                    lines_data[y].append(w)
                
                for y, l_words in lines_data.items():
                    text = " ".join([w['text'] for w in sorted(l_words, key=lambda x: x['x0'])]).strip().upper()
                    
                    found_year = False
                    for y_key, y_val in year_map.items():
                        if y_key in text:
                            elements.append({"type": "year_header", "y": y, "val": y_val, "text": text})
                            found_year = True
                            break
                    if found_year: continue

                    if "SUMMER" in text:
                        elements.append({"type": "sem_header", "y": y, "val": 3, "text": text})
                    elif "FIRST SEMESTER" in text and "SECOND SEMESTER" not in text:
                        elements.append({"type": "sem_header", "y": y, "val": 1, "text": text})
                    elif "SECOND SEMESTER" in text and "FIRST SEMESTER" not in text:
                        elements.append({"type": "sem_header", "y": y, "val": 2, "text": text})
                    
                    if "EXIT POINT" in text:
                        elements.append({"type": "exit_point", "y": y, "text": text})

                # b) Extract Tables
                table_objs = page.find_tables()
                for tobj in table_objs:
                    elements.append({"type": "table", "y": tobj.bbox[1], "obj": tobj})

                # 2. Sort elements by Y-coordinate with a "Header Priority" shift
                # If a header is within 25 units of a table's top, it likely belongs to that table.
                # We sort headers with a -20 shift so they "appear" earlier in the sequence if they are close.
                def sort_key(el):
                    if el['type'] in ["year_header", "sem_header"]:
                        return el['y'] - 20 # Priority shift
                    return el['y']

                elements.sort(key=sort_key)
                
                for el in elements:
                    if el['type'] == "year_header":
                        state["current_year"] = el['val']
                        state["current_semester"] = 1 # Default to 1 on year change
                        logger.info(f"Y={el['y']} -> YEAR {el['val']}")
                    
                    elif el['type'] == "sem_header":
                        state["current_semester"] = el['val']
                        logger.info(f"Y={el['y']} -> SEM {el['val']}")

                    elif el['type'] == "exit_point":
                        clean_desc = el['text'].replace("EXIT POINT", "").strip(": * ")
                        if clean_desc:
                            subjects.append({
                                "year_level": state["current_year"],
                                "semester": 0,
                                "is_exit_point": True,
                                "description": clean_desc,
                                "code": "EXIT",
                                "units": 0
                            })
                            logger.info(f"Y={el['y']} -> EXIT '{clean_desc}'")

                    elif el['type'] == "table":
                        data = el['obj'].extract()
                        if not data: continue
                        
                        is_side_by_side = any(len(row) >= 8 for row in data[:5])
                        logger.info(f"Y={el['y']} -> TABLE (side_by_side={is_side_by_side}, context=Y{state['current_year']} S{state['current_semester']})")
                        
                        for row_idx, row in enumerate(data):
                            clean_row = [str(c or "").strip() for c in row]
                            row_str = " ".join(clean_row).lower()
                            
                            if not any(clean_row) or "course" in row_str or "descriptive title" in row_str or "semester" in row_str:
                                continue
                                
                            # Skip totals
                            if "total" in row_str or (clean_row[0] and "total" in clean_row[0].lower()):
                                continue

                            if is_side_by_side and len(clean_row) >= 8:
                                mid = 5
                                if len(clean_row) > 10:
                                    for i in range(5, min(9, len(clean_row))):
                                        if clean_row[i]: mid = i; break
                                
                                parse_and_add_subject(subjects, clean_row[:mid], state["current_year"], 1)
                                parse_and_add_subject(subjects, clean_row[mid:], state["current_year"], 2)
                            else:
                                sem = state["current_semester"]
                                # If Summer was detected, state["current_semester"] should be 3
                                parse_and_add_subject(subjects, clean_row, state["current_year"], sem)

    except Exception as e:
        logger.error(f"FATAL ERROR: {e}", exc_info=True)
        raise ValueError(f"Parsing failed: {str(e)}")

    logger.info(f"FINISHED. Found {len(subjects)} subjects/exits.")
    return subjects

def parse_and_add_subject(subject_list, row, year, sem):
    if len(row) < 2: return
    code = row[0].strip()
    title = row[1].strip()
    
    # Noise filter
    if not code or len(code) < 2: return
    if "TOTAL" in code.upper() or "COURSE" in code.upper(): return
    if "EXIT POINT" in code.upper() or "PREREQUISITE" in code.upper(): return
    if len(title) < 4: return

    # Units extraction
    try:
        lec = 0.0
        lab = 0.0
        if len(row) > 2 and row[2] and row[2].replace('.', '', 1).isdigit():
            lec = float(row[2])
        if len(row) > 3 and row[3] and row[3].replace('.', '', 1).isdigit():
            lab = float(row[3])
        
        if lec == 0 and lab == 0 and len(row) > 2 and row[2].isdigit():
             units = int(row[2])
        else:
             units = int(lec + lab)
    except:
        units = 0
        
    prereq = row[4].replace('\n', ' ').strip() if len(row) > 4 else ""
    
    subject_list.append({
        "year_level": year,
        "semester": sem,
        "code": code.upper(),
        "description": title.replace('\n', ' ').strip(),
        "units": units,
        "is_exit_point": False,
        "prerequisite": prereq
    })

@curriculum_bp.route("/curriculum/parse", methods=["POST"])
def parse_curriculum():
    if 'file' not in request.files:
        return jsonify({"detail": "No file part"}), 400
    
    file = request.files['file']
    course_id = request.form.get('course_id')
    if not file or file.filename == '':
        return jsonify({"detail": "No selected file"}), 400

    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        file.save(tmp_path)
            
        try:
            subjects = parse_curriculum_pdf(tmp_path)
            if not subjects:
                 return jsonify({"detail": "No subjects found. Please check PDF layout."}), 400
        finally:
            if os.path.exists(tmp_path):
                try: os.remove(tmp_path)
                except: pass

        return jsonify(subjects)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return jsonify({"detail": str(e)}), 500

@curriculum_bp.route("/curriculum/<int:course_id>", methods=["POST"])
def save_curriculum(course_id: int):
    payload = request.get_json() or []
    session = SessionLocal()
    try:
        session.query(models.CurriculumSubject).filter(
            models.CurriculumSubject.course_id == course_id
        ).delete()
        
        for item in payload:
            subject = models.CurriculumSubject(
                course_id=course_id,
                year_level=item.get('year_level'),
                semester=item.get('semester'),
                code=item.get('code'),
                description=item.get('description'),
                units=item.get('units', 0),
                prerequisite=item.get('prerequisite'),
                is_exit_point=item.get('is_exit_point', False),
                extra_info=item.get('extra_info')
            )
            session.add(subject)
        session.commit()
        return jsonify({"detail": "Saved successfully", "count": len(payload)}), 201
    except SQLAlchemyError as e:
        session.rollback()
        return jsonify({"detail": str(e)}), 500
    finally:
        session.close()

@curriculum_bp.route("/curriculum/<int:course_id>", methods=["GET"])
def get_curriculum(course_id: int):
    session = SessionLocal()
    try:
        subjects = session.query(models.CurriculumSubject).filter(
            models.CurriculumSubject.course_id == course_id
        ).order_by(
            models.CurriculumSubject.year_level, 
            models.CurriculumSubject.semester,
            models.CurriculumSubject.id
        ).all()
        
        result = []
        for s in subjects:
            result.append({
                "id": s.id,
                "year_level": s.year_level,
                "semester": s.semester,
                "code": s.code,
                "description": s.description,
                "units": s.units,
                "prerequisite": s.prerequisite,
                "is_exit_point": s.is_exit_point,
                "extra_info": s.extra_info
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"detail": str(e)}), 500
    finally:
        session.close()

@curriculum_bp.route("/curriculum/<int:course_id>", methods=["DELETE"])
def delete_curriculum(course_id: int):
    session = SessionLocal()
    try:
        session.query(models.CurriculumSubject).filter(
            models.CurriculumSubject.course_id == course_id
        ).delete()
        session.commit()
        return jsonify({"detail": "Deleted successfully"})
    except Exception as e:
        session.rollback()
        return jsonify({"detail": str(e)}), 500
    finally:
        session.close()
