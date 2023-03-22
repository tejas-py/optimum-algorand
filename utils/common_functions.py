from algosdk import atomic_transaction_composer, logic
from contract.application import Optimum
from beaker import client
from flask import jsonify
import base64

# Create a Dummy Signer to fetch the transaction object
ACCOUNT_SIGNER = atomic_transaction_composer.AccountTransactionSigner("a" * 32)


# fetch the custodian wallets
def get_custodian_wallets(algod_client, indexer_client, app_id, config):
    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    # search the indexer for the result
    res = indexer_client.accounts(
        application_id=app_id,
        auth_addr=logic.get_application_address(app_id)
    )

    custodian_wallets = []
    for account in res['accounts']:
        local_state = app_client.get_account_state(account=account)
        if local_state == {}:
            continue

        # each wallet must be whitelistest irrespectively
        whitelisted = local_state.get('LOCAL_WHITELISTED')
        should_push = True
        if whitelisted != 1:
            should_push = False
        # check for all keys passed in config, if their values match
        # if anyone doesn't, we don't push that address
        for key in config:
            v = local_state.get(key)
            if v != config[key]:
                should_push = False
                break

        if should_push is True:
            custodian_wallets.append(account['address'])

    return custodian_wallets


# Returns an array with arrays of the given size.
def chunky_array(my_array, chunk_size):
    index = 0
    array_length = len(my_array)
    temp_array = []

    while index < array_length:
        my_chunk = my_array[index:index+chunk_size]
        # Do something if you want with the group
        temp_array.append(my_chunk)
        index += chunk_size

    return temp_array


# check the balance with the amount, if the wallet does not have minimum amount, the function will return false.
def check_balance(algod_client, wallet_address, amt):

    try:
        account_i = algod_client.account_info(wallet_address)
        locked_balance = account_i['min-balance']
        balance = account_i['amount']
        available_balance = balance - locked_balance

        if balance >= amt and available_balance > amt:
            return "True"
        else:
            return "False"
    except Exception as error:
        return jsonify({'message': f"Wallet not found! Error: {error}"}), 400


# Search Indexer for the VRF return number
def random_value_by_vrf(indexer_client, txn_id):
    res = indexer_client.search_transactions(txn_id)
    abi_return_value = res['transactions'][0]['logs'][0]
    decoded_value = base64.b64decode(abi_return_value)[4:]
    vrf_number = int.from_bytes(decoded_value, 'big')

    return vrf_number

