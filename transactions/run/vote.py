from algosdk import encoding, atomic_transaction_composer, transaction
import API_Controller
from contract.application import Optimum
from beaker import client
import utils

# Connect to Algod-Client and Indexer-Client in Testnet Network
algod_client = API_Controller.connection.algo_conn("testnet")
# Create a Dummy Signer to fetch the transaction object
ACCOUNT_SIGNER = atomic_transaction_composer.AccountTransactionSigner("a" * 32)


# Find and vote by each custodial wallets (which haven't voted before) for algorand governance.
def vote_by_custodial_wallet(sender_wallet, app_id, governance_address, memo):

    # Create  an app client for our app
    app_client = client.ApplicationClient(
        client=algod_client, app=Optimum(), app_id=app_id, signer=ACCOUNT_SIGNER
    )

    # extract custodial wallets from indexer, which we will fund
    custodial_wallets = utils.common_functions.get_custodian_wallets(app_id, {"registered": 1, "voted": 0})

    # split whole custodial wallets array into chunks of 3
    # as max 4 accounts can be passed in a tx group, and
    # we need the last one as the governance address
    txn_account_array = utils.common_functions.chunky_array(custodial_wallets, 3)

    # let's make the transaction objects
    txn_array = []
    j = 0

    for i in range(0, len(custodial_wallets), 3):
        # make params for each transaction
        params = algod_client.suggested_params()
        params.fee = 1000 * (len(txn_account_array[j]) if txn_account_array[j] else 0)
        # make the txn object
        atc = atomic_transaction_composer.AtomicTransactionComposer()
        app_client.add_method_call(
            atc=atc,
            method=Optimum.vote_by_custodial_wallets,
            sender=sender_wallet,
            accounts=[txn_account_array[j], governance_address],
            txn_note=memo
        )
        # push the txn object into the transaction array
        txn_array.append(atc.txn_list[0])
        j += 1

    # Assemble the transactions in group of 16, and pass return the transaction object
    txn_groups = utils.common_functions.chunky_array(txn_array, 16)

    # Assign group id to the group transactions
    group_id_transactions = []
    for txn_group in txn_groups:
        txns = transaction.assign_group_id(txn_group)
        group_id_transactions.append(txns)

    # Encode the transactions to return it
    encoded_txns = []
    for single_group_txn in group_id_transactions:
        txn_grp = []
        for single_txn in single_group_txn:
            encoded_txn = {'txn': encoding.msgpack_encode(single_txn)}
            txn_grp.append(encoded_txn)
        encoded_txns.append(txn_grp)

    return encoded_txns
