from algosdk.atomic_transaction_composer import AtomicTransactionComposer, AccountTransactionSigner
from algosdk import encoding
from connection import algo_conn
from application import Optimum
from beaker import client

# Connect to Algod-Client in Testnet Network
algod_client = algo_conn("testnet")
# Create a Dummy Signer to fetch the transaction object
ACCOUNT_SIGNER = AccountTransactionSigner("a" * 32)


def main(admin_wallet, app_id):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    # set the params
    params = algod_client.suggested_params()

    reward_rate_number = 2
    reward_rate_decimals = 10  # i.e apy = 2/10 = 0.2%

    # build the transaction
    atc = AtomicTransactionComposer()
    app_client.add_method_call(
        atc=atc,
        method=Optimum.set_governance_reward_rate,
        sender=admin_wallet,
        suggested_params=params,
        reward_rate_number=reward_rate_number,
        reward_rate_decimals=reward_rate_decimals
    )

    # extract the transaction from the ATC
    txn_details = atc.txn_list[0]
    result = [{'txn': encoding.msgpack_encode(txn_details.txn)}]

    return result
