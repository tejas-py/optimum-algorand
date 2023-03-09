from algosdk.atomic_transaction_composer import *
from algosdk import transaction, mnemonic, account, encoding
import connection
import application
from beaker import client

# Connect to Algod-Client
algod_client = connection.algo_conn("testnet")
# Create a Dummy Signer to fetch the transaction object
ACCOUNT_SIGNER = AccountTransactionSigner("a" * 32)


def call_vrf(app_id, wallet_address):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=application.Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    params = algod_client.suggested_params()
    params.fee = 2000
    params.flat_fee = True

    # build the transaction
    atc = AtomicTransactionComposer()
    app_client.add_method_call(
        atc=atc,
        method=application.Optimum.VRF,
        sender=wallet_address,
        suggested_params=params,
        foreign_apps=[110096026]
    )

    # extract the transaction from the ATC
    txn_details = atc.txn_list[0]
    result = [{'txn': encoding.msgpack_encode(txn_details.txn)}]

    return result


if __name__ == "__main__":

    call_vrf(16265514, "Z7P757RUNGXLTFLFLSYQW3VHVAFWNIEJFY7ZF5B6BMZ6HLYVDXL3JS2QVA")
