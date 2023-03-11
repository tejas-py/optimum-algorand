from algosdk import account, logic, encoding, atomic_transaction_composer
from connection import algo_conn, connect_indexer
from application import Optimum
from beaker import client

# Connect to Algod-Client in Testnet Network
algod_client = algo_conn("testnet")
indexer_client = connect_indexer("testnet")
# Create a Dummy Signer to fetch the transaction object
ACCOUNT_SIGNER = atomic_transaction_composer.AccountTransactionSigner("a" * 32)


# Generate 'n' number of accounts
def gen_accounts(n):
    accounts = []
    for i in range(n):
        private_key, account_address = account.generate_account()
        wallet = {'account_address': account_address, "private_key": private_key}
        accounts.append(wallet)

    return accounts


def whitelist_account(wallet_address, app_id):

    # create the application client
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    # Opt-in to the Optimum application first
    optin_txn = app_client.opt_in()
    print("Opt-in Transaction id:", optin_txn)

    # set the params
    params = algod_client.suggested_params()

    # call the contract to whitelist
    atc = atomic_transaction_composer.AtomicTransactionComposer()
    app_client.add_method_call(
        atc=atc,
        method=Optimum.whitelist_account,
        sender=wallet_address,
        suggested_params=params,
        rekey_to=logic.get_application_address(app_id)
    )

    # extract the transaction from the ATC
    txn_details = atc.txn_list[0]
    result = [{'txn': encoding.msgpack_encode(txn_details.txn)}]

    return result
