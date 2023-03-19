from flask import request, jsonify
import utils
import transactions


def get_custodial_wallets_with_extra_bal(opt_app_id):

    try:
        return_value = transactions.Controller.withdraw_rewards.get_custodial_wallets_with_extra_bal(opt_app_id)
        return jsonify(return_value), 200
    except Exception as error:
        return jsonify({'message': f"Server Error! {error}"}), 500


def withdraw_rewards_from_custodial_wallets(opt_app_id):

    try:
        # get the details from the payload as json object
        withdraw_reward_payload = request.get_json()
        sender_wallet = withdraw_reward_payload['sender_wallet']
        custodial_wallets = withdraw_reward_payload['custodial_wallets']
        amt_to_withdraw = int(withdraw_reward_payload['amt_to_withdraw'])
    except Exception as error:
        return jsonify({'message': f'Payload Error! Key Missing: {error}'}), 400

    # Amount required for the function to execute.
    function_transaction_fees = 1000  # Unknown number of transaction will be executed, so will take 1000

    # Wallet Information
    wallet_info = utils.common_functions.check_balance(sender_wallet, function_transaction_fees)

    # check if the wallet contains balance to execute the transaction
    if wallet_info == "True":
        try:
            txn_object = transactions.Controller.withdraw_rewards.withdraw_rewards_from_custodial_wallets(
                sender_wallet,
                opt_app_id,
                custodial_wallets,
                amt_to_withdraw
            )
            return jsonify(txn_object), 200
        except Exception as error:
            return jsonify({'message': f"Server Error! {error}"}), 500
    elif wallet_info == "False":
        return jsonify({'message': f"Wallet Balance Low, required amount: {1000}"}), 400
    else:
        return wallet_info
