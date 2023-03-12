from algosdk import encoding, atomic_transaction_composer, transaction, logic
from connection import algo_conn, connect_indexer
from application import Optimum
from beaker import client
from utils  import common_functions

# Connect to Algod-Client and Indexer-Client in Testnet Network
algod_client = algo_conn("testnet")
indexer_client = connect_indexer("testnet")
# Create a Dummy Signer to fetch the transaction object
ACCOUNT_SIGNER = atomic_transaction_composer.AccountTransactionSigner("a" * 32)


def deposit(sender_wallet, app_id, asset_id, algo_amt):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    # deposit ALGO to the contract, receive OPT
    atc = atomic_transaction_composer.AtomicTransactionComposer()

    # Transaction 1: Pay algos to smart contract
    params_txn1 = algod_client.suggested_params()
    app_client.add_transaction(
        atc=atc,
        txn=transaction.PaymentTxn(
            sender=sender_wallet,
            sp=params_txn1,
            receiver=logic.get_application_address(app_id),
            amt=algo_amt
        )
    )

    # Transaction 2: Receive OPT, call the Optimum Application
    params_txn2 = algod_client.suggested_params()
    params_txn2.fee = 2000
    app_client.add_method_call(
        atc=atc,
        method=Optimum.exchange,
        sender=sender_wallet,
        suggested_params=params_txn2,
        foreign_assets=[asset_id]
    )

    # fetch the transaction objects
    txn_1 = atc.txn_list[0]
    txn_2 = atc.txn_list[1]

    # Group Transactions
    print("Grouping transactions...")
    group_id = transaction.calculate_group_id([txn_1, txn_2])
    print("...computed groupId: ", group_id)
    txn_1.group = group_id
    txn_2.group = group_id

    txn_grp = [{'txn': encoding.msgpack_encode(txn_1)},
               {'txn': encoding.msgpack_encode(txn_2)}]

    return txn_grp


# Find and fund custodial wallets with 10000 ALGO increments.
# Returns if enough wallets are not available.
# NOTE: deposit amount is in microAlgos
def fund_custodian_wallets(sender_wallet, app_id, deposit_amt):

    # extract custodial wallets from indexer, which we will fund
    custodial_wallets_orig = common_functions.get_custodian_wallets(app_id, {'deposited': 0})

    req_wallets = int(deposit_amt/10000e6)
    if len(custodial_wallets_orig) < req_wallets:
        return {'message': f"Not enough wallets to fund."
                           f"Required ${req_wallets} but got ${custodial_wallets_orig.length}."
                           f"Please generate more accounts"}

    # we only get address we need
    custodial_wallets = custodial_wallets_orig[0:req_wallets]

    # split whole custodial wallets array into chunks of 4
    # as max 4 accounts can be passed in a tx group.
    txn_account_array = common_functions.chunky_array(custodial_wallets, 4)

    # create a for loop for transaction objects
    txn_array = []
    j = 0
    for i in range(0, req_wallets, 4):

        j += 1
