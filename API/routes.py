from flask import Flask, redirect, request, jsonify
from flask_cors import CORS
from API import Service, connection

# defining the flask app and setting up cors
app = Flask(__name__)
cors = CORS(app, resources={
    r"/*": {"origin": "*"}
})

# define the network
network = "testnet"

# connect to algod-client and Indexer-client
algod_client = connection.algo_conn(network)
indexer_client = connection.connect_indexer(network)

# Global Constant, Optimum App id and Optimum Asset id
global_opt_app_id = {"testnet": 165037939, "mainnet": 996657780}
global_opt_asa_id = {"testnet": 75919707, "mainnet": 996657698}

# current OPT app id and optimum asset id according to network
opt_app_id = global_opt_app_id[network]
opt_asa_id = global_opt_asa_id[network]


# home page
@app.route('/')
def home_page():
    return redirect("https://optimumstaking.finance", code=302)


# 404 error handling
@app.errorhandler(404)
def page_not_found(e):
    return f"<title>Page Not Found</title><h1>404 Not Found</h1><p>{e}</p>", 404


@app.post('/select-node')
def select_node():

    # define the global params
    global network
    global algod_client
    global indexer_client
    global opt_app_id
    global opt_asa_id

    try:

        # get the details from the payload as json object
        payload = request.get_json()
        node = payload['node']

    except Exception as error:
        return jsonify({'message': f'Payload Error! Key Missing: {error}'}), 400

    if node == "testnet" or node == "mainnet" or node == "sandbox":

        # switch the network for the app and asset
        opt_app_id = global_opt_app_id[network]
        opt_asa_id = global_opt_asa_id[network]

        # switch the node for the global
        network = node
        algod_client = connection.algo_conn(network)
        indexer_client = connection.connect_indexer(network)

        return jsonify({'message': f"Successfully selected {network}"}), 200

    else:
        return jsonify({'message': "Please Select the correct node"}), 400


@app.get('/get-node')
def get_node():

    # check if both the clients are running
    try:

        # fetch the current node
        algod_client_address = algod_client.algod_address
        indexer_client_address = indexer_client.indexer_address

        if algod_client_address == "https://mainnet-algorand.api.purestake.io/ps2" and indexer_client_address == "https://mainnet-algorand.api.purestake.io/idx2":
            node_network = "mainnet"

        elif algod_client_address == "https://testnet-algorand.api.purestake.io/ps2" and indexer_client_address == "https://testnet-algorand.api.purestake.io/idx2":
            node_network = "testnet"

        elif algod_client_address == "http://localhost:4001" and indexer_client_address == "http://localhost:8980":
            node_network = "sandbox"

        else:
            return jsonify({'message': "Node is not selected, please select the node."}), 500

        # fetch the node details
        node_details = {
            'message': {
                "OPT Application-id": opt_app_id,
                "OPT Asset-id": opt_asa_id,
                'node': node_network,
                'algod': {'status': algod_client.status(), 'health': algod_client.health()},
                'indexer': {'health': indexer_client.health()},
            }
        }

        return jsonify(node_details), 200

    except Exception as error:
        return jsonify({'message': f"Algod Client and Indexer Client Down! Node: {network}, Error {error}"}), 500


@app.post('/blockchain/optin/application')
def application_optin_route():
    return Service.common_txn.app_optin(algod_client, opt_app_id)


@app.post('/blockchain/optin/asset')
def asset_optin_route():
    return Service.common_txn.asset_optin(algod_client, opt_asa_id)


@app.post('/blockchain/deposit')
def deposit_route():
    return Service.deposit.deposit(algod_client, opt_app_id, opt_asa_id)


@app.post('/blockchain/deposit/fund_custodian_wallets')
def fund_custodian_wallets_route():
    return Service.deposit.fund_custodian_wallets(algod_client, indexer_client, opt_app_id)


@app.post('/blockchain/disperse_lottery/vrf_randomizer')
def disperse_lottery_route():
    return Service.disperse_lottery.get_random_value(algod_client, opt_app_id)


@app.post('/blockchain/disperse_lottery/vrf_randomizer/reveal_vrf_number')
def reveal_vrf_number_route():
    return Service.disperse_lottery.reveal_vrf_number(indexer_client)


@app.post('/blockchain/disperse_lottery/vrf_randomizer/send_vrf_number_to_admin')
def send_vrf_number_to_admin_route():
    return Service.disperse_lottery.send_vrf_number_to_admin(algod_client)


@app.post('/blockchain/disperse_lottery/get_winner_and_reward_amt')
def get_winner_and_reward_amt_route():
    return Service.disperse_lottery.get_winner_and_reward_amt(algod_client, indexer_client, opt_app_id)


@app.post('/blockchain/whitelist_account')
def whitelist_account_route():
    return Service.get_accts_and_whitelist.whitelist_account(algod_client, opt_app_id)


@app.post('/blockchain/register')
def register_by_custodial_wallets_route():
    return Service.register.register_by_custodial_wallets(algod_client, indexer_client, opt_app_id)


@app.post('/blockchain/set_governance_reward_rate')
def reward_rate_route():
    return Service.set_governance_reward_rate.reward_rate(algod_client, opt_app_id)


@app.post('/blockchain/vote')
def vote_route():
    return Service.vote.vote_by_custodial_wallet(algod_client, indexer_client, opt_app_id)


@app.post('/blockchain/withdraw')
def withdraw_route():
    return Service.withdraw.withdraw(algod_client, opt_app_id, opt_asa_id)


@app.get('/blockchain/withdraw/opt_to_algo_conversion/<int:opt_amt>')
def compute_algo_withdraw_amt_from_opt_route(opt_amt):
    return Service.withdraw.compute_algo_withdraw_amt_from_opt(algod_client, indexer_client, opt_app_id, opt_asa_id, opt_amt)


@app.post('/blockchain/withdraw/withdraw_from_custodial_wallets')
def withdraw_from_custodial_wallets_route():
    return Service.withdraw.withdraw_from_custodial_wallets(algod_client, indexer_client, opt_app_id)


@app.get('/blockchain/withdraw_rewards/custodial_wallet_balance')
def get_custodial_wallets_with_extra_bal_route():
    return Service.withdraw_rewards.get_custodial_wallets_with_extra_bal(algod_client, indexer_client, opt_app_id)


@app.post('/blockchain/withdraw_rewards/withdraw_rewards_from_custodial_wallets')
def withdraw_rewards_from_custodial_wallets_route():
    return Service.withdraw_rewards.withdraw_rewards_from_custodial_wallets(algod_client, opt_app_id)


@app.post('/blockchain/total_distributed_opt')
def total_distributed_opt_route():
    return Service.withdraw_rewards.withdraw_rewards_from_custodial_wallets(algod_client, opt_app_id)
