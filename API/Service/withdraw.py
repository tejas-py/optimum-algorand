from flask import request, jsonify
import utils
import transactions


def withdraw(opt_app_id, opt_asa_id):
    try:
        # get the details from the payload as json object
        withdraw_payload = request.get_json()
        sender_wallet = withdraw_payload['sender_wallet']
        fee_address = withdraw_payload['fee_address']
        opt_amt = int(withdraw_payload['opt_amt'])
    except Exception as error:
        return jsonify({'message': f'Payload Error! Key Missing: {error}'}), 400

    # Amount required for the function to execute.
    function_transaction_fees = 1000 + 3000  # two Transaction of fees 1000, and 3000

    # Wallet Information
    wallet_info = utils.common_functions.check_balance(sender_wallet, function_transaction_fees)

    # check if the wallet contains balance to execute the transaction
    if wallet_info == "True":
        try:
            txn_object = transactions.Controller.withdraw.withdraw(sender_wallet, fee_address,
                                                                   opt_app_id, opt_asa_id, opt_amt)
            return jsonify(txn_object), 200
        except Exception as error:
            return jsonify({'message': f"Server Error! {error}"}), 500
    elif wallet_info == "False":
        return jsonify({'message': f"Wallet Balance Low, required amount: {function_transaction_fees}"}), 400

    else:
        return wallet_info


def compute_algo_withdraw_amt_from_opt(opt_app_id, opt_asa_id, opt_amt):
    try:
        return_value = transactions.Controller.withdraw.compute_algo_withdraw_amt_from_opt(opt_app_id, opt_asa_id,
                                                                                           opt_amt)
        return jsonify(return_value), 200
    except Exception as error:
        return jsonify({'message': f"Server Error! {error}"}), 500


def withdraw_from_custodial_wallets(opt_app_id):
    try:
        # get the details from the payload as json object
        withdraw_payload = request.get_json()
        sender_wallet = withdraw_payload['sender_wallet']
        withdraw_amt = int(withdraw_payload['withdraw_amt'])
    except Exception as error:
        return jsonify({'message': f'Payload Error! Key Missing: {error}'}), 400

    # Amount required for the function to execute.
    function_transaction_fees = 1000  # Unknown number of transaction will be executed, so will take 1000

    # Wallet Information
    wallet_info = utils.common_functions.check_balance(sender_wallet, function_transaction_fees)

    # check if the wallet contains balance to execute the transaction
    if wallet_info == "True":
        try:
            txn_object = transactions.Controller.withdraw.withdraw_from_custodial_wallets(sender_wallet, opt_app_id,
                                                                                          withdraw_amt)
            return jsonify(txn_object), 200
        except Exception as error:
            return jsonify({'message': f"Server Error! {error}"}), 500
    elif wallet_info == "False":
        return jsonify({'message': f"Wallet Balance Low, required amount: {1000}"}), 400
    else:
        return wallet_info
