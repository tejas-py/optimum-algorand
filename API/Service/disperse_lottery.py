from flask import request, jsonify
import utils
import transactions


def get_random_value(algod_client, opt_app_id):

    try:
        # get the details from the payload as json object
        disperse_lottery_payload = request.get_json()
        sender_wallet = disperse_lottery_payload['sender_wallet']
    except Exception as error:
        return jsonify({'message': f'Payload Error! Key Missing: {error}'}), 400

    # Amount required for the function to execute.
    function_transaction_fees = 2000  # One Transaction with one inner transaction

    # Wallet Information
    wallet_info = utils.common_functions.check_balance(algod_client, sender_wallet, function_transaction_fees)

    # check if the wallet contains balance to execute the transaction
    if wallet_info == "True":
        try:
            txn_object = transactions.Controller.disperse_lottery.get_random_value(algod_client, opt_app_id, sender_wallet)
            return jsonify(txn_object), 200
        except Exception as error:
            return jsonify({'message': f"Server Error! {error}"}), 500
    elif wallet_info == "False":
        return jsonify({'message': f"Wallet Balance Low, required amount: {function_transaction_fees}"}), 400

    else:
        return wallet_info


def get_winner_and_reward_amt(algod_client, indexer_client, opt_app_id):

    try:
        # get the details from the payload as json object
        disperse_lottery_payload = request.get_json()
        vrf_random_number = disperse_lottery_payload['vrf_random_number']
    except Exception as error:
        return jsonify({'message': f'Payload Error! Key Missing: {error}'}), 400

    try:
        value = transactions.Controller.disperse_lottery.get_winner_and_reward_amt(algod_client, indexer_client, opt_app_id, vrf_random_number)
        return jsonify(value), 200
    except Exception as error:
        return jsonify({'message': f"Server Error! {error}"}), 500


def reveal_vrf_number(indexer_client):

    try:
        # get the details from the payload as json object
        disperse_lottery_payload = request.get_json()
        vrf_txn_id = disperse_lottery_payload['vrf_txn_id']
    except Exception as error:
        return jsonify({'message': f'Payload Error! Key Missing: {error}'}), 400

    try:
        value = transactions.Controller.disperse_lottery.reveal_vrf_number(indexer_client, vrf_txn_id)
        return jsonify(value), 200
    except Exception as error:
        return jsonify({'message': f"Server Error! {error}"}), 500


def send_vrf_number_to_admin(algod_client):

    try:
        # get the details from the payload as json object
        disperse_lottery_payload = request.get_json()
        admin_wallet = disperse_lottery_payload['admin_wallet']
        vrf_number = disperse_lottery_payload['vrf_number']

    except Exception as error:
        return jsonify({'message': f'Payload Error! Key Missing: {error}'}), 400

    try:
        value = transactions.Controller.disperse_lottery.send_vrf_number_to_admin(algod_client, admin_wallet, vrf_number)
        return jsonify(value), 200
    except Exception as error:
        return jsonify({'message': f"Server Error! {error}"}), 500
