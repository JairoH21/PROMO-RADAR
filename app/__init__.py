from flask import Flask

def create_app():
    app = Flask(__name__)

    @app.route("/")
    def home():
        return """
        <h1>🔥 Promo Radar</h1>
        <h2>Sistema funcionando!</h2>
        <p>Estamos prontos para buscar as melhores promoções.</p>
        """

    return app
