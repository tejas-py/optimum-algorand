from flask import request, jsonify
import utils


def app_optin(algod_client, opt_app_id):

    try:
        # get the details from the payload as json object
        app_optin_payload = request.get_json()
        sender_wallet = app_optin_payload['sender_wallet']
    except Exception as error:
        return jsonify({'message': f'Payload Error! Key Missing: {error}'}), 400

    # Amount required for the function to execute.
    function_transaction_fees = 1000  # One transaction of fees 1000

    # Wallet Information
    wallet_info = utils.common_functions.check_balance(algod_client, sender_wallet, function_transaction_fees)

    # check if the wallet contains balance to execute the transaction
    if wallet_info == "True":
        try:
            txn_object = utils.common_txn.app_opt_in(algod_client, sender_wallet, opt_app_id)
            return jsonify(txn_object), 200
        except Exception as error:
            return jsonify({'message': f"Server Error! {error}"}), 500
    elif wallet_info == "False":
        return jsonify({'message': f"Wallet Balance Low, required amount: {1000}"}), 400
    else:
        return wallet_info


def asset_optin(algod_client, opt_asset_id):

    try:
        # get the details from the payload as json object
        asa_optin_payload = request.get_json()
        sender_wallet = asa_optin_payload['sender_wallet']
    except Exception as error:
        return jsonify({'message': f'Payload Error! Key Missing: {error}'}), 400

    # Amount required for the function to execute.
    function_transaction_fees = 1000  # One transaction of fees 1000

    # Wallet Information
    wallet_info = utils.common_functions.check_balance(algod_client, sender_wallet, function_transaction_fees)

    # check if the wallet contains balance to execute the transaction
    if wallet_info == "True":
        try:
            txn_object = utils.common_txn.asset_opt_in(algod_client, sender_wallet, opt_asset_id)
            return jsonify(txn_object), 200
        except Exception as error:
            return jsonify({'message': f"Server Error! {error}"}), 500
    elif wallet_info == "False":
        return jsonify({'message': f"Wallet Balance Low, required amount: {1000}"}), 400
    else:
        return wallet_info
