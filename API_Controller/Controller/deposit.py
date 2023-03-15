from flask import request, jsonify
import utils
import transactions


def deposit(opt_app_id, opt_asa_id):

    try:
        # get the details from the payload as json object
        deposit_payload = request.get_json()
        sender_wallet = deposit_payload['sender_waller']
        algo_amt = int(deposit_payload['algo_amt'])
    except Exception as error:
        return jsonify({'message': f'Payload Error! Key Missing: {error}'}), 400

    # Amount required for the function to execute.
    function_transaction_fees = 1000+2000  # two Transaction of fees 1000, and 2000
    function_required_amount = algo_amt + function_transaction_fees

    # Wallet Information
    wallet_info = utils.common_functions.check_balance(sender_wallet, function_transaction_fees)

    # check if the wallet contains balance to execute the transaction
    if wallet_info == "True":
        try:
            txn_object = transactions.run.deposit.deposit(sender_wallet, opt_app_id, opt_asa_id, algo_amt)
            return jsonify(txn_object), 200
        except Exception as error:
            return jsonify({'message': f"Server Error! {error}"}), 500
    elif wallet_info == "False":
        jsonify({'message': f"Wallet Balance Low, required amount: {function_required_amount}"}), 400

    else:
        return wallet_info


def fund_custodian_wallets(opt_app_id):

    try:
        # get the details from the payload as json object
        deposit_payload = request.get_json()
        sender_wallet = deposit_payload['sender_waller']
        deposit_amt = int(deposit_payload['deposit_amt'])
    except Exception as error:
        return jsonify({'message': f'Payload Error! Key Missing: {error}'}), 400

    # Amount required for the function to execute.
    function_transaction_fees = 1000  # Unknown number of transaction will be executed, so will take 1000

    # Wallet Information
    wallet_info = utils.common_functions.check_balance(sender_wallet, function_transaction_fees)

    # check if the wallet contains balance to execute the transaction
    if wallet_info == "True":
        try:
            txn_object = transactions.run.deposit.fund_custodian_wallets(sender_wallet, opt_app_id, deposit_amt)
            return jsonify(txn_object), 200
        except Exception as error:
            return jsonify({'message': f"Server Error! {error}"}), 500
    elif wallet_info == "False":
        jsonify({'message': f"Wallet Balance Low, required amount: {1000}"}), 400
    else:
        return wallet_info
