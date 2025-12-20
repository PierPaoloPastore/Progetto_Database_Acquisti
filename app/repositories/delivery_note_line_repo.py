"""
Repository per DeliveryNoteLine.
"""
from typing import List, Optional

from app.models import DeliveryNoteLine
from app.repositories.base import SqlAlchemyRepository


class DeliveryNoteLineRepository(SqlAlchemyRepository[DeliveryNoteLine]):
    def __init__(self, session):
        super().__init__(session, DeliveryNoteLine)

    def list_by_delivery_note(self, delivery_note_id: int) -> List[DeliveryNoteLine]:
        return (
            self.session.query(DeliveryNoteLine)
            .filter(DeliveryNoteLine.delivery_note_id == delivery_note_id)
            .order_by(DeliveryNoteLine.line_number.asc())
            .all()
        )

    def get_by_id(self, line_id: int) -> Optional[DeliveryNoteLine]:
        return self.session.query(DeliveryNoteLine).get(line_id)
