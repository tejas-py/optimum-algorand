from flask import request, jsonify
import utils
import transactions


def reward_rate(algod_client, opt_app_id):

    try:
        # get the details from the payload as json object
        deposit_payload = request.get_json()
        admin_wallet = deposit_payload['admin_wallet']
    except Exception as error:
        return jsonify({'message': f'Payload Error! Key Missing: {error}'}), 400

    # Amount required for the function to execute.
    function_transaction_fees = 1000  # One Transaction of fees 1000

    # Wallet Information
    wallet_info = utils.common_functions.check_balance(algod_client, admin_wallet, function_transaction_fees)

    # check if the wallet contains balance to execute the transaction
    if wallet_info == "True":
        try:
            txn_object = transactions.Controller.set_governance_reward_rate.reward_rate(algod_client, admin_wallet, opt_app_id)
            return jsonify(txn_object), 200
        except Exception as error:
            return jsonify({'message': f"Server Error! {error}"}), 500
    elif wallet_info == "False":
        return jsonify({'message': f"Wallet Balance Low, required amount: {1000}"}), 400
    else:
        return wallet_info
