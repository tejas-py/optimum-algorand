from flask import request, jsonify
import utils
import transactions


def get_random_value(opt_app_id):

    try:
        # get the details from the payload as json object
        disperse_lottery_payload = request.get_json()
        sender_wallet = disperse_lottery_payload['sender_wallet']
    except Exception as error:
        return jsonify({'message': f'Payload Error! Key Missing: {error}'}), 400

    # Amount required for the function to execute.
    function_transaction_fees = 2000  # One Transaction with one inner transaction

    # Wallet Information
    wallet_info = utils.common_functions.check_balance(sender_wallet, function_transaction_fees)

    # check if the wallet contains balance to execute the transaction
    if wallet_info == "True":
        try:
            txn_object = transactions.Controller.disperse_lottery.get_random_value(opt_app_id, sender_wallet)
            return jsonify(txn_object), 200
        except Exception as error:
            return jsonify({'message': f"Server Error! {error}"}), 500
    elif wallet_info == "False":
        return jsonify({'message': f"Wallet Balance Low, required amount: {function_transaction_fees}"}), 400

    else:
        return wallet_info


def get_winner_and_reward_amt(opt_app_id):

    try:
        # get the details from the payload as json object
        disperse_lottery_payload = request.get_json()
        vrf_random_number = disperse_lottery_payload['vrf_random_number']
    except Exception as error:
        return jsonify({'message': f'Payload Error! Key Missing: {error}'}), 400

    try:
        value = transactions.Controller.disperse_lottery.get_winner_and_reward_amt(opt_app_id, vrf_random_number)
        return jsonify(value), 200
    except Exception as error:
        return jsonify({'message': f"Server Error! {error}"}), 500
