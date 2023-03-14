from algosdk import atomic_transaction_composer, logic
import API_Controller
from contract.application import Optimum
from beaker import client

# Connect to Algod-Client and Indexer-Client in Testnet Network
algod_client = API_Controller.connection.algo_conn("testnet")
indexer_client = API_Controller.connection.connect_indexer("testnet")
# Create a Dummy Signer to fetch the transaction object
ACCOUNT_SIGNER = atomic_transaction_composer.AccountTransactionSigner("a" * 32)


# fetch the custodian wallets
def get_custodian_wallets(app_id, config):
    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    # search the indexer for the result
    res = indexer_client.accounts(
        app_id=app_id,
        auth_addr=logic.get_application_address(app_id)
    )

    custodian_wallets = []
    for account in res.accounts:
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
            custodian_wallets.append(account.address)

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
