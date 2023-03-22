from flask import request, jsonify
import utils
import transactions


def vote_by_custodial_wallet(algod_client, indexer_client, opt_app_id):

    try:
        # get the details from the payload as json object
        vote_payload = request.get_json()
        sender_wallet = vote_payload['sender_wallet']
        txn_note = vote_payload['txn_note']
        governance_address = vote_payload['governance_address']
    except Exception as error:
        return jsonify({'message': f'Payload Error! Key Missing: {error}'}), 400

    # Amount required for the function to execute.
    function_transaction_fees = 1000  # Unknown number of transaction will be executed, so will take 1000

    # Wallet Information
    wallet_info = utils.common_functions.check_balance(algod_client, sender_wallet, function_transaction_fees)

    # check if the wallet contains balance to execute the transaction
    if wallet_info == "True":
        try:
            txn_object = transactions.Controller.vote.vote_by_custodial_wallet(algod_client, indexer_client, sender_wallet, opt_app_id,
                                                                               governance_address, txn_note)
            return jsonify(txn_object), 200
        except Exception as error:
            return jsonify({'message': f"Server Error! {error}"}), 500
    elif wallet_info == "False":
        return jsonify({'message': f"Wallet Balance Low, required amount: {function_transaction_fees}"}), 400

    else:
        return wallet_info
