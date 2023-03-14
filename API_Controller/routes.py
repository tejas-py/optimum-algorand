from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
from os import path, stat
import utils
import transactions

# defining the flask app and setting up cors
app = Flask(__name__)
cors = CORS(app, resources={
    r"/*": {"origin": "*"}
})


# home page
@app.route('/')
def home_page():
    return redirect("https://optimumstaking.finance", code=302)


# running the API
if __name__ == "__main__":
    app.run(debug=True, port=3000)
