from flask import request, jsonify
import utils
import transactions


def whitelist_account(opt_app_id):

    try:
        # get the details from the payload as json object
        disperse_lottery_payload = request.get_json()
        sender_wallet = disperse_lottery_payload['sender_waller']
    except Exception as error:
        return jsonify({'message': f'Payload Error! Key Missing: {error}'}), 400

    # Amount required for the function to execute.
    function_transaction_fees = 1000  # one Transaction of fees 1000

    # Wallet Information
    wallet_info = utils.common_functions.check_balance(sender_wallet, function_transaction_fees)

    # check if the wallet contains balance to execute the transaction
    if wallet_info == "True":
        try:
            txn_object = transactions.Controller.get_accts_and_whitelist.whitelist_account(sender_wallet, opt_app_id)
            return jsonify(txn_object), 200
        except Exception as error:
            return jsonify({'message': f"Server Error! {error}"}), 500
    elif wallet_info == "False":
        jsonify({'message': f"Wallet Balance Low, required amount: {function_transaction_fees}"}), 400

    else:
        return wallet_info
