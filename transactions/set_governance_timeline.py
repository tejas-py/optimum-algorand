import time
from algosdk.atomic_transaction_composer import AtomicTransactionComposer, AccountTransactionSigner
from algosdk import encoding
import API_Controller
from contract.application import Optimum
from beaker import client

# Connect to Algod-Client in Testnet Network
algod_client = API_Controller.connection.algo_conn("testnet")
# Create a Dummy Signer to fetch the transaction object
ACCOUNT_SIGNER = AccountTransactionSigner("a" * 32)


def main(app_id, admin_wallet_address, asset_id):
    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    # set the arguments
    now = round(time.time())
    # timelines for an algorand governance (test values)
    period_start = now + (1 * 60)
    reward_distribution = now + (2 * 60)
    registration_end = now + (3 * 60)
    period_end = now + (18 * 24 * 60 * 60)  # start + 18 days (~2 weeks)

    # set the params
    params = algod_client.suggested_params()

    # build the transaction
    atc = AtomicTransactionComposer()
    app_client.add_method_call(
        atc=atc,
        method=Optimum.set_governance_timelines,
        sender=admin_wallet_address,
        suggested_params=params,
        foreign_assets=[asset_id],
        global_reward_distribution=reward_distribution,
        global_registration_end=registration_end,
        period_start=period_start,
        period_end=period_end
    )

    # extract the transaction from the ATC
    txn_details = atc.txn_list[0]
    result = [{'txn': encoding.msgpack_encode(txn_details.txn)}]

    return result

