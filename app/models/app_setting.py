from app.extensions import db


class AppSetting(db.Model):
    __tablename__ = "app_settings"

    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(191), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<AppSetting {self.setting_key}={self.value}>"
