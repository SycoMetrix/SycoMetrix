"""SycoMetrix Flask application."""

from flask import Flask

from sycometrix.config import Config, DevelopmentConfig
from sycometrix.extensions import db, migrate

def create_app(config_class: type[Config] = DevelopmentConfig) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.json.sort_keys = False
    db.init_app(app)
    migrate.init_app(app, db)

    from sycometrix import models  # noqa: F401  (registers models with SQLAlchemy)
    from sycometrix.api import api_bp
    from sycometrix.cli import llm_ping, run_experiment, seed_models

    app.register_blueprint(api_bp, url_prefix="/api")
    app.cli.add_command(seed_models)
    app.cli.add_command(llm_ping)
    app.cli.add_command(run_experiment)
    return app
