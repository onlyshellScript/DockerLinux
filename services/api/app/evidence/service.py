from app.extensions import db
from app.evidence.models import Evidence
from app.evidence.storage import get_storage


def create_evidence(work_order_id, uploaded_by_id, evidence_type, file=None, description=None):
    ev = Evidence(
        work_order_id=work_order_id,
        uploaded_by_id=uploaded_by_id,
        evidence_type=evidence_type,
        description=description,
    )
    if file and evidence_type in ("photo", "document"):
        storage = get_storage()
        stored_name, error = storage.save(file, file.filename)
        if error:
            return None, error
        ev.file_name = file.filename
        ev.stored_name = stored_name
        ev.file_type = file.mimetype
        ev.file_size = file.stream.seek(0, 2)
        file.stream.seek(0)
    db.session.add(ev)
    db.session.commit()
    return ev, None


def list_evidences(work_order_id):
    return Evidence.query.filter_by(work_order_id=work_order_id).order_by(Evidence.created_at.desc()).all()


def get_evidence(ev_id):
    return db.session.get(Evidence, ev_id)


def delete_evidence(ev_id):
    ev = db.session.get(Evidence, ev_id)
    if not ev:
        return False
    if ev.stored_name:
        storage = get_storage()
        storage.delete(ev.stored_name)
    db.session.delete(ev)
    db.session.commit()
    return True
