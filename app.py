from chalice import Chalice
from chalicelib import api, prmbot

# Setup
app = Chalice(app_name="state_management")

app.debug = True

# Blueprints confirmed to be fully supported
app.experimental_feature_flags.update(["BLUEPRINTS"])
app.register_blueprint(api.lockapi)
app.register_blueprint(prmbot.prmbot)
