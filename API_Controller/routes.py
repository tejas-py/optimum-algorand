from flask import Flask, redirect
from flask_cors import CORS
import API_Controller.Controller

# defining the flask app and setting up cors
app = Flask(__name__)
cors = CORS(app, resources={
    r"/*": {"origin": "*"}
})

# Global Constant, Optimum App Id and Optimum Asset Id
opt_app_id = ""
opt_asa_id = ""


# home page
@app.route('/')
def home_page():
    return redirect("https://optimumstaking.finance", code=302)


@app.post('/blockchain/deposit')
def deposit_route():
    return API_Controller.Controller.deposit.deposit(opt_app_id, opt_asa_id)


@app.post('/blockchain/deposit/fund_custodian_wallets')
def fund_custodian_wallets_route():
    return API_Controller.Controller.deposit.fund_custodian_wallets(opt_app_id)


@app.post('/blockchain/disperse_lottery/vrf_randomizer')
def disperse_lottery_route():
    return API_Controller.Controller.disperse_lottery.get_random_value(opt_app_id)


@app.post('/blockchain/disperse_lottery/get_winner_and_reward_amt')
def get_winner_and_reward_amt_route():
    return API_Controller.Controller.disperse_lottery.get_winner_and_reward_amt(opt_app_id)


@app.post('/blockchain/whitelist_account')
def whitelist_account_route():
    return API_Controller.Controller.get_accts_and_whitelist.whitelist_account(opt_app_id)


@app.post('/blockchain/register')
def register_by_custodial_wallets_route():
    return API_Controller.Controller.register.register_by_custodial_wallets(opt_app_id)


@app.post('/blockchain/set_governance_reward_rate')
def reward_rate_route():
    return API_Controller.Controller.set_governance_reward_rate.reward_rate(opt_app_id)



# running the API
if __name__ == "__main__":
    app.run(debug=True, port=3000)
