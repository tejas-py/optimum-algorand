# NOTE: Incomplete, add after all the smart contract functions has been called

from algosdk.atomic_transaction_composer import AtomicTransactionComposer, AccountTransactionSigner
from algosdk import transaction, encoding
from connection import algo_conn
from application import Optimum
from beaker import client

# Connect to Algod-Client
algod_client = algo_conn("testnet")
# Create a Dummy Signer to fetch the transaction object
ACCOUNT_SIGNER = AccountTransactionSigner("a" * 32)


# opt in transaction
def app_optin(app_id, wallet_address):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    params = algod_client.suggested_params()
    params.fee = 1000
    params.flat_fee = True

    # build the transaction
    atc = AtomicTransactionComposer()
    app_client.add_transaction(
        atc=atc,
        txn=transaction.ApplicationOptInTxn(
            wallet_address,
            params,
            app_id
        )
    )

    # extract the transaction from the ATC
    txn_details = atc.txn_list[0]
    result = [{'txn': encoding.msgpack_encode(txn_details.txn)}]

    return result

if __name__ == "__main__":

    app_optin(16265514, "Z7P757RUNGXLTFLFLSYQW3VHVAFWNIEJFY7ZF5B6BMZ6HLYVDXL3JS2QVA")
