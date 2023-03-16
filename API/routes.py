from flask import Flask, redirect
from flask_cors import CORS
from API import Service

# defining the flask app and setting up cors
app = Flask(__name__)
cors = CORS(app, resources={
    r"/*": {"origin": "*"}
})

# Global Constant, Optimum App id and Optimum Asset id
opt_app_id = 165037939
opt_asa_id = 75919707


# home page
@app.route('/')
def home_page():
    return redirect("https://optimumstaking.finance", code=302)


# 404 error handling
@app.errorhandler(404)
def page_not_found(e):
    return f"<title>Page Not Found</title><h1>404 Not Found</h1><p>{e}</p>", 404


@app.post('/blockchain/optin/application')
def application_optin_route():
    return Service.common_txn.app_optin(opt_app_id)


@app.post('/blockchain/optin/asset')
def asset_optin_route():
    return Service.common_txn.asset_optin(opt_asa_id)


@app.post('/blockchain/deposit')
def deposit_route():
    return Service.deposit.deposit(opt_app_id, opt_asa_id)


@app.post('/blockchain/deposit/fund_custodian_wallets')
def fund_custodian_wallets_route():
    return Service.deposit.fund_custodian_wallets(opt_app_id)


@app.post('/blockchain/disperse_lottery/vrf_randomizer')
def disperse_lottery_route():
    return Service.disperse_lottery.get_random_value(opt_app_id)


@app.post('/blockchain/disperse_lottery/get_winner_and_reward_amt')
def get_winner_and_reward_amt_route():
    return Service.disperse_lottery.get_winner_and_reward_amt(opt_app_id)


@app.post('/blockchain/whitelist_account')
def whitelist_account_route():
    return Service.get_accts_and_whitelist.whitelist_account(opt_app_id)


@app.post('/blockchain/register')
def register_by_custodial_wallets_route():
    return Service.register.register_by_custodial_wallets(opt_app_id)


@app.post('/blockchain/set_governance_reward_rate')
def reward_rate_route():
    return Service.set_governance_reward_rate.reward_rate(opt_app_id)


@app.post('/blockchain/vote')
def vote_route():
    return Service.vote.vote_by_custodial_wallet(opt_app_id)


@app.post('/blockchain/withdraw')
def withdraw_route():
    return Service.withdraw.withdraw(opt_app_id, opt_asa_id)


@app.get('/blockchain/withdraw/opt_to_algo_conversion/<int:opt_amt>')
def compute_algo_withdraw_amt_from_opt_route(opt_amt):
    return Service.withdraw.compute_algo_withdraw_amt_from_opt(opt_app_id, opt_asa_id, opt_amt)


@app.post('/blockchain/withdraw/withdraw_from_custodial_wallets')
def withdraw_from_custodial_wallets_route():
    return Service.withdraw.withdraw_from_custodial_wallets(opt_app_id)


@app.get('/blockchain/withdraw_rewards/custodial_wallet_balance')
def get_custodial_wallets_with_extra_bal_route():
    return Service.withdraw_rewards.get_custodial_wallets_with_extra_bal(opt_app_id)


@app.post('/blockchain/withdraw_rewards/withdraw_rewards_from_custodial_wallets')
def withdraw_rewards_from_custodial_wallets_route():
    return Service.withdraw_rewards.withdraw_rewards_from_custodial_wallets(opt_app_id)
