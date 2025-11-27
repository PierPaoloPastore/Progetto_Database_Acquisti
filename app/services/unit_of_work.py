from app.extensions import db


class UnitOfWork:
    def __init__(self):
        self.session = db.session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            try:
                self.session.commit()
            except Exception:
                self.session.rollback()
                raise
        else:
            self.session.rollback()
            return False

        return False
